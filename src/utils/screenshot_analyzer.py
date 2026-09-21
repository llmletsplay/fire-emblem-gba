"""
Screenshot analysis utilities for detecting black screens, transitions, and scene changes.
"""

from PIL import Image, ImageStat
import logging
from typing import List, Tuple, Dict, Any, Optional

log = logging.getLogger(__name__)

def is_black_screen(image_path: str, threshold: int = 30) -> bool:
    """
    Check if a screenshot is mostly black (transition/loading screen).

    Args:
        image_path: Path to the image file
        threshold: Maximum average brightness to consider "black" (0-255)

    Returns:
        True if the image is mostly black
    """
    try:
        img = Image.open(image_path).convert('L')  # Convert to grayscale
        # Use PIL's ImageStat instead of numpy
        stat = ImageStat.Stat(img)
        avg_brightness = stat.mean[0]  # Get mean brightness

        is_black = avg_brightness < threshold
        if is_black:
            log.debug(f"Black screen detected: {image_path} (avg brightness: {avg_brightness:.1f})")

        return is_black
    except Exception as e:
        log.error(f"Error analyzing image {image_path}: {e}")
        return False

def compare_screenshots(img_paths: List[str]) -> Dict[str, Any]:
    """
    Compare multiple screenshots to detect transitions and choose the best one.

    Args:
        img_paths: List of paths to screenshot files

    Returns:
        Dictionary with analysis results
    """
    results = {
        "black_screens": [],
        "best_index": 0,
        "is_transitioning": False,
        "similarity_scores": []
    }

    if not img_paths:
        return results

    # Check each screenshot for black screens
    for i, path in enumerate(img_paths):
        if is_black_screen(path):
            results["black_screens"].append(i)

    # If all are black, we're probably in a transition
    if len(results["black_screens"]) == len(img_paths):
        results["is_transitioning"] = True
        log.info("All screenshots are black - likely in transition")
        return results

    # Calculate similarity between consecutive screenshots
    if len(img_paths) > 1:
        for i in range(len(img_paths) - 1):
            if i not in results["black_screens"] and (i+1) not in results["black_screens"]:
                similarity = calculate_similarity(img_paths[i], img_paths[i+1])
                results["similarity_scores"].append(similarity)
            else:
                results["similarity_scores"].append(0)

    # Choose the best screenshot (prefer non-black, middle screenshot)
    non_black_indices = [i for i in range(len(img_paths)) if i not in results["black_screens"]]

    if non_black_indices:
        # Prefer middle screenshot if it's not black
        middle = len(img_paths) // 2
        if middle in non_black_indices:
            results["best_index"] = middle
        else:
            # Otherwise take the first non-black screenshot
            results["best_index"] = non_black_indices[0]

    # Detect if we're transitioning (high difference between screenshots)
    if results["similarity_scores"]:
        avg_similarity = sum(results["similarity_scores"]) / len(results["similarity_scores"])
        if avg_similarity < 0.7:  # Less than 70% similar suggests transition
            results["is_transitioning"] = True
            log.info(f"Scene transition detected (avg similarity: {avg_similarity:.2f})")

    return results

def calculate_similarity(img_path1: str, img_path2: str) -> float:
    """
    Calculate similarity between two images (0-1, where 1 is identical).

    Uses a simple pixel comparison for speed.
    """
    try:
        img1 = Image.open(img_path1).convert('RGB')
        img2 = Image.open(img_path2).convert('RGB')

        # Resize to small size for faster comparison
        size = (64, 64)
        img1 = img1.resize(size)
        img2 = img2.resize(size)

        # Get pixel data
        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())

        # Calculate difference
        total_diff = 0
        for p1, p2 in zip(pixels1, pixels2):
            # Calculate RGB difference
            diff = sum(abs(a - b) for a, b in zip(p1, p2))
            total_diff += diff

        # Normalize (max diff per pixel is 255*3 = 765)
        max_diff = len(pixels1) * 765
        similarity = 1.0 - (total_diff / max_diff)

        return similarity

    except Exception as e:
        log.error(f"Error comparing images: {e}")
        return 0.0

