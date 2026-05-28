"""
Run the full Phase-2 grid: every locked leaderboard model over all tasks.

Each model runs in its own `python -m mcp_bench.runner` subprocess (clean state,
isolated failures). Resume is on, so re-running skips completed (model, task)
cells — safe to interrupt and restart across sessions / rate-limit windows.

After the grid, re-render the leaderboard:
    uv run python scripts/render_leaderboard.py

Usage:
    uv run python scripts/run_grid.py                 # all locked models, all tasks
    uv run python scripts/run_grid.py --tasks sqlite  # restrict task set
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from mcp_bench.providers import LEADERBOARD_MODELS


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", default="all")
    p.add_argument("--models", default="", help="comma subset; default = locked set")
    args = p.parse_args()

    models = args.models.split(",") if args.models else LEADERBOARD_MODELS

    failures: list[str] = []
    for i, model in enumerate(models, start=1):
        print(f"\n{'=' * 70}\n[{i}/{len(models)}] {model}\n{'=' * 70}", flush=True)
        proc = subprocess.run(
            [sys.executable, "-m", "mcp_bench.runner", "--model", model, "--tasks", args.tasks],
        )
        if proc.returncode != 0:
            failures.append(model)
            print(f"  !! {model} exited {proc.returncode}", flush=True)

    print(f"\nGrid complete. Models with non-zero exit: {failures or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
