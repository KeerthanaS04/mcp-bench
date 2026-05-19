# MCP-Bench: Research framing

## Motivation

The Model Context Protocol (MCP), released by Anthropic in November 2024, is becoming a de-facto standard for connecting LLMs to external tools and data sources. Despite rapid adoption, **no peer-reviewed benchmark exists** for measuring how reliably agents use MCP-exposed tools. Existing agent benchmarks (BFCL, ToolBench, τ-bench, AgentBench) test isolated function calls or proprietary tool wrappers — none measure agent behavior against the actual MCP protocol with real, community-maintained servers.

MCP-Bench fills that gap.

## Research questions

### RQ1 — Tool-selection accuracy under distractors

When an agent has access to N MCP tools but only one (or a specific subset) is correct for the task, how often does it select the right tool? How does accuracy degrade as N increases?

**Hypothesis:** Selection accuracy decreases monotonically with tool count, but the slope varies by model — instruction-tuned models with explicit tool-use training degrade more gracefully than vanilla chat models.

### RQ2 — Error recovery

When an MCP tool returns an error (wrong arguments, resource not found, transient failure), does the agent recover by adjusting its approach, or does it loop / give up / hallucinate around the error?

**Hypothesis:** Recovery rate is weakly correlated with base-model size and more strongly tied to specific tool-use training. Reasoning-time models (R1, QwQ) show meaningfully better recovery than instruct models of similar size.

### RQ3 — Cross-provider variance

The same open-source model served by different inference providers (NVIDIA API, Groq, Together AI) often uses different default system prompts, sampling parameters, and quantizations. How much does provider choice change benchmark results?

**Hypothesis:** Variance is non-trivial (>5 percentage points absolute on success rate for at least one model), implying benchmarks must specify the provider, not just the model. This is a methodological finding for the agent-eval field.

### RQ4 — Cost-per-successful-task

Combining token cost and success rate, what is the practical efficiency frontier across models?

**Hypothesis:** The Pareto frontier is broader than common discourse suggests — small open-source models (Llama-3.1-8B, Qwen-2.5-7B) are competitive with 70B+ models on simple tool-use tasks at 10–100× lower cost.

## Scope

**In scope (v0.1):** single-agent, single-turn tasks; English-language instructions; programmatically verifiable outcomes; 6 official MCP servers (filesystem, sqlite, fetch, github, memory, postgres).

**Out of scope (deferred to v0.2+):** multi-agent coordination; multilingual instructions; subjective tasks requiring human eval; non-MCP tool protocols (OpenAI function-calling, plugins).

## Comparison to prior work

| Benchmark | Tool protocol | # tools | Real tools | Measures recovery | Multi-provider |
|---|---|---|---|---|---|
| BFCL | OpenAI functions | ~50 abstract | No | No | No |
| ToolBench | REST APIs | 16,000+ | Partial | No | No |
| τ-bench | Custom | 1 (per env) | Yes | No | No |
| AgentBench | Various | Variable | Yes | Partial | No |
| **MCP-Bench (this work)** | **MCP** | **6 servers, ~30 tools** | **Yes** | **Yes** | **Yes** |

## What we are explicitly not claiming

- Not a measurement of "general agent capability" — specific to MCP-style tool use.
- Programmatic ground truth means we cannot evaluate open-ended tasks. This is a deliberate limitation that buys us trustworthy numbers.
- v0.1 uses single-turn task formulations; multi-turn dialogue is left for future work.

## Threats to validity

- **Task-design bias:** tasks we hand-write may favor patterns current models handle well. *Mitigation:* ≥10% of tasks are written with explicit failure expectations; we report expected-failure rate as a sanity check.
- **MCP server bugs:** failures may reflect server issues rather than agent behavior. *Mitigation:* smoke-test every server before each eval run; pin server versions; document server bugs encountered.
- **Provider rate limits:** may skew results if some models run in degraded modes. *Mitigation:* log every request and flag throttled responses; rerun affected tasks.
- **Sampling stochasticity:** single runs at non-zero temperature are noisy. *Mitigation:* temperature=0 for the headline numbers; report sampling-variance ablation on a subset.

## Cold-emailable findings the report should produce

By the end of Phase 3, the technical report should make at least 3 of the following concrete claims, each backed by data:

- "Model X has the highest tool-selection accuracy but the worst recovery rate."
- "Provider P changes Model Y's success rate by Z points compared to provider Q."
- "The top failure mode is W, accounting for V% of failed runs across all models."
- "Reasoning model R outperforms similarly-sized instruct model I by S points on multi-step tasks."
- "On simple tasks, small model M at cost C achieves N% of large model L's success rate at C/10."

These are the cold-email-worthy results that turn this from a leaderboard into a research artifact.
