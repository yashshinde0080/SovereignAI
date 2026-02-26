#!/bin/bash

# Build script for SovereignAI Edge

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building SovereignAI Edge..."

# Build frontend
echo "Building frontend..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

# Build CLI (create executable with PyInstaller)
echo "Building CLI..."
cd "$PROJECT_DIR"
pip install pyinstaller
pyinstaller --onefile --name sovereign-cli cli/main.py

# Build Electron app
echo "Building desktop app..."
cd "$PROJECT_DIR/electron"
npm install
npm run build

echo "Build complete!"
echo "Outputs:"
echo "  - Frontend: frontend/out/"
echo "  - CLI: dist/sovereign-cli"
echo "  - Desktop: electron/dist/"