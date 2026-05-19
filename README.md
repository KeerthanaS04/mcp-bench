# MCP-Bench

An evaluation suite measuring how reliably open-source LLM agents use tools exposed through the **Model Context Protocol (MCP)**.

## What this is

MCP-Bench is a research benchmark, not just a leaderboard. We construct natural-language tasks that require an agent to use real MCP servers, then measure both **task success** and **how / where agents fail**.

See [RESEARCH.md](RESEARCH.md) for the research questions, and [METRICS.md](METRICS.md) for what we measure.

## Status

**Phase 0** — foundation. Not yet runnable end-to-end.

## Repository layout

```
mcp-bench/
├── backend/                  # agent loop, eval harness, tasks (Phases 1–2)
│   ├── src/mcp_bench/        # Python package
│   ├── tasks/                # task definitions, organized by MCP server
│   ├── scripts/              # smoke test and utility scripts
│   ├── sandbox/              # working dir for filesystem MCP server
│   ├── results/              # per-(model, task) outputs (gitignored)
│   ├── traces/               # full conversation traces (gitignored)
│   ├── pyproject.toml
│   └── .python-version
├── frontend/                 # Gradio app for Hugging Face Space (Phase 3)
│   ├── app.py
│   ├── pyproject.toml
│   ├── .python-version
│   └── README.md
├── reports/                  # technical report drafts (.md → .pdf)
├── RESEARCH.md               # research questions, hypotheses, prior-work table
├── METRICS.md                # metric definitions and formulas
├── .env.example              # API key template — copy to .env at this root
├── .gitignore
├── LICENSE                   # Apache 2.0
└── README.md                 # you are here
```

## Setup

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+, Git.

### 1. Configure environment (project root)

```powershell
cd C:\Users\KeerthanaS\projects\mcp-bench
Copy-Item .env.example .env
# Open .env in any editor and paste at least your NVIDIA_API_KEY
```

### 2. Set up the backend

```powershell
cd backend
uv sync
```

### 3. Verify Phase 0 plumbing

```powershell
# From inside backend/
uv run python scripts/smoke_test.py
```

Expected: three green **PASS** lines and "All checks passed."

## Phases (with cut-lines)

| Phase | Goal | Deliverable | Status |
|---|---|---|---|
| 0 | Foundation | repo scaffold, smoke test passes | in progress |
| 1 | Pilot | agent loop, 30 tasks, 3 MCP servers, 3 models | pending |
| 2 | Core benchmark | 150 tasks, 6 servers, 8 models, full metrics | pending |
| 3 | Analysis & publication | failure analysis, HF Space, dataset on HF Hub, draft report | pending |
| 4 | Stretch | multi-turn, adversarial, prompting ablations, workshop submission | pending |

## License

Apache 2.0 (code), CC-BY 4.0 (dataset, when released in Phase 3).
