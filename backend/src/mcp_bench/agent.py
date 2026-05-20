"""
ReAct-style agent loop.

One function — `run_agent` — drives a single task to completion (or step cap).
It produces a `Trace` containing:

  * `messages` — the literal OpenAI chat-completions message list, replayable
  * `events`   — structured records suitable for metric computation
  * `status`   — terminal state ("answered" | "step_cap" | "model_error")
  * `final_text` — the model's final assistant text, if any

The loop is intentionally minimal (~150 LOC, no framework). The point of this
benchmark is to measure model behavior; abstractions would confound it.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from .mcp_client import MCPClientPool
from .providers import LLMClient, ToolCall

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a set of tools. "
    "Use them to complete the user's task. When the task is complete, "
    "respond with a brief final answer in plain text. "
    "If a tool returns an error, decide whether to retry with corrected "
    "arguments, try a different tool, or stop and report the issue."
)


@dataclass
class AgentEvent:
    """One discrete thing that happened during the run. Order is preserved."""

    step: int
    kind: str  # "assistant_message" | "tool_call" | "tool_result" | "model_error" | "stop"
    timestamp: float
    # assistant_message fields
    content: str | None = None
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # tool_call / tool_result fields
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    tool_is_error: bool = False
    # generic
    detail: str | None = None


@dataclass
class Trace:
    task_id: str
    model: str
    status: str  # "answered" | "step_cap" | "model_error"
    final_text: str | None
    messages: list[dict[str, Any]] = field(default_factory=list)
    events: list[AgentEvent] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0

    @property
    def steps(self) -> int:
        return sum(1 for e in self.events if e.kind == "assistant_message")

    @property
    def tool_calls(self) -> int:
        return sum(1 for e in self.events if e.kind == "tool_call")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "status": self.status,
            "final_text": self.final_text,
            "messages": self.messages,
            "events": [e.__dict__ for e in self.events],
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
        }


async def run_agent(
    task_id: str,
    task_prompt: str,
    mcp_pool: MCPClientPool,
    llm: LLMClient,
    *,
    max_steps: int = 20,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_tokens_per_step: int = 1024,
    temperature: float = 0.0,
) -> Trace:
    tools_schema = mcp_pool.openai_tool_schemas()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt},
    ]
    trace = Trace(
        task_id=task_id,
        model=llm.spec.short_name,
        status="step_cap",
        final_text=None,
        messages=messages,
        started_at=time.time(),
    )

    for step in range(1, max_steps + 1):
        # The LLM client is sync; offload to a thread so we don't block the
        # async event loop that owns the MCP stdio sessions.
        try:
            resp = await asyncio.to_thread(
                llm.chat,
                messages=messages,
                tools=tools_schema,
                max_tokens=max_tokens_per_step,
                temperature=temperature,
            )
        except Exception as e:
            trace.events.append(
                AgentEvent(
                    step=step,
                    kind="model_error",
                    timestamp=time.time(),
                    detail=f"{type(e).__name__}: {e}",
                )
            )
            trace.status = "model_error"
            trace.final_text = None
            trace.ended_at = time.time()
            return trace
        trace.total_prompt_tokens += resp.prompt_tokens
        trace.total_completion_tokens += resp.completion_tokens

        trace.events.append(
            AgentEvent(
                step=step,
                kind="assistant_message",
                timestamp=time.time(),
                content=resp.content,
                finish_reason=resp.finish_reason,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
            )
        )

        # Append the assistant turn to the running chat history.
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": resp.content,
        }
        if resp.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments_json},
                }
                for tc in resp.tool_calls
            ]
        messages.append(assistant_msg)

        if not resp.tool_calls:
            trace.status = "answered"
            trace.final_text = resp.content
            trace.events.append(
                AgentEvent(step=step, kind="stop", timestamp=time.time(), detail="no_tool_calls")
            )
            break

        # Execute each requested tool call in declared order.
        for tc in resp.tool_calls:
            args, parse_err = _parse_args(tc.arguments_json)
            trace.events.append(
                AgentEvent(
                    step=step,
                    kind="tool_call",
                    timestamp=time.time(),
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    tool_args=args if parse_err is None else None,
                    detail=parse_err,
                )
            )

            if parse_err is not None:
                tool_text = f"ERROR: could not parse tool arguments as JSON: {parse_err}"
                is_err = True
            else:
                try:
                    tool_text, is_err = await mcp_pool.call_tool(tc.name, args)
                except Exception as e:
                    tool_text = f"ERROR: {type(e).__name__}: {e}"
                    is_err = True

            trace.events.append(
                AgentEvent(
                    step=step,
                    kind="tool_result",
                    timestamp=time.time(),
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    tool_result=tool_text,
                    tool_is_error=is_err,
                )
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_text,
                }
            )
    else:
        # for/else: step cap reached without break
        trace.events.append(
            AgentEvent(
                step=max_steps,
                kind="stop",
                timestamp=time.time(),
                detail=f"step_cap_reached ({max_steps})",
            )
        )

    trace.ended_at = time.time()
    return trace


def _parse_args(arguments_json: str) -> tuple[dict[str, Any], str | None]:
    """Tolerantly parse an LLM-emitted JSON args blob. Returns (args, err_or_None)."""
    if not arguments_json or not arguments_json.strip():
        return {}, None
    try:
        parsed = json.loads(arguments_json)
    except json.JSONDecodeError as e:
        return {}, f"{e.msg} at line {e.lineno} col {e.colno}"
    if not isinstance(parsed, dict):
        return {}, f"expected JSON object, got {type(parsed).__name__}"
    return parsed, None