def detect_text_box(img_path: str, bottom_rows_px: int = 48,
                    dark_threshold: float = 80.0, contrast_threshold: float = 25.0,
                    top_min_brightness: float = 40.0) -> bool:
    """
    Detect FE GBA text box at bottom of screenshot.

    Text boxes in Fire Emblem GBA games have a dark background with bright text
    at the bottom ~48px of the 160px screen. Three conditions must ALL be true:
    1. Bottom region avg brightness < dark_threshold (dark background)
    2. Bottom region stddev > contrast_threshold (text creates variance)
    3. Top region avg brightness > top_min_brightness (not a full black screen)

    Args:
        img_path: Path to screenshot image file
        bottom_rows_px: Height of bottom region to check (default 48px = ~30% of 160px)
        dark_threshold: Max avg brightness for bottom region to be "dark"
        contrast_threshold: Min stddev for bottom region to have "text contrast"
        top_min_brightness: Min avg brightness for top region (filters full-black screens)

    Returns:
        True if a text box is detected at the bottom of the screen
    """
    try:
        img = Image.open(img_path).convert('L')  # Grayscale
        width, height = img.size

        if height < bottom_rows_px + 10:
            return False

        # Split into bottom (text box area) and top (game area)
        bottom = img.crop((0, height - bottom_rows_px, width, height))
        top = img.crop((0, 0, width, height - bottom_rows_px))

        bottom_stat = ImageStat.Stat(bottom)
        top_stat = ImageStat.Stat(top)

        bottom_mean = bottom_stat.mean[0]
        bottom_stddev = bottom_stat.stddev[0]
        top_mean = top_stat.mean[0]

        is_dark_bottom = bottom_mean < dark_threshold
        has_text_contrast = bottom_stddev > contrast_threshold
        is_not_black_screen = top_mean > top_min_brightness

        detected = is_dark_bottom and has_text_contrast and is_not_black_screen

        if detected:
            log.info(f"Text box detected: bottom_mean={bottom_mean:.1f}, "
                     f"bottom_stddev={bottom_stddev:.1f}, top_mean={top_mean:.1f}")
        else:
            log.debug(f"No text box: bottom_mean={bottom_mean:.1f}, "
                      f"bottom_stddev={bottom_stddev:.1f}, top_mean={top_mean:.1f}")

        return detected

    except Exception as e:
        log.warning(f"Text box detection failed for {img_path}: {e}")
        return False


def _cluster_tiles(tile_set):
    """Group tiles into connected components using 8-connectivity (Chebyshev distance <= 1)."""
    remaining = set(tile_set)
    clusters = []
    while remaining:
        seed = remaining.pop()
        cluster = {seed}
        queue = [seed]
        while queue:
            cx, cy = queue.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nb = (cx + dx, cy + dy)
                    if nb in remaining:
                        remaining.discard(nb)
                        cluster.add(nb)
                        queue.append(nb)
        clusters.append(cluster)
    return clusters


