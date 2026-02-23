#!/bin/bash
# scripts/build.sh

set -e

echo "Building SovereignAI Edge..."

# Clean
cargo clean

# Build release
cargo build --release --features online

# Create distribution directory
DIST_DIR="dist/SovereignAI"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR/bin"
mkdir -p "$DIST_DIR/configs"
mkdir -p "$DIST_DIR/models/installed"
mkdir -p "$DIST_DIR/models/.cache"
mkdir -p "$DIST_DIR/workspace/sessions"
mkdir -p "$DIST_DIR/workspace/documents"
mkdir -p "$DIST_DIR/workspace/logs"
mkdir -p "$DIST_DIR/workspace/exports"
mkdir -p "$DIST_DIR/vector_store"
mkdir -p "$DIST_DIR/database"
mkdir -p "$DIST_DIR/plugins"

# Copy binary
cp target/release/sovereign-ai "$DIST_DIR/bin/sovereign-runtime"
cp target/release/sovereign-ai "$DIST_DIR/bin/sovereign-cli"

# Copy configs
cp configs/default.toml "$DIST_DIR/configs/"

# Copy scripts
cp scripts/launch.sh "$DIST_DIR/"
cp scripts/launch.bat "$DIST_DIR/"
chmod +x "$DIST_DIR/launch.sh"
chmod +x "$DIST_DIR/bin/sovereign-runtime"

# Strip symbols
strip "$DIST_DIR/bin/sovereign-runtime"
strip "$DIST_DIR/bin/sovereign-cli"

echo ""
echo "Build complete: $DIST_DIR"
echo ""
echo "Usage:"
echo "  cd $DIST_DIR"
echo "  ./launch.sh info"
echo "  ./launch.sh pull /path/to/model.gguf --source local"
echo "  ./launch.sh run llama3:8b --mode auto"
echo "  ./launch.sh serve"
echo "  ./launch.sh chat llama3:8b"