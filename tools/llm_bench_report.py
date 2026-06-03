#!/usr/bin/env python3
"""
Summarize LLM chapter benchmarks written by llmdriver to logs/llm/chapters.jsonl.

Usage:
  python tools/llm_bench_report.py [--path logs/llm/chapters.jsonl]
"""

import argparse
import json
import os
from collections import defaultdict


def load_entries(path: str):
    if not os.path.exists(path):
        print(f"No benchmark file found at {path}")
        return []
    entries = []
    with open(path, "r") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="logs/llm/chapters.jsonl")
    args = ap.parse_args()

    entries = load_entries(args.path)
    if not entries:
        return

    by_chapter = defaultdict(list)
    for e in entries:
        by_chapter[str(e.get("chapter_id"))].append(e)

    print("LLM Chapter Benchmark Summary\n")
    overall_time = 0.0
    overall_tokens = 0
    for chap in sorted(by_chapter.keys(), key=lambda x: (len(x), x)):
        runs = by_chapter[chap]
        total_time = sum(float(r.get("duration_sec", 0.0)) for r in runs)
        total_tokens = sum(int(r.get("tokens_used", 0)) for r in runs)
        mean_time = total_time / max(1, len(runs))
        mean_tokens = total_tokens / max(1, len(runs))
        overall_time += total_time
        overall_tokens += total_tokens
        print(f"Chapter {chap}: runs={len(runs)} total={total_time:.1f}s avg={mean_time:.1f}s avg_tokens={mean_tokens:.0f}")

    print(f"\nOverall: time={overall_time:.1f}s tokens≈{overall_tokens}")


if __name__ == "__main__":
    main()

