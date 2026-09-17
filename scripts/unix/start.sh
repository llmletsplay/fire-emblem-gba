#!/bin/bash

# Fire Emblem AI Agent - Unified Startup Script
# This script starts both the backend and frontend in a clean, production-ready way

echo "Fire Emblem GBA AI Agent"
echo "========================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load .env early so ROM_FILE/FE_GAME and provider settings are available.
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

FE_GAME="${FE_GAME:-}"

if [ -z "${ROM_FILE:-}" ]; then
  detected_roms=()
  for candidate in FE7.gba fe7.gba FE8.gba fe8.gba; do
    if [ -f "roms/$candidate" ]; then
      detected_roms+=("$candidate")
    fi
  done

  if [ "${#detected_roms[@]}" -eq 1 ]; then
    ROM_FILE="${detected_roms[0]}"
  else
    echo -e "${RED}Error: ROM_FILE is not configured.${NC}"
    echo "Set ROM_FILE in .env to FE7.gba or FE8.gba."
    echo "Examples: ROM_FILE=FE7.gba FE_GAME=fe7 or ROM_FILE=FE8.gba FE_GAME=fe8"
    exit 1
  fi
fi

ROM_PATH="roms/${ROM_FILE}"

# Check for required files
if [ ! -f "$ROM_PATH" ]; then
  echo -e "${RED}Error: ROM file not found at ${ROM_PATH}${NC}"
  echo "Place your legally obtained FE7 or FE8 ROM in roms/ and set ROM_FILE in .env."
  echo "Examples: ROM_FILE=FE7.gba FE_GAME=fe7 or ROM_FILE=FE8.gba FE_GAME=fe8"
  exit 1
fi

# Check for Python
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}Error: Python 3 is not installed${NC}"
  exit 1
fi

# Check for Node.js
if ! command -v node &>/dev/null; then
  echo -e "${RED}Error: Node.js is not installed${NC}"
  exit 1
fi

# Create necessary directories
echo -e "${GREEN}Creating necessary directories...${NC}"
mkdir -p fe-client/public/chronicle/screenshots
mkdir -p assets/maps
mkdir -p assets/sprites
mkdir -p screenshots

# Install Python dependencies if needed
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}Creating Python virtual environment...${NC}"
  python3 -m venv venv
fi

echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -q -r requirements.txt 2>/dev/null || {
  echo -e "${RED}Failed to install Python dependencies${NC}"
  exit 1
}

# Install Node dependencies
echo -e "${YELLOW}Installing frontend dependencies...${NC}"
cd fe-client
if [ ! -d "node_modules" ]; then
  npm install --quiet || {
    echo -e "${RED}Failed to install Node dependencies${NC}"
    exit 1
  }
fi
cd ..

# Function to cleanup on exit
cleanup() {
  echo -e "\n${YELLOW}Shutting down services...${NC}"
  # Kill all child processes
  kill $(jobs -p) 2>/dev/null
  wait $(jobs -p) 2>/dev/null
  echo -e "${GREEN}All services stopped.${NC}"
  exit 0
}

# Set up trap for clean shutdown
trap cleanup SIGINT SIGTERM

# Start the React frontend
echo -e "${GREEN}Starting React frontend...${NC}"
cd fe-client
npm run dev &
FRONTEND_PID=$!
cd ..

# Give frontend time to start
sleep 3

# Check if LLM_PROVIDER is already configured in .env
MODE="${LLM_PROVIDER:-}"
case "$MODE" in
  ""|OPENAI|ANTHROPIC|GEMINI|GROQ|TOGETHER|GROK|OLLAMA|LMSTUDIO|CUSTOM|ZAI|MINIMAX)
    ;;
  *)
    echo -e "${YELLOW}Ignoring unsupported LLM_PROVIDER from .env: $MODE${NC}"
    MODE=""
    ;;
esac

# Only run interactive setup if LLM_PROVIDER is not set
if [ -z "$MODE" ]; then
  # Run interactive setup to select/configure LLM provider
  # This handles provider selection and API key entry.
  echo -e "${YELLOW}Configuring LLM provider...${NC}"

  # Remove old result file
  rm -f .llm_provider_result

  # Run interactively (not in subshell so user can see prompts)
  python3 src/llm/interactive_setup.py
  SETUP_EXIT=$?

  if [ $SETUP_EXIT -ne 0 ]; then
    echo -e "${RED}LLM provider setup failed or was cancelled.${NC}"
    cleanup
    exit 1
  fi

  # Read provider from result file
  if [ -f ".llm_provider_result" ]; then
    MODE=$(cat .llm_provider_result)
    rm -f .llm_provider_result
  fi

  if [ -z "$MODE" ]; then
    echo -e "${RED}Error: No LLM provider configured.${NC}"
    cleanup
    exit 1
  fi
fi

# Export LLM_PROVIDER for Python to use
export LLM_PROVIDER="$MODE"
echo -e "${GREEN}Using LLM provider: $MODE${NC}"
if [ -n "$FE_GAME" ]; then
  echo -e "${GREEN}Using game: $FE_GAME ($ROM_FILE)${NC}"
else
  echo -e "${GREEN}Using ROM: $ROM_FILE (game will be inferred)${NC}"
fi

# Start the Python backend with auto mode
echo -e "${GREEN}Starting AI backend with $MODE model...${NC}"
python3 src/core/run.py --auto &
BACKEND_PID=$!

# Display status
echo ""
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo ""
echo "📍 Service URLs:"
echo "   • Frontend:  http://localhost:5173"
echo "   • WebSocket: ws://localhost:8765"
echo "   • mGBA:      localhost:8888"
echo ""
echo "📖 Instructions:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. The AI will automatically start playing the configured Fire Emblem GBA ROM"
echo "   3. Switch to Chronicle tab to see story interpretations"
echo "   4. Press Ctrl+C to stop all services"
echo ""
echo -e "${YELLOW}Logs will appear below...${NC}"
echo "========================================"

# Wait for all background processes
wait $FRONTEND_PID $BACKEND_PID
