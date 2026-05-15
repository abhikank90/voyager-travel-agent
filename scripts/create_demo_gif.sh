#!/bin/bash
#
# Create Demo GIF from Screen Recording
# Usage: bash scripts/create_demo_gif.sh path/to/recording.mov
#

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <input-video.mov>"
    echo "Example: $0 ~/Desktop/voyager-demo.mov"
    exit 1
fi

INPUT="$1"
OUTPUT_DIR="docs/demo"
SPEED="2"  # 2x speed

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎬 Creating Demo GIF${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg not found. Installing..."
    brew install ffmpeg
fi

echo -e "${BLUE}⚡ Step 1: Speeding up video (${SPEED}x)${NC}"
TEMP_FAST="$OUTPUT_DIR/temp_fast.mov"
ffmpeg -i "$INPUT" -filter:v "setpts=1/${SPEED}*PTS" -an "$TEMP_FAST" -y

echo ""
echo -e "${BLUE}🎨 Step 2: Converting to GIF (optimized for web)${NC}"
GIF_OUTPUT="$OUTPUT_DIR/voyager-demo.gif"

# High quality GIF with optimized palette
ffmpeg -i "$TEMP_FAST" \
    -vf "fps=15,scale=1000:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=single[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" \
    -loop 0 \
    "$GIF_OUTPUT" -y

echo ""
echo -e "${BLUE}🗜️  Step 3: Optimizing GIF size${NC}"

# Install gifsicle if not present
if ! command -v gifsicle &> /dev/null; then
    echo "Installing gifsicle..."
    brew install gifsicle
fi

OPTIMIZED_OUTPUT="$OUTPUT_DIR/voyager-demo-optimized.gif"
gifsicle -O3 --colors 256 --lossy=80 "$GIF_OUTPUT" -o "$OPTIMIZED_OUTPUT"

# Clean up
rm "$TEMP_FAST"
rm "$GIF_OUTPUT"
mv "$OPTIMIZED_OUTPUT" "$GIF_OUTPUT"

echo ""
echo -e "${GREEN}✅ Demo GIF created successfully!${NC}"
echo ""
echo "📍 Location: $GIF_OUTPUT"
echo ""

# Get file size
SIZE=$(du -h "$GIF_OUTPUT" | cut -f1)
echo "📦 Size: $SIZE"
echo ""
echo "To add to README.md, use:"
echo ""
echo "![Voyager Demo](docs/demo/voyager-demo.gif)"
echo ""
