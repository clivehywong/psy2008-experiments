#!/usr/bin/env python3
"""Build the Gray & Wedderburn (1960) 'Dear Aunt Jane' dichotic stimulus.

Classic design: two word streams, one per ear, presented SIMULTANEOUSLY in pairs
so that neither ear alone is meaningful, but switching between ears yields the
phrase "Dear Aunt Jane":

    pair 1   pair 2     pair 3
    LEFT  (male)  : Dear     seven      Jane     -> heard alone: "Dear seven Jane"
    RIGHT (female): nine     Aunt       six      -> heard alone: "nine Aunt six"

A listener shadowing the LEFT ear hears "Dear … seven … Jane"; following the
MEANING instead gives "Dear Aunt Jane" (switch to the right ear for "Aunt").
Numbers are written as English words so the TTS cannot read them as digits in
another language.

ROBUSTNESS: Poe MiniMax is non-deterministic — it has produced expansions (a lone
"seven" once came back as ~1.04 s, i.e. "seven dollars") and can use a non-English
J ("Jane" -> /j/ "Yane"). Each word is therefore synthesised with a per-word spec
(language_boost where needed) and VALIDATED on trimmed duration + syllable count,
retrying until it passes or the attempts run out.

Output: dear_aunt_jane.wav / .mp3 + dear_aunt_jane.json.
"""
import json, math, os, struct, subprocess, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "_reviews", "_scripts")))
from gen_speech_poe import synth

MALE_VOICE   = os.environ.get("MALE_VOICE", "English_Trustworth_Man")
FEMALE_VOICE = os.environ.get("FEMALE_VOICE", "English_Graceful_Lady")
SLOT   = float(os.environ.get("SLOT", "1.20"))    # seconds per simultaneous pair
LEAD   = float(os.environ.get("LEAD", "0.70"))
TAIL   = 1.2
SR     = 44100
WORD_RMS_DB = float(os.environ.get("WORD_RMS_DB", "-18"))
ATTEMPTS = int(os.environ.get("ATTEMPTS", "5"))
# word, ear, pair slot, MAX syllables, (min,max) trimmed seconds, language_boost
# (max syllables is an upper bound to catch TTS expansions, e.g. a lone "seven"
#  once came back 1.04 s / several syllables -> "seven dollars")
SPECS = [
    ("Dear",  "left",  0, 2, (0.35, 0.85), None),
    ("seven", "left",  1, 3, (0.50, 0.95), None),
    ("Jane",  "left",  2, 2, (0.40, 0.85), "English"),   # glides to "Yane" without boost
    ("nine",  "right", 0, 2, (0.40, 0.85), None),
    ("Aunt",  "right", 1, 2, (0.35, 0.85), None),
    ("six",   "right", 2, 2, (0.35, 0.85), None),
]


def trim(samples):
    peak = max(1, max(abs(x) for x in samples))
    thr = peak * 0.02
    a, b = 0, len(samples) - 1
    while a < b and abs(samples[a]) < thr: a += 1
    while b > a and abs(samples[b]) < thr: b -= 1
    marg = int(0.01 * SR)
    return samples[max(0, a - marg):min(len(samples), b + marg)]


def nuclei(samples, hi=0.35, lo=0.18):
    """Count syllable-like energy peaks (catches TTS expansions)."""
    hop = int(0.01 * SR)
    env = []
    for s in range(0, max(1, len(samples) - hop), hop):
        seg = samples[s:s + hop]
        env.append(math.sqrt(sum(x * x for x in seg) / len(seg)))
    mx = max(env) or 1
    n, above = 0, False
    for v in env:
        v /= mx
        if not above and v > hi: n += 1; above = True
        elif above and v < lo: above = False
    return n


def say_word(word, voice, tag, boost, min_s, max_s, max_syll):
    last = None
    for attempt in range(1, ATTEMPTS + 1):
        mp3 = os.path.join(HERE, f"_{tag}.mp3")
        kw = {"language_boost": boost} if boost else {}
        synth(word, mp3, voice, 1.0, **kw)
        raw = os.path.join(HERE, f"_{tag}.raw")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
                        "-f", "s16le", raw], check=True)
        data = open(raw, "rb").read()
        samples = list(struct.unpack("<%dh" % (len(data) // 2), data))
        for f in (mp3, raw):
            try: os.remove(f)
            except OSError: pass
        if not samples:
            last = "empty audio"; continue
        samples = trim(samples)
        dur = len(samples) / SR
        syl = nuclei(samples)
        ok = (min_s <= dur <= max_s) and (1 <= syl <= max_syll)
        print(f"    {word!r:8s} attempt {attempt}: dur={dur:.2f}s syllables={syl} "
              f"(limits {min_s}-{max_s}s, <= {max_syll} syll) {'OK' if ok else 'REJECT'}")
        if ok:
            rms = (sum(x * x for x in samples) / len(samples)) ** 0.5 or 1.0
            gain = (10 ** (WORD_RMS_DB / 20) * 32768) / rms
            return [max(-32768, min(32767, int(x * gain))) for x in samples]
        last = f"dur={dur:.2f}s syllables={syl}"
    raise RuntimeError(f"{word!r} failed validation after {ATTEMPTS} attempts ({last})")


def place(buf, samples, offset_s):
    start = int(offset_s * SR)
    end = min(len(buf), start + len(samples))
    buf[start:end] = samples[:end - start]
    return start / SR


def main():
    total = LEAD + 2 * SLOT + TAIL + 1.0
    n = int(total * SR)
    left, right = [0] * n, [0] * n
    meta = {"slot": SLOT, "lead": LEAD, "sample_rate": SR, "duration": total, "words": []}
    buffers = {"left": left, "right": right}
    voices = {"left": MALE_VOICE, "right": FEMALE_VOICE}
    for word, ear, slot, max_syll, (lo, hi), boost in SPECS:
        print(f"  {ear:5s} {word!r}")
        samples = say_word(word, voices[ear], ear[0], boost, lo, hi, max_syll)
        onset = place(buffers[ear], samples, LEAD + slot * SLOT)
        meta["words"].append({"ear": ear, "voice": voices[ear], "word": word, "slot": slot,
                              "onset": round(onset, 3), "boost": boost, "seconds": round(len(samples) / SR, 2)})

    peak = max(1, max(abs(x) for x in left), max(abs(x) for x in right))
    scale = (0.85 * 32767) / peak
    left = [max(-32768, min(32767, int(x * scale))) for x in left]
    right = [max(-32768, min(32767, int(x * scale))) for x in right]

    def write_mono(path, buf):
        w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(struct.pack("<%dh" % len(buf), *buf)); w.close()
    write_mono(os.path.join(HERE, "_L.wav"), left)
    write_mono(os.path.join(HERE, "_R.wav"), right)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "_L.wav"),
                    "-i", os.path.join(HERE, "_R.wav"), "-filter_complex", "[0:a][1:a]amerge=inputs=2[out]",
                    "-map", "[out]", "-c:a", "pcm_s16le", os.path.join(HERE, "dear_aunt_jane.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "dear_aunt_jane.wav"),
                    "-codec:a", "libmp3lame", "-b:a", "128k", os.path.join(HERE, "dear_aunt_jane.mp3")], check=True)
    json.dump(meta, open(os.path.join(HERE, "dear_aunt_jane.json"), "w"), indent=2)
    for f in ("_L.wav", "_R.wav"):
        try: os.remove(os.path.join(HERE, f))
        except OSError: pass
    print(f"built dear_aunt_jane.wav / .mp3  ({total:.2f}s)")


if __name__ == "__main__":
    main()
