"""Listens to the finished voice files with Whisper (offline) and lists any short clip (letters, "big X",
numbers 0-100, single words) that doesn't sound like what it should. Uses the same rules as make_voice.py.

Run: tools/.venv/Scripts/python tools/check_voice.py
"""
import json
import pathlib

import numpy as np
import soundfile as sf

from voicecheck import edges_ok, ends_in_vowel, heard_ok, transcribe

here = pathlib.Path(__file__).parent
root = here.parent
idx = json.loads((root / "voice" / "index.json").read_text())
lines = json.loads((here / "lines.json").read_text(encoding="utf-8"))
cache = {}


def clip_audio(key):
    sp, st, du = idx["clips"][key]
    if sp not in cache:
        a, sr = sf.read(root / "voice" / f"{sp}.mp3")
        shift = np.argmax(np.abs(a) > .25) / sr - idx["marker"]  # same marker correction the game uses
        cache[sp] = (a, sr, shift)
    a, sr, shift = cache[sp]
    s = int((st + shift) * sr)
    return a[s:s + int(du * sr)].astype(np.float32), sr


keys = [k for k, t in lines.items() if len(t.split()) <= 2]
import os, re
if os.environ.get("LETTERS_NUMBERS"):
    keys = [k for k in keys if re.fullmatch(r"(?:(?:big|little) )?[A-Z]|\d+", k)]
bad = []
for k in keys:
    a, sr = clip_audio(k)
    heard = transcribe(a, sr)
    words_ok, edges = heard_ok(k, lines[k], heard), edges_ok(a, sr, len(lines[k].split()), ends_in_vowel(k, lines[k]))
    if not (words_ok and edges):
        bad.append((k, lines[k], heard, "extra sound at start/end" if not edges else ""))
        print(f"  FAIL {k!r:14} should say {lines[k]!r:16} heard {heard!r} {'(extra sound at start/end)' if not edges else ''}", flush=True)
print(f"checked {len(keys)} short clips, {len(bad)} not heard as expected")
(here / "voice_check.json").write_text(json.dumps(bad, indent=1))
