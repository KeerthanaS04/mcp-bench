"""
Phase 1 CLI runner.

Usage:
    uv run python -m mcp_bench.runner --model llama-3.3-70b --tasks all
    uv run python -m mcp_bench.runner --model llama-3.1-8b --tasks filesystem --limit 3

Outputs:
    backend/results/<model>.jsonl       one line per (model, task), append-only
    backend/results/<model>_summary.md  aggregated leaderboard row
    backend/traces/<model>/<task_id>.json  full trace per task

Resume is on by default: tasks already present in the results JSONL are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from rich.console import Console

from .agent import run_agent
from .mcp_client import MCPClientPool, MCPServerConfig
from .metrics import (
    ModelMetrics,
    PerTaskMetrics,
    aggregate,
    compute_per_task,
    format_markdown_table,
)
from .providers import LLMClient, list_models
from .tasks import Task, apply_setup, load_tasks, run_check

console = Console()

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BACKEND_DIR.parent
SANDBOX_DIR = BACKEND_DIR / "sandbox"
TASKS_DIR = BACKEND_DIR / "tasks"
DEFAULT_RESULTS_DIR = BACKEND_DIR / "results"
DEFAULT_TRACES_DIR = BACKEND_DIR / "traces"

VALID_SERVERS = ("filesystem", "sqlite", "fetch")


def build_mcp_configs(needed: Iterable[str]) -> list[MCPServerConfig]:
    """Return the MCP server launch configs for the requested logical names.

    We point filesystem at the sandbox directory, sqlite at a single DB inside
    the sandbox, and fetch with no path argument.
    """
    cfgs: list[MCPServerConfig] = []
    for name in needed:
        if name == "filesystem":
            cfgs.append(
                MCPServerConfig(
                    name="filesystem",
                    command="npx",
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        str(SANDBOX_DIR),
                    ],
                    cwd=str(SANDBOX_DIR),
                )
            )
        elif name == "sqlite":
            cfgs.append(
                MCPServerConfig(
                    name="sqlite",
                    command="uvx",
                    args=[
                        "mcp-server-sqlite",
                        "--db-path",
                        str(SANDBOX_DIR / "tasks.db"),
                    ],
                )
            )
        elif name == "fetch":
            cfgs.append(
                MCPServerConfig(
                    name="fetch",
                    command="uvx",
                    args=["mcp-server-fetch"],
                )
            )
        else:
            raise ValueError(f"unknown MCP server: {name!r}")
    return cfgs


def read_done_task_ids(results_path: Path) -> set[str]:
    if not results_path.exists():
        return set()
    done: set[str] = set()
    with results_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = rec.get("task_id")
            if tid:
                done.add(tid)
    return done


def filter_tasks(all_tasks: list[Task], tasks_arg: str) -> list[Task]:
    if tasks_arg == "all":
        return all_tasks
    wanted = set(tasks_arg.split(","))
    bad = wanted - set(VALID_SERVERS)
    if bad:
        raise SystemExit(f"unknown task set(s): {sorted(bad)}. Choose from {VALID_SERVERS} or 'all'.")
    return [t for t in all_tasks if set(t.servers) & wanted]


async def run_one_task(
    task: Task,
    model: str,
    llm: LLMClient,
    traces_dir: Path,
) -> PerTaskMetrics:
    apply_setup(task, SANDBOX_DIR)
    configs = build_mcp_configs(task.servers)
    async with MCPClientPool(configs) as pool:
        available = [t.qualified_name for t in pool.tools]
        trace = await run_agent(
            task_id=task.id,
            task_prompt=task.prompt,
            mcp_pool=pool,
            llm=llm,
            max_steps=task.max_steps,
        )

    # Check ground truth.
    check_result = run_check(task.check, SANDBOX_DIR, trace.final_text)
    per = compute_per_task(task, trace, available).with_success(check_result.passed)

    # Write trace + per-task record.
    traces_dir.mkdir(parents=True, exist_ok=True)
    trace_path = traces_dir / f"{task.id}.json"
    trace_path.write_text(
        json.dumps(
            {
                **trace.to_dict(),
                "check_passed": check_result.passed,
                "check_detail": check_result.detail,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return per


def append_result(results_path: Path, per: PerTaskMetrics) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(per)) + "\n")


def load_existing_results(results_path: Path) -> list[PerTaskMetrics]:
    """Read the JSONL results, keeping only the most recent record per task_id.

    The JSONL is append-only, so re-runs of the same task leave older entries
    behind. The aggregate should reflect the latest result.
    """
    if not results_path.exists():
        return []
    by_id: dict[str, PerTaskMetrics] = {}
    with results_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_id[rec["task_id"]] = PerTaskMetrics(**rec)
    return list(by_id.values())


async def amain(args: argparse.Namespace) -> int:
    load_dotenv(REPO_ROOT / ".env")

    all_tasks = load_tasks(TASKS_DIR)
    if args.only:
        tasks = [t for t in all_tasks if t.id == args.only]
        if not tasks:
            console.print(f"[red]no task with id {args.only!r}[/red]")
            return 1
    else:
        tasks = filter_tasks(all_tasks, args.tasks)
        if args.limit:
            tasks = tasks[: args.limit]
    if not tasks:
        console.print("[red]no tasks selected[/red]")
        return 1

    try:
        llm = LLMClient(args.model)
    except (KeyError, RuntimeError) as e:
        console.print(f"[red]{e}[/red]")
        console.print(f"Available models: {list_models()}")
        return 2

    results_dir = Path(args.results_dir)
    traces_dir = Path(args.traces_dir) / args.model
    results_path = results_dir / f"{args.model}.jsonl"

    done = read_done_task_ids(results_path) if args.resume else set()
    if done:
        console.print(f"[dim]resuming: skipping {len(done)} task(s) already in {results_path}[/dim]")

    todo = [t for t in tasks if t.id not in done]
    console.print(
        f"[bold]model[/bold]={args.model}  "
        f"[bold]tasks[/bold]={len(todo)} (of {len(tasks)} selected)"
    )

    for i, task in enumerate(todo, start=1):
        console.print(
            f"[dim]({i}/{len(todo)})[/dim] [bold]{task.id}[/bold]  "
            f"servers={task.servers}  max_steps={task.max_steps}"
        )
        try:
            per = await run_one_task(task, args.model, llm, traces_dir)
        except Exception as e:
            console.print(f"  [red]ERROR: {type(e).__name__}: {e}[/red]")
            if isinstance(e, BaseExceptionGroup):
                for sub in e.exceptions:
                    console.print(f"  [red]  inner: {type(sub).__name__}: {sub}[/red]")
            if args.debug:
                import traceback
                console.print("[red]" + traceback.format_exc() + "[/red]")
            continue
        append_result(results_path, per)
        mark = "[green]PASS[/green]" if per.success else "[red]FAIL[/red]"
        console.print(
            f"  {mark}  calls={per.n_calls}  hallucinated={per.n_hallucinated}  "
            f"errors={per.n_errored}  status={per.status}  "
            f"tokens={per.prompt_tokens + per.completion_tokens}"
        )

    # Aggregate over everything currently on disk for this model (incl. resumed).
    all_records = load_existing_results(results_path)
    if not all_records:
        console.print("[yellow]no results to aggregate[/yellow]")
        return 0

    agg = aggregate(all_records)
    summary_md = _write_summary(results_dir, agg)
    console.print("\n[bold]Summary[/bold]")
    console.print(summary_md)
    return 0


def _write_summary(results_dir: Path, agg: ModelMetrics) -> str:
    summary_md = format_markdown_table([agg])
    (results_dir / f"{agg.model}_summary.md").write_text(summary_md + "\n", encoding="utf-8")
    (results_dir / f"{agg.model}_summary.json").write_text(
        json.dumps(asdict(agg), indent=2), encoding="utf-8"
    )
    return summary_md


def main() -> int:
    p = argparse.ArgumentParser(prog="mcp_bench.runner", description="Run MCP-Bench tasks.")
    p.add_argument("--model", required=True, help=f"one of {list_models()}")
    p.add_argument(
        "--tasks",
        default="all",
        help=f"'all' or comma-separated subset of {VALID_SERVERS}",
    )
    p.add_argument("--limit", type=int, default=0, help="cap on number of tasks (0 = no cap)")
    p.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    p.add_argument("--traces-dir", default=str(DEFAULT_TRACES_DIR))
    p.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="re-run tasks even if already in the results file",
    )
    p.add_argument("--debug", action="store_true", help="print full tracebacks on task errors")
    p.add_argument("--only", help="run only the task with this id (overrides --tasks/--limit)")
    args = p.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
