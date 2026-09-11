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

# Resolve host:port from the settings DB (security.api_port / bind_localhost_only)
API_ADDR="$(python -c "import sys; sys.path.insert(0, 'backend'); from main import get_server_config; h, p = get_server_config(); h = '127.0.0.1' if h == '0.0.0.0' else h; print(f'{h}:{p}')" 2>/dev/null || echo "127.0.0.1:8000")"
API_PORT="${API_ADDR##*:}"
echo -e "${GREEN}✓${NC} API will listen on $API_ADDR"

# Create necessary directories (all runtime storage lives in workspace/)
mkdir -p "$SCRIPT_DIR/workspace/sessions"
mkdir -p "$SCRIPT_DIR/workspace/documents"
mkdir -p "$SCRIPT_DIR/workspace/logs"
mkdir -p "$SCRIPT_DIR/workspace/plugins"

# Start backend
echo -e "${BLUE}Starting backend server...${NC}"

cd "$SCRIPT_DIR/backend"

# Check if the configured port is in use
if lsof -Pi :$API_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Port $API_PORT is already in use. Stopping existing process...${NC}"
    kill $(lsof -Pi :$API_PORT -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 1
fi

# Start backend (honors settings DB: security.api_port, security.bind_localhost_only)
python main.py &
BACKEND_PID=$!

echo -e "${GREEN}✓${NC} Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend...${NC}"
for i in {1..30}; do
    if curl -s "http://$API_ADDR/health" > /dev/null 2>&1; then
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
echo -e "  API:  ${BLUE}http://$API_ADDR${NC}"
echo -e "  Docs: ${BLUE}http://$API_ADDR/docs${NC}"
echo ""
echo -e "  CLI:  ${YELLOW}./sovereign --help${NC}   (or: cd backend/app && python -m cli.main --help)"
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