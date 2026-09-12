#!/usr/bin/env python3
"""Build the Gray & Wedderburn (1960) 'Dear Aunt Jane' dichotic stimulus.

Classic design: the two ears carry different word streams, interleaved in time, so
that NEITHER ear alone is meaningful, but switching between ears yields the phrase
"Dear Aunt Jane":
    LEFT  (male)  : Dear  ·  7  ·  Jane      -> as heard alone: "Dear 7 Jane"
    RIGHT (female):   9   · Aunt ·   6       -> as heard alone: "9 Aunt 6"
A listener shadowing one ear reports the meaningful cross-ear phrase instead.

Each word is synthesised separately (Poe MiniMax Speech 2.8) and placed at a fixed
time slot, so both ears are sample-aligned. Output: dear_aunt_jane.wav / .mp3 and
dear_aunt_jane.json (word/slot map).
"""
import json, os, struct, subprocess, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "_reviews", "_scripts")))
from gen_speech_poe import synth

MALE_VOICE   = os.environ.get("MALE_VOICE", "English_Trustworth_Man")
FEMALE_VOICE = os.environ.get("FEMALE_VOICE", "English_Graceful_Lady")
SLOT   = float(os.environ.get("SLOT", "0.90"))    # seconds between word onsets
LEAD   = float(os.environ.get("LEAD", "0.60"))    # silence before the first word
TAIL   = 1.2
SR     = 44100
WORDS_LEFT  = [("Dear", 0), ("7", 2), ("Jane", 4)]   # male,  left ear
WORDS_RIGHT = [("9", 1),    ("Aunt", 3), ("6", 5)]   # female,right ear


def say_word(word, voice, tag):
    mp3 = os.path.join(HERE, f"_{tag}.mp3")
    synth(word, mp3, voice, 1.0)
    raw = os.path.join(HERE, f"_{tag}.raw")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", str(SR),
                    "-f", "s16le", raw], check=True)
    data = open(raw, "rb").read()
    n = len(data) // 2
    samples = struct.unpack("<%dh" % n, data)
    for f in (mp3, raw):
        try: os.remove(f)
        except OSError: pass
    return samples


def place(buf, samples, offset_s):
    start = int(offset_s * SR)
    end = min(len(buf), start + len(samples))
    buf[start:end] = samples[:end - start]
    return start / SR


def main():
    total = LEAD + 5 * SLOT + TAIL
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
    write_mono(os.path.join(HERE, "_L.wav"), left)
    write_mono(os.path.join(HERE, "_R.wav"), right)

    # loudness-match the two ears, then merge to stereo
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "_L.wav"),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", os.path.join(HERE, "_Lp.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "_R.wav"),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", os.path.join(HERE, "_Rp.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "_Lp.wav"),
                    "-i", os.path.join(HERE, "_Rp.wav"), "-filter_complex", "[0:a][1:a]amerge=inputs=2[out]",
                    "-map", "[out]", "-c:a", "pcm_s16le", os.path.join(HERE, "dear_aunt_jane.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "dear_aunt_jane.wav"),
                    "-codec:a", "libmp3lame", "-b:a", "128k", os.path.join(HERE, "dear_aunt_jane.mp3")], check=True)
    json.dump(meta, open(os.path.join(HERE, "dear_aunt_jane.json"), "w"), indent=2)
    for f in ("_L.wav", "_R.wav", "_Lp.wav", "_Rp.wav"):
        try: os.remove(os.path.join(HERE, f))
        except OSError: pass
    print(json.dumps(meta, indent=2))
    print("built dear_aunt_jane.wav / .mp3")


if __name__ == "__main__":
    main()
