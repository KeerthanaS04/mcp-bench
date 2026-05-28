# MCP-Bench leaderboard

_Generated 2026-05-28 20:57 UTC. Programmatic ground truth; no LLM-as-judge._

## Main leaderboard (baseline — only the task's required server exposed)

| model | n | TSR | TSA(proxy) | HCR | RR | AVR | S2S | CPST($) | mean steps | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4-pro-together | 50 | 0.96 | 1.00 | 0.00 | 1.00 | 0.95 | 1.8 | 0.0020 | 2.7 | 93 |
| gpt-oss-20b | 67 | 0.93 | 1.00 | 0.00 | 0.93 | 0.79 | 2.0 | 0.0005 | 3.0 | 137 |
| gpt-oss-120b | 66 | 0.92 | 1.00 | 0.00 | 0.91 | 0.92 | 2.0 | 0.0006 | 3.0 | 134 |
| qwen-3-next-80b | 70 | 0.86 | 1.00 | 0.00 | 0.60 | 0.87 | 1.9 | 0.0017 | 3.0 | 141 |
| llama-4-scout-groq | 44 | 0.84 | 1.00 | 0.00 | 0.60 | 0.92 | 1.5 | 0.0006 | 2.5 | 65 |
| llama-3.3-70b-together | 50 | 0.72 | 0.55 | 0.58 | 0.21 | 0.35 | 1.4 | 0.0033 | 3.7 | 137 |
| qwen-2.5-7b | 50 | 0.70 | 1.00 | 0.06 | 0.33 | 0.82 | 1.7 | 0.0008 | 2.2 | 90 |
| llama-3.1-8b | 38 | 0.55 | 1.00 | 0.01 | 0.43 | 0.37 | 2.7 | 0.0006 | 3.8 | 108 |

**Metric legend** — TSR: task success rate · TSA(proxy): fraction of calls on an
allowed-server tool (meaningful only under distractors) · HCR: hallucinated-call
rate (lower better) · RR: recovery rate among runs with a tool error · AVR:
argument-validity rate · S2S: tool calls per successful task · CPST: USD cost per
successful task (list-price estimates — see providers.PRICING) · n: tasks run.


## RQ3 — cross-provider (same logical model, different provider)

The same Llama-3.3-70B-Instruct served by different providers. Compare TSR + HCR against the baseline `llama-3.3-70b-together` row above.

| model | n | TSR | TSA(proxy) | HCR | RR | AVR | S2S | CPST($) | mean steps | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| llama-3.3-70b-groq | 22 | 1.00 | 1.00 | 0.00 | 1.00 | 0.88 | 1.5 | 0.0025 | 2.5 | 32 |

## RQ1 — distractor conditions (extra servers' tools exposed)

Compare a model's TSA/TSR here against its baseline row above.

| model | n | TSR | TSA(proxy) | HCR | RR | AVR | S2S | CPST($) | mean steps | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4-pro-together | 1 | 1.00 | 1.00 | 0.00 | - | 1.00 | 1.0 | 0.0076 | 2.0 | 1 |
| gpt-oss-120b | 50 | 0.96 | 1.00 | 0.00 | 1.00 | 0.96 | 2.0 | 0.0024 | 3.0 | 102 |
| gpt-oss-20b | 48 | 0.94 | 1.00 | 0.00 | 0.83 | 0.82 | 1.7 | 0.0016 | 2.8 | 88 |
| llama-4-scout-groq | 24 | 0.92 | 1.00 | 0.00 | 1.00 | 0.91 | 1.5 | 0.0022 | 2.5 | 35 |
| qwen-3-next-80b | 49 | 0.90 | 1.00 | 0.00 | 0.75 | 0.95 | 2.0 | 0.0047 | 3.0 | 98 |
| qwen-2.5-7b | 50 | 0.76 | 0.99 | 0.08 | 0.33 | 0.83 | 1.3 | 0.0048 | 2.1 | 71 |
| gpt-oss-120b | 4 | 0.75 | 1.00 | 0.00 | - | 1.00 | 1.7 | 0.0011 | 2.5 | 6 |
| llama-3.3-70b-together | 46 | 0.67 | 0.60 | 0.40 | 0.29 | 0.46 | 1.8 | 0.0164 | 3.2 | 101 |
| llama-3.1-8b | 38 | 0.47 | 0.94 | 0.01 | 0.17 | 0.40 | 1.7 | 0.0045 | 3.5 | 97 |

_Condition encoded in the row label suffix `__d-<servers>`._
