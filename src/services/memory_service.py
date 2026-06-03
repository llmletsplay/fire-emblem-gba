"""
Memory Service - WebSocket endpoint for streaming game state

Provides real-time Fire Emblem game state to the web UI for overlay display.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional
from src.utils.memory_reader import GBAMemoryReader, GBAGameState, get_memory_reader

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for broadcasting memory state to web clients"""

    def __init__(self, socket_client=None):
        self.socket_client = socket_client
        self.memory_reader = None
        self.last_state = None

        if socket_client:
            try:
                self.memory_reader = get_memory_reader(socket_client)
                if self.memory_reader:
                    logger.info(f"Memory service initialized with {self.memory_reader.game.title} reader")
                else:
                    logger.warning("Memory reader creation returned None")
            except Exception as e:
                logger.warning(f"Memory service fallback to vision-only: {e}")

    def get_current_state(self) -> Optional[Dict[str, Any]]:
        """Get current game state as dictionary"""
        if not self.memory_reader:
            return None

        try:
            state = self.memory_reader.read_game_state()
            self.last_state = state

            return self._format_state_for_ui(state)
        except Exception as e:
            logger.error(f"Failed to read game state: {e}")
            return None

    def _format_state_for_ui(self, state: GBAGameState) -> Dict[str, Any]:
        """Format game state for web UI consumption"""
        return {
            # Game info
            'chapter': state.chapter,
            'turn': state.turn,
            'phase': state.phase,

            # Cursor
            'cursor': {
                'x': state.cursor_x,
                'y': state.cursor_y
            },

            # Unit counts
            'counts': {
                'players': state.player_count,
                'enemies': state.enemy_count,
                'players_alive': state.alive_player_count,
                'enemies_alive': state.alive_enemy_count
            },

            # Player units (detailed)
            'player_units': [
                {
                    'id': unit.char_id,
                    'class': unit.class_id,
                    'level': unit.level,
                    'exp': unit.exp,
                    'hp': unit.current_hp,
                    'max_hp': unit.max_hp,
                    'hp_percent': unit.hp_percent * 100,
                    'position': {'x': unit.x, 'y': unit.y},
                    'stats': {
                        'str': unit.strength,
                        'skl': unit.skill,
                        'spd': unit.speed,
                        'def': unit.defense,
                        'res': unit.resistance,
                        'lck': unit.luck
                    },
                    'status': {
                        'alive': unit.is_alive,
                        'moved': unit.has_moved
                    }
                }
                for unit in state.player_units if unit.is_alive
            ],

            # Enemy units (simplified for UI)
            'enemy_units': [
                {
                    'id': unit.char_id,
                    'class': unit.class_id,
                    'hp': unit.current_hp,
                    'max_hp': unit.max_hp,
                    'hp_percent': unit.hp_percent * 100,
                    'position': {'x': unit.x, 'y': unit.y}
                }
                for unit in state.enemy_units if unit.is_alive
            ],

            # Timestamp
            'timestamp': asyncio.get_event_loop().time()
        }

    async def broadcast_loop(self, broadcast_func, interval: float = 0.5):
        """
        Continuous loop to broadcast game state

        Args:
            broadcast_func: Async function to broadcast data
            interval: Seconds between broadcasts
        """
        logger.info(f"Starting memory broadcast loop (interval={interval}s)")

        while True:
            try:
                state_data = self.get_current_state()

                if state_data:
                    await broadcast_func({
                        'type': 'memory_state',
                        'data': state_data
                    })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in memory broadcast loop: {e}")
                await asyncio.sleep(1.0)  # Back off on error


# Global instance
_memory_service = None

def get_memory_service(socket_client=None) -> MemoryService:
    """Get or create global memory service"""
    global _memory_service

    if _memory_service is None:
        _memory_service = MemoryService(socket_client)

    return _memory_service