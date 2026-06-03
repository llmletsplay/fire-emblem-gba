import os
import sys
from dotenv import load_dotenv
from src.utils.file_utils import find_mgba

# Load .env BEFORE reading any env vars — config.py is imported early,
# so without this, os.getenv() calls below would miss .env values.
load_dotenv(os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), '.env'))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

# Simple env helpers
def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1","true","yes","on"}

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

PORT = _env_int('FE_MGBA_PORT', 8888)
LOAD_SAVESTATE = _env_bool('FE_LOAD_SAVESTATE', False)
LUA_SCRIPT = os.path.join(PROJECT_ROOT, 'lua/socketserver.lua')
benchmark_path = None   # default: no external benchmark

# Screenshot configuration
DRAW_GRID_OVERLAY = False  # Whether to draw red grid lines on screenshots (set to True for debugging)
GRID_COLOR = (255, 0, 0, 128)  # RGBA color for grid overlay (semi-transparent red)
GRID_SIZE = 16  # Grid cell size in pixels
SCREENSHOT_CAPTURE_COUNT = _env_int('FE_SCREENSHOT_CAPTURE_COUNT', 3)  # Number of screenshots to capture per cycle

# Text box / dialogue detection
TEXT_BOX_DETECTION_ENABLED = _env_bool('FE_TEXT_BOX_DETECTION', True)
TEXT_BOX_BOTTOM_PX = _env_int('FE_TEXT_BOX_BOTTOM_PX', 48)
TEXT_BOX_DARK_THRESHOLD = _env_float('FE_TEXT_BOX_DARK_THRESHOLD', 80.0)
TEXT_BOX_CONTRAST_THRESHOLD = _env_float('FE_TEXT_BOX_CONTRAST_THRESHOLD', 25.0)
TEXT_BOX_TOP_MIN_BRIGHTNESS = _env_float('FE_TEXT_BOX_TOP_MIN_BRIGHTNESS', 40.0)

# Flash/animation detection
FLASH_DETECTION_ENABLED = _env_bool('FE_FLASH_DETECTION', True)
FLASH_DIFF_THRESHOLD = _env_int('FE_FLASH_DIFF_THRESHOLD', 40)
FLASH_MIN_TILE_RATIO = _env_float('FE_FLASH_MIN_TILE_RATIO', 0.15)
FLASH_EXCLUDE_TOP_ROWS = _env_int('FE_FLASH_EXCLUDE_TOP_ROWS', 3)  # Skip top N tile rows (HUD area)

# Movement/attack tile detection (blue=movement range, red=attack-only range)
MOVEMENT_TILE_DETECTION = _env_bool('FE_MOVEMENT_TILE_DETECTION', True)
MOVEMENT_BLUE_THRESHOLD = _env_int('FE_MOVEMENT_BLUE_THRESHOLD', 20)  # Blue channel dominance for movement tiles
MOVEMENT_RED_THRESHOLD = _env_int('FE_MOVEMENT_RED_THRESHOLD', 30)    # Red channel dominance for attack tiles

# Chronicle configuration
CHRONICLE_ENABLED = True  # Enable saving story interpretations and screenshots
CHRONICLE_PATH = os.path.join(PROJECT_ROOT, 'assets/chronicle')
MAX_CHRONICLE_ENTRIES = 100  # Maximum number of chronicle entries to keep

# Map feature configuration
USE_MAP_CONTEXT = False  # Enable/disable using chapter maps for vision context
MAPS_PATH = os.path.join(PROJECT_ROOT, 'assets/maps')
SPRITES_PATH = os.path.join(PROJECT_ROOT, 'assets/sprites')

# ROM configuration
# FE_GAME can be: "fe7" or "fe8" - set this to skip auto-detection
# If not set, infers from ROM_FILE env var (fe7.gba -> fe7, fe8.gba -> fe8)
ROMS_FOLDER = os.path.join(PROJECT_ROOT, 'roms')
SUPPORTED_ROM_FILES = ('FE7.gba', 'fe7.gba', 'FE8.gba', 'fe8.gba')

def _detect_rom_file():
    configured = os.getenv('ROM_FILE', '').strip()
    if configured:
        return configured

    found = [
        candidate for candidate in SUPPORTED_ROM_FILES
        if os.path.exists(os.path.join(ROMS_FOLDER, candidate))
    ]
    return found[0] if len(found) == 1 else ''

DEFAULT_ROM_FILE = _detect_rom_file()
ROM_PATH = os.path.join(ROMS_FOLDER, DEFAULT_ROM_FILE) if DEFAULT_ROM_FILE else ''

