# Runtime Artifacts & Data Locations

This project generates a few files and folders at runtime. They are intentionally ignored by Git to keep the repo small and free of personal data.

Screenshots and Minimap
- `latest.png` — Current screen capture; refreshed frequently
- `minimap.png` — Optional minimap overlay; generated if enabled
- `screenshot_*.png` — Saved screenshots for the Chronicle

Knowledge Base
- `fe_knowledge.json` — Local, persistent knowledge base driving improved prompts. Safe to delete; it will be recreated.

Chronicle Data
- `assets/chronicle/` — Server-side images/metadata for Chronicle views
- `fe-client/public/chronicle/` — Frontend assets for the Chronicle

Logs
- `logs/` — General runtime logs (websocket, etc.)
  - `logs/llm/chapters.jsonl` — Per-chapter timings/tokens (`run_id`-stamped)
  - `logs/llm/requests.jsonl` — Per-request latencies/tokens (`run_id`-stamped)
  - `logs/state/snapshots.jsonl` — Phase-change snapshots (`run_id`-stamped)

Notes
- All of the above are ignored via `.gitignore` and not committed.
- You can clean them safely between runs if needed.

Run / Session IDs
- Provide your own tag via `FE_RUN_ID=your-experiment`, or a UUID will be generated.
- HTTP endpoints and CLI tools can filter/summarize by run.
