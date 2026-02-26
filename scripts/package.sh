#!/bin/bash

# Package script for distribution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="1.0.0"
OUTPUT_DIR="$PROJECT_DIR/release"

echo "Packaging SovereignAI Edge v$VERSION..."

mkdir -p "$OUTPUT_DIR"

# Create portable package
PACKAGE_NAME="SovereignAI-Edge-$VERSION-portable"
PACKAGE_DIR="$OUTPUT_DIR/$PACKAGE_NAME"

rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Copy files
cp -r "$PROJECT_DIR/backend" "$PACKAGE_DIR/"
cp -r "$PROJECT_DIR/cli" "$PACKAGE_DIR/"
cp -r "$PROJECT_DIR/frontend/out" "$PACKAGE_DIR/frontend" 2>/dev/null || true
cp -r "$PROJECT_DIR/config" "$PACKAGE_DIR/"
cp "$PROJECT_DIR/launch.sh" "$PACKAGE_DIR/"
cp "$PROJECT_DIR/launch.bat" "$PACKAGE_DIR/"
cp "$PROJECT_DIR/README.md" "$PACKAGE_DIR/"

# Create empty directories
mkdir -p "$PACKAGE_DIR/models/installed"
mkdir -p "$PACKAGE_DIR/workspace"
mkdir -p "$PACKAGE_DIR/database"
mkdir -p "$PACKAGE_DIR/plugins"

# Remove unnecessary files
find "$PACKAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.pyc" -delete 2>/dev/null || true
find "$PACKAGE_DIR" -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true

# Create archive
cd "$OUTPUT_DIR"
tar -czvf "$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"
zip -r "$PACKAGE_NAME.zip" "$PACKAGE_NAME"

echo "Packages created:"
echo "  - $OUTPUT_DIR/$PACKAGE_NAME.tar.gz"
echo "  - $OUTPUT_DIR/$PACKAGE_NAME.zip"

# Create checksum
cd "$OUTPUT_DIR"
sha256sum "$PACKAGE_NAME.tar.gz" > "$PACKAGE_NAME.tar.gz.sha256"
sha256sum "$PACKAGE_NAME.zip" > "$PACKAGE_NAME.zip.sha256"

echo "Done!"