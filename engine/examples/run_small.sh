#!/bin/bash
# Example: 256MB budget — forces layer streaming
# The model weights are evicted/loaded on-demand to stay within budget.

MODEL="${1:-models/tinyllama-1.1B.gguf}"

python -m engine run "$MODEL" \
    -p "The capital of France is" \
    -n 64 \
    --budget 256 \
    --verbose
