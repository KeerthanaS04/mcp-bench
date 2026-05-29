"""
Phase 3 — publish the MCP-Bench task set to Hugging Face Hub.

Builds an HF Datasets dataset from `backend/tasks/*.json`, generates a
dataset card explaining the schema and the named check/setup operators,
and pushes everything to `<your-hf-username>/mcp-bench`.

Requires HF_TOKEN in .env (write scope). Run once; re-running republishes.

    uv run python scripts/publish_dataset.py
    uv run python scripts/publish_dataset.py --dry-run     # build locally only
    uv run python scripts/publish_dataset.py --repo-id KeerthanaS04/mcp-bench
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
TASKS_DIR = BACKEND / "tasks"
REPO_ROOT = BACKEND.parent
BUILD_DIR = BACKEND / "hf_dataset_build"

DEFAULT_REPO_ID = "keerthanaSubru57/mcp-bench"


def load_all_tasks() -> list[dict]:
    """Load every task with a `server` derived from its `servers[0]` for
    convenient HF-side filtering, and serialize the rest verbatim."""
    out: list[dict] = []
    for path in sorted(TASKS_DIR.glob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")):
            entry = dict(entry)
            entry["server"] = entry["servers"][0] if entry.get("servers") else "unknown"
            # Stringify nested check/setup so the row stays flat-loadable.
            entry["check_json"] = json.dumps(entry.get("check", {}), ensure_ascii=False)
            entry["setup_json"] = json.dumps(entry.get("setup", []), ensure_ascii=False)
            out.append(entry)
    return out


def write_dataset_card(card_path: Path, repo_id: str, n_tasks: int,
                      by_server: Counter, by_difficulty: Counter,
                      by_skill: Counter) -> None:
    by_server_md = "\n".join(f"- **{s}**: {n}" for s, n in sorted(by_server.items()))
    by_difficulty_md = "\n".join(f"- **{d}**: {n}" for d, n in by_difficulty.most_common())
    by_skill_md = "\n".join(f"- **{s}**: {n}" for s, n in by_skill.most_common())

    card = f"""\
---
license: cc-by-4.0
tags:
  - tool-use
  - mcp
  - model-context-protocol
  - agents
  - benchmark
language:
  - en
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: tasks
        path: tasks.json
---

# MCP-Bench tasks (v0.1)

The 70-task dataset behind [**MCP-Bench**](https://github.com/KeerthanaS04/mcp-bench) —
a reliability benchmark for open-source LLM agents using Anthropic's
**Model Context Protocol (MCP)**.

## At a glance

- **Tasks:** {n_tasks}
- **MCP servers covered:**
{by_server_md}
- **Difficulty:**
{by_difficulty_md}
- **Skill (RQ1/RQ2 stratifier):**
{by_skill_md}

## How a task is structured

Each task is a JSON object with these fields:

| Field | Meaning |
|---|---|
| `id` | Unique task identifier (`fs_001_...`, `sql_003_...`, `gh_009_...`, etc.) |
| `description` | Short human-readable summary |
| `prompt` | The exact user message the agent receives |
| `servers` | MCP server(s) the task needs (`["filesystem"]`, `["postgres"]`, …) |
| `setup` | Ordered list of named setup operators to seed the sandbox (`write_file`, `init_sqlite`, `init_memory`) |
| `check` | A single named check operator that decides pass/fail programmatically |
| `tags` | Freeform tags (e.g. `single-tool`, `multi-step`, `RQ2`) |
| `difficulty` | `easy` / `medium` / `hard` |
| `skill` | `selection` / `composition` / `recovery` / `ambiguity` |

For HF Datasets-friendly loading, `setup_json` and `check_json` are also
provided as serialized strings of the nested objects.

## Named operators

**Setup operators** (`backend/src/mcp_bench/tasks.py`):

- `write_file`, `mkdir`, `init_sqlite`, `init_memory`

**Check operators** (every check is deterministic — no LLM judge):

- `file_exists`, `file_not_exists`
- `file_content_equals`, `file_content_contains`
- `final_text_contains`, `final_text_regex`
- `sqlite_query_returns`
- `memory_has_entity`, `memory_not_has_entity`, `memory_has_relation`,
  `memory_entity_observation_contains`, `memory_entity_count`
- `all_of`

This lets every pass/fail decision be reproduced from a trace.

## Loading

```python
from datasets import load_dataset
ds = load_dataset("{repo_id}", split="tasks")
print(ds[0]["prompt"])
```

## Citation

```bibtex
@misc{{mcp-bench-2026,
  title  = {{MCP-Bench: A Reliability Benchmark for Open-Source LLM Agents Using the Model Context Protocol}},
  author = {{Keerthana S}},
  year   = {{2026}},
  url    = {{https://github.com/KeerthanaS04/mcp-bench}},
  note   = {{v0.1}}
}}
```

## License

CC-BY 4.0 (this dataset). The harness code is Apache 2.0.
"""
    card_path.write_text(card, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="<user>/<dataset>")
    p.add_argument("--dry-run", action="store_true", help="build locally; do not push")
    args = p.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    tasks = load_all_tasks()
    if not tasks:
        print(f"no tasks found in {TASKS_DIR}")
        return 1

    by_server = Counter(t["server"] for t in tasks)
    by_difficulty = Counter(t.get("difficulty", "easy") for t in tasks)
    by_skill = Counter(t.get("skill", "selection") for t in tasks)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tasks_path = BUILD_DIR / "tasks.json"
    tasks_path.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in tasks),
        encoding="utf-8",
    )
    card_path = BUILD_DIR / "README.md"
    write_dataset_card(card_path, args.repo_id, len(tasks), by_server, by_difficulty, by_skill)

    print(f"built local dataset in {BUILD_DIR}")
    print(f"  {len(tasks)} tasks  servers={dict(by_server)}  "
          f"difficulty={dict(by_difficulty)}  skill={dict(by_skill)}")

    if args.dry_run:
        print("dry-run: skipping HF push.")
        return 0

    token = os.getenv("HF_TOKEN")
    if not token:
        print("HF_TOKEN not set in .env — cannot push. Re-run with --dry-run or set the token.")
        return 2

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub missing. Install with: uv add huggingface_hub")
        return 3

    api = HfApi(token=token)
    print(f"pushing to https://huggingface.co/datasets/{args.repo_id}")
    api.create_repo(args.repo_id, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        folder_path=str(BUILD_DIR),
        repo_id=args.repo_id,
        repo_type="dataset",
        commit_message="MCP-Bench v0.1 task set",
    )
    print(f"done. visit https://huggingface.co/datasets/{args.repo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
