"""Shared helpers: decide what a clip should sound like and ask Whisper (offline) what it actually hears."""
import pathlib
import re

import numpy as np

here = pathlib.Path(__file__).parent
_model = None

LETTER_SOUNDS = {
    "A": {"a", "ay", "eh", "hey"}, "B": {"b", "be", "bee"}, "C": {"c", "see", "sea", "si"}, "D": {"d", "dee", "de"},
    "E": {"e", "ee", "ea"}, "F": {"f", "eff", "ef"}, "G": {"g", "gee", "ji"}, "H": {"h", "aitch", "age", "ach", "eich"},
    "I": {"i", "eye", "aye", "ai"}, "J": {"j", "jay", "jae"}, "K": {"k", "kay", "okay", "kai", "ka"}, "L": {"l", "el", "ell", "elle"},
    "M": {"m", "em"}, "N": {"n", "en"}, "O": {"o", "oh", "owe"}, "P": {"p", "pee", "pea"},
    "Q": {"q", "queue", "cue", "kew"}, "R": {"r", "are", "ar"}, "S": {"s", "ess", "es"}, "T": {"t", "tee", "tea"},
    "U": {"u", "you", "yu"}, "V": {"v", "vee", "ve"}, "W": {"w", "double you", "doubleyou", "double u"}, "X": {"x", "ex"},
    "Y": {"y", "why", "wye"}, "Z": {"z", "zee", "zed"},
}
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num_words(n):
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    return "one hundred"


def norm(t):
    t = t.lower().replace("-", " ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


def accepted(key, text):
    """Set of normalized transcripts that count as correct, and an optional required prefix ("big"/"little")."""
    if key in LETTER_SOUNDS: return LETTER_SOUNDS[key], ""
    m = re.fullmatch(r"(big|little) ([A-Z])", key)
    if m: return LETTER_SOUNDS[m.group(2)], m.group(1)
    if key.isdigit():
        n = int(key); return {str(n), norm(num_words(n)), num_words(n).replace(" ", "")}, ""
    return {norm(text), norm(text).replace(" ", "")}, ""


# Words that sound exactly alike; the recognizer may write either one.
HOMOPHONES = {
    "ten": {"10"}, "tens": {"10s"}, "one": {"1", "won"}, "ones": {"1s", "once"}, "hundred": {"100"}, "bee": {"b", "be"},
    "see": {"c", "sea"}, "to": {"two", "2", "too"}, "pear": {"pair", "pare"}, "deer": {"dear"}, "cents": {"sense", "scents"},
    "rhyme": {"rime"}, "hmm": {"hum", "hm", "mm", "mmm"}, "rows of": {"rose of"}, "maze": {"maize", "mays", "mayes"},
    "big s": {"big ass", "big es"}, "big x": {"big axe", "big ax"}, "find the": {"find that"}, "pie": {"pi"}, "eye": {"i", "aye"},
    "you": {"u"}, "are": {"r"}, "why": {"y"}, "oh": {"o"}, "sun": {"son"}, "tie": {"thai"}, "big ess": {"big ass", "big s"}, "big ex": {"big axe", "big x"},
}


def edges_ok(a, sr, words=1, vowel_end=True):
    """False if a separate, voiced little sound (an "uh") sits before the word or after it.
    Hissy consonants like s, sh, f are high-pitched noise and don't count; an "uh" is low and voiced."""
    n = int(sr * .02)
    frames = [a[i:i + n] for i in range(0, len(a) - n, n)]
    if not frames: return False
    e = np.array([np.sqrt(np.mean(f ** 2)) for f in frames])
    fr = np.fft.rfftfreq(n, 1 / sr)
    low = np.array([(lambda s: s[(fr > 80) & (fr < 1000)].sum() / max(1e-9, s[fr > 80].sum()))(np.abs(np.fft.rfft(f)) ** 2) for f in frames])
    act = e > e.max() * .08
    segs, start = [], None
    for i, v in enumerate(act):
        if v and start is None: start = i
        if not v and start is not None: segs.append((start, i)); start = None
    if start is not None: segs.append((start, len(act)))
    # Merge pieces separated by less than 40 ms (normal consonant dips inside a word).
    merged = []
    for sg in segs:
        if merged and sg[0] - merged[-1][1] < 2: merged[-1] = (merged[-1][0], sg[1])
        else: merged.append(sg)
    if len(merged) < 2: return True
    main = max(e.max(), 1e-9)
    def uh(s):  # a short (<160 ms), quieter, low-pitched voiced burst
        lo, hi = s
        return hi - lo <= 8 and e[lo:hi].max() < main * .5 and low[lo:hi].mean() > .6
    if words == 1 and uh(merged[0]): return False
    if vowel_end and uh(merged[-1]): return False
    return True


def ends_in_vowel(key, text):
    """Letter names and numbers that end on a vowel sound, where a trailing "uh" can hide."""
    m = re.fullmatch(r"(?:(?:big|little) )?([A-Z])", key)
    if m: return m.group(1) in "ABCDEGIJKOPQTUVWYZ"
    if key.isdigit(): return bool(re.search(r"(two|three|zero|ty)$", num_words(int(key))))
    return False


def mp3_roundtrip(a, sr):
    """The clip as it will sound after MP3 packing (what the game actually plays)."""
    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, a, sr, format="MP3", bitrate_mode="VARIABLE", compression_level=0.25)
    buf.seek(0)
    b, _ = sf.read(buf, dtype="float32")
    return b


def heard_ok(key, text, heard):
    forms, prefix = accepted(key, text)
    forms = forms | HOMOPHONES.get(norm(text), set()) | HOMOPHONES.get(norm(key), set())
    h = norm(heard)
    if prefix:
        if not h.startswith(prefix): return False
        h = h[len(prefix):].strip()
    return h in forms or h.replace(" ", "") in forms


def transcribe(a, sr):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("base.en", device="cpu", compute_type="int8", download_root=str(here / ".cache" / "whisper"))
    pad = np.zeros(int(sr * .25), np.float32)
    a = np.concatenate([pad, a.astype(np.float32), pad])
    n = int(len(a) * 16000 / sr)
    a16 = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
    segs, _ = _model.transcribe(a16, language="en", beam_size=5, without_timestamps=True, condition_on_previous_text=False)
    return " ".join(s.text for s in segs).strip()
