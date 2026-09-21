"""Unit tests for tutorial sequence step inference (no ROM required)."""

from src.game.tutorial_progress import (
    derive_tutorial_target,
    infer_active_tutorial_step,
    prefer_tutorial_tile,
)


CH0_SEQ = [
    {"coords": [(5, 4)], "step": "move", "description": "Move Lyn to (5,4)"},
    {
        "coords": [(2, 2), (4, 2), (3, 3)],
        "step": "attack",
        "description": "Attack Batta",
    },
    {"coords": [(3, 2)], "step": "seize", "description": "Seize gate"},
]


def test_infer_lyn_at_7_7_targets_forced_move():
    party = [{"name": "Lyn", "x": 7, "y": 7, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 0
    assert info["target"] == (5, 4)
    assert info["kind"] == "move"
    assert derive_tutorial_target(CH0_SEQ, party) == (5, 4)


def test_infer_skips_completed_move_when_lyn_on_tile():
    party = [{"name": "Lyn", "x": 5, "y": 4, "hasMoved": False}]
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 1
    assert info["target"] == (2, 2)
    assert info["kind"] == "attack"


def test_attack_occupancy_without_hasMoved_does_not_skip():
    seq = [
        {
            "coords": [(7, 5), (6, 6), (8, 6), (7, 7)],
            "step": "attack",
            "description": "Attack range",
        },
        {"coords": [(5, 4)], "step": "move", "description": "Next move"},
    ]
    party = [{"name": "Lyn", "x": 7, "y": 7, "hasMoved": False}]
    info = infer_active_tutorial_step(seq, party)
    assert info["index"] == 0
    assert info["kind"] == "attack"
    assert info["target"] == (7, 5)


def test_attack_skips_when_hasMoved_on_approach_tile():
    seq = [
        {"coords": [(7, 5), (7, 7)], "step": "attack", "description": "Attack range"},
        {"coords": [(5, 4)], "step": "move", "description": "Next move"},
    ]
    party = [{"name": "Lyn", "x": 7, "y": 7, "hasMoved": True}]
    info = infer_active_tutorial_step(seq, party)
    assert info["index"] == 1
    assert info["target"] == (5, 4)


def test_prefer_tutorial_tile_picks_reachable_alt():
    dest = prefer_tutorial_tile(
        (5, 4),
        movement_tiles=[[7, 5], [6, 6]],
        step_coords=[(5, 4), (7, 5)],
    )
    assert dest == (7, 5)
