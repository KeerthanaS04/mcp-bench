# MCP-Bench

A reliability benchmark for open-source LLM agents using the **Model Context Protocol (MCP)** — Anthropic's open standard (released November 2024) for connecting LLMs to external tools.

> 📄 **Read the full report:** [reports/mcp-bench-v0.1.md](reports/mcp-bench-v0.1.md)
> 🤗 **Dataset** (pending publish): [`huggingface.co/datasets/keerthanaSubru57/mcp-bench`](https://huggingface.co/datasets/keerthanaSubru57/mcp-bench)
> 🎛️ **Interactive leaderboard** (pending publish): [`huggingface.co/spaces/keerthanaSubru57/mcp-bench-leaderboard`](https://huggingface.co/spaces/keerthanaSubru57/mcp-bench-leaderboard)

---

## TL;DR

**The first programmatically-graded multi-provider benchmark for MCP tool-use reliability.** 8 models × 70 tasks × 6 MCP servers × 3 providers, 7 metrics, no LLM-as-judge.

### Leaderboard

| # | Model | TSR | HCR | RR | AVR | CPST (USD) |
|---|---|---|---|---|---|---|
| 1 | deepseek-v4-pro-together | **0.96** | 0.00 | 1.00 | 0.95 | $0.0020 |
| 2 | **gpt-oss-20b** | **0.93** | 0.00 | 0.93 | 0.79 | **$0.0005** |
| 3 | gpt-oss-120b | 0.92 | 0.00 | 0.91 | 0.92 | $0.0006 |
| 4 | qwen-3-next-80b | 0.86 | 0.00 | 0.60 | 0.87 | $0.0017 |
| 5 | llama-4-scout (Groq) | 0.82 | 0.00 | 0.60 | 0.93 | $0.0006 |
| 6 | llama-3.3-70b (Together) | 0.72 | **0.58** | 0.21 | 0.35 | $0.0033 |
| 7 | qwen-2.5-7b | 0.70 | 0.06 | 0.33 | 0.82 | $0.0008 |
| 8 | llama-3.1-8b | 0.49 | 0.01 | 0.40 | 0.45 | $0.0009 |

Always-current source: [reports/leaderboard.md](reports/leaderboard.md).

### Headline findings

- 🥇 **DeepSeek-V4-Pro tops the leaderboard** (TSR 0.96) — a model family one of the three providers couldn't even serve reliably.
- 💰 **GPT-OSS-20B is the Pareto value winner** — matches the 120B on success rate at the lowest cost per success on the board.
- 🚩 **Same Llama-3.3-70B weights ≠ same behavior across providers.** TSR 1.00 on Groq vs 0.77 on Together-Turbo; hallucinated-call rate jumps from **0% on Groq to 68% on Together-Turbo** on the apples-to-apples 22-task overlap. The provider serving stack — not the model — determines tool grounding.
- 🔁 **Llama family loop pathology** independently observed on three different (model, server, task) triples — model repeats one tool call until step cap.

Full RQ-by-RQ analysis: [`reports/mcp-bench-v0.1.md`](reports/mcp-bench-v0.1.md). Failure-mode clustering: [`reports/failure_patterns.md`](reports/failure_patterns.md). Cross-provider variance deep-dive: [`reports/provider_notes.md`](reports/provider_notes.md).

---

## Research questions

- **RQ1** — Tool-selection accuracy under N distractor tools
- **RQ2** — Error-recovery rate after MCP tool errors
- **RQ3** — Cross-provider variance for the same model
- **RQ4** — Cost per successful task (CPST)

Full framing in [RESEARCH.md](RESEARCH.md); metric definitions in [METRICS.md](METRICS.md).

---

## Repository layout

```
mcp-bench/
├── backend/
│   ├── src/mcp_bench/        # agent loop, MCP client pool, providers, metrics, runner (~700 LOC)
│   ├── tasks/                # 70 task definitions across 6 MCP servers
│   ├── scripts/              # smoke test, model validator, grid runner, leaderboard renderer,
│   │                         #   failure-mode clustering, provider variance analysis,
│   │                         #   postgres docker setup
│   ├── sandbox/              # working dir for filesystem / memory MCP servers
│   ├── results/              # per-(model, task) JSONL outputs (gitignored)
│   ├── traces/               # full conversation traces (gitignored)
│   └── pyproject.toml        # base + optional `analysis` dependency group
├── frontend/                 # Gradio app for the HF Space (Phase 3 build in progress)
├── reports/                  # leaderboard, technical report, failure patterns, provider notes
├── RESEARCH.md
├── METRICS.md
└── .env.example
```

---

## Quick start

**Prerequisites:** Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Node.js 20+, Docker Desktop (for postgres tasks), Git.

### 1. Configure environment

```powershell
cd C:\path\to\mcp-bench
Copy-Item .env.example .env
# Open .env and fill in the API keys you have. NVIDIA_API_KEY is enough to start;
# GROQ / TOGETHER / GITHUB / HF tokens unlock more models and more servers.
```

### 2. Install

```powershell
cd backend
uv sync                          # base install (runs the benchmark)
uv sync --extra analysis         # adds sentence-transformers + HDBSCAN (~2GB; needed for Phase 3 scripts)
```

### 3. Verify plumbing

```powershell
uv run python scripts/smoke_test.py
```

Expected: three green **PASS** lines (env loaded, NVIDIA reachable, filesystem MCP server spawns and lists tools).

### 4. Run one model

```powershell
# Run a single model over all 70 tasks (resumable)
uv run python -m mcp_bench.runner --model gpt-oss-20b --tasks all
```

Or just one server's tasks:
```powershell
uv run python -m mcp_bench.runner --model llama-3.1-8b --tasks sqlite
```

### 5. Run the whole grid

```powershell
uv run python scripts/run_grid.py
```

Iterates the locked 8-model leaderboard set. Fully resumable across rate-limit windows.

### 6. Render the leaderboard

```powershell
uv run python scripts/render_leaderboard.py
```

Writes [`reports/leaderboard.md`](reports/leaderboard.md) and `backend/results/leaderboard.json`.

### 7. (Optional) Phase 3 analysis

```powershell
uv run python scripts/cluster_failures.py     # → reports/failure_patterns.md
uv run python scripts/provider_variance.py    # → reports/provider_notes.md
```

### MCP server setup (only when you want those task sets)

- **github** — needs `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env` (read-only scope is enough; see `backend/scripts/servers.md`).
- **postgres** — needs Docker, then:
  ```powershell
  backend\scripts\setup_postgres.ps1
  ```
  Spins up a local Postgres container on port **5433** (chosen to not collide with any native Postgres on 5432) seeded with a small `employees / departments / salaries` schema.

---

## Project status

| Phase | Status |
|---|---|
| 0 — Foundation | ✅ done |
| 1 — Pilot (3 models × 30 tasks) | ✅ done |
| 2 — Core benchmark (8 models × 70 tasks × 6 servers, all 4 RQs instrumented) | ✅ done |
| 3 — Analysis & publication (failure analysis, HF Space, dataset release, report) | 🔄 in progress |
| 4 — Workshop submission (multi-turn, adversarial, ablations) | 🗓 future |

---

## Citation

If you use MCP-Bench, please cite:

```bibtex
@misc{mcp-bench-2026,
  title  = {MCP-Bench: A Reliability Benchmark for Open-Source LLM Agents Using the Model Context Protocol},
  author = {Keerthana S},
  year   = {2026},
  url    = {https://github.com/KeerthanaS04/mcp-bench},
  note   = {v0.1}
}
```

---

## License

- **Code:** [Apache 2.0](LICENSE)
- **Dataset** (when released): CC-BY 4.0
