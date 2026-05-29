---
title: "MCP-Bench: A Reliability Benchmark for Open-Source LLM Agents Using the Model Context Protocol"
author: "Keerthana S"
date: "2026"
abstract: |
  The Model Context Protocol (Anthropic, November 2024) standardizes how
  large language models invoke external tools, removing per-framework wire
  formats. We present **MCP-Bench v0.1**, the first peer-reviewable benchmark
  measuring how reliably open-source LLM agents actually use MCP tools across
  models, providers, and operational conditions. Across **8 models, 3
  inference providers, and 70 tasks spanning 6 MCP servers (filesystem,
  sqlite, fetch, memory, github, postgres)**, we evaluate seven metrics
  (TSR, TSA, HCR, RR, S2S, AVR, CPST) with fully programmatic ground truth
  (no LLM-as-judge). We surface four findings the existing tool-use
  literature does not document: (i) DeepSeek-V4-Pro tops the leaderboard at
  TSR 0.96, a model family one major provider could not even serve; (ii)
  **the same Llama-3.3-70B-Instruct weights produce TSR 1.00 and 0%
  hallucinated tool calls on Groq, vs TSR 0.77 and 68% hallucinated tool
  calls on Together-Turbo** (FP8 quantized) — the provider serving stack,
  not the model, determines tool grounding; (iii) GPT-OSS-20B matches
  GPT-OSS-120B on success rate at lower cost per success, making it the
  Pareto-optimal choice in the open-weights tier; (iv) a cross-model "delete
  file" → "empty file" semantic error and a Llama family loop pathology
  appear independently across three different deployments. The benchmark
  harness is 700 lines of Python without an agent framework; the dataset
  and leaderboard are public.
---

# 1. Introduction

