"""Unit tests for legal_moves catalog + MOVE: mN resolution (no ROM required)."""

from src.game.command_executor import resolve_attack_target_tile
from src.game.command_parser import parse_command, parse_move_id_line
from src.game.legal_moves import (
    build_legal_moves,
    legal_moves_for_prompt,
    resolve_move_id,
)


def _map_state(**overrides):
    base = {
        "text_box_visible": False,
        "input_locked": False,
        "in_dialogue": False,
        "in_menu": False,
        "screen_context": "player_phase map",
        "party": [
            {"name": "Lyn", "x": 2, "y": 3, "hasMoved": False},
            {"name": "Sain", "x": 3, "y": 3, "hasMoved": False},
        ],
        "unit_status": {"Lyn": "available", "Sain": "available"},
        "enemies": [{"name": "Batta", "x": 5, "y": 3, "id": 1}],
        "movement_tiles": [],
        "attack_opportunities": [],
        "unit_is_selected": False,
        "selected_unit": None,
        "cursor": [2, 3],
    }
    base.update(overrides)
    return base


def test_build_legal_moves_ids_are_sequential_mN():
    moves = build_legal_moves(_map_state())
    assert moves, "expected at least select / end_turn options"
    ids = [m["id"] for m in moves]
    assert ids[0] == "m0"
    for i, mid in enumerate(ids):
        assert mid == f"m{i}"
    assert all(m.get("command") for m in moves)
    assert all(m.get("summary") for m in moves)


def test_build_legal_moves_select_and_end_turn():
    moves = build_legal_moves(_map_state())
    kinds = {m["kind"] for m in moves}
    assert "select" in kinds
    assert "end_turn" in kinds
    lyn = next(m for m in moves if m["kind"] == "select" and "Lyn" in m["command"])
    assert 'SELECT unit="Lyn"' in lyn["command"]


def test_build_legal_moves_selected_unit_move_attack():
    state = _map_state(
        unit_is_selected=True,
        selected_unit="Lyn",
        movement_tiles=[[4, 3], [5, 3], [3, 3]],
        attack_opportunities=[
            {"target": "Batta", "move_to": [4, 3], "tile": [4, 3]},
        ],
    )
    moves = build_legal_moves(state)
    assert moves[0]["id"] == "m0"
    attack = next(m for m in moves if m["kind"] == "move_attack")
    assert 'SELECT unit="Lyn"' in attack["command"]
    assert "ATTACK target=\"Batta\"" in attack["command"]
    assert any(m["kind"] == "move_wait" for m in moves)


def test_parse_move_id_line_extracts_mN():
    assert parse_move_id_line("MOVE: m0") == "m0"
    assert parse_move_id_line("reasoning...\nMOVE: m12\n") == "m12"
    assert parse_move_id_line("```\nMOVE: m3\n```") == "m3"
    assert parse_move_id_line("MOVE: 7") == "m7"
    assert parse_move_id_line("COMMAND: A") is None


def test_resolve_move_id_to_command():
    moves = build_legal_moves(
        _map_state(
            unit_is_selected=True,
            selected_unit="Lyn",
            movement_tiles=[[4, 3]],
            attack_opportunities=[
                {"target": "Batta", "move_to": [4, 3]},
            ],
        )
    )
    mid = parse_move_id_line("I will strike.\nMOVE: m0")
    chosen = resolve_move_id(mid, moves)
    assert chosen is not None
    assert chosen["id"] == "m0"
    seq = parse_command(chosen["command"])
    assert seq.commands, f"expected parsable COMMAND from {chosen['command']!r}"
    # First catalog entry for this state is move_attack
    assert seq.commands[0].type == "SELECT"
    assert seq.commands[0].unit == "Lyn"


def test_legal_moves_for_prompt_omits_full_command():
    moves = build_legal_moves(_map_state())
    prompt = legal_moves_for_prompt(moves)
    assert prompt
    assert set(prompt[0].keys()) == {"id", "kind", "summary"}


def test_resolve_attack_target_tile_from_opportunities():
    game_state = {
        "enemies": [{"name": "Batta", "x": 5, "y": 3, "id": 1}],
        "attack_opportunities": [
            {
                "target": "Batta",
                "move_to": [4, 3],
                "enemy_at": [5, 3],
            }
        ],
    }
    tile, source, enemy = resolve_attack_target_tile(game_state, "Batta", (4, 3))
    assert tile == (5, 3)
    assert source == "attack_opportunities"
    assert enemy is not None
    assert enemy["name"] == "Batta"


def test_resolve_attack_target_tile_adjacent_fallback():
    game_state = {
        "enemies": [{"name": "Batta", "x": 5, "y": 3, "id": 1}],
        "attack_opportunities": [],
    }
    tile, source, enemy = resolve_attack_target_tile(game_state, "Batta", (4, 3))
    assert tile == (5, 3)
    assert source == "adjacent_to_cursor"
    assert enemy["name"] == "Batta"


def test_build_legal_moves_start_screen_ui_only():
    """Title screen offers START/A/B only — never END_TURN / SELECT."""
    state = {
        "phase": "start_screen",
        "text_box_visible": False,
        "input_locked": False,
        "in_dialogue": False,
        "in_menu": False,
        "screen_context": "title",
        "party": [],
        "unit_status": {},
        "enemies": [],
        "movement_tiles": [],
        "attack_opportunities": [],
        "unit_is_selected": False,
        "selected_unit": None,
    }
    moves = build_legal_moves(state)
    assert moves, "expected START/A/B on start_screen"
    kinds = {m["kind"] for m in moves}
    cmds = {m["command"] for m in moves}
    assert kinds == {"ui_start", "ui_a", "ui_b"}
    assert cmds == {"START", "A", "B"}
    assert "end_turn" not in kinds
    assert not any("END_TURN" in m["command"] for m in moves)
    # START must parse as BUTTON so validator/executor accept it
    seq = parse_command("START")
    assert len(seq.commands) == 1
    assert seq.commands[0].type == "BUTTON"
    assert seq.commands[0].button == "START"



def test_build_legal_moves_hard_prefers_tutorial_target():
    """When tutorial_target is set and reachable, it becomes m0 and other waits are omitted."""
    state = _map_state(
        unit_is_selected=True,
        selected_unit="Lyn",
        cursor_on_player="Lyn",
        movement_tiles=[[4, 3], [5, 3], [9, 8], [3, 3]],
        attack_opportunities=[],
        tutorial_target=(9, 8),
        tutorial_step_index=0,
        tutorial_step="Move Lyn to (9,8) - advance toward enemy",
        tutorial_sequence=[
            {"coords": [(9, 8)], "step": "move", "description": "Move Lyn to (9,8)"},
        ],
    )
    moves = build_legal_moves(state)
    assert moves, "expected tutorial move"
    assert moves[0]["id"] == "m0"
    assert "TUTORIAL" in moves[0]["summary"]
    assert "to=[9,8]" in moves[0]["command"]
    # Hard-prefer: no flood of other move_wait destinations
    wait_moves = [m for m in moves if m["kind"] == "move_wait"]
    assert len(wait_moves) == 1
    assert wait_moves[0]["command"].endswith("MOVE to=[9,8] WAIT")
