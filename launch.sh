#!/bin/bash

# SovereignAI Edge Launcher

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║       SovereignAI Edge v1.0.0         ║"
echo "║   Portable Offline AI Platform        ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Check if virtual environment exists
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies if needed
if [ ! -f "$VENV_DIR/.installed" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/backend/requirements.txt"
    touch "$VENV_DIR/.installed"
fi

echo -e "${GREEN}✓${NC} Dependencies installed"

# Create necessary directories (all runtime storage lives in workspace/)
mkdir -p "$SCRIPT_DIR/workspace/sessions"
mkdir -p "$SCRIPT_DIR/workspace/documents"
mkdir -p "$SCRIPT_DIR/workspace/logs"
mkdir -p "$SCRIPT_DIR/workspace/plugins"

# Start backend
echo -e "${BLUE}Starting backend server...${NC}"

cd "$SCRIPT_DIR/backend"

# Check if port is in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 8000 is already in use. Stopping existing process...${NC}"
    kill $(lsof -Pi :8000 -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 1
fi

# Start uvicorn
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo -e "${GREEN}✓${NC} Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend...${NC}"
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Backend is ready"
        break
    fi
    sleep 1
done

# Open browser or show CLI info
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}SovereignAI Edge is running!${NC}"
echo ""
echo -e "  API:  ${BLUE}http://127.0.0.1:8000${NC}"
echo -e "  Docs: ${BLUE}http://127.0.0.1:8000/docs${NC}"
echo ""
echo -e "  CLI:  ${YELLOW}python -m cli.main --help${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo -e "Press ${RED}Ctrl+C${NC} to stop"

# Handle shutdown
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    echo -e "${GREEN}Goodbye!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep running
wait $BACKEND_PID