def detect_flash_regions(
    img_paths: List[str],
    grid_size: int = 16,
    diff_threshold: int = 40,
    min_tile_ratio: float = 0.15,
    exclude_bottom_fraction: float = 0.15,
    exclude_top_rows: int = 2,
) -> List[Dict[str, Any]]:
    """
    Compare multiple screenshots to find tiles that are flashing/animating.

    Compares each pair of frames pixel-by-pixel, partitions the screen into
    a grid of tiles, and flags tiles where a significant fraction of pixels
    changed between frames.  A tile must be flagged in at least 2 of 3
    frame-pair comparisons to be included (consensus filter).

    Args:
        img_paths: List of screenshot file paths (ideally 3).
        grid_size: Tile size in pixels (GBA tiles are 16x16).
        diff_threshold: Per-channel pixel diff to count as "changed".
        min_tile_ratio: Fraction of a tile's pixels that must change.
        exclude_bottom_fraction: Bottom portion of screen to skip (dialogue box area).

    Returns:
        List of dicts with keys: screen_tile, type, confidence.
        Capped at 5 results, sorted by confidence descending.
    """
    if len(img_paths) < 2:
        return []

    try:
        images = [Image.open(p).convert("RGB") for p in img_paths]
    except Exception as e:
        log.warning(f"Flash detection: failed to open images: {e}")
        return []

    width, height = images[0].size
    cols = width // grid_size
    rows = height // grid_size
    exclude_row = int(rows * (1.0 - exclude_bottom_fraction))

    # Build pixel data lists once
    pixel_data = [list(img.getdata()) for img in images]

    # For each frame pair, compute which tiles are flagged
    pair_indices = []
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            pair_indices.append((i, j))

    # tile_votes[row][col] = number of frame pairs where tile was flagged
    tile_votes: Dict[Tuple[int, int], int] = {}
    tile_max_ratio: Dict[Tuple[int, int], float] = {}

    for pi, pj in pair_indices:
        pix_a = pixel_data[pi]
        pix_b = pixel_data[pj]

        for tr in range(exclude_top_rows, exclude_row):
            for tc in range(cols):
                changed = 0
                total = 0
                for py in range(tr * grid_size, (tr + 1) * grid_size):
                    for px in range(tc * grid_size, (tc + 1) * grid_size):
                        idx = py * width + px
                        r1, g1, b1 = pix_a[idx]
                        r2, g2, b2 = pix_b[idx]
                        max_diff = max(abs(r1 - r2), abs(g1 - g2), abs(b1 - b2))
                        if max_diff >= diff_threshold:
                            changed += 1
                        total += 1
                ratio = changed / total if total > 0 else 0.0
                if ratio >= min_tile_ratio:
                    key = (tc, tr)
                    tile_votes[key] = tile_votes.get(key, 0) + 1
                    tile_max_ratio[key] = max(tile_max_ratio.get(key, 0.0), ratio)

    # Consensus: require flagged in 2+ frame pairs
    min_votes = 2 if len(pair_indices) >= 3 else 1
    consensus = [
        (tile, tile_max_ratio[tile])
        for tile, votes in tile_votes.items()
        if votes >= min_votes
    ]

    if not consensus:
        return []

    # Sort by confidence (max change ratio) descending
    consensus.sort(key=lambda x: x[1], reverse=True)

    # Classify per-cluster: isolated small groups = cursor_indicator, large = highlight_area
    tile_set = set(tile for tile, _ in consensus)
    clusters = _cluster_tiles(tile_set)
    tile_cluster_size = {}
    for cluster in clusters:
        for tile in cluster:
            tile_cluster_size[tile] = len(cluster)

    results = []
    for tile, confidence in consensus[:5]:
        csize = tile_cluster_size.get(tile, 1)
        # Prefer isolated single tiles (size 1) as cursor indicators
        # Tiles > 3 are likely HUD noise or large animations
        type_name = "cursor_indicator" if csize <= 2 else "highlight_area"
        results.append({
            "screen_tile": list(tile),
            "type": type_name,
            "confidence": round(confidence, 2),
            "cluster_size": csize,
        })

    return results


