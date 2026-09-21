"""Unit tests for tutorial sequence step inference (no ROM required).

Covers the live-verified FE7 Ch0 sequence:
  start Lyn@(13,7) → (8,7) → WAIT → (8,6) attack → (5,4) → item → (4,2) attack → seize (3,2)
"""

from src.data.fe7_chapters import FE7_CHAPTERS
from src.game.tutorial_progress import (
    derive_tutorial_target,
    infer_active_tutorial_step,
    prefer_tutorial_tile,
)


CH0_SEQ = FE7_CHAPTERS[0]["tutorial_sequence"]


def _lyn(x, y, has_moved=False, hp=20):
    return [{"name": "Lyn", "x": x, "y": y, "hasMoved": has_moved, "hp": hp}]


def test_ch0_sequence_matches_verified_table():
    kinds = [s["step"] for s in CH0_SEQ]
    coords = [s["coords"][0] for s in CH0_SEQ]
    assert kinds == ["move", "wait", "attack", "move", "item", "attack", "seize"]
    assert coords == [(8, 7), (8, 7), (8, 6), (5, 4), (5, 4), (4, 2), (3, 2)]


def test_infer_start_wants_first_move_8_7():
    party = _lyn(13, 7)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 0
    assert info["target"] == (8, 7)
    assert info["kind"] == "move"
    assert derive_tutorial_target(CH0_SEQ, party) == (8, 7)


def test_infer_after_move_to_8_7_wants_wait():
    """On (8,7) without hasMoved → WAIT step (do not skip to attack)."""
    party = _lyn(8, 7, has_moved=False)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 1
    assert info["kind"] == "wait"
    assert info["target"] == (8, 7)


def test_infer_after_wait_wants_attack_8_6():
    party = _lyn(8, 7, has_moved=True)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 2
    assert info["kind"] == "attack"
    assert info["target"] == (8, 6)


def test_infer_post_enemy_phase_wait_done_via_brigand_adjacent():
    """After WAIT, hasMoved resets; brigand@(7,6) adjacent to (8,6) implies WAIT done."""
    party = _lyn(8, 7, has_moved=False)
    enemies = [{"name": "Brigand", "x": 7, "y": 6}]
    info = infer_active_tutorial_step(
        CH0_SEQ, party, acting_unit_name="Lyn", enemies=enemies
    )
    assert info["index"] == 2
    assert info["kind"] == "attack"
    assert info["target"] == (8, 6)


def test_infer_on_attack_tile_without_acting_still_attack():
    """Occupancy of approach tile alone must NOT skip the attack step."""
    party = _lyn(8, 6, has_moved=False)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 2
    assert info["kind"] == "attack"
    assert info["target"] == (8, 6)


def test_infer_after_brigand_kill_wants_move_5_4():
    party = _lyn(8, 6, has_moved=True)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 3
    assert info["kind"] == "move"
    assert info["target"] == (5, 4)


def test_infer_on_5_4_wants_item():
    party = _lyn(5, 4, has_moved=False, hp=6)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 4
    assert info["kind"] == "item"
    assert info["target"] == (5, 4)


def test_infer_after_item_wants_batta_attack_4_2():
    party = _lyn(5, 4, has_moved=True, hp=16)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 5
    assert info["kind"] == "attack"
    assert info["target"] == (4, 2)


def test_infer_on_4_2_without_acting_still_attack():
    party = _lyn(4, 2, has_moved=False)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 5
    assert info["kind"] == "attack"


def test_infer_after_batta_wants_seize_3_2():
    party = _lyn(4, 2, has_moved=True)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == 6
    assert info["kind"] == "seize"
    assert info["target"] == (3, 2)


def test_infer_seize_complete_when_acted_on_gate():
    party = _lyn(3, 2, has_moved=True)
    info = infer_active_tutorial_step(CH0_SEQ, party, acting_unit_name="Lyn")
    assert info["index"] == -1
    assert info["target"] is None


def test_ch1_through_10_are_unverified_empty():
    for ch in range(1, 11):
        data = FE7_CHAPTERS[ch]
        assert data.get("needs_verification", True) is True or data.get("verified") is not True
        assert data.get("tutorial_sequence") == []


def test_prefer_tutorial_tile_hard_prefers_primary():
    dest = prefer_tutorial_tile(
        (8, 7),
        movement_tiles=[[8, 7], [9, 8], [7, 7]],
        step_coords=[(8, 7)],
    )
    assert dest == (8, 7)


def test_prefer_tutorial_tile_picks_reachable_alt():
    dest = prefer_tutorial_tile(
        (8, 7),
        movement_tiles=[[7, 5], [6, 6]],
        step_coords=[(8, 7), (7, 5)],
    )
    assert dest == (7, 5)
