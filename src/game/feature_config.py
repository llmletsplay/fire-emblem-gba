"""
Centralized feature configuration module.

This module provides a single source of truth for all feature toggles and configurations.
Modify the settings here to enable/disable features across the entire application.
"""

import os

# =============================================================================
# FEATURE TOGGLES - Single source of truth for all features
# =============================================================================

# Vision and Image Processing Features
# -----------------------------------------------------------------------------
# When False, screenshots are sent directly to the main LLM as images (requires multimodal model).
# When True, a separate vision model processes images into text descriptions first.
# Configurable via FE_USE_VISION_MODEL env var (default: true).
USE_VISION_MODEL = os.getenv("FE_USE_VISION_MODEL", "true").lower() in ("1", "true", "yes", "on")
TRUST_VISION_DESCRIPTIONS = True  # Whether to fully trust vision model descriptions (prevents hallucinations)
VISION_OVERRIDE_MAIN_MODEL = True  # Vision descriptions override any conflicting main model assumptions

# Minimap and Navigation Features
# -----------------------------------------------------------------------------
MINIMAP_ENABLED = False  # Global toggle for minimap features (currently has issues, recommend False)
MINIMAP_2D_ENABLED = False  # Use 2D minimap visualization (only works if MINIMAP_ENABLED is True)
USE_INTERNAL_MAPPING = False  # Use internal game state mapping (has accuracy issues, recommend False)
PATHFINDING_ENABLED = False  # Enable automatic pathfinding (depends on mapping, recommend False)

# Model and Performance Features
# -----------------------------------------------------------------------------
REASONING_ENABLED = True  # Enable reasoning mode for supported models
STREAM_RESPONSES = True  # Stream LLM responses for better user experience
ONE_IMAGE_PER_PROMPT = True  # Send only one image per prompt (better for most models)

# Debugging and Logging Features
# -----------------------------------------------------------------------------
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"  # Enable debug logging
LOG_VISION_DESCRIPTIONS = True  # Log full vision model descriptions for debugging
LOG_LLM_RAW_OUTPUT = True  # Log raw LLM outputs for debugging
SAVE_SCREENSHOTS = True  # Save screenshots to disk for debugging

# UI and Frontend Features
# -----------------------------------------------------------------------------
SHOW_VISION_IN_UI = True  # Display vision descriptions in the web UI
SHOW_MINIMAP_IN_UI = MINIMAP_ENABLED  # Show minimap in UI (tied to MINIMAP_ENABLED)
AUTO_REFRESH_SCREENSHOTS = True  # Auto-refresh screenshots in the UI

# Game-Specific Features
# -----------------------------------------------------------------------------
HANDLE_DIALOGUE_SCREENS = True  # Automatically handle dialogue/menu screens
DETECT_TITLE_SCREENS = True  # Detect and handle title/menu screens

# =============================================================================
# CONFIGURATION VALUES - Adjust these based on your needs
# =============================================================================

# Timeouts (in seconds)
DEFAULT_LLM_TIMEOUT = 120
DEFAULT_VISION_TIMEOUT = 30
SCREENSHOT_INTERVAL = 5  # How often to capture screenshots

# Token Limits
MAX_TOKENS = int(os.getenv("FE_MAX_TOKENS", "8192"))  # Maximum tokens for LLM responses
VISION_MAX_TOKENS = 300  # Maximum tokens for vision descriptions

# UI Settings
SCREENSHOT_POLL_INTERVAL = 5000  # milliseconds
MINIMAP_POLL_INTERVAL = 5000  # milliseconds

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_feature_enabled(feature_name: str) -> bool:
    """
    Check if a feature is enabled.

    Args:
        feature_name: Name of the feature (should match a variable name above)

    Returns:
        Boolean indicating if the feature is enabled
    """
    return globals().get(feature_name, False)

def get_config_value(config_name: str, default=None):
    """
    Get a configuration value.

    Args:
        config_name: Name of the configuration
        default: Default value if not found

    Returns:
        Configuration value or default
    """
    return globals().get(config_name, default)

def override_feature(feature_name: str, value: bool):
    """
    Override a feature setting at runtime (useful for testing).

    Args:
        feature_name: Name of the feature to override
        value: New value for the feature
    """
    if feature_name in globals():
        globals()[feature_name] = value
        print(f"Feature '{feature_name}' set to {value}")
    else:
        print(f"Warning: Feature '{feature_name}' not found")

# =============================================================================
# FEATURE DEPENDENCIES - Automatically handle dependent features
# =============================================================================

# If minimap is disabled, disable dependent features
if not MINIMAP_ENABLED:
    MINIMAP_2D_ENABLED = False
    SHOW_MINIMAP_IN_UI = False
    USE_INTERNAL_MAPPING = False
    PATHFINDING_ENABLED = False

# If vision model is disabled, disable dependent features
if not USE_VISION_MODEL:
    TRUST_VISION_DESCRIPTIONS = False
    VISION_OVERRIDE_MAIN_MODEL = False
    LOG_VISION_DESCRIPTIONS = False
    SHOW_VISION_IN_UI = False

# If debug mode is on, enable more logging
if DEBUG_MODE:
    LOG_VISION_DESCRIPTIONS = True
    LOG_LLM_RAW_OUTPUT = True
    SAVE_SCREENSHOTS = True

print(f"Feature Configuration Loaded:")
print(f"  - Vision Model: {USE_VISION_MODEL}")
print(f"  - Minimap: {MINIMAP_ENABLED}")
print(f"  - Internal Mapping: {USE_INTERNAL_MAPPING}")
print(f"  - Debug Mode: {DEBUG_MODE}")
