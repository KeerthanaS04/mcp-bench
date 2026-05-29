"""
Bundle backend artifacts into frontend/data/ so the Gradio Space can render
them statically. No live model calls happen in v0.1 — everything the Space
shows is precomputed here and shipped as JSON / Markdown alongside the app.

Outputs:
  frontend/data/leaderboard.json        # ranked + cross-provider + distractor
  frontend/data/tasks.json              # the 70-task dataset (one obj per task)
  frontend/data/per_task_results.json   # task_id x model -> success matrix
  frontend/data/failure_patterns.md     # named failure clusters
  frontend/data/provider_notes.md       # RQ3 cross-provider deep dive

Run from anywhere:
    uv run python frontend/scripts/bundle.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "backend"
REPORTS = REPO_ROOT / "reports"
FRONTEND = REPO_ROOT / "frontend"
DATA_OUT = FRONTEND / "data"


def copy_text(src: Path, dst: Path, label: str) -> None:
    if not src.exists():
        print(f"  [skip] {label}: {src} not found")
        return
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  ok  {label}: {dst.relative_to(REPO_ROOT)}")


def bundle_tasks() -> list[dict]:
    """Merge every backend/tasks/*.json into a flat list. Strip the raw setup
    operators (the Space doesn't need them; they would bloat the bundle)."""
    tasks: list[dict] = []
    for path in sorted((BACKEND / "tasks").glob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")):
            tasks.append(
                {
                    "id": entry["id"],
                    "description": entry.get("description", ""),
                    "prompt": entry["prompt"],
                    "server": (entry.get("servers") or ["unknown"])[0],
                    "tags": entry.get("tags", []),
                    "difficulty": entry.get("difficulty", "easy"),
                    "skill": entry.get("skill", "selection"),
                }
            )
    return tasks


def bundle_per_task_matrix() -> dict:
    """Read every backend/results/<model>.jsonl (baseline only — skip the
    __d- distractor files and any model_error rows) and produce a
    task_id -> {model: success} matrix.
    """
    results_dir = BACKEND / "results"
    matrix: dict[str, dict[str, bool]] = {}
    models: list[str] = []
    for path in sorted(results_dir.glob("*.jsonl")):
        stem = path.stem
        if "__d-" in stem:
            continue
        models.append(stem)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("status") == "model_error":
                continue
            tid = rec["task_id"]
            matrix.setdefault(tid, {})[stem] = bool(rec["success"])
    return {"models": models, "tasks": matrix}


def main() -> int:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    print(f"bundling into {DATA_OUT.relative_to(REPO_ROOT)}")

    copy_text(
        BACKEND / "results" / "leaderboard.json",
        DATA_OUT / "leaderboard.json",
        "leaderboard",
    )

    tasks = bundle_tasks()
    (DATA_OUT / "tasks.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  ok  tasks: {len(tasks)} entries -> data/tasks.json")

    matrix = bundle_per_task_matrix()
    (DATA_OUT / "per_task_results.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  ok  per_task_results: {len(matrix['tasks'])} tasks x "
        f"{len(matrix['models'])} models -> data/per_task_results.json"
    )

    copy_text(
        REPORTS / "failure_patterns.md",
        DATA_OUT / "failure_patterns.md",
        "failure_patterns",
    )
    copy_text(
        REPORTS / "provider_notes.md",
        DATA_OUT / "provider_notes.md",
        "provider_notes",
    )

    print("\nbundle complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
