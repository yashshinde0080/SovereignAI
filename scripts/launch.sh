#!/bin/bash
# scripts/launch.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOVEREIGN_ROOT="$(dirname "$SCRIPT_DIR")"

export SOVEREIGN_HOME="$SOVEREIGN_ROOT"

cd "$SOVEREIGN_ROOT"

if [ ! -f "bin/sovereign-runtime" ]; then
    echo "Building SovereignAI..."
    cargo build --release
    mkdir -p bin
    cp target/release/sovereign-ai bin/sovereign-runtime
    cp target/release/sovereign-ai bin/sovereign-cli
fi

echo "╔══════════════════════════════════════╗"
echo "║     SovereignAI Edge v0.1.0          ║"
echo "║     Portable Offline LLM Runtime     ║"
echo "╚══════════════════════════════════════╝"

exec ./bin/sovereign-runtime "$@"