
"""Blue movement overlay detection (cyan-on-grass)."""
from pathlib import Path

def test_detect_blue_on_live_fixture():
    from src.utils.screenshot_analyzer import detect_movement_tiles
    # Optional live fixture copied during babysitting; skip if absent.
    shot = Path(__file__).resolve().parents[1] / "tmp-latest.png"
    if not shot.exists():
        return
    r = detect_movement_tiles([str(shot)], blue_threshold=20)
    assert len(r["blue_tiles"]) >= 15, r["blue_tiles"]
