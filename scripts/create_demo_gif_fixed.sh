#!/bin/bash
#
# Fixed Demo GIF Creator
# Usage: bash scripts/create_demo_gif_fixed.sh path/to/recording.mov [speed]
#
# Speed: 2 (default), 3, 4, etc. Higher = faster
#

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <input-video.mov> [speed]"
    echo ""
    echo "Examples:"
    echo "  $0 ~/Desktop/demo.mov          # 2x speed (default)"
    echo "  $0 ~/Desktop/demo.mov 3        # 3x speed"
    echo "  $0 ~/Desktop/demo.mov 4        # 4x speed (good for long demos)"
    echo ""
    exit 1
fi

INPUT="$1"
SPEED="${2:-2}"  # Default 2x speed
OUTPUT_DIR="docs/demo"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🎬 Creating Demo GIF${NC}"
echo -e "Speed: ${YELLOW}${SPEED}x${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR" 2>/dev/null || true

# Check dependencies
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    brew install ffmpeg
fi

if ! command -v gifsicle &> /dev/null; then
    echo "Installing gifsicle..."
    brew install gifsicle
fi

# Calculate speed factor for ffmpeg
SPEED_FACTOR=$(echo "1/$SPEED" | bc -l)

echo -e "${BLUE}⚡ Step 1: Speeding up video (${SPEED}x)${NC}"
TEMP_FAST="$OUTPUT_DIR/temp_fast.mp4"

ffmpeg -i "$INPUT" \
    -filter:v "setpts=${SPEED_FACTOR}*PTS" \
    -r 30 \
    -an \
    "$TEMP_FAST" -y \
    2>&1 | grep -E "time=|Duration" || true

echo ""
echo -e "${BLUE}🎨 Step 2: Creating optimized GIF${NC}"
GIF_TEMP="$OUTPUT_DIR/temp.gif"

# Create GIF with proper settings
ffmpeg -i "$TEMP_FAST" \
    -vf "fps=15,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer" \
    "$GIF_TEMP" -y \
    2>&1 | grep -E "time=|Duration" || true

echo ""
echo -e "${BLUE}🗜️  Step 3: Optimizing file size${NC}"
GIF_OUTPUT="$OUTPUT_DIR/voyager-demo.gif"

gifsicle -O3 --colors 128 --lossy=60 "$GIF_TEMP" -o "$GIF_OUTPUT"

# Cleanup
rm -f "$TEMP_FAST"
rm -f "$GIF_TEMP"

echo ""
echo -e "${GREEN}✅ Demo GIF created!${NC}"
echo ""
echo "📍 Location: $GIF_OUTPUT"

# Show file size
if [ -f "$GIF_OUTPUT" ]; then
    SIZE=$(du -h "$GIF_OUTPUT" | cut -f1)
    echo "📦 Size: $SIZE"

    # Get duration
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null || echo "unknown")
    if [ "$DURATION" != "unknown" ]; then
        NEW_DURATION=$(echo "$DURATION / $SPEED" | bc -l)
        printf "⏱️  Duration: %.1fs (was %.1fs)\n" "$NEW_DURATION" "$DURATION"
    fi
fi

echo ""
echo "To add to README.md:"
echo ""
echo "![Voyager Demo](docs/demo/voyager-demo.gif)"
echo ""

# Check if file is too large
if [ -f "$GIF_OUTPUT" ]; then
    SIZE_BYTES=$(stat -f%z "$GIF_OUTPUT" 2>/dev/null || stat -c%s "$GIF_OUTPUT" 2>/dev/null || echo "0")
    SIZE_MB=$(echo "scale=1; $SIZE_BYTES / 1048576" | bc 2>/dev/null || echo "0")

    if (( $(echo "$SIZE_MB > 5" | bc -l) )); then
        echo -e "${YELLOW}⚠️  File size is ${SIZE_MB}MB (> 5MB)${NC}"
        echo ""
        echo "To reduce size, try:"
        echo "  1. Increase speed: $0 $INPUT $((SPEED + 1))"
        echo "  2. Reduce width: Edit script and change scale=900 to scale=700"
        echo "  3. Reduce colors: Edit script and change colors=128 to colors=64"
    fi
fi
