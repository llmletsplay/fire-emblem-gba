"""Offline check for ATTACK tile resolution (no mGBA)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / "fe-gba"
sys.path.insert(0, str(ROOT))
from src.game.command_executor import get_enemy_by_name, resolve_attack_target_tile, execute_command_sequence
from src.game.command_parser import Command

enemies = [
    {"name": "Unit 0x3E", "id": "0x3E", "x": 3, "y": 9},
    {"name": "Unit 0x3E", "id": "0x3E", "x": 9, "y": 4},
]
cursor = (8, 4)
e = get_enemy_by_name(enemies, "Unit 0x3E", cursor=cursor)
assert (e["x"], e["y"]) == (9, 4), e
state = {
    "enemies": enemies,
    "attack_opportunities": [
        {"move_to": [8, 4], "target": "Unit 0x3E", "enemy_at": [9, 4]},
    ],
    "cursor": cursor,
    "phase": "player_phase",
}
tile, src, enemy = resolve_attack_target_tile(state, "Unit 0x3E", cursor)
assert tile == (9, 4) and src == "attack_opportunities", (tile, src)
buttons, desc = execute_command_sequence([Command(type="ATTACK", target="Unit 0x3E")], state)
assert "RIGHT" in buttons, buttons
print("PASS", buttons, desc, src)
