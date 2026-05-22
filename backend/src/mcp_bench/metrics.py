"""
Compute MCP-Bench metrics from agent traces.

Two layers:
  * compute_per_task(task, trace, available_tool_names) -> PerTaskMetrics
        Pure-function: takes one task + one trace, returns counters.
        The `success` flag comes from running the task's check op separately
        (in the runner) and is attached afterward via .with_success().

  * aggregate(per_task_results) -> ModelMetrics
        Reduces across tasks for one (model, run) and computes:
        TSR, TSA (proxy), HCR, RR, S2S, AVR, mean tokens.

Metric definitions live in METRICS.md. This module's job is to implement
them faithfully and document any Phase-1 simplifications inline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .agent import Trace
from .mcp_client import SEP
from .providers import cost_usd
from .tasks import Task


@dataclass
class PerTaskMetrics:
    task_id: str
    model: str
    success: bool | None  # None until task's check op is run

    n_calls: int = 0  # total tool calls the model attempted
    n_hallucinated: int = 0  # calls naming a tool not in the available toolset
    n_wrong_server: int = 0  # calls to a tool from a server not in task.servers
    n_accepted: int = 0  # tool_result with is_error == False
    n_errored: int = 0  # tool_result with is_error == True
    n_tools_available: int = 0  # size of the toolset exposed (incl. distractors) — RQ1 stratifier

    had_tool_error: bool = False

    steps: int = 0  # assistant turns
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0  # RQ4: priced from tokens, 0.0 if model unpriced

    status: str = ""  # "answered" | "step_cap" | "model_error"

    def with_success(self, success: bool) -> PerTaskMetrics:
        self.success = success
        return self


@dataclass
class ModelMetrics:
    model: str
    n_tasks: int

    # Primary
    tsr: float = 0.0
    tsa_proxy: float = 0.0
    hcr: float = 0.0
    rr: float | None = None  # None when no task had a tool error

    # Secondary
    s2s: float | None = None  # mean tool calls in successful tasks; None if no successes
    avr: float = 0.0
    cpst: float | None = None  # RQ4: USD cost per successful task; None if no successes
    mean_steps: float = 0.0
    mean_prompt_tokens: float = 0.0
    mean_completion_tokens: float = 0.0

    # Diagnostics
    n_successes: int = 0
    n_step_cap: int = 0
    n_with_error: int = 0
    total_tool_calls: int = 0
    total_cost_usd: float = 0.0


def compute_per_task(
    task: Task,
    trace: Trace,
    available_tool_names: Iterable[str],
) -> PerTaskMetrics:
    """Build a per-task counter from one trace. `available_tool_names` is the
    set of qualified names actually exposed by the MCP pool for this run."""
    available = set(available_tool_names)
    allowed_servers = set(task.servers)

    tool_calls = [e for e in trace.events if e.kind == "tool_call"]
    tool_results = [e for e in trace.events if e.kind == "tool_result"]

    n_calls = len(tool_calls)
    n_hallucinated = sum(1 for e in tool_calls if (e.tool_name or "") not in available)
    n_wrong_server = sum(
        1
        for e in tool_calls
        if (e.tool_name or "").split(SEP, 1)[0] not in allowed_servers
    )
    n_accepted = sum(1 for e in tool_results if not e.tool_is_error)
    n_errored = sum(1 for e in tool_results if e.tool_is_error)

    return PerTaskMetrics(
        task_id=task.id,
        model=trace.model,
        success=None,
        n_calls=n_calls,
        n_hallucinated=n_hallucinated,
        n_wrong_server=n_wrong_server,
        n_accepted=n_accepted,
        n_errored=n_errored,
        n_tools_available=len(available),
        had_tool_error=n_errored > 0,
        steps=trace.steps,
        prompt_tokens=trace.total_prompt_tokens,
        completion_tokens=trace.total_completion_tokens,
        cost_usd=cost_usd(
            trace.model, trace.total_prompt_tokens, trace.total_completion_tokens
        ),
        status=trace.status,
    )


def aggregate(results: list[PerTaskMetrics]) -> ModelMetrics:
    if not results:
        raise ValueError("cannot aggregate empty result list")
    if any(r.success is None for r in results):
        raise ValueError("aggregate() requires every per-task result to have success set")

    n = len(results)
    model = results[0].model
    total_calls = sum(r.n_calls for r in results)

    # Primary
    n_success = sum(1 for r in results if r.success)
    tsr = n_success / n

    # HCR = hallucinated / total_calls (0 when no calls were made — define as 0)
    hcr = (sum(r.n_hallucinated for r in results) / total_calls) if total_calls else 0.0

    # TSA proxy = (calls to tools on an allowed server) / total_calls
    # = 1 - (wrong-server fraction). Without distractors, this is 1.0 minus HCR.
    n_correct_server = total_calls - sum(r.n_wrong_server for r in results)
    tsa_proxy = (n_correct_server / total_calls) if total_calls else 0.0

    # AVR = accepted / total_calls
    avr = (sum(r.n_accepted for r in results) / total_calls) if total_calls else 0.0

    # RR: only over tasks that had a tool error
    err_tasks = [r for r in results if r.had_tool_error]
    rr = (sum(1 for r in err_tasks if r.success) / len(err_tasks)) if err_tasks else None

    # S2S: only over successful tasks
    succ = [r for r in results if r.success]
    s2s = (sum(r.n_calls for r in succ) / len(succ)) if succ else None

    # CPST (RQ4): total spend across ALL runs / number of successes. Charging
    # failures' cost to the successes is intentional — it captures the real
    # price of getting a working result, including wasted attempts.
    total_cost = sum(r.cost_usd for r in results)
    cpst = (total_cost / len(succ)) if succ else None

    return ModelMetrics(
        model=model,
        n_tasks=n,
        tsr=tsr,
        tsa_proxy=tsa_proxy,
        hcr=hcr,
        rr=rr,
        s2s=s2s,
        avr=avr,
        cpst=cpst,
        mean_steps=sum(r.steps for r in results) / n,
        mean_prompt_tokens=sum(r.prompt_tokens for r in results) / n,
        mean_completion_tokens=sum(r.completion_tokens for r in results) / n,
        n_successes=n_success,
        n_step_cap=sum(1 for r in results if r.status == "step_cap"),
        n_with_error=len(err_tasks),
        total_tool_calls=total_calls,
        total_cost_usd=total_cost,
    )


def format_markdown_table(rows: list[ModelMetrics]) -> str:
    """Render a leaderboard. Empty values shown as '—'."""
    header = (
        "| model | TSR | TSA(proxy) | HCR | RR | AVR | S2S | CPST($) | mean steps | calls |"
    )
    sep = "|---|---|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for r in rows:
        rr = f"{r.rr:.2f}" if r.rr is not None else "-"
        s2s = f"{r.s2s:.1f}" if r.s2s is not None else "-"
        cpst = f"{r.cpst:.4f}" if r.cpst is not None else "-"
        lines.append(
            f"| {r.model} | {r.tsr:.2f} | {r.tsa_proxy:.2f} | {r.hcr:.2f} | "
            f"{rr} | {r.avr:.2f} | {s2s} | {cpst} | {r.mean_steps:.1f} | {r.total_tool_calls} |"
        )
    return "\n".join(lines)
