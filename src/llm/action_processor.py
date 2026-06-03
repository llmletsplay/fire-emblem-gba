"""
Action and image processing - extracted from llmdriver.py

Handles action result capture, image encoding, and vision model interactions.
"""

import os
import base64
import logging
import tempfile
import re

from src.core import config
from src.game.actions import ActionResult

log = logging.getLogger(__name__)


def capture_action_result(action_type, action_description, prev_state, current_state):
    """Capture the result of an action for LLM feedback.
    
    Note: This compares current state's visible indicators (movement_tiles, unit_is_selected)
    rather than cursor position, since cursor update timing is unreliable.
    """
    result = ActionResult(success=False, action_type=action_type, message="")
    
    movement_tiles = current_state.get("movement_tiles", [])
    unit_is_selected = current_state.get("unit_is_selected", False)
    phase = current_state.get("phase", "unknown")
    
    result.movement_tiles = [tuple(t) for t in movement_tiles]
    result.phase = phase
    result.unit_selected = unit_is_selected or bool(movement_tiles)
    
    if action_type == "SELECT":
        if movement_tiles or unit_is_selected:
            result.success = True
            result.message = f"Unit selected. Movement tiles visible: {len(movement_tiles)}"
        else:
            result.message = "No movement tiles visible"
    
    elif action_type == "MOVE":
        prev_movement = prev_state.get("movement_tiles", []) if prev_state else []
        if len(movement_tiles) != len(prev_movement) or not movement_tiles:
            result.success = True
            result.unit_moved = True
            result.message = "Unit action completed"
        else:
            result.message = "Movement tiles unchanged"
    
    elif action_type == "ATTACK":
        result.success = True
        result.message = "Attack executed"
    else:
        result.success = True
        result.message = f"Action '{action_type}' completed"
    
    if not result.success and not result.error:
        result.error = result.message
    
    return result.to_dict()


def encode_image_base64(image_path: str) -> str | None:
    """Reads an image file and returns its base64 encoded string."""
    if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
        return None
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        log.error(f"Error reading/encoding image '{image_path}': {e}")
        return None


def detect_game_phase(description: str) -> str:
    """Detect the current game phase from vision description - based on what's actually visible."""
    desc_lower = description.lower()

    if ("black" in desc_lower or "dark screen" in desc_lower) and "fire emblem" not in desc_lower:
        return "transition"

    if "fire emblem" in desc_lower and ("press start" in desc_lower or "title" in desc_lower or "sacred stones" in desc_lower or "blazing blade" in desc_lower or "blazing sword" in desc_lower):
        return "menu"

    if "text box" in desc_lower and "bottom" in desc_lower:
        return "story_dialogue"

    if "grid" in desc_lower and ("red" in desc_lower or "overlay" in desc_lower):
        return "tactical_map"

    if "portrait" in desc_lower or "character face" in desc_lower:
        return "story_dialogue"

    if "menu" in desc_lower or "options" in desc_lower or "buttons" in desc_lower or "save" in desc_lower:
        return "menu"

    if "text" in desc_lower and "can read" in desc_lower:
        return "story_dialogue"

    return "unknown"


def get_image_description(image_base64, image_type="screenshot", vision_client=None, vision_model=None):
    """Get a text description of an image using the vision model."""
    if not vision_client or not vision_model:
        return None

    try:
        if vision_model == "glm-mcp-vision":
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                image_data = base64.b64decode(image_base64)
                temp_file.write(image_data)
                temp_file_path = temp_file.name

            try:
                if config.ANTI_HALLUCINATION and image_type == "screenshot":
                    prompt = """Describe ONLY what you can ACTUALLY SEE in this Fire Emblem screenshot.
Focus on:
1. Game phase (battle map, dialogue, menu)
2. Visible units (blue=player, red=enemy)
3. UI elements (menus, text boxes)
4. Blue squares if visible (movement range)
5. Text content in dialogue boxes — READ and transcribe any visible text exactly
6. Flashing or highlighted tiles — note their approximate grid position

Do NOT:
- Invent unit names unless shown
- Assume positions not visible
- Add story details not on screen"""
                elif image_type == "minimap":
                    prompt = """Describe this Fire Emblem tactical map. Identify:
- Unit positions (blue=player, red=enemy)
- Terrain features (forests, mountains, villages)
- Objectives (throne, gates, chests)
- Strategic chokepoints
Be concise and focus on tactical information."""
                else:
                    prompt = """Describe ONLY what you can see in this screenshot.

Focus on:
1. Is the screen mostly black or is there visible content?
2. Are there any text boxes visible? If yes, what text can you read?
3. Are there character portraits or faces visible?
4. Is there a grid pattern overlaid on the screen?
5. What colors and shapes do you see?
6. Are there any menu options or buttons visible?

Be literal and descriptive."""

                description = vision_client.analyze_image_sync(temp_file_path, prompt)

                if description:
                    log.info(f"Got {image_type} description from MCP vision: {len(description)} chars")
                    return description
                else:
                    log.warning(f"MCP vision returned empty description for {image_type}")

            finally:
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

        else:
            if config.ANTI_HALLUCINATION and image_type == "screenshot":
                prompt = """Describe ONLY what you can ACTUALLY SEE in this Fire Emblem screenshot.
Focus on:
1. Game phase (battle map, dialogue, menu)
2. Visible units (blue=player, red=enemy)
3. UI elements (menus, text boxes)
4. Blue squares if visible (movement range)
5. Text content in dialogue boxes — READ and transcribe any visible text exactly
6. Flashing or highlighted tiles — note their approximate grid position

Do NOT:
- Invent unit names unless shown
- Assume positions not visible
- Add story details not on screen"""
            elif image_type == "minimap":
                prompt = """Describe this Fire Emblem tactical map. Identify:
- Unit positions (blue=player, red=enemy)
- Terrain features (forests, mountains, villages)
- Objectives (throne, gates, chests)
- Strategic chokepoints
Be concise and focus on tactical information."""
            else:
                prompt = """Describe what you see in this screenshot.

Focus on:
1. Is the screen mostly black or visible content?
2. Text boxes visible? What text can you read?
3. Character portraits visible?
4. Grid pattern overlaid?
5. Colors and shapes?
6. Menu options or buttons?"""

            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]}
            ]

            response = vision_client.chat.completions.create(
                model=vision_model,
                messages=messages,
                max_tokens=500,
            )

            description = response.choices[0].message.content
            if description:
                log.info(f"Got {image_type} description from vision model: {len(description)} chars")
                return description

    except Exception as e:
        log.error(f"Error getting {image_type} description: {e}")

    return None
