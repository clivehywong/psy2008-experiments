#!/usr/bin/env python3
"""Build the dichotic stereo pair using Poe MiniMax Speech 2.8 (natural voices).
Male (English_Trustworth_Man) -> LEFT ear; Female (English_Graceful_Lady) -> RIGHT ear.
Speeds are tuned so both tracks end at TARGET seconds; channels are loudness-matched.
Run from the dichotic folder: ../../..//.venv/bin/python build_audio_minimax.py
"""
import os, subprocess, sys, math, struct, wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "_reviews", "_scripts")))
from gen_speech_poe import synth

MALE_VOICE   = os.environ.get("MALE_VOICE", "English_Trustworth_Man")
FEMALE_VOICE = os.environ.get("FEMALE_VOICE", "English_Graceful_Lady")
TARGET       = float(os.environ.get("TARGET", "48"))     # seconds, both tracks
# perceived-loudness balance: male speech band measured ~2 dB hotter at equal LUFS,
# so the female gets a presence lift and a slightly higher loudness target.
MALE_I       = float(os.environ.get("MALE_I", "-17.5"))
FEMALE_I     = float(os.environ.get("FEMALE_I", "-15.5"))
MALE_AF      = os.environ.get("MALE_AF", "highpass=f=80")
FEMALE_AF    = os.environ.get("FEMALE_AF", "equalizer=f=2200:width_type=o:width=1.4:g=1.5")
RATE_LIMIT   = (0.5, 2.0)

def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "csv=p=0", p]).decode().strip())

def to_wav(src, out, atempo=1.0, loud_i=-16.0, pre=""):
    af = (f"atempo={atempo}," if abs(atempo - 1) > 0.001 else "") + \
         (f"{pre}," if pre else "") + \
         f"loudnorm=I={loud_i}:TP=-1.5:LRA=11,aformat=sample_fmts=s16:sample_rates=44100,apad,atrim=0:{TARGET}"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", af, out], check=True)

def main():
    texts = {"male": open(os.path.join(HERE, "passage_walk.txt")).read(),
             "female": open(os.path.join(HERE, "passage_garden.txt")).read()}
    voices = {"male": MALE_VOICE, "female": FEMALE_VOICE}
    raw = {}
    for k in ("male", "female"):
        p = os.path.join(HERE, f"_{k}_raw.mp3")
        _, note = synth(texts[k], p, voices[k], 1.0)
        d = dur(p)
        speed = max(RATE_LIMIT[0], min(RATE_LIMIT[1], d / TARGET))
        p2 = os.path.join(HERE, f"_{k}_tuned.mp3")
        synth(texts[k], p2, voices[k], round(speed, 3))
        d2 = dur(p2)
        print(f"{k:6s} {voices[k]:26s} speed={speed:.2f}  {d:.1f}s -> {d2:.1f}s")
        raw[k] = p2
    # final exact match with a tiny atempo (identical target for both channels)
    to_wav(raw['male'], os.path.join(HERE, "_male_pad.wav"), atempo=dur(raw['male']) / TARGET,
           loud_i=MALE_I, pre=MALE_AF)
    to_wav(raw['female'], os.path.join(HERE, "_female_pad.wav"), atempo=dur(raw['female']) / TARGET,
           loud_i=FEMALE_I, pre=FEMALE_AF)
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-i", os.path.join(HERE, "_male_pad.wav"),
                    "-i", os.path.join(HERE, "_female_pad.wav"),
                    "-filter_complex", "[0:a][1:a]amerge=inputs=2[out]", "-map", "[out]",
                    "-c:a", "pcm_s16le", os.path.join(HERE, "dichotic_stereo.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(HERE, "dichotic_stereo.wav"),
                    "-codec:a", "libmp3lame", "-b:a", "128k", os.path.join(HERE, "dichotic_stereo.mp3")], check=True)
    for f in ("_male_raw.mp3","_female_raw.mp3","_male_tuned.mp3","_female_tuned.mp3","_male_pad.wav","_female_pad.wav"):
        try: os.remove(os.path.join(HERE, f))
        except OSError: pass
    print("built dichotic_stereo.wav / .mp3")

if __name__ == "__main__":
    main()
