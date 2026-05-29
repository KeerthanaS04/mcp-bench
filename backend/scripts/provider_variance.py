"""
Phase 3 — RQ3 provider variance analysis.

Compares the same logical model (Llama-3.3-70B-Instruct) served by different
providers — Groq, Together — over the overlapping task subset. Reports:

  * Overall TSR / HCR / AVR per provider.
  * Per-task-server breakdown.
  * Per-task pass/fail matrix (which tasks succeed on one provider but not
    another — the "variance hot spots").
  * Largest-disagreement tasks (sorted by std across providers).
  * The NVIDIA variant is documented qualitatively (degenerate loop; no
    full task set ever completed).

Outputs reports/provider_notes.md.

Run after the main grid:
    uv run python scripts/provider_variance.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import pstdev

BACKEND = Path(__file__).resolve().parent.parent
RESULTS_DIR = BACKEND / "results"
TASKS_DIR = BACKEND / "tasks"
REPORTS_DIR = BACKEND.parent / "reports"
OUT_PATH = REPORTS_DIR / "provider_notes.md"

# The cross-provider trio for Llama-3.3-70B-Instruct.
TRIO = {
    "groq": "llama-3.3-70b-groq",
    "together": "llama-3.3-70b-together",
    # NVIDIA's variant is documented qualitatively below; no full result file
    # exists because the model degenerate-loops on every task.
}

TOP_N_DISAGREEMENTS = 12


def load_records(model: str) -> list[dict]:
    path = RESULTS_DIR / f"{model}.jsonl"
    if not path.exists():
        return []
    records: dict[str, dict] = {}  # dedupe-on-load (last wins; skip model_error)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("status") == "model_error":
            continue
        records[rec["task_id"]] = rec
    return list(records.values())


def task_server_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted(TASKS_DIR.glob("*.json")):
        for entry in json.loads(f.read_text(encoding="utf-8")):
            servers = entry.get("servers", [])
            out[entry["id"]] = servers[0] if servers else "unknown"
    return out


def fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}"


def main() -> int:
    server_of = task_server_lookup()
    per_provider: dict[str, dict[str, dict]] = {}
    for provider, model in TRIO.items():
        recs = load_records(model)
        if not recs:
            print(f"[skip] no records for {model}")
            continue
        per_provider[provider] = {r["task_id"]: r for r in recs}

    if not per_provider:
        print("no provider data — nothing to compare")
        return 1

    # 1) Overlap task ids (intersection across providers we have data for)
    sets = [set(d.keys()) for d in per_provider.values()]
    overlap = sorted(set.intersection(*sets)) if len(sets) > 1 else sorted(sets[0])

    # 2) Overall aggregates on the overlap
    def agg(prov: str) -> dict:
        d = per_provider[prov]
        sub = [d[t] for t in overlap if t in d]
        n = len(sub)
        if n == 0:
            return {"n": 0}
        n_success = sum(1 for r in sub if r["success"])
        total_calls = sum(r["n_calls"] for r in sub)
        return {
            "n": n,
            "tsr": n_success / n,
            "hcr": (sum(r["n_hallucinated"] for r in sub) / total_calls)
            if total_calls
            else 0.0,
            "avr": (sum(r["n_accepted"] for r in sub) / total_calls)
            if total_calls
            else 0.0,
            "total_calls": total_calls,
        }

    aggs = {p: agg(p) for p in per_provider}

    # 3) Per-task disagreements — tasks where one provider passes and another fails
    disagreements = []
    for tid in overlap:
        outcomes = {p: per_provider[p][tid]["success"] for p in per_provider}
        n_pass = sum(1 for v in outcomes.values() if v)
        n_fail = len(outcomes) - n_pass
        if n_pass > 0 and n_fail > 0:
            disagreements.append((tid, outcomes))

    # 4) Per-server breakdown
    by_server: dict[str, dict[str, list[bool]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for tid in overlap:
        s = server_of.get(tid, "unknown")
        for p in per_provider:
            by_server[s][p].append(bool(per_provider[p][tid]["success"]))

    # 5) Variance — std of TSR across providers, per server bucket
    server_variance = []
    for s, prov_outcomes in by_server.items():
        per_provider_tsr = {
            p: (sum(v) / len(v)) if v else None for p, v in prov_outcomes.items()
        }
        valid = [t for t in per_provider_tsr.values() if t is not None]
        if len(valid) >= 2:
            server_variance.append((s, per_provider_tsr, pstdev(valid)))
    server_variance.sort(key=lambda x: x[2], reverse=True)

    # ----------------------------------------------------------------
    # Render
    # ----------------------------------------------------------------
    lines = [
        "# RQ3 — Provider variance for Llama-3.3-70B-Instruct",
        "",
        "_Same logical model, three providers — different behavior. This document "
        "quantifies the cross-provider gap on the overlapping task set._",
        "",
        f"**Overlapping tasks compared:** {len(overlap)} "
        f"(intersection across {len(per_provider)} providers with full data).",
        "",
        "## 1. Overall metrics (on the overlap subset)",
        "",
        "| provider | n | TSR | HCR | AVR | total tool calls |",
        "|---|---|---|---|---|---|",
    ]
    for prov, a in aggs.items():
        lines.append(
            f"| {prov} ({TRIO[prov]}) | {a['n']} | "
            f"{fmt_pct(a.get('tsr'))} | {fmt_pct(a.get('hcr'))} | "
            f"{fmt_pct(a.get('avr'))} | {a.get('total_calls', 0)} |"
        )

    lines += [
        "",
        "**NVIDIA — qualitative:** `meta/llama-3.3-70b-instruct` on NVIDIA "
        "degenerate-loops on every task we tried: same successful tool call "
        "repeated until the 20-step cap, never emitting a content message to "
        "signal completion. Roughly **65k tokens for a single 'write one "
        "file' task.** Documented as a Phase-1 finding; no full result file "
        "exists because the loop pathology made bulk runs uneconomical. The "
        "Groq and Together cells above are the *measurable* halves of the "
        "cross-provider story.",
        "",
        "## 2. Per-server TSR (the variance map)",
        "",
        "Where does the cross-provider gap live? Higher std = larger "
        "disagreement between providers on that server's tasks.",
        "",
        "| server | " + " | ".join(per_provider.keys()) + " | std |",
        "|---|" + "---|" * (len(per_provider) + 1),
    ]
    for s, prov_tsr, sd in server_variance:
        row = [s] + [fmt_pct(prov_tsr.get(p)) for p in per_provider] + [f"{sd:.3f}"]
        lines.append("| " + " | ".join(row) + " |")

    lines += [
        "",
        "## 3. Tasks where providers disagree (one passes, another fails)",
        "",
        f"{len(disagreements)} of {len(overlap)} tasks show split outcomes.",
        "",
        "| task | server | " + " | ".join(per_provider.keys()) + " |",
        "|---|---|" + "---|" * len(per_provider),
    ]
    for tid, outcomes in disagreements[:TOP_N_DISAGREEMENTS]:
        s = server_of.get(tid, "?")
        row = [tid, s] + [
            "✅" if outcomes[p] else "❌" for p in per_provider
        ]
        lines.append("| " + " | ".join(row) + " |")
    if len(disagreements) > TOP_N_DISAGREEMENTS:
        lines.append(
            f"\n_… and {len(disagreements) - TOP_N_DISAGREEMENTS} more._"
        )

    lines += [
        "",
        "## 4. The HCR story",
        "",
        "Hallucinated-call rate — fraction of tool calls naming a tool not in "
        "the provided MCP schema — is the cleanest single discriminator "
        "between these providers. The Together-Turbo serving causes the model "
        "to call functions from training-data memory (`requests_get`, `wget`, "
        "`mkdir`, dropping the `server__` prefix) instead of binding to the "
        "schema. **Same model on Groq scores HCR 0.00 on every completed "
        "task** (n=22 sample). The provider stack — not the model — "
        "determines tool grounding.",
        "",
        "## 5. Takeaway",
        "",
        "Llama-3.3-70B-Instruct is **not one model** from a tool-use "
        "reliability standpoint. It is three different deployments with "
        "wildly different behavior: a working baseline on Groq, a "
        "hallucination-heavy quantized variant on Together-Turbo, and a "
        "non-terminating loop on NVIDIA. The model card does not tell you "
        "this — only running the benchmark across providers does.",
        "",
    ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"  providers: {list(per_provider)} | overlap: {len(overlap)} | "
          f"disagreements: {len(disagreements)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
