#!/usr/bin/env bash
# Apply Ch0 verified harness commit onto Mac checkout.
# Run on machineId 8958adc4-24ef-4f68-8dc2-5bd09ea6cf53 (macbook-lite.local)
set -euo pipefail
REPO="${1:-/Users/area/repos/llmletsplay-fire-emblem/fe-gba}"
BUNDLE="${2:-}"
cd "$REPO"
git checkout feat/minimax-harness-refresh
if [[ -n "$BUNDLE" && -f "$BUNDLE" ]]; then
  git pull "$BUNDLE" feat/minimax-harness-refresh || git fetch "$BUNDLE" && git merge FETCH_HEAD
else
  # Prefer lite SSH remote
  git remote get-url lite >/dev/null 2>&1 || git remote add lite git@github.com-lite:llmletsplay/fire-emblem-gba.git
  git fetch lite feat/minimax-harness-refresh || git fetch origin feat/minimax-harness-refresh
  git merge --ff-only FETCH_HEAD || git cherry-pick 101950634659e705b77f7dbc5acc97083072d7da
fi
# Ensure Ch0 env defaults (do not commit .env)
if [[ -f .env ]]; then
  grep -q '^FE_SAVESTATE_SLOT=' .env || echo 'FE_SAVESTATE_SLOT=1' >> .env
  # Prefer slot 1 for clean Ch0; leave FE_LOAD_SAVESTATE as operator chooses
fi
PYTHONPATH=. python3 -m pytest tests/test_tutorial_progress.py tests/test_legal_moves.py -q
echo "OK: Ch0 verified wiring present. Tip: FE_LOAD_SAVESTATE=true FE_SAVESTATE_SLOT=1"
