from src.game.command_parser import parse_command, parse_command_from_llm_output
from src.game.command_validator import validate_command_sequence


def test_parse_semantic_command_sequence():
    seq = parse_command('SELECT unit="Lyn" MOVE to=[8,7] ATTACK target="Batta"')

    assert [cmd.type for cmd in seq.commands] == ["SELECT", "MOVE", "ATTACK"]
    assert seq.commands[0].unit == "Lyn"
    assert seq.commands[1].coord == (8, 7)
    assert seq.commands[2].target == "Batta"


def test_raw_button_sequence_is_rejected():
    seq = parse_command_from_llm_output("COMMAND: L;L;U;A;")

    assert seq is not None
    assert seq.commands == []


def test_single_button_command_is_allowed():
    seq = parse_command_from_llm_output("COMMAND: A")

    assert seq is not None
    assert len(seq.commands) == 1
    assert seq.commands[0].type == "BUTTON"
    assert seq.commands[0].button == "A"


def test_validator_rejects_already_acted_unit():
    seq = parse_command('SELECT unit="Lyn"')
    result = validate_command_sequence(
        seq.commands,
        {
            "phase": "player_phase",
            "cursor": (1, 1),
            "unit_status": {"Lyn": "already_acted"},
            "party": [{"name": "Lyn", "x": 1, "y": 1, "hasMoved": True}],
            "enemies": [],
        },
    )

    assert not result.valid
    assert "already acted" in " ".join(result.errors)


def test_validator_autocorrects_move_to_nearest_valid_tile():
    seq = parse_command("MOVE to=[10,10]")
    result = validate_command_sequence(
        seq.commands,
        {
            "phase": "player_phase",
            "cursor": (1, 1),
            "movement_tiles": [[2, 2], [3, 3]],
            "party": [],
            "enemies": [],
        },
    )

    assert result.valid
    assert result.commands[0].coord == (3, 3)
    assert any("Auto-corrected" in correction for correction in result.corrections)
