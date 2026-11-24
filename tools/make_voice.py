"""Records every line in tools/lines.json with the Kokoro voice model and packs the clips
into a few MP3 "sprites" plus voice/index.json, which the game uses to play each phrase.

Run from the games folder:
    node tools/extract_lines.mjs
    tools/.venv/Scripts/python tools/make_voice.py

Clips are cached in tools/.cache/clips, so re-running only records new or changed lines.
"""
import hashlib
import json
import pathlib
import re
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

VOICE = "af_heart"
SPEED = 0.95
SR = 24000
CLIPS_PER_SPRITE = 140
MARKER_AT = 0.2      # seconds; a short click the game finds to correct MP3 decoder delay
LEAD = 0.5           # first clip starts here
GAP = 0.25           # silence between clips

here = pathlib.Path(__file__).parent
root = here.parent
cache = here / ".cache" / "clips"
cache.mkdir(parents=True, exist_ok=True)
out_dir = root / "voice"
out_dir.mkdir(exist_ok=True)

lines = json.loads((here / "lines.json").read_text(encoding="utf-8"))
kokoro = Kokoro(str(here / ".cache" / "kokoro-v1.0.int8.onnx"), str(here / ".cache" / "voices-v1.0.bin"))


def trim(a, pad=0.03):
    # Threshold relative to the clip's own peak, so faint trailing breath/vowel tails get cut.
    peak = float(np.max(np.abs(a))) or 1.0
    idx = np.where(np.abs(a) > max(0.006, peak * 0.03))[0]
    if len(idx) == 0:
        return a[: int(SR * 0.1)]
    s = max(0, idx[0] - int(SR * pad))
    e = min(len(a), idx[-1] + int(SR * pad))
    a = a[s:e].copy()
    fi, fo = int(SR * 0.005), min(len(a) // 3, int(SR * 0.04))
    a[:fi] *= np.linspace(0, 1, fi)            # no click at the start
    a[-fo:] *= np.linspace(1, 0, fo) ** 1.5    # soft, clean ending
    return a


def speakable(text):
    # A bare word (a letter name, a number, "plus") said on its own tends to get an extra "uh" at the end.
    # Saying it as a complete sentence ("Dee.") ends it cleanly. Short items are also said a little slower.
    short = len(text.split()) <= 2
    t = text if not short or re.search(r"[.!?:]$", text) else text + "."
    return t, (0.88 if short else SPEED)


def clip_for(text):
    t, speed = speakable(text)
    h = hashlib.sha1(f"v2|{VOICE}|{speed}|{t}".encode()).hexdigest()[:16]
    f = cache / f"{h}.npy"
    if f.exists():
        return np.load(f)
    samples, sr = kokoro.create(t, voice=VOICE, speed=speed, lang="en-us")
    assert sr == SR, sr
    a = trim(np.asarray(samples, dtype=np.float32))
    peak = float(np.max(np.abs(a))) or 1.0
    a = a * (0.85 / peak)  # even loudness from clip to clip
    np.save(f, a)
    return a


keys = list(lines.keys())
index = {"marker": MARKER_AT, "sprites": {}, "clips": {}}
for si in range(0, len(keys), CLIPS_PER_SPRITE):
    name = f"v{si // CLIPS_PER_SPRITE + 1}"
    parts = [np.zeros(int(SR * MARKER_AT), dtype=np.float32)]
    t = np.arange(int(SR * 0.012)) / SR
    parts.append((0.7 * np.sin(2 * np.pi * 1500 * t)).astype(np.float32))
    pos = MARKER_AT + len(t) / SR
    parts.append(np.zeros(int(SR * (LEAD - pos)), dtype=np.float32))
    pos = LEAD
    for k in keys[si: si + CLIPS_PER_SPRITE]:
        a = clip_for(lines[k])
        index["clips"][k] = [name, round(pos, 4), round(len(a) / SR, 4)]
        parts.append(a)
        parts.append(np.zeros(int(SR * GAP), dtype=np.float32))
        pos += len(a) / SR + int(SR * GAP) / SR
        done = len(index["clips"])
        if done % 25 == 0:
            print(f"{done}/{len(keys)}", flush=True)
    audio = np.concatenate(parts)
    sf.write(out_dir / f"{name}.mp3", audio, SR, format="MP3", bitrate_mode="VARIABLE", compression_level=0.75)
    index["sprites"][name] = f"voice/{name}.mp3"
    print(f"wrote {name}.mp3 ({len(audio) / SR:.0f}s)", flush=True)

(out_dir / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
total = sum((out_dir / f"{n}.mp3").stat().st_size for n in index["sprites"])
print(f"done: {len(keys)} clips, {len(index['sprites'])} sprites, {total / 1e6:.1f} MB")
sys.exit(0)
