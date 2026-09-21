from src.core.llmdriver import _auto_ui_advance_chord, _auto_ui_advance_streak
import src.core.llmdriver as driver


def setup_function():
    driver._auto_ui_advance_streak = 0


def test_start_screen_skips_llm_with_start_then_a():
    chord, reason = _auto_ui_advance_chord({"phase": "start_screen"})
    assert chord == "START;"
    assert "AUTO_START_SCREEN" in reason
    chord2, reason2 = _auto_ui_advance_chord({"phase": "start_screen"})
    assert chord2 == "A;"
    assert driver._auto_ui_advance_streak == 2


def test_player_phase_does_not_auto_advance():
    chord, reason = _auto_ui_advance_chord({"phase": "player_phase", "party": [{"name": "Lyn"}]})
    assert chord is None
    assert reason is None
    assert driver._auto_ui_advance_streak == 0


def test_locked_dialogue_auto_a():
    chord, reason = _auto_ui_advance_chord({
        "phase": "player_phase",
        "text_box_visible": True,
        "input_locked": True,
    })
    assert chord == "A;"
    assert reason == "AUTO_DIALOGUE_ADVANCE"


def test_start_screen_executor_inject():
    from src.game.command_executor import execute_command_sequence
    from src.game.command_parser import parse_command
    seq = parse_command('SELECT unit="Lyn"')
    buttons, desc = execute_command_sequence(seq.commands, {"phase": "start_screen"})
    assert "START" in buttons.upper()
    assert "START_SCREEN_ADVANCE" in desc
