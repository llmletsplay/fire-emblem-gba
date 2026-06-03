"""Shared image utilities for the FE8 agent.

Provides helpers to convert base64 image strings and various screenshot inputs
to numpy arrays or PIL images. Keeps LLM code DRY and consistent.
"""

from __future__ import annotations

import base64
import io
import logging
import struct
from typing import Any, Optional, Tuple

from PIL import Image


log = logging.getLogger(__name__)


def base64_to_pil(base64_str: str) -> Image.Image:
    """Decode a base64 (optionally data URL prefixed) string into a PIL Image.

    Accepts strings like "data:image/png;base64,..." or raw base64 payloads.
    """
    # Remove data URL prefix if present
    if "," in base64_str and base64_str.strip().lower().startswith("data:image"):
        base64_str = base64_str.split(",", 1)[1]

    img_data = base64.b64decode(base64_str)
    img = Image.open(io.BytesIO(img_data))
    return img


def base64_to_array(base64_str: str, size: Optional[Tuple[int, int]] = None):
    """Decode a base64 image to a numpy RGB array.

    If `size` is provided as (width, height), resizes the image before returning.
    """
    # Lazy import to avoid requiring numpy in LLM-only mode
    import numpy as np  # type: ignore
    img = base64_to_pil(base64_str)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if size is not None:
        img = img.resize(size, Image.LANCZOS)
    return np.array(img)


def to_numpy(screenshot: Any):
    """Convert various screenshot formats to a numpy RGB array.

    Supports:
    - Base64 strings (optionally data URL prefixed)
    - File path (str)
    - PIL Image
    - numpy array (RGB)
    """
    if isinstance(screenshot, str):
        # data URL prefix indicates base64 image
        if screenshot.strip().lower().startswith("data:image"):
            # Lazy import for numpy
            import numpy as np  # type: ignore
            img = base64_to_pil(screenshot)
            return np.array(img)
        # Otherwise assume filesystem path
        img = Image.open(screenshot)
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Lazy import for numpy
        import numpy as np  # type: ignore
        return np.array(img)

    if isinstance(screenshot, Image.Image):
        if screenshot.mode != "RGB":
            screenshot = screenshot.convert("RGB")
        # Lazy import for numpy
        import numpy as np  # type: ignore
        return np.array(screenshot)

    try:
        import numpy as np  # type: ignore
        if isinstance(screenshot, np.ndarray):
            return screenshot
    except Exception:
        pass

    raise ValueError(f"Unsupported screenshot type: {type(screenshot)}")


def capture(sock, filename: str, timeout: float = 3.0, retries: int = 2, retry_delay: float = 0.2) -> str:
    """Capture current emulator screen via socket 'CAP' and save as PNG.

    Protocol: server sends 4‑byte big‑endian length followed by ARGB32 pixels.
    Resolution is 240x160 for GBA; infer from payload length when possible.
    """
    # Avoid importing numpy here; use pure Python/PIL to keep LLM mode lean
    from src.utils.socket_utils import _flush_socket
    import os as _os

    # Allow environment overrides for tuning without code changes
    try:
        timeout = float(_os.getenv('FE_CAP_TIMEOUT', timeout))
    except Exception:
        pass
    try:
        retries = int(_os.getenv('FE_CAP_RETRIES', retries))
    except Exception:
        pass
    try:
        retry_delay = float(_os.getenv('FE_CAP_RETRY_DELAY', retry_delay))
    except Exception:
        pass

    _flush_socket(sock)
    prev_timeout = sock.gettimeout()
    tries = 0
    last_err = None
    while tries <= max(0, retries):
      try:
        sock.settimeout(timeout)
        sock.sendall(b"CAP\n")

        # Read exactly 4 bytes for length, or detect error line
        header = bytearray()
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                raise RuntimeError("Socket closed before CAP length header")
            header.extend(chunk)

        # If server returned ASCII error (e.g., 'ERR '), handle gracefully
        if header.startswith(b"ERR"):
            # Read remainder of the line
            rest = bytearray()
            while True:
                chunk = sock.recv(4096)
                if not chunk or b"\n" in chunk:
                    break
                rest.extend(chunk)
            msg = (header + rest).decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"CAP failed: {msg}")

        size = struct.unpack(">I", bytes(header))[0]
        payload = bytearray()
        while len(payload) < size:
            chunk = sock.recv(min(65536, size - len(payload)))
            if not chunk:
                raise RuntimeError("Socket closed during CAP payload")
            payload.extend(chunk)

        # Determine dimensions (default to GBA native resolution)
        width, height = 240, 160
        pixels = size // 4
        if pixels == 240 * 160:
            width, height = 240, 160
        else:
            # Fallback: try a few common scales (2x, 3x)
            if pixels == 480 * 320:
                width, height = 480, 320
            elif pixels == 720 * 480:
                width, height = 720, 480
            else:
                log.warning("Unexpected CAP pixel count %d; assuming 240x160", pixels)

        # Convert ARGB bytes to RGBA tuples
        it = iter(payload)
        rgba = []
        append = rgba.append
        try:
            while True:
                a = next(it)
                r = next(it)
                g = next(it)
                b = next(it)
                append((r, g, b, a))
        except StopIteration:
            pass

        img = Image.new("RGBA", (width, height))
        img.putdata(rgba)
        img.save(filename)
        return filename
      except TimeoutError as e:
        last_err = e
        log.warning("CAP timeout (try %d/%d). Retrying...", tries + 1, max(1, retries + 1))
        # drain and wait a bit before retry
        _flush_socket(sock)
        time_sleep = retry_delay if retry_delay and retry_delay > 0 else 0
        if time_sleep:
            import time as _t
            _t.sleep(time_sleep)
        tries += 1
        continue
      except Exception as e:
        last_err = e
        # For non-timeout errors, only retry once
        log.warning("CAP error (try %d/%d): %s", tries + 1, max(1, retries + 1), e)
        _flush_socket(sock)
        import time as _t
        _t.sleep(retry_delay)
        tries += 1
        continue
      finally:
        # Restore previous timeout behavior
        try:
            sock.settimeout(prev_timeout)
        except Exception:
            pass
    # If all retries failed, raise the last error
    if last_err:
        raise last_err
    raise RuntimeError("CAP failed without exception but no image saved")
