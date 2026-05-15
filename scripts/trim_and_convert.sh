#!/bin/bash
#
# Manual Trim & Convert to GIF
# Lets you specify exact time ranges to keep
#
# Usage: bash scripts/trim_and_convert.sh input.mov "0-3 8-12 20-25"
#

set -e

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input-video.mov> <time-ranges>"
    echo ""
    echo "Time ranges: space-separated START-END pairs (in seconds)"
    echo ""
    echo "Example:"
    echo "  $0 ~/Desktop/demo.mov \"0-3 8-12 20-25\""
    echo ""
    echo "This keeps:"
    echo "  0-3 seconds   (typing query)"
    echo "  8-12 seconds  (viewing results)"
    echo "  20-25 seconds (final screen)"
    echo ""
    echo "Everything else is SKIPPED"
    echo ""
    exit 1
fi

INPUT="$1"
RANGES="$2"
OUTPUT_DIR="docs/demo"
SPEED=2  # Speed up kept sections 2x

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}✂️  Trimming video${NC}"
echo "Keeping: $RANGES"
echo ""

mkdir -p "$OUTPUT_DIR" 2>/dev/null || true

# Create temporary files for each segment
PARTS=()
i=0

for range in $RANGES; do
    START=$(echo $range | cut -d'-' -f1)
    END=$(echo $range | cut -d'-' -f2)
    DURATION=$(echo "$END - $START" | bc)

    PART="$OUTPUT_DIR/part_${i}.mp4"
    echo "Extracting ${START}s to ${END}s (${DURATION}s)..."

    ffmpeg -ss "$START" -i "$INPUT" -t "$DURATION" -c copy "$PART" -y -v quiet
    PARTS+=("$PART")
    i=$((i+1))
done

# Concatenate all parts
echo ""
echo "Combining segments..."
CONCAT_FILE="$OUTPUT_DIR/concat.txt"
rm -f "$CONCAT_FILE"

for part in "${PARTS[@]}"; do
    echo "file '$(basename $part)'" >> "$CONCAT_FILE"
done

COMBINED="$OUTPUT_DIR/combined.mp4"
ffmpeg -f concat -safe 0 -i "$CONCAT_FILE" -c copy "$COMBINED" -y -v quiet

# Speed up
echo "Speeding up ${SPEED}x..."
SPEED_FACTOR=$(echo "1/$SPEED" | bc -l)
FAST="$OUTPUT_DIR/fast.mp4"

ffmpeg -i "$COMBINED" \
    -filter:v "setpts=${SPEED_FACTOR}*PTS" \
    -r 30 -an "$FAST" -y -v quiet

# Convert to GIF
echo "Converting to GIF..."
GIF_TEMP="$OUTPUT_DIR/temp.gif"

ffmpeg -i "$FAST" \
    -vf "fps=15,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse" \
    "$GIF_TEMP" -y -v quiet

# Optimize
echo "Optimizing..."
GIF_OUTPUT="$OUTPUT_DIR/voyager-demo.gif"
gifsicle -O3 --colors 128 --lossy=60 "$GIF_TEMP" -o "$GIF_OUTPUT"

# Cleanup
rm -f "${PARTS[@]}"
rm -f "$CONCAT_FILE"
rm -f "$COMBINED"
rm -f "$FAST"
rm -f "$GIF_TEMP"

echo ""
echo -e "${GREEN}✅ Done!${NC}"
echo ""
echo "📍 Location: $GIF_OUTPUT"

if [ -f "$GIF_OUTPUT" ]; then
    SIZE=$(du -h "$GIF_OUTPUT" | cut -f1)
    echo "📦 Size: $SIZE"
fi

echo ""
echo "To add to README:"
echo "![Demo](docs/demo/voyager-demo.gif)"
echo ""