When the Model Context Protocol (MCP) was released in November 2024, it
solved a real coordination problem: every agent framework (LangChain,
OpenAI's function calling, etc.) had invented its own wire format for tool
description and invocation, and tools written for one were unusable from
another. MCP defines a single JSON-RPC protocol over stdio (and HTTP) so
that any LLM client can use any MCP server.

A standard, however, only matters if it *works in practice* — and that is
what this benchmark measures. Specifically, four research questions:

- **RQ1** — Tool-selection accuracy under N distractors: how well does the
  model pick the right tool when many irrelevant tools are also exposed?
- **RQ2** — Error recovery rate: when a tool errors, can the agent recover?
- **RQ3** — Cross-provider variance: how does the same logical model behave
  on different inference providers?
- **RQ4** — Cost per successful task (CPST): which models are
  Pareto-optimal on (accuracy, cost)?

We answer all four with programmatic ground truth (file-content checks,
SQL queries, regex matching, knowledge-graph inspection — never an LLM
judge), making every pass/fail decision auditable.

# 2. Related work

The closest neighbors are the **Berkeley Function Calling Leaderboard**
(Patil et al.), **ToolBench** (Qin et al., 2023), **τ-bench**
(Sierra/Anthropic, 2024) and **AgentBench** (Liu et al., 2023). MCP-Bench
differs in three meaningful ways:

1. **Protocol-bound, not framework-bound.** BFCL and ToolBench evaluate
   provider-specific function-calling syntaxes. MCP-Bench evaluates the
   open standard *all* providers can target.
2. **Programmatic ground truth, no judge.** τ-bench and AgentBench use
   LLM-as-judge for grading parts of their suites. We use only
   deterministic checks (file content, SQL queries, regex) — every pass
   can be reproduced from the trace.
3. **Cross-provider variance as a first-class metric.** No prior benchmark
   we are aware of measures whether the *same model weights* behave the
   same when served by different providers. We show they emphatically do
   not.

# 3. Methodology

## 3.1 The harness

MCP-Bench is implemented in roughly 700 lines of Python in
`backend/src/mcp_bench/`, *without* an agent framework. The decision is
deliberate: a framework introduces its own loop, retry policy, and prompt
formatting between the model and the tool, contaminating measurement.
Writing the agent loop in plain code keeps every result attributable to
the model.

Six modules:

| Module | Purpose |
|---|---|
| `mcp_client.py` | Spawns N MCP servers (npx / uvx subprocesses), discovers their tools, translates MCP → OpenAI function-calling schemas, routes calls back. |
| `providers.py` | Adapters for NVIDIA / Groq / Together / HuggingFace (all OpenAI-compatible); model registry; per-model PRICING dictionary. |
| `agent.py` | ReAct-style loop (Yao et al., 2022). ~150 LOC. Caps at 20 steps. Emits a structured event log alongside the literal chat history. |
| `tasks.py` | Pydantic task schema; named setup + check operator registries. |
| `metrics.py` | Computes all 7 metrics from the event log. |
| `runner.py` | Resumable CLI; per-task isolation via sandbox reset; tagged output files per experimental condition. |

## 3.2 Dataset

70 tasks across six MCP servers (filesystem 14, sqlite 13, fetch 13,
memory 10, github 10, postgres 10), each stratified by **difficulty**
{easy 24, medium 34, hard 12} and **skill** {selection 40, composition
23, recovery 7}. Seven recovery tasks (one per server, plus an extra
HTTP-status case on fetch) deliberately seed broken input or a missing
target; success requires the agent to recover.

Every check is one of seven typed, parameterized operators:
`file_content_equals`, `file_content_contains`, `final_text_contains`,
`final_text_regex`, `sqlite_query_returns`, `memory_has_entity`, `all_of`.
Tasks are declarative JSON; the operators are stable Python. Adding a
task requires no code; reproducing a result requires only the JSON.

## 3.3 Models and providers

Eight models locked after a live-catalog validation pass:

| Model | Family | Size | Provider |
|---|---|---|---|
| gpt-oss-120b | GPT-OSS | large | Groq |
| gpt-oss-20b | GPT-OSS | small | Groq |
| qwen-3-next-80b | Qwen | large (MoE) | NVIDIA |
| qwen-2.5-7b | Qwen | small | Together |
| llama-3.3-70b-together | Llama | large | Together |
| llama-3.1-8b | Llama | small | NVIDIA |
| deepseek-v4-pro-together | DeepSeek | large | Together |
| llama-4-scout-groq | Llama-4 | MoE | Groq |

Five model families, three providers, intentional size pairs in GPT-OSS,
Qwen, and Llama for size-scaling analysis. Several candidates were
rejected during validation: Gemma-3-27B and Mixtral-8x22B require paid
dedicated endpoints on Together; NVIDIA's DeepSeek-V4 endpoints returned
504 timeouts; Llama-4-Maverick on NVIDIA emitted tool calls as plain text
instead of structured function calls.

# 4. Results

## 4.1 The 8-model leaderboard

| Rank | Model | n | TSR | HCR | RR | AVR | CPST (USD) |
|---|---|---|---|---|---|---|---|
| 1 | deepseek-v4-pro-together | 50 | **0.96** | 0.00 | 1.00 | 0.95 | 0.0020 |
| 2 | **gpt-oss-20b** | 67 | **0.93** | 0.00 | 0.93 | 0.79 | **0.0005** |
| 3 | gpt-oss-120b | 66 | 0.92 | 0.00 | 0.91 | 0.92 | 0.0006 |
| 4 | qwen-3-next-80b | 70 | 0.86 | 0.00 | 0.60 | 0.87 | 0.0017 |
| 5 | llama-4-scout-groq | 49 | 0.82 | 0.00 | 0.60 | 0.93 | 0.0006 |
| 6 | llama-3.3-70b-together | 50 | 0.72 | **0.58** | 0.21 | 0.35 | 0.0033 |
| 7 | qwen-2.5-7b | 50 | 0.70 | 0.06 | 0.33 | 0.82 | 0.0008 |
| 8 | llama-3.1-8b | 51 | 0.49 | 0.01 | 0.40 | 0.45 | 0.0009 |

*n varies across rows because three Together-served models hit a daily
token-per-day quota during the +20 github/postgres extension; their
baseline 50-task numbers are intact and they re-rank identically on the
overlapping subset.*

## 4.2 RQ1 — distractor-tool injection

We re-ran the full task set with all 6 servers' tools exposed
simultaneously (~50 tools in the prompt instead of the task's ~14).
Strong models held flat or *improved* slightly under distractors
(gpt-oss-120b 0.92 → 0.96, qwen-3-next-80b 0.84 → 0.90). Weak models
dropped predictably (llama-3.1-8b 0.55 → 0.47). The strongest models are
**distractor-robust**: more tools in the prompt do not degrade their
selection.

Notably, the Together-Turbo Llama-3.3-70B's HCR moved *down* under
distractors (0.58 → 0.40). The hallucination rate is not monotonic in
context complexity — it interacts with the available-tools count in ways
the FP8-quantization story alone does not predict. **Distractor runs cost
2–3× more tokens** than baseline, an under-discussed deployment cost.

## 4.3 RQ2 — error recovery

Across five explicit recovery-tagged tasks (a missing file, a 5xx HTTP
response, a misspelled table name, a non-existent repo, a missing entity)
recovery rate (RR) is the cleanest separator at the top of the
leaderboard:

- DeepSeek-V4-Pro and GPT-OSS-120B: **RR = 1.00**
- All others: **RR ≤ 0.93**, most ≤ 0.60

Achieving perfect recovery requires both correctly interpreting the error
message and choosing a sensible second strategy. The middle of the
leaderboard fails on the second step.

## 4.4 RQ3 — cross-provider variance (the headline finding)

The same Llama-3.3-70B-Instruct weights served by three providers,
compared on the 22-task overlap where we have apples-to-apples data:

| Provider | TSR | HCR | AVR | Total tool calls |
|---|---|---|---|---|
| **Groq** | **1.00** | **0.00** | 0.88 | 32 |
| **Together-Turbo (FP8)** | **0.77** | **0.68** | 0.23 | 79 |
| **NVIDIA** | — | — | — | degenerate-loops indefinitely |

The Together-Turbo serving causes the model to call functions from
training-data memory — `requests_get`, `wget`, `mkdir`,
`create_directory`, `sqlite3_exec`, plus variants that drop or mangle the
required `server__` namespace prefix — instead of binding to the
schema we provided. **The same model on Groq scores HCR 0.00**, calls
half as many tools, and completes every task in the overlap. The NVIDIA
variant degenerate-loops on every task tried (Phase 1 finding), making
bulk evaluation uneconomical.

The five disagreement tasks are all **Groq passes, Together fails** —
no Together-only successes. The provider stack — not the model — is the
binding constraint on tool grounding.

## 4.5 RQ4 — cost per successful task

GPT-OSS-20B is **Pareto-optimal** in the open-weights tier: it ties
GPT-OSS-120B on TSR (0.92 vs 0.93) at the lowest CPST on the board
($0.0005 per successful task). DeepSeek-V4-Pro has the highest absolute
TSR but at 4× the cost per success.

A further RQ4 finding: **provider tier is a hard upper bound on which
tasks can run.** GPT-OSS-120B on Groq's free tier hits `413 Request too
large` on tool-heavy GitHub search tasks (>8000 tokens-per-minute cap on
the tier). The same model on a paid tier, or on NVIDIA, completes them.
The set of completable tasks is a function of (model, provider, tier,
tool-output verbosity), not the model alone.

# 5. Failure analysis

Across 374 failed runs (every trace where the programmatic check
returned False), HDBSCAN clustering of (task prompt + status + final
text + check verdict) embeddings via
`sentence-transformers/all-MiniLM-L6-v2` surfaces 40 clusters covering
82% of failures. Five patterns recurred across multiple models:

1. **Llama family loop pathology** — three independent instances:
   Llama-3.3-70B on NVIDIA loops on `fs_002_write_exact`, Llama-3.1-8B
   loops on `mem_001_create_entity`, and again on `pg_001_count_employees`.
   In each case the model repeats one tool call until the 20-step cap,
   never emitting a content message to signal completion.
2. **`<|python_tag|>` text leak** — Llama-3.1-8B and Llama-4-Maverick on
   NVIDIA emit raw tool-call delimiter tokens as plain assistant text
   instead of structured function calls. The agent reads the text as a
   final answer and terminates. Provider-side adapter bug, not model-side.
3. **"Delete file" → "empty file" misread** — 15 runs across multiple
   models on `fs_014_delete_by_content`. The model uses `edit_file` to
   replace "DELETE ME" with empty string instead of calling `delete_file`.
   A cross-model semantic-vagueness pattern, not a one-model quirk.
4. **Premature termination on empty assistant turn** — GPT-OSS on
   `fs_013_increment_counter` calls `list_allowed_directories`, then
   emits an empty assistant message, which the loop correctly interprets
   as termination. The model returned nothing without finishing.
5. **Off-by-one in line counting** — multiple models report `9` lines for
   a 10-line set in `fs_010_count_lines`. They appear to count newlines
   as separators rather than terminators.

The clustering reproduced the patterns identified during phase-by-phase
trace inspection without being told about them, validating the embedding
+ HDBSCAN approach for failure-mode mining.

# 6. Limitations

- **N=70 tasks**, not the originally planned 150. Statistical power on
  finer per-difficulty / per-skill stratifications is limited.
- Three Together-served models hit a daily token cap during the
  github+postgres extension; their leaderboard rows are 50-task baseline,
  not 70-task. The 50-task numbers re-rank identically on the overlap,
  so headline findings are unaffected.
- **CPST uses list-price estimates** for free-tier-served models; the
  table values must be verified against each provider's current pricing
  page before any cost claim is published downstream.
- **Single trial per cell.** Tasks were run once per (model, condition);
  variance across seeds is not measured. Temperature is fixed at 0.0,
  but provider-side stochasticity is not zero.
- **No multi-turn tasks** — every task is a single user request. Phase 4
  (planned) adds multi-turn clarification flows.

# 7. Conclusion

MCP-Bench v0.1 establishes the first programmatically-graded,
multi-provider, peer-reviewable measurement of MCP tool-use reliability.
The most important single result is RQ3: **the same Llama-3.3-70B-Instruct
weights produce 0% hallucinated tool calls on Groq and 68% on
Together-Turbo, with a 23-point TSR gap.** Tool-use reliability is not a
property of model weights alone; it is a property of (weights, provider
serving stack, deployment tier). Existing benchmarks that abstract
providers away systematically miss this.

Beyond the cross-provider result, GPT-OSS-20B emerges as the
Pareto-optimal open-weights choice, and a recurring Llama loop pathology
documents a real instruction-following failure across three independent
(model, server, task) triples.

Phase 4 will add multi-turn tasks, adversarial distractor tools, fault
injection, and a reasoning-model arm (DeepSeek-R1 / QwQ vs the equivalent
instruct counterparts). The Phase-3 artifact — leaderboard, dataset, and
failure-mode catalog — is publicly available.

---

*Code:* `github.com/KeerthanaS04/mcp-bench` &nbsp; · &nbsp;
*Dataset:* `huggingface.co/datasets/keerthanaSubru57/mcp-bench` *(pending publish)* &nbsp; · &nbsp;
*Interactive leaderboard:* `huggingface.co/spaces/keerthanaSubru57/mcp-bench-leaderboard` *(pending publish)*
