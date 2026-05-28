"""
Inference-provider adapters.

All four providers we target (NVIDIA API Catalog, Groq, Together AI,
HuggingFace Inference Providers) expose an OpenAI-compatible
chat-completions API. So we use the `openai` Python SDK against each
provider's base URL, with the provider's own API key.

The registry below is the single source of truth for which models can
be addressed by which short name. To support RQ3 (cross-provider
variance) in Phase 2, add the same logical model under multiple
provider entries (e.g. "llama-3.3-70b-groq" vs "llama-3.3-70b-nvidia").

Public surface:
  * LLMClient(short_name).chat(messages, tools=...) -> ChatResponse
  * ChatResponse with .content, .tool_calls (normalized), .usage tokens
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str


PROVIDERS: dict[str, ProviderConfig] = {
    "nvidia": ProviderConfig(
        "nvidia", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"
    ),
    "groq": ProviderConfig(
        "groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"
    ),
    "together": ProviderConfig(
        "together", "https://api.together.xyz/v1", "TOGETHER_API_KEY"
    ),
    "hf": ProviderConfig(
        "hf", "https://router.huggingface.co/v1", "HF_TOKEN"
    ),
}


@dataclass(frozen=True)
class ModelSpec:
    short_name: str
    provider: str
    model_id: str  # what the provider's API expects


MODELS: dict[str, ModelSpec] = {
    # Phase 1 pilot models. NVIDIA's catalog rolled forward in early 2026:
    # Qwen2.5 and DeepSeek-V3 no longer hosted; replaced by Qwen3-Next and
    # DeepSeek-V4. Llama family unchanged.
    "llama-3.1-8b": ModelSpec(
        "llama-3.1-8b", "nvidia", "meta/llama-3.1-8b-instruct"
    ),
    "llama-3.3-70b": ModelSpec(
        "llama-3.3-70b", "nvidia", "meta/llama-3.3-70b-instruct"
    ),
    "llama-4-maverick": ModelSpec(
        "llama-4-maverick", "nvidia", "meta/llama-4-maverick-17b-128e-instruct"
    ),
    "qwen-3-next-80b": ModelSpec(
        "qwen-3-next-80b", "nvidia", "qwen/qwen3-next-80b-a3b-instruct"
    ),
    "deepseek-v4-flash": ModelSpec(
        "deepseek-v4-flash", "nvidia", "deepseek-ai/deepseek-v4-flash"
    ),
    "deepseek-v4-pro": ModelSpec(
        "deepseek-v4-pro", "nvidia", "deepseek-ai/deepseek-v4-pro"
    ),
    "qwen-3.5-122b": ModelSpec(
        "qwen-3.5-122b", "nvidia", "qwen/qwen3.5-122b-a10b"
    ),
    # Third Phase-1 family, on Groq (NVIDIA's DeepSeek/Llama-4/Qwen3.5 were all
    # flaky for tool use as of 2026-05). GPT-OSS is a distinct model family and
    # Groq is a second provider — doubles as early RQ3 cross-provider signal.
    "gpt-oss-120b": ModelSpec(
        "gpt-oss-120b", "groq", "openai/gpt-oss-120b"
    ),
    # RQ3 cross-provider trio: the SAME logical model (Llama-3.3-70B-Instruct)
    # served by three providers. NVIDIA's copy degenerate-loops; Groq's and
    # Together's complete cleanly. This is the cross-provider variance result.
    "llama-3.3-70b-groq": ModelSpec(
        "llama-3.3-70b-groq", "groq", "llama-3.3-70b-versatile"
    ),
    "llama-3.3-70b-together": ModelSpec(
        "llama-3.3-70b-together", "together", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    ),
    # Phase 2 candidates for the 8-model leaderboard — chosen for family + size
    # diversity. Validated via scripts/validate_models.py before the grid run.
    "gpt-oss-20b": ModelSpec(
        "gpt-oss-20b", "groq", "openai/gpt-oss-20b"
    ),
    "qwen-2.5-7b": ModelSpec(
        "qwen-2.5-7b", "together", "Qwen/Qwen2.5-7B-Instruct-Turbo"
    ),
    "gemma-3-27b": ModelSpec(
        "gemma-3-27b", "together", "google/gemma-3-27b-it"
    ),
    "mixtral-8x22b": ModelSpec(
        "mixtral-8x22b", "together", "mistralai/Mixtral-8x22B-Instruct-v0.1"
    ),
    # DeepSeek family via Together (NVIDIA's DeepSeek endpoints 504'd). The
    # R1-distill is a reasoning model — lets us ask whether test-time reasoning
    # helps MCP tool use (a Phase-4 question we can preview here).
    "deepseek-v4-pro-together": ModelSpec(
        "deepseek-v4-pro-together", "together", "deepseek-ai/DeepSeek-V4-Pro"
    ),
    "deepseek-r1-distill-70b": ModelSpec(
        "deepseek-r1-distill-70b", "together", "deepseek-ai/DeepSeek-R1-Distill-Llama-70B"
    ),
    # Llama 4 on Groq — Maverick leaked tool-calls-as-text on NVIDIA; does Scout
    # behave on a different provider?
    "llama-4-scout-groq": ModelSpec(
        "llama-4-scout-groq", "groq", "meta-llama/llama-4-scout-17b-16e-instruct"
    ),
}


@dataclass(frozen=True)
class Price:
    """USD per 1,000,000 tokens."""

    input_per_mtok: float
    output_per_mtok: float


# Per-model token pricing for RQ4 (cost per successful task).
#
# !!! THESE ARE APPROXIMATE LIST PRICES (USD / 1M tokens) as of 2026-05 and
# MUST be verified against each provider's published pricing page before any
# RQ4 number is reported. For free-tier-served models (NVIDIA), we use the
# model's list-price equivalent so cross-provider comparison stays fair, per
# the METRICS.md / CLAUDE.md convention. Update here; everything downstream
# (cost_usd, CPST) recomputes automatically.
PRICING: dict[str, Price] = {
    "llama-3.1-8b": Price(0.05, 0.08),
    "llama-3.3-70b": Price(0.60, 0.60),
    "llama-4-maverick": Price(0.20, 0.60),
    "qwen-3-next-80b": Price(0.15, 0.60),
    "deepseek-v4-flash": Price(0.10, 0.40),
    "deepseek-v4-pro": Price(0.40, 1.20),
    "qwen-3.5-122b": Price(0.20, 0.80),
    "gpt-oss-120b": Price(0.15, 0.75),
    "llama-3.3-70b-groq": Price(0.59, 0.79),
    "llama-3.3-70b-together": Price(0.88, 0.88),
    "gpt-oss-20b": Price(0.10, 0.50),
    "qwen-2.5-7b": Price(0.30, 0.30),
    "gemma-3-27b": Price(0.80, 0.80),
    "mixtral-8x22b": Price(1.20, 1.20),
    "deepseek-v4-pro-together": Price(0.40, 1.20),
    "deepseek-r1-distill-70b": Price(2.00, 2.00),
    "llama-4-scout-groq": Price(0.11, 0.34),
}


def cost_usd(model_short_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Cost in USD for a (prompt, completion) token pair. Returns 0.0 with a
    model we have no price for — callers should treat 0.0 as 'unpriced', not free."""
    price = PRICING.get(model_short_name)
    if price is None:
        return 0.0
    return (
        prompt_tokens / 1_000_000 * price.input_per_mtok
        + completion_tokens / 1_000_000 * price.output_per_mtok
    )


