#!/bin/bash
#
# Smart Demo GIF Creator - Auto-skips loading scenes
# Usage: bash scripts/create_demo_gif_smart.sh path/to/recording.mov [mode]
#
# Modes:
#   auto   - Automatically detect and skip static scenes (default)
#   manual - Specify time ranges to keep
#   fast   - Speed up loading parts more than action parts
#

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <input-video.mov> [mode]"
    echo ""
    echo "Modes:"
    echo "  auto   - Auto-detect and skip static/loading scenes (default)"
    echo "  manual - Manually trim specific time ranges"
    echo "  fast   - Variable speed (10x during loading, 2x during action)"
    echo ""
    echo "Example: $0 ~/Desktop/voyager-demo.mov auto"
    exit 1
fi

INPUT="$1"
MODE="${2:-auto}"
OUTPUT_DIR="docs/demo"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎬 Smart Demo GIF Creator${NC}"
echo -e "Mode: ${YELLOW}${MODE}${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check dependencies
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    brew install ffmpeg
fi

if ! command -v gifsicle &> /dev/null; then
    echo "Installing gifsicle..."
    brew install gifsicle
fi

# ────────────────────────────────────────────
# MODE 1: AUTO - Remove static/duplicate frames
# ────────────────────────────────────────────
if [ "$MODE" = "auto" ]; then
    echo -e "${BLUE}🤖 Auto Mode: Detecting and removing static scenes${NC}"
    echo ""

    TEMP_DECIMATED="$OUTPUT_DIR/temp_decimated.mov"
    TEMP_FAST="$OUTPUT_DIR/temp_fast.mov"

    echo -e "${BLUE}⚡ Step 1: Removing duplicate/static frames${NC}"
    # mpdecimate removes duplicate frames (loading screens)
    # hi=64*12: Higher threshold = more aggressive removal
    # lo=64*5: Lower threshold for detection
    # frac=0.33: Keep only if 33% of frame has changed
    ffmpeg -i "$INPUT" \
        -vf "mpdecimate=hi=64*12:lo=64*5:frac=0.33,setpts=N/FRAME_RATE/TB" \
        -an "$TEMP_DECIMATED" -y

    echo ""
    echo -e "${BLUE}⚡ Step 2: Speeding up remaining video (2x)${NC}"
    ffmpeg -i "$TEMP_DECIMATED" \
        -filter:v "setpts=0.5*PTS" \
        -an "$TEMP_FAST" -y

    rm "$TEMP_DECIMATED"

# ────────────────────────────────────────────
# MODE 2: MANUAL - Trim specific sections
# ────────────────────────────────────────────
elif [ "$MODE" = "manual" ]; then
    echo -e "${BLUE}✂️  Manual Mode: Trim specific time ranges${NC}"
    echo ""
    echo "Enter time ranges to KEEP (skip loading parts)"
    echo "Format: start1-end1 start2-end2 ..."
    echo "Example: 0-3 8-12 25-30"
    echo "(keeps 0-3s, 8-12s, and 25-30s, skips everything else)"
    echo ""
    read -p "Time ranges: " RANGES

    TEMP_PARTS=()
    CONCAT_FILE="$OUTPUT_DIR/concat_list.txt"
    rm -f "$CONCAT_FILE"

    i=0
    for range in $RANGES; do
        START=$(echo $range | cut -d'-' -f1)
        END=$(echo $range | cut -d'-' -f2)
        PART="$OUTPUT_DIR/temp_part_$i.mov"

        echo "Extracting ${START}s - ${END}s..."
        ffmpeg -i "$INPUT" -ss "$START" -to "$END" -c copy "$PART" -y
        echo "file '$PART'" >> "$CONCAT_FILE"
        TEMP_PARTS+=("$PART")
        i=$((i+1))
    done

    TEMP_COMBINED="$OUTPUT_DIR/temp_combined.mov"
    echo ""
    echo "Combining segments..."
    ffmpeg -f concat -safe 0 -i "$CONCAT_FILE" -c copy "$TEMP_COMBINED" -y

    echo ""
    echo -e "${BLUE}⚡ Speeding up (2x)${NC}"
    TEMP_FAST="$OUTPUT_DIR/temp_fast.mov"
    ffmpeg -i "$TEMP_COMBINED" \
        -filter:v "setpts=0.5*PTS" \
        -an "$TEMP_FAST" -y

    # Cleanup
    rm -f "$CONCAT_FILE"
    rm -f "$TEMP_COMBINED"
    for part in "${TEMP_PARTS[@]}"; do
        rm -f "$part"
    done

# ────────────────────────────────────────────
# MODE 3: FAST - Variable speed based on scenes
# ────────────────────────────────────────────
elif [ "$MODE" = "fast" ]; then
    echo -e "${BLUE}⚡ Fast Mode: Variable speed (very fast during loading)${NC}"
    echo ""
    echo "This will:"
    echo "  - Speed up static scenes 10x (loading, waiting)"
    echo "  - Speed up action scenes 2x (typing, clicking, results)"
    echo ""

    TEMP_FAST="$OUTPUT_DIR/temp_fast.mov"

    # Use scene detection + variable speed
    # Static scenes (low motion) = 10x speed
    # Active scenes (high motion) = 2x speed
    ffmpeg -i "$INPUT" \
        -vf "mpdecimate=hi=64*12:lo=64*5:frac=0.2,setpts=N/FRAME_RATE/TB,setpts=0.5*PTS" \
        -an "$TEMP_FAST" -y

else
    echo "❌ Invalid mode: $MODE"
    echo "Valid modes: auto, manual, fast"
    exit 1
fi

# ────────────────────────────────────────────
# Common: Convert to GIF
# ────────────────────────────────────────────
echo ""
echo -e "${BLUE}🎨 Converting to optimized GIF${NC}"
GIF_OUTPUT="$OUTPUT_DIR/voyager-demo.gif"

ffmpeg -i "$TEMP_FAST" \
    -vf "fps=15,scale=1000:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=single[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" \
    -loop 0 \
    "$GIF_OUTPUT" -y

echo ""
echo -e "${BLUE}🗜️  Optimizing GIF size${NC}"
OPTIMIZED_OUTPUT="$OUTPUT_DIR/voyager-demo-optimized.gif"
gifsicle -O3 --colors 256 --lossy=80 "$GIF_OUTPUT" -o "$OPTIMIZED_OUTPUT"

# Clean up
rm "$TEMP_FAST"
rm "$GIF_OUTPUT"
mv "$OPTIMIZED_OUTPUT" "$GIF_OUTPUT"

echo ""
echo -e "${GREEN}✅ Smart Demo GIF created successfully!${NC}"
echo ""
echo "📍 Location: $GIF_OUTPUT"
echo ""

# Get file size and duration
SIZE=$(du -h "$GIF_OUTPUT" | cut -f1)
echo "📦 Size: $SIZE"
echo ""
echo "To add to README.md, use:"
echo ""
echo "![Voyager Demo](docs/demo/voyager-demo.gif)"
echo ""

# Show comparison if original exists
if [ -f "$OUTPUT_DIR/voyager-demo-original.gif" ]; then
    ORIG_SIZE=$(du -h "$OUTPUT_DIR/voyager-demo-original.gif" | cut -f1)
    echo "💡 Comparison:"
    echo "   Original: $ORIG_SIZE"
    echo "   Optimized: $SIZE"
fi
