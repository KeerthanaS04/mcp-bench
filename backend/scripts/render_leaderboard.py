"""
Render the MCP-Bench leaderboard from backend/results/*.jsonl.

Outputs:
  reports/leaderboard.md        human-readable, sorted by TSR
  backend/results/leaderboard.json   machine-readable aggregates

Result files are grouped by experimental condition via their filename:
  <model>.jsonl              baseline run (main leaderboard)
  <model>__d-<servers>.jsonl distractor run (RQ1 section)

Cost (CPST) is recomputed from tokens + the current PRICING table, so a price
edit is reflected just by re-running this script. Run:

    uv run python scripts/render_leaderboard.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from mcp_bench.metrics import aggregate, format_markdown_table
from mcp_bench.providers import LEADERBOARD_MODELS
from mcp_bench.runner import load_existing_results

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
RESULTS_DIR = BACKEND_DIR / "results"
REPORTS_DIR = REPO_ROOT / "reports"

METRIC_LEGEND = """\
**Metric legend** — TSR: task success rate · TSA(proxy): fraction of calls on an
allowed-server tool (meaningful only under distractors) · HCR: hallucinated-call
rate (lower better) · RR: recovery rate among runs with a tool error · AVR:
argument-validity rate · S2S: tool calls per successful task · CPST: USD cost per
successful task (list-price estimates — see providers.PRICING) · n: tasks run.
"""


def main() -> int:
    files = sorted(RESULTS_DIR.glob("*.jsonl"))
    if not files:
        print(f"no result files in {RESULTS_DIR}")
        return 1

    # The main leaderboard is just the locked 8-model set. Anything else with a
    # baseline file (e.g. llama-3.3-70b-groq) is a cross-provider RQ3 variant
    # and gets its own section, so partial / variant runs don't masquerade as
    # ranked results in the headline table.
    locked = set(LEADERBOARD_MODELS)

    ranked, cross_provider, distractor = [], [], []
    json_dump: dict[str, dict] = {}

    for path in files:
        records = load_existing_results(path)
        if not records:
            continue
        agg = aggregate(records)
        json_dump[path.stem] = asdict(agg)
        if "__d-" in path.stem:
            distractor.append((path.stem, agg))
        elif path.stem in locked:
            ranked.append((path.stem, agg))
        else:
            cross_provider.append((path.stem, agg))

    ranked.sort(key=lambda x: x[1].tsr, reverse=True)
    cross_provider.sort(key=lambda x: x[1].model)
    distractor.sort(key=lambda x: x[1].tsr, reverse=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [
        "# MCP-Bench leaderboard",
        "",
        f"_Generated {ts}. Programmatic ground truth; no LLM-as-judge._",
        "",
        "## Main leaderboard (baseline — only the task's required server exposed)",
        "",
        format_markdown_table([a for _, a in ranked]),
        "",
        METRIC_LEGEND,
    ]

    if cross_provider:
        out += [
            "",
            "## RQ3 — cross-provider (same logical model, different provider)",
            "",
            "The same Llama-3.3-70B-Instruct served by different providers. "
            "Compare TSR + HCR against the baseline `llama-3.3-70b-together` "
            "row above.",
            "",
            format_markdown_table([a for _, a in cross_provider]),
        ]

    if distractor:
        out += [
            "",
            "## RQ1 — distractor conditions (extra servers' tools exposed)",
            "",
            "Compare a model's TSA/TSR here against its baseline row above.",
            "",
            format_markdown_table([a for _, a in distractor]),
            "",
            "_Condition encoded in the row label suffix `__d-<servers>`._",
        ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS_DIR / "leaderboard.md"
    md_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    json_path = RESULTS_DIR / "leaderboard.json"
    json_path.write_text(json.dumps(json_dump, indent=2), encoding="utf-8")

    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    print(
        f"  ranked: {len(ranked)}  cross-provider: {len(cross_provider)}  "
        f"distractor: {len(distractor)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
