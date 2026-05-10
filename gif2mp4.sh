#!/usr/bin/env bash
# Convert a GIF to a compact MP4 (h264, tuned for dithered/grain content)
#
# Usage: ./gif2mp4.sh input.gif [output.mp4]

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 input.gif [output.mp4]" >&2
    exit 1
fi

input="$1"
output="${2:-${input%.gif}.mp4}"

ffmpeg -y -i "$input" \
    -c:v libx264 -crf 45 \
    -preset veryslow -tune grain \
    -pix_fmt yuv420p \
    -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" \
    -movflags faststart \
    "$output"

echo "Done: $output ($(du -h "$output" | cut -f1))"
