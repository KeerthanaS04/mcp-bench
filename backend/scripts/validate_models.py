"""
Smoke-validate candidate models before committing them to a full grid run.

For each model short-name, runs a single probe task (a simple filesystem write)
and reports whether it: connects, calls tools, and completes. This catches the
failure modes Phase 1 surfaced — dead model IDs (404), provider timeouts (504),
tool-call-as-text leaks, and degenerate loops — cheaply, one task per model.

Writes only trace files (under traces/_validate_<model>/), never results JSONL,
so it does not pollute the leaderboard.

Usage:
    uv run python scripts/validate_models.py                 # all registry models
    uv run python scripts/validate_models.py gpt-oss-20b qwen-2.5-7b   # a subset
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from mcp_bench.providers import LLMClient, list_models
from mcp_bench.runner import (
    DEFAULT_TRACES_DIR,
    REPO_ROOT,
    TASKS_DIR,
    run_one_task,
)
from mcp_bench.tasks import load_tasks

PROBE_TASK_ID = "fs_002_write_exact"


async def main(candidates: list[str]) -> int:
    load_dotenv(REPO_ROOT / ".env")
    tasks = {t.id: t for t in load_tasks(TASKS_DIR)}
    probe = tasks[PROBE_TASK_ID]

    print(f"Probing {len(candidates)} model(s) with task {PROBE_TASK_ID!r}\n")
    print(f"{'model':<26} {'result':<8} {'calls':<6} {'status':<14} note")
    print("-" * 78)

    working: list[str] = []
    for name in candidates:
        try:
            llm = LLMClient(name)
        except Exception as e:
            print(f"{name:<26} {'SKIP':<8} {'-':<6} {'-':<14} {type(e).__name__}: {e}")
            continue
        try:
            per = await run_one_task(
                probe, name, llm, DEFAULT_TRACES_DIR / f"_validate_{name}"
            )
        except Exception as e:
            note = f"{type(e).__name__}: {str(e)[:50]}"
            print(f"{name:<26} {'ERROR':<8} {'-':<6} {'-':<14} {note}")
            continue
        result = "PASS" if per.success else "fail"
        if per.success:
            working.append(name)
        print(
            f"{name:<26} {result:<8} {per.n_calls:<6} {per.status:<14} "
            f"hcr={per.n_hallucinated} err={per.n_errored}"
        )

    print("\nworking models:", working)
    return 0


if __name__ == "__main__":
    requested = sys.argv[1:] or list_models()
    raise SystemExit(asyncio.run(main(requested)))