def detect_movement_tiles(
    img_paths: List[str],
    grid_size: int = 16,
    blue_threshold: int = 30,
    red_threshold: int = 30,
    exclude_top_rows: int = 2,
    exclude_bottom_fraction: float = 0.25,
) -> Dict[str, Any]:
    """
    Detect blue (movement) and red (attack) tile overlays on the tactical map.

    In Fire Emblem GBA, when a unit is selected:
    - Blue tiles show valid movement destinations
    - Red tiles show attack-only range (can attack from afar, cannot stop here)

    The overlays pulse on/off across frames. This function analyzes each
    screenshot independently and takes the union of detections. Tiles that
    appear blue/red in ALL frames are excluded (likely terrain like water).

    Detection per tile: avg blue - max(avg red, avg green) > blue_threshold
    (analogous for red).

    Args:
        img_paths: List of screenshot file paths (ideally 3-4 from the same cycle).
        grid_size: Tile size in pixels (GBA tiles are 16x16).
        blue_threshold: Min blue channel dominance to flag as movement tile.
        red_threshold: Min red channel dominance to flag as attack tile.
        exclude_top_rows: Skip top N tile rows (HUD area).
        exclude_bottom_fraction: Bottom portion of screen to skip (dialogue box).

    Returns:
        Dict with "blue_tiles" and "red_tiles" as lists of (col, row) screen
        tile positions. Empty lists if nothing detected.
    """
    if not img_paths:
        return {"blue_tiles": [], "red_tiles": []}

    tile_blue_frames: Dict[Tuple[int, int], int] = {}
    tile_red_frames: Dict[Tuple[int, int], int] = {}
    n_frames = 0

    for img_path in img_paths:
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            continue

        n_frames += 1
        width, height = img.size
        cols = width // grid_size
        rows = height // grid_size
        exclude_row = int(rows * (1.0 - exclude_bottom_fraction))

        pixels = list(img.getdata())

        for tr in range(exclude_top_rows, exclude_row):
            for tc in range(cols):
                r_sum = g_sum = b_sum = 0
                for py in range(tr * grid_size, (tr + 1) * grid_size):
                    base = py * width + tc * grid_size
                    for px in range(grid_size):
                        r, g, b = pixels[base + px]
                        r_sum += r
                        g_sum += g
                        b_sum += b

                count = grid_size * grid_size
                avg_r = r_sum / count
                avg_g = g_sum / count
                avg_b = b_sum / count

                key = (tc, tr)
                # Pure blue (old metric) OR translucent cyan overlay on grass.
                # FE GBA movement tint is cyan blended over green terrain, so
                # avg_b - max(r,g) stays ~5–20 and misses the diamond entirely.
                pure_blue = avg_b - max(avg_r, avg_g) > blue_threshold
                cyan_overlay = (
                    avg_b - avg_r > 35
                    and avg_b > 150
                    and avg_g > 120
                )
                if pure_blue or cyan_overlay:
                    tile_blue_frames[key] = tile_blue_frames.get(key, 0) + 1
                elif avg_r - max(avg_g, avg_b) > red_threshold:
                    tile_red_frames[key] = tile_red_frames.get(key, 0) + 1

    if n_frames == 0:
        return {"blue_tiles": [], "red_tiles": []}

    # Filter: include tiles detected in at least 1 frame.
    # Exclude tiles detected in ALL frames (likely constant terrain like water).
    blue_tiles = []
    for key, cnt in tile_blue_frames.items():
        if n_frames >= 3 and cnt == n_frames:
            continue  # consistently blue across every frame → terrain, skip
        blue_tiles.append(key)

    red_tiles = []
    for key, cnt in tile_red_frames.items():
        if n_frames >= 3 and cnt == n_frames:
            continue
        red_tiles.append(key)

    # Remove any tile that appears in both sets (noise)
    blue_set = set(blue_tiles)
    red_set = set(red_tiles)
    overlap = blue_set & red_set
    blue_set -= overlap
    red_set -= overlap

    if blue_set or red_set:
        log.info(f"Movement tiles detected: {len(blue_set)} blue, {len(red_set)} red")

    return {
        "blue_tiles": sorted(blue_set),
        "red_tiles": sorted(red_set),
    }


def screen_tile_to_map_estimate(
    screen_x: int,
    screen_y: int,
    cursor_map_x: int,
    cursor_map_y: int,
    camera_x: int = None,
    camera_y: int = None,
) -> Tuple[int, int]:
    """
    Estimate map coordinates from screen tile position.

    If BmSt camera pixel coordinates are available, uses them for accurate
    conversion: map_tile = screen_tile + camera_pixels / 16.

    Otherwise, falls back to assuming the cursor is at screen center
    (tile 7,5 on a 15x10 tile screen).

    Returns:
        (map_x, map_y) estimated map coordinates.
    """
    if camera_x is not None and camera_y is not None:
        # Accurate: camera tells us the pixel offset of the viewport
        map_x = screen_x + camera_x // 16
        map_y = screen_y + camera_y // 16
    else:
        # Fallback: assume cursor is at screen center (tile 7, 5)
        map_x = cursor_map_x + (screen_x - 7)
        map_y = cursor_map_y + (screen_y - 5)
    return (map_x, map_y)


