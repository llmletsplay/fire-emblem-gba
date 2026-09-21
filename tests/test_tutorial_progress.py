"""Unit tests for tutorial sequence step inference (no ROM required)."""

from src.game.tutorial_progress import (
    derive_tutorial_target,
    infer_active_tutorial_step,
    prefer_tutorial_tile,
)


CH0_SEQ = [
    {"coords": [(9, 8)], "step": "move", "description": "Move Lyn to (9,8)"},
    {
        "coords": [(7, 5), (6, 6), (8, 6), (7, 7)],
        "step": "attack",
        "description": "Attack range around brigand",
    },
    {"coords": [(5, 4)], "step": "move", "description": "Move closer for vulnerary"},
]


def test_infer_first_step_when_lyn_at_start():
    party = [{"name": "Lyn", "x": 13, "y": 7, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 0
    assert info["target"] == (9, 8)
    assert info["kind"] == "move"
    assert derive_tutorial_target(CH0_SEQ, party) == (9, 8)


def test_infer_skips_completed_move_when_lyn_on_tile():
    party = [{"name": "Lyn", "x": 9, "y": 8, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 1
    assert info["target"] == (7, 5)
    assert info["kind"] == "attack"


def test_infer_lyn_at_7_7_still_needs_first_move():
    """(7,7) is an attack-step tile, but step0 move to (9,8) is unmet first."""
    party = [{"name": "Lyn", "x": 7, "y": 7, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party)
    assert info["index"] == 0
    assert info["target"] == (9, 8)


def test_prefer_tutorial_tile_picks_reachable_alt():
    dest = prefer_tutorial_tile(
        (9, 8),
        movement_tiles=[[7, 5], [6, 6]],
        step_coords=[(9, 8), (7, 5)],
    )
    assert dest == (7, 5)
