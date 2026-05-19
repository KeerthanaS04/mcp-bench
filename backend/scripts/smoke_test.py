"""
Phase 0 smoke test.

Verifies, in order:
  1. .env file is loaded and NVIDIA_API_KEY is set.
  2. NVIDIA API responds to a minimal chat completion request.
  3. The official filesystem MCP server can be spawned via npx and lists tools.

If all 3 steps pass, Phase 0 plumbing is correct and Phase 1 can begin.
Run with:  uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

console = Console()

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
SANDBOX_DIR = BACKEND_DIR / "sandbox"


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    console.print(f"  {mark}  {label}{suffix}")
    return ok


def step_1_env() -> bool:
    console.print("\n[bold]Step 1[/bold]  Load .env")
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return check(".env exists", False, f"copy .env.example to .env at {env_path}")
    load_dotenv(env_path)
    key = os.getenv("NVIDIA_API_KEY", "")
    if not key:
        return check("NVIDIA_API_KEY is set", False, "value is empty in .env")
    if not key.startswith("nvapi-"):
        return check("NVIDIA_API_KEY looks valid", False, "expected to start with 'nvapi-'")
    return check("NVIDIA_API_KEY is set", True, f"key=nvapi-...{key[-4:]}")


def step_2_nvidia() -> bool:
    console.print("\n[bold]Step 2[/bold]  NVIDIA API chat completion")
    try:
        from openai import OpenAI
    except ImportError:
        return check("openai package importable", False, "run: uv sync")

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
    )
    model = "meta/llama-3.1-8b-instruct"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with only the single word: pong"}],
            max_tokens=8,
            temperature=0.0,
        )
    except Exception as e:
        return check(f"NVIDIA API call ({model})", False, repr(e))
    text = (resp.choices[0].message.content or "").strip().lower()
    return check(f"NVIDIA API call ({model})", "pong" in text, f"got: {text!r}")


async def step_3_mcp() -> bool:
    console.print("\n[bold]Step 3[/bold]  Spawn filesystem MCP server")
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        return check("mcp package importable", False, "run: uv sync")

    SANDBOX_DIR.mkdir(exist_ok=True)
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(SANDBOX_DIR)],
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                names = [t.name for t in result.tools]
    except FileNotFoundError:
        return check("filesystem MCP server", False, "npx not found — install Node.js LTS")
    except Exception as e:
        return check("filesystem MCP server", False, repr(e))
    return check(
        "filesystem MCP server",
        len(names) > 0,
        f"{len(names)} tools: {', '.join(names[:5])}{'...' if len(names) > 5 else ''}",
    )


def main() -> int:
    console.print(Panel.fit("[bold]MCP-Bench · Phase 0 smoke test[/bold]"))
    results = [step_1_env()]
    if results[0]:
        results.append(step_2_nvidia())
    else:
        console.print("\n[dim]Skipping step 2 (NVIDIA API) — fix step 1 first[/dim]")
        results.append(False)
    results.append(asyncio.run(step_3_mcp()))
    console.print()
    if all(results):
        console.print(Panel.fit("[bold green]All checks passed[/bold green]  Phase 0 plumbing is ready"))
        return 0
    console.print(Panel.fit("[bold red]Some checks failed[/bold red]  fix the issues above before Phase 1"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