def get_screenshot_description(img_path: str) -> str:
    """
    Get a basic description of what's visible in the screenshot.
    This is a simplified version that doesn't rely on AI.
    """
    try:
        img = Image.open(img_path).convert('RGB')
        width, height = img.size

        # Use ImageStat for statistics
        stat = ImageStat.Stat(img)
        avg_color = stat.mean  # Returns [R, G, B] averages
        brightness = sum(avg_color) / 3

        # Check for dominant colors
        is_dark = brightness < 50
        is_bright = brightness > 200
        has_red_overlay = avg_color[0] > avg_color[1] + 20  # Red grid lines

        description = []

        if is_dark:
            description.append("Dark/black screen")
        elif is_bright:
            description.append("Bright screen")

        if has_red_overlay:
            description.append("Red overlay visible (possibly grid)")

        # Check bottom quarter for text (simplified check)
        bottom_region = img.crop((0, height * 3 // 4, width, height))
        bottom_stat = ImageStat.Stat(bottom_region)

        # High variance in bottom region might indicate text
        if bottom_stat.stddev[0] > 50:  # Check standard deviation
            description.append("Possible text at bottom")

        return ", ".join(description) if description else "Normal game screen"

    except Exception as e:
        log.error(f"Error describing screenshot: {e}")
        return "Unable to analyze"


def detect_tutorial_target(
    img_paths: List[str],
    grid_size: int = 16,
    exclude_top_rows: int = 2,
    exclude_bottom_fraction: float = 0.25,
) -> Tuple[Optional[Tuple[int, int]], Dict[str, Any]]:
    """
    Detect tutorial/objective target cursor on the tactical map.

    In FE7 tutorials, the game shows a blinking cursor with 4 corner borders at the target tile.
    This function detects such targets using:
    1. Color-based detection: looks for yellow/orange/green (tutorial cursor colors)
    2. Multi-frame consistency: tutorial target appears in SAME position across ALL frames
    3. Isolation filter: targets are typically single isolated tiles

    Args:
        img_paths: List of screenshot file paths (4+ frames recommended).
        grid_size: Tile size in pixels (GBA tiles are 16x16).
        exclude_top_rows: Skip top N tile rows (HUD area).
        exclude_bottom_fraction: Bottom portion of screen to skip (dialogue box).

    Returns:
        Tuple of (target_map_coords, detection_info) where:
        - target_map_coords: (x, y) map tile coordinates if detected, else None
        - detection_info: dict with detection details for debugging
    """
    result = {
        "detected": False,
        "screen_tile": None,
        "method": None,
        "confidence": 0.0,
        "detection_type": None,
    }

    if len(img_paths) < 2:
        return None, result

    try:
        images = [Image.open(p).convert("RGB") for p in img_paths]
    except Exception as e:
        log.warning(f"Tutorial target detection: failed to open images: {e}")
        return None, result

    width, height = images[0].size
    cols = width // grid_size
    rows = height // grid_size
    exclude_row = int(rows * (1.0 - exclude_bottom_fraction))

    # === Expanded color detection ===
    # Tutorial cursors are typically yellow/orange/amber with high brightness
    # FE7 tutorial cursor "shines white" - pulses white every second
    # Also add lighter yellows and near-whites that might appear on light backgrounds
    tutorial_colors = [
        # Standard colors
        ((0, 200, 0), (60, 255, 60)),      # Green
        ((180, 180, 0), (255, 255, 80)),   # Yellow (bright)
        ((200, 100, 0), (255, 200, 50)),   # Orange
        ((0, 200, 200), (60, 255, 255)),   # Cyan
        # Extended yellows (for FE7 tutorial cursor)
        ((200, 150, 0), (255, 220, 50)),   # Golden yellow
        ((220, 180, 20), (255, 255, 100)), # Light yellow
        ((180, 140, 0), (255, 200, 80)),  # Amber
        # White-ish (for bright cursors on light terrain)
        ((200, 200, 150), (255, 255, 200)), # Off-white/yellow
        # WHITE - FE7 tutorial cursor "shines white" every second
        ((180, 180, 180), (255, 255, 255)), # White (bright)
        ((200, 200, 200), (255, 255, 255)), # Pure white
        # Light gray with slight color tint
        ((160, 160, 140), (255, 255, 180)), # Warm white
    ]

    # === Multi-frame position tracking ===
    # Track which tiles have tutorial colors in each frame
    # Tutorial target PULSES (shines white every second) - appears in MOST frames but NOT all
    # We need to detect tiles that appear in 2+ frames (not necessarily all)
    tile_frames_present: Dict[Tuple[int, int], int] = {}  # tile -> count of frames with color

    for img_idx, img in enumerate(images):
        pixels = list(img.getdata())

        for tr in range(exclude_top_rows, exclude_row):
            for tc in range(cols):
                # Sample from EDGES and CORNERS of the tile (not center)
                # The "4 corner borders" effect is at the corners!
                sample_brightness = []
                
                # Sample corners (4 corners)
                corner_offsets = [
                    (0, 0),  # top-left
                    (grid_size - 1, 0),  # top-right
                    (0, grid_size - 1),  # bottom-left
                    (grid_size - 1, grid_size - 1),  # bottom-right
                ]
                
                for dy, dx in corner_offsets:
                    py = tr * grid_size + dy
                    px = tc * grid_size + dx
                    if 0 <= py < height and 0 <= px < width:
                        idx = py * width + px
                        r, g, b = pixels[idx]
                        brightness = (r + g + b) / 3
                        sample_brightness.append(brightness)
                
                # Also sample edges
                mid = grid_size // 2
                edge_offsets = [
                    (mid, 0),  # top-middle
                    (mid, grid_size - 1),  # bottom-middle
                    (0, mid),  # left-middle
                    (grid_size - 1, mid),  # right-middle
                ]
                
                for dy, dx in edge_offsets:
                    py = tr * grid_size + dy
                    px = tc * grid_size + dx
                    if 0 <= py < height and 0 <= px < width:
                        idx = py * width + px
                        r, g, b = pixels[idx]
                        brightness = (r + g + b) / 3
                        sample_brightness.append(brightness)
                
                avg_brightness = sum(sample_brightness) / len(sample_brightness) if sample_brightness else 0

                # Check if any bright pixel (white/pulsing) at edges/corners
                # White = high brightness (180+) with low color tint
                if avg_brightness > 180:
                    # Check if it's white-ish (roughly equal RGB)
                    center_idx = tr * grid_size + mid, tc * grid_size + mid
                    if 0 <= center_idx[0] < height and 0 <= center_idx[1] < width:
                        idx = center_idx[0] * width + center_idx[1]
                        r, g, b = pixels[idx]
                        # White = roughly equal and high
                        if abs(r - g) < 30 and abs(r - b) < 30 and r > 180:
                            tile = (tc, tr)
                            tile_frames_present[tile] = tile_frames_present.get(tile, 0) + 1
                            continue

                # Also check for yellow/orange at corners (not just white)
                r_sum = g_sum = b_sum = 0
                sample_count = 0
                for dy, dx in corner_offsets:
                    py = tr * grid_size + dy
                    px = tc * grid_size + dx
                    if 0 <= py < height and 0 <= px < width:
                        idx = py * width + px
                        r, g, b = pixels[idx]
                        r_sum += r
                        g_sum += g
                        b_sum += b
                        sample_count += 1

                if sample_count == 0:
                    continue

                avg_r = r_sum / sample_count
                avg_g = g_sum / sample_count
                avg_b = b_sum / sample_count

                # Check if this tile matches any tutorial color
                for (min_rgb, max_rgb) in tutorial_colors:
                    if (min_rgb[0] <= avg_r <= max_rgb[0] and
                        min_rgb[1] <= avg_g <= max_rgb[1] and
                        min_rgb[2] <= avg_b <= max_rgb[2]):
                        tile = (tc, tr)
                        tile_frames_present[tile] = tile_frames_present.get(tile, 0) + 1
                        break

    # === Key filter: Must appear in MOST frames (but not all - it pulses!) ===
    # Tutorial target pulses every second - appears in ~50% of frames
    # So we look for tiles present in 2+ frames out of 6
    n_frames = len(images)
    min_frames = max(2, n_frames // 3)  # At least 2 frames, or ~33% of frames
    max_frames = n_frames - 1  # But NOT all (since it pulses)
    
    # Get all candidates that appear in the right number of frames
    all_candidates = [
        tile for tile, frame_count in tile_frames_present.items()
        if min_frames <= frame_count <= max_frames
    ]

    # === Secondary: Also check for high-brightness pixels (edge detection) ===
    # Tutorial cursor has 4 corner borders - check for high contrast at tile corners
    edge_candidates: Dict[Tuple[int, int], float] = {}

    for img in images:
        pixels = list(img.getdata())

        for tr in range(exclude_top_rows, exclude_row):
            for tc in range(cols):
                # Check corners for bright pixels (border effect)
                corner_brightness = []
                corners = [
                    (tr * grid_size, tc * grid_size),  # top-left
                    (tr * grid_size, tc * grid_size + grid_size - 1),  # top-right
                    (tr * grid_size + grid_size - 1, tc * grid_size),  # bottom-left
                    (tr * grid_size + grid_size - 1, tc * grid_size + grid_size - 1),  # bottom-right
                ]
                for cy, cx in corners:
                    if 0 <= cy < height and 0 <= cx < width:
                        idx = cy * width + cx
                        r, g, b = pixels[idx]
                        brightness = (r + g + b) / 3
                        corner_brightness.append(brightness)

                if corner_brightness:
                    avg_corner = sum(corner_brightness) / len(corner_brightness)
                    if avg_corner > 180:  # Very bright corner
                        tile = (tc, tr)
                        edge_candidates[tile] = max(edge_candidates.get(tile, 0), avg_corner)

    # === Combine and score ===
    final_candidates: Dict[Tuple[int, int], float] = {}

    # Add pulsing color candidates (high confidence - appeared in ~50% of frames)
    for tile in all_candidates:
        final_candidates[tile] = final_candidates.get(tile, 0) + 3.0

    # Add edge candidates
    for tile, brightness in edge_candidates.items():
        if tile in final_candidates:
            final_candidates[tile] += 1.0  # Bonus for having bright corners too

    # Find best candidate
    best_tile = None
    best_score = 0

    for tile, score in final_candidates.items():
        if score > best_score:
            best_score = score
            best_tile = tile

    if best_tile and best_score >= 2:
        result["detected"] = True
        result["screen_tile"] = list(best_tile)
        result["confidence"] = min(best_score / 5.0, 1.0)
        result["detection_type"] = "stable_color" if best_score >= 3 else "color+edge"

        log.info(f"Tutorial target detected at screen tile {best_tile}, "
                 f"confidence: {result['confidence']:.2f}, score: {best_score:.1f}, "
                 f"in {n_frames} frames")

        return (best_tile[0], best_tile[1]), result

    # Debug info
    log.debug(f"No tutorial target detected. Candidates: {all_candidates}, "
              f"edge candidates: {list(edge_candidates.keys())[:5]}, "
              f"frames: {n_frames}")
    return None, result
    for tile in set(color_candidates):
        if tile not in tile_scores:
            tile_scores[tile] = {"color_votes": 0, "flash_votes": 0, "methods": []}
        tile_scores[tile]["color_votes"] += 1
        tile_scores[tile]["methods"].append("color")

    # Add flash-based candidates
    for tile in flash_candidates:
        if tile not in tile_scores:
            tile_scores[tile] = {"color_votes": 0, "flash_votes": 0, "methods": []}
        tile_scores[tile]["flash_votes"] += 1
        tile_scores[tile]["methods"].append("flash")

    # Find best candidate
    best_tile = None
    best_score = 0

    for tile, scores in tile_scores.items():
        # Prioritize tiles detected by BOTH methods (higher confidence)
        if scores["color_votes"] > 0 and scores["flash_votes"] > 0:
            score = scores["color_votes"] + scores["flash_votes"] + 2  # Bonus for multi-method
        else:
            score = scores["color_votes"] + scores["flash_votes"]

        if score > best_score:
            best_score = score
            best_tile = tile

    if best_tile and best_score >= 2:
        result["detected"] = True
        result["screen_tile"] = best_tile
        result["confidence"] = min(best_score / 5.0, 1.0)
        result["detection_type"] = "color+flash" if best_score >= 4 else "color" if "color" in tile_scores[best_tile]["methods"] else "flash"

        log.info(f"Tutorial target detected at screen tile {best_tile}, confidence: {result['confidence']:.2f}")

        return (best_tile[0], best_tile[1]), result

    # No reliable target found
    log.debug(f"No tutorial target detected. Candidates: {tile_scores}")
    return None, result