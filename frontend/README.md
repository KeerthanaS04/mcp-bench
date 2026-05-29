---
title: MCP-Bench Leaderboard
emoji: 📊
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 5.13.0
python_version: "3.12"
app_file: app.py
pinned: false
license: apache-2.0
---

# MCP-Bench · Leaderboard

Interactive Gradio frontend for [MCP-Bench](https://github.com/KeerthanaS04/mcp-bench) —
a reliability benchmark for open-source LLM agents using the Model Context
Protocol. **8 models × 70 tasks × 6 MCP servers**, 7 metrics, programmatic
ground truth (no LLM-as-judge).

## Tabs

- **Leaderboard** — sortable model × metric table (TSR, HCR, RR, AVR, S2S, CPST, …)
- **Task explorer** — filter the 70-task dataset by server/difficulty/skill and inspect each task's per-model outcomes
- **Failure analysis** — top failure patterns surfaced by HDBSCAN clustering of failed traces
- **Provider comparison** — RQ3 deep dive: the same Llama-3.3-70B weights across three providers

## Local run

```powershell
cd frontend
uv sync
python scripts/bundle.py    # populate data/ from backend artifacts
python app.py               # http://127.0.0.1:7860
```

## Deploy to Hugging Face Space

The repository root has the YAML frontmatter that HF Spaces expects (see top
of this file). To publish:

```powershell
# from frontend/
python scripts/bundle.py
git init           # if not already
git remote add space https://huggingface.co/spaces/keerthanaSubru57/mcp-bench-leaderboard
git add app.py requirements.txt README.md data/ scripts/
git commit -m "MCP-Bench v0.1 leaderboard"
git push space main
```

(See the project root README for the end-to-end publishing path including
the dataset upload.)

## What gets bundled

`scripts/bundle.py` reads from `../backend/` and `../reports/` and writes:

- `data/leaderboard.json` — full aggregates per model
- `data/tasks.json` — the 70-task dataset (flattened, prompts only)
- `data/per_task_results.json` — task_id × model success matrix
- `data/failure_patterns.md` — top failure clusters
- `data/provider_notes.md` — RQ3 cross-provider analysis

The Space is **read-only** — no model APIs are called at runtime.

## License

Code: Apache 2.0 · Dataset: CC-BY 4.0
