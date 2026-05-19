# MCP-Bench: Metric definitions

All metrics are computed per (model, task) pair and aggregated to (model) level. Aggregation is mean unless otherwise noted.

## Primary metrics

### Task Success Rate (TSR)

Binary outcome per task: did the agent's final state match the ground-truth specification?

```
TSR(model) = (# tasks where success_check(final_state) == True) / (# tasks)
```

Ground truth is computed programmatically per task type:
- **Filesystem tasks:** assert file contents or paths match expected.
- **SQLite tasks:** assert DB state (row counts, specific row values) matches expected.
- **Fetch tasks:** assert extracted information matches a pinned reference snapshot.

**No LLM-as-judge is used in v0.1.** This buys us trust at the cost of task expressivity.

### Tool-Selection Accuracy (TSA)

Of all tool calls made by the agent, what fraction were on the "correct" tool for the current sub-goal?

Each task specifies a set of valid tools per step. A call is correct if `(tool_name, sub_goal_index)` is in the valid set.

```
TSA(model) = (# correct tool calls) / (# total tool calls)
```

For tasks with a single valid tool, TSA reduces to per-call accuracy. For tasks where multiple tools are valid at each step, any valid choice counts as correct.

### Hallucinated Call Rate (HCR)

A tool call is *hallucinated* if it references:
- A tool name not in the agent's available toolset, **or**
- An argument name not in the tool's schema, **or**
- An argument value of clearly wrong type (e.g., dict where string expected).

```
HCR(model) = (# hallucinated calls) / (# total tool calls)
```

Lower is better. Distinct from TSA — a call can be on the wrong tool but well-formed.

### Recovery Rate (RR)

Restricted to runs that experienced at least one tool error.

```
RR(model) = (# runs with ≥1 error that ended in success) / (# runs with ≥1 error)
```

A "tool error" is any tool call that returned an MCP error response. RR isolates: given that something went wrong, did the agent recover?

## Secondary metrics

### Steps-to-Success (S2S)

For successful runs only: number of tool calls before the final answer.

```
S2S(model) = mean(# tool calls in successful runs)
```

Reported alongside TSR — a model with high TSR but high S2S is inefficient.

### Cost per Successful Task (CPST) — supports RQ4

```
CPST(model) = sum(input_tokens × input_price + output_tokens × output_price)
              / (# successful tasks)
```

Token counts logged per call; per-provider prices stored in `src/mcp_bench/providers.py`. Reported in USD per success. Lower is better.

### Argument Validity Rate (AVR)

Of all tool calls, what fraction had arguments that the MCP server accepted (i.e., didn't return a validation error)?

```
AVR(model) = (# tool calls accepted by server) / (# total tool calls)
```

Lower than TSA in practice — a call can be on the right tool but with bad arguments.

## Per-RQ aggregation

| RQ | Headline metric | Stratification |
|---|---|---|
| RQ1 (Tool selection under distractors) | TSA | by # tools available (3, 6, 9, 15) |
| RQ2 (Error recovery) | RR | also report mean recovery attempts before success |
| RQ3 (Provider variance) | std(TSR) across providers | per fixed model |
| RQ4 (Cost) | CPST + Pareto frontier of (TSR, CPST) | across all model × provider pairs |

## What we explicitly do not measure (v0.1)

- **Subjective output quality** — would require human or LLM judge; out of scope.
- **Latency** — varies by provider load and is not the model's responsibility.
- **Multi-turn coherence** — out of scope until v0.2.
- **Safety / harmful tool use** — orthogonal scope; reference work elsewhere.
