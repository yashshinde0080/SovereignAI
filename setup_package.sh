#!/bin/bash
set -e

# Create graphify package directory
mkdir -p graphify

# Move all graphify_*.py files into graphify/ and rename (strip prefix)
for f in $(ls graphify_*.py 2>/dev/null); do
    name=$(echo "$f" | sed 's/^graphify_//')
    mv "$f" "graphify/$name"
done

# Create __init__.py if missing
if [ ! -f graphify/__init__.py ]; then
    echo "# graphify package" > graphify/__init__.py
fi

# Ensure all expected modules exist
for m in detect extract cache semantic semantic_subagent build cluster analyze report export ingest watch cli; do
    if [ ! -f graphify/${m}.py ]; then
        echo "Missing module: graphify/${m}.py"
    fi
done

echo "Package structure ready."
