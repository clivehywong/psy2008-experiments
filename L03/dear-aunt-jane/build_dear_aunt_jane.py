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

Each word is synthesised separately (Poe MiniMax Speech 2.8) and placed at a
shared time slot, so the two ears are sample-aligned. Output: dear_aunt_jane.wav
/ .mp3 and dear_aunt_jane.json (word/slot map).
"""
import json, os, struct, subprocess, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "_reviews", "_scripts")))
from gen_speech_poe import synth

MALE_VOICE   = os.environ.get("MALE_VOICE", "English_Trustworth_Man")
FEMALE_VOICE = os.environ.get("FEMALE_VOICE", "English_Graceful_Lady")
LANG_BOOST = os.environ.get("LANG_BOOST", "English")   # forces English pronunciation (J in "Jane")
SLOT   = float(os.environ.get("SLOT", "1.20"))    # seconds per simultaneous pair
LEAD   = float(os.environ.get("LEAD", "0.70"))    # silence before the first pair
TAIL   = 1.2
SR     = 44100
# simultaneous pairs: index 0,1,2 = pair number (both ears share the same onset)
WORDS_LEFT  = [("Dear", 0), ("seven", 1), ("Jane", 2)]   # male,  left ear
WORDS_RIGHT = [("nine", 0), ("Aunt", 1),  ("six", 2)]    # female,right ear


WORD_RMS_DB = float(os.environ.get("WORD_RMS_DB", "-18"))   # per-word loudness target (RMS dBFS)


def say_word(word, voice, tag):
    mp3 = os.path.join(HERE, f"_{tag}.mp3")
    synth(word, mp3, voice, 1.0, language_boost=LANG_BOOST)
    raw = os.path.join(HERE, f"_{tag}.raw")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
                    "-f", "s16le", raw], check=True)
    data = open(raw, "rb").read()
    n = len(data) // 2
    samples = list(struct.unpack("<%dh" % n, data))
    for f in (mp3, raw):
        try: os.remove(f)
        except OSError: pass
    # trim leading/trailing silence (TTS often pads) so pairs line up tightly
    peak = max(1, max(abs(x) for x in samples))
    thr = peak * 0.02
    a, b = 0, len(samples) - 1
    while a < b and abs(samples[a]) < thr: a += 1
    while b > a and abs(samples[b]) < thr: b -= 1
    marg = int(0.01 * SR)
    samples = samples[max(0, a - marg):min(len(samples), b + marg)]
    # normalise each word to the same RMS so both ears are equally loud
    rms = (sum(x * x for x in samples) / max(1, len(samples))) ** 0.5 or 1.0
    gain = (10 ** (WORD_RMS_DB / 20) * 32768) / rms
    samples = [max(-32768, min(32767, int(x * gain))) for x in samples]
    return samples


def place(buf, samples, offset_s):
    start = int(offset_s * SR)
    end = min(len(buf), start + len(samples))
    buf[start:end] = samples[:end - start]
    return start / SR


def main():
    total = LEAD + 2 * SLOT + TAIL + 1.0      # 3 pairs at slots 0,1,2 + room for the last word
    n = int(total * SR)
    left, right = [0] * n, [0] * n
    meta = {"slot": SLOT, "lead": LEAD, "sample_rate": SR, "duration": total, "words": []}
    for word, slot in WORDS_LEFT:
        s = say_word(word, MALE_VOICE, "l")
        t = place(left, s, LEAD + slot * SLOT)
        meta["words"].append({"ear": "left", "voice": MALE_VOICE, "word": word, "slot": slot, "onset": round(t, 3)})
    for word, slot in WORDS_RIGHT:
        s = say_word(word, FEMALE_VOICE, "r")
        t = place(right, s, LEAD + slot * SLOT)
        meta["words"].append({"ear": "right", "voice": FEMALE_VOICE, "word": word, "slot": slot, "onset": round(t, 3)})

    def write_mono(path, buf):
        w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(struct.pack("<%dh" % len(buf), *buf)); w.close()

    # both ears were built from words at the same RMS: scale them together (single global
    # gain) so the two channels stay equal, with a true-peak guard.
    peak = max(1, max(abs(x) for x in left), max(abs(x) for x in right))
    scale = (0.85 * 32767) / peak
    left = [max(-32768, min(32767, int(x * scale))) for x in left]
    right = [max(-32768, min(32767, int(x * scale))) for x in right]
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
    print(json.dumps(meta, indent=2))
    print("built dear_aunt_jane.wav / .mp3")


if __name__ == "__main__":
    main()
