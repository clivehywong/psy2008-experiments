#!/usr/bin/env bash
# Rebuild the dichotic listening audio from the two passage scripts.
# Usage: ./build_audio.sh
# Requires: macOS `say`, ffmpeg on PATH.
set -euo pipefail
cd "$(dirname "$0")"

MALE_VOICE="${MALE_VOICE:-Daniel}"      # en-GB male
FEMALE_VOICE="${FEMALE_VOICE:-Samantha}" # en-US female

say -v "$MALE_VOICE"   -f passage_bicycle.txt -o left_male.aiff
say -v "$FEMALE_VOICE" -f passage_bees.txt    -o right_female.aiff

d1=$(ffprobe -v error -show_entries format=duration -of csv=p=0 left_male.aiff)
d2=$(ffprobe -v error -show_entries format=duration -of csv=p=0 right_female.aiff)
target=$(python3 -c "print(max($d1, $d2))")
echo "male=${d1}s female=${d2}s -> padding both to ${target}s"

ffmpeg -y -v error -i left_male.aiff -i right_female.aiff -filter_complex \
  "[0:a]aformat=sample_fmts=s16:sample_rates=44100,apad,atrim=0:${target}[a0];\
[1:a]aformat=sample_fmts=s16:sample_rates=44100,apad,atrim=0:${target}[a1];\
[a0][a1]amerge=inputs=2[out]" -map "[out]" -c:a pcm_s16le dichotic_stereo.wav

ffmpeg -y -v error -i dichotic_stereo.wav -codec:a libmp3lame -b:a 128k dichotic_stereo.mp3

echo "done:"
ls -la dichotic_stereo.wav dichotic_stereo.mp3
