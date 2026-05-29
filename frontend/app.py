"""
MCP-Bench — Gradio frontend for the Hugging Face Space.

Four tabs, all rendered from precomputed static artifacts in `data/`
(no live model calls, no API keys needed at runtime):

  1. Leaderboard       — sortable model x metric table
  2. Task explorer     — filter by server/difficulty/skill, view tasks
                         + per-model pass/fail matrix
  3. Failure analysis  — top failure patterns + representative examples
  4. Provider comparison — RQ3 cross-provider deep dive (Llama-3.3-70B)

Run locally:
    cd frontend
    python scripts/bundle.py     # (re)populate data/ from backend
    python app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# Load all bundled artifacts
# ---------------------------------------------------------------------------

def _load_json(name: str, default):
    p = DATA_DIR / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def _load_md(name: str, default: str) -> str:
    p = DATA_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else default


LEADERBOARD = _load_json("leaderboard.json", {})
TASKS = _load_json("tasks.json", [])
MATRIX = _load_json("per_task_results.json", {"models": [], "tasks": {}})
FAILURE_PATTERNS = _load_md(
    "failure_patterns.md",
    "_Failure patterns not bundled yet. Run `python scripts/bundle.py`._",
)
PROVIDER_NOTES = _load_md(
    "provider_notes.md",
    "_Provider notes not bundled yet. Run `python scripts/bundle.py`._",
)

LOCKED_MODELS = [
    "gpt-oss-120b", "gpt-oss-20b",
    "qwen-3-next-80b", "qwen-2.5-7b",
    "llama-3.3-70b-together", "llama-3.1-8b",
    "deepseek-v4-pro-together", "llama-4-scout-groq",
]

LEADERBOARD_COLUMNS = [
    "rank", "model", "n", "TSR", "TSA(proxy)", "HCR", "RR",
    "AVR", "S2S", "CPST($)", "mean steps", "calls",
]


# ---------------------------------------------------------------------------
# Tab 1 — Leaderboard
# ---------------------------------------------------------------------------

def leaderboard_df() -> pd.DataFrame:
    rows = []
    # Use only locked baseline models for the main table (exclude __d-* and
    # cross-provider variants, which get their own sections).
    for stem, agg in LEADERBOARD.items():
        if "__d-" in stem:
            continue
        if stem not in LOCKED_MODELS:
            continue
        rows.append(
            {
                "model": stem,
                "n": agg.get("n_tasks", 0),
                "TSR": round(agg.get("tsr", 0), 3),
                "TSA(proxy)": round(agg.get("tsa_proxy", 0), 3),
                "HCR": round(agg.get("hcr", 0), 3),
                "RR": round(agg["rr"], 3) if agg.get("rr") is not None else None,
                "AVR": round(agg.get("avr", 0), 3),
                "S2S": round(agg["s2s"], 2) if agg.get("s2s") is not None else None,
                "CPST($)": round(agg["cpst"], 4) if agg.get("cpst") is not None else None,
                "mean steps": round(agg.get("mean_steps", 0), 2),
                "calls": agg.get("total_tool_calls", 0),
            }
        )
    df = pd.DataFrame(rows).sort_values("TSR", ascending=False, ignore_index=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


# ---------------------------------------------------------------------------
# Tab 2 — Task explorer
# ---------------------------------------------------------------------------

ALL_SERVERS = sorted({t["server"] for t in TASKS}) or ["filesystem"]
ALL_DIFFICULTIES = ["easy", "medium", "hard"]
ALL_SKILLS = ["selection", "composition", "recovery", "ambiguity"]


def filter_tasks(servers: list[str], difficulties: list[str], skills: list[str]):
    servers = servers or ALL_SERVERS
    difficulties = difficulties or ALL_DIFFICULTIES
    skills = skills or ALL_SKILLS
    rows = []
    for t in TASKS:
        if t["server"] not in servers:
            continue
        if t["difficulty"] not in difficulties:
            continue
        if t["skill"] not in skills:
            continue
        per_model = MATRIX.get("tasks", {}).get(t["id"], {})
        n_pass = sum(1 for v in per_model.values() if v)
        n_run = len(per_model)
        rows.append(
            {
                "task_id": t["id"],
                "server": t["server"],
                "difficulty": t["difficulty"],
                "skill": t["skill"],
                "pass/run": f"{n_pass}/{n_run}" if n_run else "—",
                "prompt": (t["prompt"][:140] + "…") if len(t["prompt"]) > 140 else t["prompt"],
            }
        )
    return pd.DataFrame(rows)


def task_detail(task_id: str | None) -> str:
    if not task_id:
        return "_Select a task above to see its full prompt and per-model results._"
    t = next((x for x in TASKS if x["id"] == task_id), None)
    if t is None:
        return f"Unknown task id: `{task_id}`."
    per_model = MATRIX.get("tasks", {}).get(task_id, {})

    lines = [
        f"### `{task_id}`",
        f"**Server:** {t['server']} &nbsp; **Difficulty:** {t['difficulty']} &nbsp; **Skill:** {t['skill']}",
        f"**Tags:** `{', '.join(t.get('tags', []))}`",
        "",
        "**Prompt:**",
        "",
        f"> {t['prompt']}",
        "",
        "**Per-model outcomes:**",
        "",
        "| model | result |",
        "|---|---|",
    ]
    for model in sorted(per_model):
        ok = per_model[model]
        lines.append(f"| `{model}` | {'✅ pass' if ok else '❌ fail'} |")
    if not per_model:
        lines.append("| _(no recorded results yet)_ | — |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tab 4 — Provider comparison chart
# ---------------------------------------------------------------------------

def provider_chart_df() -> pd.DataFrame:
    """For the Llama-3.3-70B cross-provider trio, render a small DF gradio
    can plot as a bar chart.
    """
    rows = []
    for stem, agg in LEADERBOARD.items():
        if not stem.startswith("llama-3.3-70b"):
            continue
        if "__d-" in stem:
            continue
        provider = (
            "Together-Turbo"
            if stem.endswith("-together")
            else "Groq"
            if stem.endswith("-groq")
            else "NVIDIA"
        )
        rows.append(
            {
                "provider": provider,
                "TSR": round(agg.get("tsr", 0), 3),
                "HCR": round(agg.get("hcr", 0), 3),
                "AVR": round(agg.get("avr", 0), 3),
                "n": agg.get("n_tasks", 0),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

HEADER_MD = """
# MCP-Bench

