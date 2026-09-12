#!/usr/bin/env bash
# Rebuild the dichotic listening audio from the two passage scripts.
# Usage: ./build_audio.sh
# Requires: macOS `say`, ffmpeg on PATH.
#
# Fallback pipeline (macOS voices). The preferred pipeline is build_audio_minimax.py
# (natural Poe MiniMax Speech 2.8 voices); this one writes dichotic_stereo_mac.* so it
# does not overwrite the shipped dichotic_stereo_mac.mp3.
# Design: male voice (Eddy, en-US) = LEFT ear; female (Samantha, en-US) = RIGHT ear.
# `say` rate for these voices clamps to a few tiers, so we speak at the slow tier
# (-r 100) and then stretch with atempo (pitch-preserving) so both tracks end at
# exactly TARGET seconds — equal length, ~120-125 wpm, comfortable for shadowing.
set -euo pipefail
cd "$(dirname "$0")"

MALE_VOICE="${MALE_VOICE:-Eddy (English (US))}"   # clear male; Daniel was hard to hear
FEMALE_VOICE="${FEMALE_VOICE:-Samantha}"
RATE="${RATE:-100}"
TARGET="${TARGET:-48}"                            # seconds, both tracks

say -v "$MALE_VOICE"   -r "$RATE" -f passage_walk.txt   -o left_male.aiff
say -v "$FEMALE_VOICE" -r "$RATE" -f passage_garden.txt -o right_female.aiff

d1=$(ffprobe -v error -show_entries format=duration -of csv=p=0 left_male.aiff)
d2=$(ffprobe -v error -show_entries format=duration -of csv=p=0 right_female.aiff)
a1=$(python3 -c "print(round($d1/$TARGET, 4))")
a2=$(python3 -c "print(round($d2/$TARGET, 4))")
echo "male=${d1}s (atempo ${a1})  female=${d2}s (atempo ${a2})  -> ${TARGET}s both"

ffmpeg -y -v error -i left_male.aiff -af \
  "atempo=${a1},loudnorm=I=-16:TP=-1.5:LRA=11,aformat=sample_fmts=s16:sample_rates=44100,apad,atrim=0:${TARGET}" \
  left_pad.wav
ffmpeg -y -v error -i right_female.aiff -af \
  "atempo=${a2},loudnorm=I=-16:TP=-1.5:LRA=11,aformat=sample_fmts=s16:sample_rates=44100,apad,atrim=0:${TARGET}" \
  right_pad.wav

ffmpeg -y -v error -i left_pad.wav -i right_pad.wav -filter_complex \
  "[0:a][1:a]amerge=inputs=2[out]" -map "[out]" -c:a pcm_s16le dichotic_stereo_mac.wav
ffmpeg -y -v error -i dichotic_stereo_mac.wav -codec:a libmp3lame -b:a 128k dichotic_stereo_mac.mp3
rm -f left_pad.wav right_pad.wav

echo "done:"
ls -la dichotic_stereo_mac.wav dichotic_stereo_mac.mp3
