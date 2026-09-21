from src.game.command_parser import parse_command, parse_command_from_llm_output, parse_move_id_line
from src.game.command_validator import validate_command_sequence
from src.game.legal_moves import build_legal_moves, resolve_move_id


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



def test_parse_move_id_and_resolve_to_command():
    """MOVE: mN from model output maps through legal_moves to a semantic COMMAND."""
    state = {
        "text_box_visible": False,
        "input_locked": False,
        "in_dialogue": False,
        "in_menu": False,
        "party": [{"name": "Lyn", "x": 1, "y": 1, "hasMoved": False}],
        "unit_status": {"Lyn": "available"},
        "enemies": [],
        "movement_tiles": [],
        "attack_opportunities": [],
        "unit_is_selected": False,
    }
    moves = build_legal_moves(state)
    assert moves and moves[0]["id"] == "m0"
    move_id = parse_move_id_line("Picking Lyn.\nMOVE: m0")
    assert move_id == "m0"
    chosen = resolve_move_id(move_id, moves)
    assert chosen is not None
    seq = parse_command(chosen["command"])
    assert seq.commands
    assert seq.commands[0].type in {"SELECT", "END_TURN", "BUTTON"}


def test_validator_allows_ui_on_start_screen():
    seq = parse_command("START")
    result = validate_command_sequence(
        seq.commands,
        {"phase": "start_screen", "cursor": (0, 0), "party": [], "enemies": []},
    )
    assert result.valid, result.errors
    assert not any("Cannot execute" in e for e in result.errors)


def test_validator_rejects_end_turn_on_start_screen():
    seq = parse_command("END_TURN")
    result = validate_command_sequence(
        seq.commands,
        {"phase": "start_screen", "cursor": (0, 0), "party": [], "enemies": []},
    )
    assert not result.valid
    assert any("END_TURN" in e and "start_screen" in e for e in result.errors)


def test_select_prefers_map_path_when_nearby():
    from src.game.command_executor import execute_command_sequence
    from src.game.command_parser import parse_command
    seq = parse_command('SELECT unit="Lyn"')
    buttons, desc = execute_command_sequence(
        seq.commands,
        {
            "phase": "player_phase",
            "cursor": (7, 9),
            "cursor_on_player": None,
            "party": [{"name": "Lyn", "x": 7, "y": 7, "hasMoved": False}],
            "enemies": [],
            "movement_tiles": [],
        },
    )
    assert "map path" in desc.lower()
    assert "UP" in buttons.upper()
    assert buttons.upper().endswith("A;") or buttons.upper().endswith("A")


def test_select_paths_from_playst_when_display_lies():
    """PlaySt at (7,9) while display/cursor_on claim Lyn at (7,7)."""
    from src.game.command_executor import execute_command_sequence
    from src.game.command_parser import parse_command
    seq = parse_command('SELECT unit="Lyn" MOVE to=[7,2] WAIT')
    buttons, desc = execute_command_sequence(
        seq.commands,
        {
            "phase": "player_phase",
            "cursor": (7, 7),
            "cursor_memory": (7, 9),
            "display_cursor": (7, 7),
            "cursor_on_player": "Lyn",
            "party": [{"name": "Lyn", "x": 7, "y": 7, "hasMoved": False}],
            "enemies": [],
            "movement_tiles": [[7, 7], [7, 6], [7, 5], [7, 4], [7, 3], [7, 2]],
        },
    )
    assert "map path" in desc.lower()
    # UP UP to Lyn, A select, then UP*5 to (7,2), A confirm
    assert buttons.upper().startswith("UP;UP;A;")
    assert "UP;UP;UP;UP;UP;A;" in buttons.upper()