@dataclass
class ToolCall:
    id: str
    name: str  # the OpenAI-side function name == our MCP qualified_name
    arguments_json: str  # raw string, agent layer parses it


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str | None = None
    raw: Any = None  # original ChatCompletion, kept for debugging


def list_models() -> list[str]:
    return sorted(MODELS)


# The locked Phase-2 leaderboard set: 8 models, 5 families, 3 providers, with
# large/small size pairs for GPT-OSS, Qwen, and Llama. Validated working via
# scripts/validate_models.py (2026-05). Gemma/Mixtral need paid Together
# dedicated endpoints; NVIDIA's DeepSeek/Qwen3.5 endpoints were flaky.
LEADERBOARD_MODELS: list[str] = [
    "gpt-oss-120b",
    "gpt-oss-20b",
    "qwen-3-next-80b",
    "qwen-2.5-7b",
    "llama-3.3-70b-together",
    "llama-3.1-8b",
    "deepseek-v4-pro-together",
    "llama-4-scout-groq",
]


class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat endpoint.

    One instance per (model). The provider is looked up from MODELS,
    and the base_url + API key are pulled from PROVIDERS + env. We don't
    hold long-lived state — chat() can be called repeatedly.
    """

    def __init__(self, model_short_name: str):
        if model_short_name not in MODELS:
            raise KeyError(
                f"unknown model {model_short_name!r}. Known: {list_models()}"
            )
        self.spec = MODELS[model_short_name]
        provider = PROVIDERS[self.spec.provider]
        key = os.getenv(provider.api_key_env)
        if not key:
            raise RuntimeError(
                f"env var {provider.api_key_env!r} is not set "
                f"(required for provider {provider.name!r})"
            )
        self.provider = provider
        self.client = OpenAI(base_url=provider.base_url, api_key=key)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ChatResponse:
        kwargs: dict[str, Any] = {
            "model": self.spec.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            # Several NVIDIA-hosted models (e.g. Llama-3.1-8B) reject assistant
            # messages with >1 tool_call in their chat template. Forcing
            # sequential keeps the loop compatible across providers and also
            # makes trace analysis simpler.
            kwargs["parallel_tool_calls"] = False

        resp = self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments_json=tc.function.arguments or "{}",
                )
            )

        usage = resp.usage
        return ChatResponse(
            content=msg.content,
            tool_calls=tool_calls,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            finish_reason=choice.finish_reason,
            raw=resp,
        )
