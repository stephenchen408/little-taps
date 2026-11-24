"""Records every line in tools/lines.json with the Kokoro voice model and packs the clips
into a few MP3 "sprites" plus voice/index.json, which the game uses to play each phrase.

Run from the games folder:
    node tools/extract_lines.mjs
    tools/.venv/Scripts/python tools/make_voice.py

Clips are cached in tools/.cache/clips, so re-running only records new or changed lines.
"""
import hashlib
import os
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


def after_pause(a):
    """Keeps only the audio after the longest pause (drops the "Okay..." lead-in). None if there's no clear pause."""
    n = int(SR * .01)
    e = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)])
    act = e > e.max() * .03
    on = np.where(act)[0]
    best, run, end = 0, 0, None
    for i in range(on[0], on[-1]):
        run = run + 1 if not act[i] else 0
        if run > best: best, end = run, i
    if best * .01 < .12: return None
    return a[(end + 1) * n - int(SR * .02):]


def finish(a):
    a = trim(np.asarray(a, dtype=np.float32))
    peak = float(np.max(np.abs(a))) or 1.0
    return a * (0.85 / peak)  # even loudness from clip to clip


def variants(key, text):
    """Ways to record a short item, best first. Very short inputs come out garbled more often, so the item is
    said after a lead-in ("Okay... Dee.") and cut out at the pause. Letters also try the bare capital letter."""
    t = text.rstrip(".!?:")
    alts = [t]
    m = re.fullmatch(r"(?:(big|little) )?([A-Z])", key)
    if m: alts.append(f"{m.group(1)} {m.group(2)}" if m.group(1) else m.group(2))
    extra = {"H": ["aych", "eych", "the letter aitch"], "W": ["double-you"], "R": ["ar"], "Y": ["wye"]}
    if m: alts += [f"{m.group(1)} {e}" if m.group(1) else e for e in extra.get(m.group(2), [])]
    out = []
    for x in alts:
        out += [("Okay... {}.", .88, x), ("Now... {}.", .85, x), ("Okay... {}!", .92, x), ("Alright... {}.", .82, x)]
    out.append(("{}.", .88, t))
    # Letters the model says oddly: spell the sounds out phonetically (these come out right).
    PH = {"H": "ˈeɪʧ", "K": "kˈeɪ", "S": "ˈɛs", "X": "ˈɛks", "F": "ˈɛf", "L": "ˈɛl", "N": "ˈɛn", "M": "ˈɛm"}
    if m and m.group(2) in PH:
        pre = "" if not m.group(1) else ("bˈɪɡ " if m.group(1) == "big" else "lˈɪɾəl ")
        for lead in ("nˈaʊ...", "ˈoʊkeɪ..."):
            for sp in (.85, .8, .92):
                out.append((lead + " {}.", sp, pre + PH[m.group(2)], True))
    return [v if len(v) == 4 else (*v, False) for v in out]


report = []


def clip_for(key, text):
    if len(text.split()) > 2:
        # Sentences: said as written.
        h = hashlib.sha1(f"v2|{VOICE}|{SPEED}|{text}".encode()).hexdigest()[:16]
        f = cache / f"{h}.npy"
        if f.exists(): return np.load(f)
        a = finish(kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")[0])
        np.save(f, a)
        return a
    # Short items (letters, numbers, single words): keep the first take that Whisper hears correctly.
    f = cache / f"v3_{hashlib.sha1(f'{VOICE}|{key}|{text}'.encode()).hexdigest()[:16]}.npy"
    if f.exists(): return np.load(f)
    from voicecheck import transcribe, heard_ok, edges_ok, ends_in_vowel, mp3_roundtrip
    first = None
    for tmpl, speed, t, ph in variants(key, text):
        raw = kokoro.create(tmpl.format(t), voice=VOICE, speed=speed, lang="en-us", is_phonemes=ph)[0]
        if tmpl != "{}.":
            raw = after_pause(raw)
            if raw is None: continue
        a = finish(raw)
        # Judge the take as the game will play it (after MP3 packing), and reject any extra "uh" before/after.
        heard = transcribe(mp3_roundtrip(a, SR), SR)
        if first is None: first = (a, heard)
        if heard_ok(key, text, heard) and heard_ok(key, text, transcribe(a, SR)) and edges_ok(a, SR, len(text.split()), ends_in_vowel(key, text)):
            np.save(f, a)
            return a
    report.append((key, first[1]))
    print(f"  no take passed for {key!r}; best heard {first[1]!r}", flush=True)
    np.save(f, first[0])
    return first[0]


keys = list(lines.keys())
if os.environ.get("ONLY"):
    # Quick trial: record and check just these keys, without writing the voice files.
    for k in os.environ["ONLY"].split("|"):
        a = clip_for(k, lines[k])
        from voicecheck import transcribe
        print(f"{k!r:12} -> {transcribe(a, SR)!r}", flush=True)
    sys.exit(0)
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
        a = clip_for(k, lines[k])
        index["clips"][k] = [name, round(pos, 4), round(len(a) / SR, 4)]
        parts.append(a)
        parts.append(np.zeros(int(SR * GAP), dtype=np.float32))
        pos += len(a) / SR + int(SR * GAP) / SR
        done = len(index["clips"])
        if done % 25 == 0:
            print(f"{done}/{len(keys)}", flush=True)
    audio = np.concatenate(parts)
    sf.write(out_dir / f"{name}.mp3", audio, SR, format="MP3", bitrate_mode="VARIABLE", compression_level=float(os.environ.get("MP3Q", "0.25")))
    index["sprites"][name] = f"voice/{name}.mp3"
    print(f"wrote {name}.mp3 ({len(audio) / SR:.0f}s)", flush=True)

(out_dir / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
total = sum((out_dir / f"{n}.mp3").stat().st_size for n in index["sprites"])
(here / "voice_report.json").write_text(json.dumps(report, indent=1))
print(f"unresolved short clips: {len(report)}")
print(f"done: {len(keys)} clips, {len(index['sprites'])} sprites, {total / 1e6:.1f} MB")
sys.exit(0)
