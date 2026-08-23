#!/bin/bash
# Example: 1GB budget — most layers fit in memory, fewer evictions

MODEL="${1:-models/tinyllama-1.1B.gguf}"

python -m engine run "$MODEL" \
    -p "Write a haiku about programming" \
    -n 128 \
    --budget 1024 \
    --verbose
