"""
Task schema, loader, and the named-operator registries for setup + checks.

Design:
  * Tasks live as JSON entries under backend/tasks/<server>.json.
  * Each task references named setup ops (prepare sandbox state) and a
    single named check op (decide pass/fail).
  * Operators are plain Python functions registered in SETUP_OPS / CHECK_OPS.
    Adding a new task = JSON only. Adding a new op = one Python function.

The sandbox is cleared between tasks by the runner, so setup ops can assume
they start from an empty directory.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field


class OpSpec(BaseModel):
    """A named operator with arbitrary parameters."""

    kind: str
    params: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: str
    description: str
    prompt: str
    servers: list[str]  # MCP server names this task needs
    setup: list[OpSpec] = Field(default_factory=list)
    check: OpSpec
    max_steps: int = 20
    tags: list[str] = Field(default_factory=list)


@dataclass
class CheckResult:
    passed: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def load_tasks(tasks_dir: Path, servers: list[str] | None = None) -> list[Task]:
    """Load all tasks from <tasks_dir>/*.json. If `servers` is given, only
    return tasks whose `servers` field is a subset of the allowed list."""
    all_tasks: list[Task] = []
    for path in sorted(tasks_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON array of tasks")
        for entry in data:
            all_tasks.append(Task.model_validate(entry))
    if servers is not None:
        allowed = set(servers)
        all_tasks = [t for t in all_tasks if set(t.servers).issubset(allowed)]
    ids = [t.id for t in all_tasks]
    if len(ids) != len(set(ids)):
        dupes = [i for i in ids if ids.count(i) > 1]
        raise ValueError(f"duplicate task ids: {sorted(set(dupes))}")
    return all_tasks


# ---------------------------------------------------------------------------
# Setup operators — prepare sandbox state before the agent runs
# ---------------------------------------------------------------------------

SetupFn = Callable[[Path, dict[str, Any]], None]


def _setup_write_file(sandbox: Path, params: dict[str, Any]) -> None:
    path = sandbox / params["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(params["content"], encoding="utf-8")


def _setup_mkdir(sandbox: Path, params: dict[str, Any]) -> None:
    (sandbox / params["path"]).mkdir(parents=True, exist_ok=True)


def _setup_init_sqlite(sandbox: Path, params: dict[str, Any]) -> None:
    db_path = sandbox / params["db"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(params["sql"])
        con.commit()
    finally:
        con.close()


SETUP_OPS: dict[str, SetupFn] = {
    "write_file": _setup_write_file,
    "mkdir": _setup_mkdir,
    "init_sqlite": _setup_init_sqlite,
}


def reset_sandbox(sandbox: Path) -> None:
    if sandbox.exists():
        for child in sandbox.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    sandbox.mkdir(parents=True, exist_ok=True)


def apply_setup(task: Task, sandbox: Path) -> None:
    reset_sandbox(sandbox)
    for op in task.setup:
        fn = SETUP_OPS.get(op.kind)
        if fn is None:
            raise KeyError(f"unknown setup op {op.kind!r} (task {task.id})")
        fn(sandbox, op.params)


# ---------------------------------------------------------------------------
# Check operators — decide whether the agent succeeded
# ---------------------------------------------------------------------------

# Signature: (sandbox_dir, final_text, params) -> CheckResult
CheckFn = Callable[[Path, str | None, dict[str, Any]], CheckResult]


def _check_file_exists(sandbox: Path, _t: str | None, p: dict[str, Any]) -> CheckResult:
    path = sandbox / p["path"]
    return CheckResult(path.exists() and path.is_file(), f"path={path}")


def _check_file_not_exists(sandbox: Path, _t: str | None, p: dict[str, Any]) -> CheckResult:
    path = sandbox / p["path"]
    return CheckResult(not path.exists(), f"path={path}")


def _check_file_content_equals(
    sandbox: Path, _t: str | None, p: dict[str, Any]
) -> CheckResult:
    path = sandbox / p["path"]
    if not path.is_file():
        return CheckResult(False, f"missing file: {path}")
    actual = path.read_text(encoding="utf-8")
    expected = p["content"]
    if p.get("strip", False):
        actual = actual.strip()
        expected = expected.strip()
    return CheckResult(actual == expected, f"path={path} match={actual == expected}")


def _check_file_content_contains(
    sandbox: Path, _t: str | None, p: dict[str, Any]
) -> CheckResult:
    path = sandbox / p["path"]
    if not path.is_file():
        return CheckResult(False, f"missing file: {path}")
    actual = path.read_text(encoding="utf-8")
    needle = p["substring"]
    if p.get("case_insensitive", False):
        return CheckResult(needle.lower() in actual.lower(), f"path={path}")
    return CheckResult(needle in actual, f"path={path}")


def _check_final_text_contains(
    _s: Path, final_text: str | None, p: dict[str, Any]
) -> CheckResult:
    if final_text is None:
        return CheckResult(False, "no final text (agent did not answer)")
    needles = p.get("substrings") or [p["substring"]]
    hay = final_text.lower() if p.get("case_insensitive", True) else final_text
    needles_cmp = [n.lower() for n in needles] if p.get("case_insensitive", True) else needles
    require_all = p.get("require_all", True)
    hits = [n for n in needles_cmp if n in hay]
    if require_all:
        return CheckResult(len(hits) == len(needles_cmp), f"hits={len(hits)}/{len(needles_cmp)}")
    return CheckResult(len(hits) > 0, f"hits={len(hits)}/{len(needles_cmp)}")


def _check_final_text_regex(
    _s: Path, final_text: str | None, p: dict[str, Any]
) -> CheckResult:
    if final_text is None:
        return CheckResult(False, "no final text")
    flags = re.IGNORECASE if p.get("case_insensitive", True) else 0
    m = re.search(p["pattern"], final_text, flags=flags)
    return CheckResult(m is not None, f"pattern={p['pattern']!r}")


def _check_sqlite_query_returns(
    sandbox: Path, _t: str | None, p: dict[str, Any]
) -> CheckResult:
    db = sandbox / p["db"]
    if not db.is_file():
        return CheckResult(False, f"missing db: {db}")
    con = sqlite3.connect(db)
    try:
        rows = con.execute(p["sql"]).fetchall()
    finally:
        con.close()
    expected = [tuple(r) for r in p["expected_rows"]]
    actual = [tuple(r) for r in rows]
    return CheckResult(actual == expected, f"actual={actual!r} expected={expected!r}")


def _check_all_of(
    sandbox: Path, final_text: str | None, p: dict[str, Any]
) -> CheckResult:
    sub_results: list[str] = []
    for sub in p["checks"]:
        spec = OpSpec.model_validate(sub)
        r = run_check(spec, sandbox, final_text)
        sub_results.append(f"{spec.kind}={'PASS' if r.passed else 'FAIL'}({r.detail})")
        if not r.passed:
            return CheckResult(False, "; ".join(sub_results))
    return CheckResult(True, "; ".join(sub_results))


CHECK_OPS: dict[str, CheckFn] = {
    "file_exists": _check_file_exists,
    "file_not_exists": _check_file_not_exists,
    "file_content_equals": _check_file_content_equals,
    "file_content_contains": _check_file_content_contains,
    "final_text_contains": _check_final_text_contains,
    "final_text_regex": _check_final_text_regex,
    "sqlite_query_returns": _check_sqlite_query_returns,
    "all_of": _check_all_of,
}


def run_check(spec: OpSpec, sandbox: Path, final_text: str | None) -> CheckResult:
    fn = CHECK_OPS.get(spec.kind)
    if fn is None:
        return CheckResult(False, f"unknown check op: {spec.kind!r}")
    try:
        return fn(sandbox, final_text, spec.params)
    except Exception as e:
        return CheckResult(False, f"check raised {type(e).__name__}: {e}")
