import os
import sys
import shutil
import logging
from tqdm import tqdm

log = logging.getLogger(__name__)

def find_mgba():
    # os.name == "nt" for window
    exe_name = "mgba.exe" if os.name == "nt" else "mgba"
    path = shutil.which(exe_name)
    if path:
        log.debug("Found mGBA executable at %s", path)
        return path

    # fallback for search common install locations
    search_paths = []

    if sys.platform.startswith("win"):
        search_paths = [
            "C:\\Program Files\\mGBA",
            "C:\\Program Files (x86)\\mGBA",
            os.path.expanduser("~\\Downloads\\mGBA")
        ]
    elif sys.platform == "darwin":  # macOS
        search_paths = [
            "/Applications/mGBA.app/Contents/MacOS",
            "/usr/local/bin",
            os.path.expanduser("~/Applications"),
        ]
    elif sys.platform.startswith("linux"):
        search_paths = [
            "/usr/bin",
            "/usr/local/bin",
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/.local/bin"),
        ]

    for folder in search_paths:
        full_path = os.path.join(folder, exe_name)
        if os.path.exists(full_path):
            return full_path
    
    print_dot_interval = 2000  # status dot every 2000 dirs
    log.info("Searching for mGBA executable under home directory...")
    
    # Count total directories first (for accurate progress)
    
    dirs = []
    count = 0

    for root, _, _ in os.walk(os.path.expanduser("~")):
        dirs.append(root)
        count += 1
        if count % print_dot_interval == 0:
            # periodic progress without flooding logs
            log.debug("Scanning directories... (%d)", count)
    

    for root in tqdm(dirs, desc="Scanning directories"):
        try:
            if exe_name in os.listdir(root):
                return os.path.join(root, exe_name)
        except (PermissionError, FileNotFoundError):
            continue
    log.warning("mGBA executable not found in PATH or common locations")
    return None
