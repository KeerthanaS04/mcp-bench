"""
Liveness check for one or more MCP servers — spawns each, lists its tools.

Loads .env first so the github + postgres servers see their credentials /
connection string. Writes nothing.

Usage:
    uv run python scripts/probe_server.py             # github + postgres by default
    uv run python scripts/probe_server.py github
    uv run python scripts/probe_server.py memory filesystem sqlite fetch
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from mcp_bench.mcp_client import MCPClientPool
from mcp_bench.runner import REPO_ROOT, build_mcp_configs


async def main(servers: list[str]) -> int:
    load_dotenv(REPO_ROOT / ".env")
    ok = True
    for s in servers:
        try:
            async with MCPClientPool(build_mcp_configs([s])) as pool:
                names = [t.name for t in pool.tools]
                preview = names[:8]
                more = f"...(+{len(names) - 8})" if len(names) > 8 else ""
                print(f"{s:<12} OK  ({len(names)} tools)  {preview}{more}")
        except Exception as e:
            ok = False
            print(f"{s:<12} FAIL — {type(e).__name__}: {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:] or ["github", "postgres"]
    raise SystemExit(asyncio.run(main(args)))
