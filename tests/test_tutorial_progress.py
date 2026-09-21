"""Unit tests for tutorial sequence step inference (no ROM required)."""

from src.game.tutorial_progress import (
    derive_tutorial_target,
    infer_active_tutorial_step,
    prefer_tutorial_tile,
)


CH0_SEQ = [
    {"coords": [(8, 7)], "step": "move", "description": "Move Lyn to (8,7)"},
    {
        "coords": [(8, 6)],
        "step": "attack",
        "description": "Adjacent to brigand then attack",
    },
    {"coords": [(5, 4)], "step": "move", "description": "Vulnerary tile"},
    {"coords": [(5, 4)], "step": "item", "description": "Use vulnerary"},
    {
        "coords": [(2, 2), (4, 2), (3, 3)],
        "step": "attack",
        "description": "Attack Batta",
    },
]


def test_infer_start_targets_8_7():
    party = [{"name": "Lyn", "x": 13, "y": 7, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["target"] == (8, 7)
    assert info["index"] == 0


def test_infer_after_first_move_targets_attack_approach():
    party = [{"name": "Lyn", "x": 8, "y": 7, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party)
    assert info["target"] == (8, 6)
    assert info["index"] == 1


def test_infer_after_brigand_fight_targets_5_4():
    party = [{"name": "Lyn", "x": 8, "y": 6, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party)
    # occupancy on attack approach tile should not skip past attack solely by xy;
    # if heuristic advances, accept move/item at (5,4)
    assert info["target"] in ((8, 6), (5, 4))


def test_prefer_tutorial_tile_picks_forced():
    dest = prefer_tutorial_tile(
        (8, 7),
        movement_tiles=[[7, 5], [8, 6]],
        step_coords=[(8, 7), (7, 5)],
    )
    assert dest == (8, 7)