A reliability benchmark for open-source LLM agents using the **Model Context Protocol**.
8 models × 70 tasks × 6 MCP servers · 7 metrics · programmatic ground truth, no LLM-as-judge.

- 📦 [Code on GitHub](https://github.com/KeerthanaS04/mcp-bench)
- 🤗 [Task dataset](https://huggingface.co/datasets/keerthanaSubru57/mcp-bench)
- 📄 [Technical report](https://github.com/KeerthanaS04/mcp-bench/blob/main/reports/mcp-bench-v0.1.md)
"""

with gr.Blocks(title="MCP-Bench leaderboard", theme=gr.themes.Soft()) as demo:
    gr.Markdown(HEADER_MD)

    with gr.Tabs():
        with gr.TabItem("Leaderboard"):
            gr.Markdown(
                "Baseline runs (each task's *required* server only). "
                "Sort by clicking column headers."
            )
            gr.Dataframe(value=leaderboard_df, interactive=False, wrap=True)

        with gr.TabItem("Task explorer"):
            gr.Markdown(
                "Filter the 70-task dataset and see which models pass each task."
            )
            with gr.Row():
                f_servers = gr.CheckboxGroup(
                    ALL_SERVERS, value=ALL_SERVERS, label="Server"
                )
                f_difficulty = gr.CheckboxGroup(
                    ALL_DIFFICULTIES, value=ALL_DIFFICULTIES, label="Difficulty"
                )
                f_skill = gr.CheckboxGroup(
                    ALL_SKILLS, value=ALL_SKILLS, label="Skill"
                )
            task_table = gr.Dataframe(
                value=filter_tasks(ALL_SERVERS, ALL_DIFFICULTIES, ALL_SKILLS),
                interactive=False,
                wrap=True,
                label="Tasks",
            )
            for f in (f_servers, f_difficulty, f_skill):
                f.change(filter_tasks, [f_servers, f_difficulty, f_skill], task_table)

            picker = gr.Dropdown(
                choices=[t["id"] for t in TASKS],
                label="Task detail (pick an id to see full prompt + per-model outcomes)",
                value=None,
            )
            detail_md = gr.Markdown(task_detail(None))
            picker.change(task_detail, picker, detail_md)

        with gr.TabItem("Failure analysis"):
            gr.Markdown(
                "Failed traces were embedded with `all-MiniLM-L6-v2` and clustered "
                "with HDBSCAN; the top patterns are featured here. Cluster names are "
                "heuristic — rename in the technical report."
            )
            gr.Markdown(FAILURE_PATTERNS)

        with gr.TabItem("Provider comparison"):
            gr.Markdown("## RQ3 — same model, three providers")
            gr.Markdown(
                "Quick numerical comparison for Llama-3.3-70B-Instruct across the "
                "providers we have full data for. The NVIDIA variant is documented "
                "qualitatively in the deep-dive below — it degenerate-loops on every "
                "task and never terminates."
            )
            gr.Dataframe(
                value=provider_chart_df,
                interactive=False,
                wrap=True,
            )
            gr.BarPlot(
                value=provider_chart_df,
                x="provider",
                y="TSR",
                title="TSR by provider (Llama-3.3-70B-Instruct)",
                height=300,
            )
            gr.BarPlot(
                value=provider_chart_df,
                x="provider",
                y="HCR",
                title="HCR — hallucinated tool calls (lower is better)",
                height=300,
            )
            gr.Markdown("## Deep-dive")
            gr.Markdown(PROVIDER_NOTES)


if __name__ == "__main__":
    demo.launch()
