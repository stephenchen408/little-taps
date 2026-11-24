# Little Taps

Ad-free learning games for kids, from preschool up to about age 10. They run in the browser and can be added to an iPhone or iPad home screen as an app that works offline.

**Play:** https://stephenchen408.github.io/little-taps/ — open it in Safari, tap Share, then **Add to Home Screen**.

- **Play** tab (ages 3–6): Blocks, Build, Numbers, Letters, Spell, Math, Trace, Balloons, Shapes, Animals, Pairs, Paint
- **Challenge** tab (ages 6–10): Robot (coding), Balance (early algebra), Times (multiplication), Words (word ladders), Puzzle (shape filling), Shop (money and change)

Levels, stickers and settings are saved on the device only.

## How it's built

- `index.html` is the whole game in one file.
- `voice/` holds the recorded voice. Every line the games say is listed in the data block of `index.html`.
- `docs/` is the home-screen app version that GitHub Pages serves. It's generated, so don't edit it by hand.

## Rebuilding

```
node tools/extract_lines.mjs                         # list every voice line
tools/.venv/Scripts/python tools/make_voice.py       # record new or changed lines (Kokoro, runs offline)
tools/.venv/Scripts/python tools/make_icons.py       # app icons
node tools/build_site.mjs                            # build docs/
```

`make_voice.py` needs the Kokoro model in `tools/.cache/` (`kokoro-v1.0.int8.onnx` and `voices-v1.0.bin` from the kokoro-onnx releases) and a virtual environment with `kokoro-onnx` and `soundfile` installed.
