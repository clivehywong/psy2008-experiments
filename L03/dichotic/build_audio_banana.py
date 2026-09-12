#!/usr/bin/env python3
"""Build the 'banana' variant of the dichotic pair.
Female (RIGHT ear) is reused byte-identically from the shipped dichotic_stereo.wav;
the male script gets one random 'banana' inside EVERY sentence from the second
sentence onwards (ungrammatical by design), so the only difference from the
standard clip is the injected word in the MALE (LEFT) ear.
Outputs dichotic_stereo_banana.wav / .mp3 + passage_walk_banana.txt (the exact text).
"""
import os, random, re, subprocess, sys, struct, wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "_reviews", "_scripts")))
from gen_speech_poe import synth

MALE_VOICE = os.environ.get("MALE_VOICE", "English_Trustworth_Man")
SEED       = int(os.environ.get("BANANA_SEED", "7"))
TARGET     = float(os.environ.get("TARGET", "48"))
MALE_I     = float(os.environ.get("MALE_I", "-17.5"))
MALE_AF    = os.environ.get("MALE_AF", "highpass=f=80")

def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "csv=p=0", p]).decode().strip())

def make_banana_text(text, seed):
    """One 'banana' inserted at a random internal position of every sentence except the first."""
    rng = random.Random(seed)
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    out, slots = [], []
    for i, s in enumerate(sents):
        if i == 0:
            out.append(s)
            continue
        words = s.split()
        slot = rng.randint(1, len(words) - 1) if len(words) > 1 else 0
        words.insert(slot, "banana")
        slots.append(slot)
        out.append(" ".join(words))
    return " ".join(out), len(sents) - 1, slots

def main():
    src = os.path.join(HERE, "dichotic_stereo.wav")
    # 1. reuse the shipped female channel exactly (right = index 1)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                    "-af", "pan=mono|c0=c1",
                    os.path.join(HERE, "_banana_right.wav")], check=True)
    print(f"female channel reused from {src} ({dur(os.path.join(HERE,'_banana_right.wav')):.2f}s)")

    # 2. banana text: one banana in every sentence from the second onwards
    raw = open(os.path.join(HERE, "passage_walk.txt")).read()
    text, n, slots = make_banana_text(raw, SEED)
    open(os.path.join(HERE, "passage_walk_banana.txt"), "w").write(text + "\n")
    print(f"inserted {n} 'banana' (one per sentence from #2; word slots {slots}; seed {SEED})")

    # 3. male TTS, tuned to TARGET
    p0 = os.path.join(HERE, "_banana_male_raw.mp3")
    synth(text, p0, MALE_VOICE, 1.0)
    speed = max(0.5, min(2.0, dur(p0) / TARGET))
    p1 = os.path.join(HERE, "_banana_male.mp3")
    synth(text, p1, MALE_VOICE, round(speed, 3))
    print(f"male raw={dur(p0):.1f}s  speed={speed:.2f} -> {dur(p1):.1f}s")
    at = dur(p1) / TARGET
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", p1, "-af",
                    f"atempo={at:.4f},{MALE_AF},loudnorm=I={MALE_I}:TP=-1.5:LRA=11,aformat=sample_fmts=s16:sample_rates=44100,apad,atrim=0:{TARGET}",
                    os.path.join(HERE, "_banana_left.wav")], check=True)

    # 4. merge (left = banana male, right = shipped female) + mp3
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-i", os.path.join(HERE, "_banana_left.wav"),
                    "-i", os.path.join(HERE, "_banana_right.wav"),
                    "-filter_complex", "[0:a][1:a]amerge=inputs=2[out]", "-map", "[out]",
                    "-c:a", "pcm_s16le", os.path.join(HERE, "dichotic_stereo_banana.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "dichotic_stereo_banana.wav"),
                    "-codec:a", "libmp3lame", "-b:a", "128k", os.path.join(HERE, "dichotic_stereo_banana.mp3")], check=True)
    for f in ("_banana_male_raw.mp3","_banana_male.mp3","_banana_left.wav","_banana_right.wav"):
        try: os.remove(os.path.join(HERE, f))
        except OSError: pass
    print("built dichotic_stereo_banana.wav / .mp3")

if __name__ == "__main__":
    main()
