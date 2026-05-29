"""
Phase 3 — failure-mode clustering.

Walks backend/traces/, finds every (model, task) run where the programmatic
ground-truth check failed, embeds (task prompt + status signals + final agent
text + check detail) with sentence-transformers/all-MiniLM-L6-v2, clusters
with HDBSCAN. For each top cluster: representative examples, dominant
signals (status/model/server), suggested name.

Outputs reports/failure_patterns.md.

Requires the `analysis` optional dependency group:
    uv sync --extra analysis
    uv run python scripts/cluster_failures.py

Why this is structured this way:
  - We exclude model identity from the embedding text so clusters reflect
    failure *semantics*, not just "which model failed." Model populations
    per cluster are then surfaced in the report.
  - Representative examples = nearest-to-centroid; gives a faithful snapshot.
  - Cluster naming uses heuristic signals (status patterns, call counts,
    error counts) — the user is expected to rename based on known Phase 2
    findings (Llama loop, Together-Turbo hallucination, etc.).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

import hdbscan

BACKEND = Path(__file__).resolve().parent.parent
TRACES_DIR = BACKEND / "traces"
TASKS_DIR = BACKEND / "tasks"
REPORTS_DIR = BACKEND.parent / "reports"
OUT_PATH = REPORTS_DIR / "failure_patterns.md"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_CLUSTER_SIZE = 4  # minimum failures for a "real" pattern
REPORT_TOP_K = 8
EXAMPLES_PER_CLUSTER = 3


@dataclass
class FailedRun:
    model: str
    task_id: str
    task_prompt: str
    task_server: str
    final_text: str
    status: str
    n_calls: int
    n_errored: int
    check_detail: str


# ---------------------------------------------------------------------------
# Load failed runs
# ---------------------------------------------------------------------------

def load_task_lookup() -> dict[str, tuple[str, list[str]]]:
    """task_id -> (prompt, servers)"""
    out: dict[str, tuple[str, list[str]]] = {}
    for path in sorted(TASKS_DIR.glob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")):
            out[entry["id"]] = (entry["prompt"], list(entry.get("servers", [])))
    return out


def load_failed_runs() -> list[FailedRun]:
    tasks = load_task_lookup()
    failed: list[FailedRun] = []
    for model_dir in sorted(TRACES_DIR.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith("_"):
            continue
        for trace_file in sorted(model_dir.glob("*.json")):
            try:
                d = json.loads(trace_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if d.get("check_passed", False):
                continue  # passed runs are skipped
            tid = d.get("task_id")
            if tid not in tasks:
                continue
            prompt, servers = tasks[tid]
            events = d.get("events", [])
            n_errored = sum(
                1
                for e in events
                if e.get("kind") == "tool_result" and e.get("tool_is_error")
            )
            failed.append(
                FailedRun(
                    model=model_dir.name,
                    task_id=tid,
                    task_prompt=prompt,
                    task_server=servers[0] if servers else "unknown",
                    final_text=(d.get("final_text") or "")[:600],
                    status=d.get("status", ""),
                    n_calls=int(d.get("tool_calls", 0)),
                    n_errored=n_errored,
                    check_detail=(d.get("check_detail") or "")[:300],
                )
            )
    return failed


def embedding_text(r: FailedRun) -> str:
    """Text fed to the embedder. Model identity intentionally omitted so
    clusters reflect failure semantics, not who failed."""
    return (
        f"task ({r.task_server}): {r.task_prompt[:300]}\n"
        f"status: {r.status} | tool_calls={r.n_calls} | tool_errors={r.n_errored}\n"
        f"final answer: {r.final_text}\n"
        f"check verdict: {r.check_detail}"
    )


# ---------------------------------------------------------------------------
# Cluster naming heuristic
# ---------------------------------------------------------------------------

def suggest_name(members: list[FailedRun]) -> str:
    n = len(members)
    statuses = Counter(r.status for r in members)
    top_status, top_status_n = statuses.most_common(1)[0]
    avg_calls = sum(r.n_calls for r in members) / n
    avg_errors = sum(r.n_errored for r in members) / n
    pct_zero_calls = sum(1 for r in members if r.n_calls == 0) / n
    pct_step_cap = sum(1 for r in members if r.status == "step_cap") / n
    pct_model_error = sum(1 for r in members if r.status == "model_error") / n
    pct_zero_tokens = (
        sum(1 for r in members if r.n_calls == 0 and r.status == "model_error") / n
    )

    if pct_step_cap >= 0.5 and avg_calls >= 15:
        return "Step-cap loop (model repeats calls until cap)"
    if pct_zero_tokens >= 0.5:
        return "Provider rate-limit wall (0 tokens, 0 calls)"
    if pct_model_error >= 0.5:
        return "Transient model_error (API failures)"
    if pct_zero_calls >= 0.5 and top_status == "answered":
        return "Premature termination — answered without calling any tool"
    if avg_errors >= 2.0:
        return "Heavy tool-call errors (bad arguments / wrong tool name)"
    if top_status == "answered":
        return "Wrong final answer (tool calls succeeded, answer failed check)"
    return f"Mixed: {dict(statuses)}"


def nearest_to_centroid(
    embeddings: np.ndarray, indices: list[int], k: int
) -> list[int]:
    """Return the k indices (from `indices`) whose embeddings are closest to
    the cluster centroid."""
    pts = embeddings[indices]
    centroid = pts.mean(axis=0)
    dists = np.linalg.norm(pts - centroid, axis=1)
    order = np.argsort(dists)[:k]
    return [indices[i] for i in order]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_report(
    failed: list[FailedRun],
    labels: np.ndarray,
    embeddings: np.ndarray,
) -> str:
    cluster_counts = Counter(int(l) for l in labels)
    real_clusters = sorted(
        (c for c in cluster_counts if c != -1),
        key=lambda c: cluster_counts[c],
        reverse=True,
    )
    top = real_clusters[:REPORT_TOP_K]

    n_failed = len(failed)
    n_models = len({r.model for r in failed})
    n_clustered = sum(cluster_counts[c] for c in real_clusters)
    n_noise = cluster_counts.get(-1, 0)

    lines: list[str] = [
        "# MCP-Bench failure-mode analysis",
        "",
        f"_Generated from **{n_failed} failed runs** across **{n_models} models**_ "
        f"(every trace in `backend/traces/` where the programmatic check returned False)."
        f" Embedded with `{EMBED_MODEL}`, clustered with HDBSCAN "
        f"(min_cluster_size={MIN_CLUSTER_SIZE}). "
        f"{len(real_clusters)} clusters surfaced; {n_clustered} runs clustered, "
        f"{n_noise} unclustered (noise).",
        "",
        f"Top {len(top)} clusters by size are featured below. Cluster names are "
        "heuristic suggestions based on dominant signals — rename freely.",
        "",
    ]

    for rank, c in enumerate(top, 1):
        member_idx = [i for i, l in enumerate(labels) if l == c]
        members = [failed[i] for i in member_idx]
        rep_idx = nearest_to_centroid(embeddings, member_idx, EXAMPLES_PER_CLUSTER)
        name = suggest_name(members)

        status_counts = Counter(r.status for r in members)
        model_counts = Counter(r.model for r in members)
        server_counts = Counter(r.task_server for r in members)
        avg_calls = sum(r.n_calls for r in members) / len(members)
        avg_errors = sum(r.n_errored for r in members) / len(members)

        lines += [
            f"## Pattern {rank} — {name}",
            "",
            f"**Size:** {len(members)} runs &nbsp; &nbsp;"
            f"**Mean tool calls:** {avg_calls:.1f} &nbsp; &nbsp;"
            f"**Mean tool errors:** {avg_errors:.1f}",
            "",
            f"**Status distribution:** {dict(status_counts.most_common())}  ",
            f"**Top models:** {dict(model_counts.most_common(4))}  ",
            f"**Top task servers:** {dict(server_counts.most_common(4))}",
            "",
            f"**Representative examples (nearest to cluster centroid):**",
            "",
        ]

        for j, idx in enumerate(rep_idx, 1):
            r = failed[idx]
            lines += [
                f"<details><summary><code>{r.model}</code> · "
                f"<code>{r.task_id}</code> · status: <code>{r.status}</code> · "
                f"calls: {r.n_calls} · errors: {r.n_errored}</summary>",
                "",
                f"**Task prompt:** {r.task_prompt}",
                "",
                f"**Final agent text:** {r.final_text or '_(empty)_'}",
                "",
                f"**Check verdict:** {r.check_detail or '_(none)_'}",
                "",
                "</details>",
                "",
            ]

    if n_noise:
        lines += [
            f"## Unclustered (noise): {n_noise} runs",
            "",
            "Failures too unique to cluster with the rest. Worth eyeballing for one-off bugs "
            "or task-specific weirdness.",
            "",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"loading failed runs from {TRACES_DIR}")
    failed = load_failed_runs()
    if not failed:
        print("no failed runs found.")
        return 1
    print(f"  {len(failed)} failed runs across {len({r.model for r in failed})} models")

    print(f"embedding {len(failed)} runs with {EMBED_MODEL} (this may download the model on first run)")
    model = SentenceTransformer(EMBED_MODEL)
    texts = [embedding_text(r) for r in failed]
    embeddings = model.encode(
        texts, show_progress_bar=True, normalize_embeddings=True
    )
    embeddings = np.asarray(embeddings, dtype=np.float32)

    print(f"clustering with HDBSCAN (min_cluster_size={MIN_CLUSTER_SIZE})")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, metric="euclidean")
    labels = clusterer.fit_predict(embeddings)

    counts = Counter(int(l) for l in labels)
    print(f"  cluster sizes: {dict(sorted(counts.items()))}")

    out = render_report(failed, labels, embeddings)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(out, encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