# Determine game from environment or ROM filename
def _detect_game_from_env():
    # Explicit FE_GAME takes priority
    fe_game = os.getenv('FE_GAME', '').lower()
    if fe_game in ('fe7', 'fe8'):
        return fe_game
    # Infer from ROM_FILE
    rom_file = DEFAULT_ROM_FILE.lower()
    if 'fe7' in rom_file or 'blazing' in rom_file or 'blading' in rom_file:
        return 'fe7'
    if 'fe8' in rom_file or 'sacred' in rom_file:
        return 'fe8'
    return ''

FE_GAME = _detect_game_from_env()

# LLM timeout configuration (in seconds)
# These can be overridden by environment variables for different API providers
# Default values work well for most OpenAI-compatible APIs
LLM_STREAM_TIMEOUT = _env_int('LLM_STREAM_TIMEOUT', 120)  # Time to wait for streaming response
LLM_TOTAL_TIMEOUT = _env_int('LLM_TOTAL_TIMEOUT', 150)    # Total time including processing

MGBA_EXE = find_mgba() or os.getenv('FE_MGBA_EXE')
if MGBA_EXE and not os.path.exists(MGBA_EXE):
    print(f"Warning: configured mGBA executable '{MGBA_EXE}' does not exist.", file=sys.stderr)
    MGBA_EXE = None
if not MGBA_EXE:
    print("Warning: mGBA executable not found. Auto-detection failed - set FE_MGBA_EXE manually.", file=sys.stderr)

# Session management configuration
SESSION_MAX_COUNT = _env_int('FE_SESSION_MAX_COUNT', 10)  # Maximum sessions to keep
SESSION_MAX_SCREENSHOTS = _env_int('FE_SESSION_MAX_SCREENSHOTS', 500)  # Max screenshots per session

# Memory window configuration
MEMORY_WINDOW_SIZE = _env_int('FE_MEMORY_WINDOW_SIZE', 12)  # Rolling context window size (reduced for token efficiency)
MEMORY_THUMBNAIL_COUNT = _env_int('FE_MEMORY_THUMBNAIL_COUNT', 5)  # Thumbnails per API request (reduced for token efficiency)

# Token budget configuration
MAX_INPUT_TOKENS = _env_int('FE_MAX_INPUT_TOKENS', 100000)  # Max tokens before compaction kicks in (conservative — most models cap at 128-131K)
CLEANUP_WINDOW = _env_int('FE_CLEANUP_WINDOW', 5)  # Summarize chat history every N turns

# Compaction thresholds
COMPACTION_MIN_CHAT_HISTORY = 4  # Minimum chat history turns to keep during compaction
COMPACTION_MIN_MEMORY_ENTRIES = 8  # Minimum memory entries to keep during compaction
COMPACTION_REDUCED_THUMBNAILS = 3  # Reduced thumbnail count during compaction

# Content truncation limits
MEMORY_DESCRIPTION_TRUNCATE = 300  # Max chars for screen_description in memory entries
MEMORY_REASONING_TRUNCATE = 300  # Max chars for ai_reasoning in memory entries
DROPPED_CONTENT_PREVIEW_LENGTH = 500  # Max chars for dropped content preview during compaction

# Action length limit
MAX_ACTION_BUTTONS = _env_int('FE_MAX_ACTION_BUTTONS', 8)  # Hard cap on buttons per action (keep short, observe, repeat)

# Vision model configuration
VISION_RESPONSE_MAX_TOKENS = 300  # Max tokens for vision model responses

# WebSocket configuration
WEBSOCKET_PORT = _env_int('FE_WEBSOCKET_PORT', 8765)  # WebSocket server port

# AI Enhancement Features - Simple on/off switches
PERSISTENT_LEARNING = True  # Save and learn from past experiences
ANTI_HALLUCINATION = True  # Only describe what's actually visible
SMART_MENU_ESCAPE = False  # DISABLED - AI learns organically from memory
MOVEMENT_COACHING = False  # DISABLED - AI learns organically from memory
STRATEGIC_PLANNING = True  # Use strategic decision framework
CONTEXT_HINTS_ENABLED = _env_bool('FE_CONTEXT_HINTS_ENABLED', False)  # DISABLED - Let LLM use its own knowledge

# Tutorial mode (for FE7 Lyn's Tale chapters 1-10)
# When true, includes tutorial_target and tutorial_sequence in context
# When false, skips tutorial-specific features for Chapter 11+ (Eliwood's Tale)
TUTORIAL_MODE = _env_bool('FE_TUTORIAL', True)

# Model selection - Get from environment or use default
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o')
