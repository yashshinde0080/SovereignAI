#!/bin/bash
# Example: unlimited budget — all weights stay in memory (fastest)

MODEL="${1:-models/tinyllama-1.1B.gguf}"

python -m engine run "$MODEL" \
    -p "Once upon a time" \
    -n 256
