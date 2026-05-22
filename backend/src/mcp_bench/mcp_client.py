"""
MCP client pool.

Wraps the official `mcp` SDK so the rest of the codebase can:
  * spawn one or more MCP servers concurrently (filesystem, sqlite, fetch, ...)
  * see a flat, namespaced list of all their tools
  * call any tool by qualified name
  * hand the LLM an OpenAI-function-calling-compatible tool schema

The qualified-name convention is "<server>__<tool>" (double-underscore separator).
OpenAI function-calling names must match ^[a-zA-Z0-9_-]{1,64}$, so we cannot use
dots or slashes. Double-underscore is rare in real MCP tool names, so collision
risk is low; we assert against it at registration time.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SEP = "__"


@dataclass
class MCPServerConfig:
    """How to launch one MCP server.

    `name` is our short logical name ("filesystem"). `command` + `args` are
    passed straight to the OS — typically `npx -y @modelcontextprotocol/...`
    for Node servers or `uvx ...` for Python servers.

    `cwd` controls the server's working directory. For the filesystem server
    we set this to the sandbox so the model can use plain relative paths
    ('notes.txt' rather than 'sandbox/notes.txt').
    """

    name: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None
    cwd: str | None = None


@dataclass
class MCPTool:
    server: str
    name: str  # original name on the server
    qualified_name: str  # "<server>__<tool>" — what we hand to the LLM
    description: str
    input_schema: dict[str, Any]


class MCPClientPool:
    """Holds live sessions to N MCP servers. Use as an async context manager.

    Example:
        configs = [
            MCPServerConfig("filesystem", "npx",
                ["-y", "@modelcontextprotocol/server-filesystem", "./sandbox"]),
        ]
        async with MCPClientPool(configs) as pool:
            schemas = pool.openai_tool_schemas()       # for the LLM
            text, is_err = await pool.call_tool(
                "filesystem__read_file", {"path": "x.txt"})
    """

    def __init__(self, configs: list[MCPServerConfig]):
        self.configs = configs
        self._sessions: dict[str, ClientSession] = {}
        self._exit_stack: AsyncExitStack | None = None
        self.tools: list[MCPTool] = []

    async def __aenter__(self) -> MCPClientPool:
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()
        try:
            for cfg in self.configs:
                # The SDK uses cfg.env verbatim as the subprocess environment if
                # it's not None — which would drop PATH and break npx/uvx. Merge
                # our extras over the SDK's safe default environment instead.
                env = cfg.env
                if env is not None:
                    from mcp.client.stdio import get_default_environment

                    env = {**get_default_environment(), **cfg.env}
                params = StdioServerParameters(
                    command=cfg.command, args=cfg.args, env=env, cwd=cfg.cwd
                )
                read, write = await self._exit_stack.enter_async_context(
                    stdio_client(params)
                )
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                self._sessions[cfg.name] = session

                listing = await session.list_tools()
                for t in listing.tools:
                    assert SEP not in t.name, (
                        f"tool '{t.name}' on server '{cfg.name}' contains the "
                        f"reserved separator '{SEP}'"
                    )
                    self.tools.append(
                        MCPTool(
                            server=cfg.name,
                            name=t.name,
                            qualified_name=f"{cfg.name}{SEP}{t.name}",
                            description=t.description or "",
                            input_schema=t.inputSchema
                            or {"type": "object", "properties": {}},
                        )
                    )
        except BaseException:
            await self._exit_stack.__aexit__(None, None, None)
            self._exit_stack = None
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._exit_stack is not None:
            await self._exit_stack.__aexit__(exc_type, exc, tb)
            self._exit_stack = None

    async def call_tool(
        self, qualified_name: str, args: dict[str, Any]
    ) -> tuple[str, bool]:
        """Invoke a tool. Returns (flattened_text_content, is_error)."""
        if SEP not in qualified_name:
            raise ValueError(
                f"tool name must be qualified as 'server{SEP}tool', got: {qualified_name}"
            )
        server_name, tool_name = qualified_name.split(SEP, 1)
        session = self._sessions.get(server_name)
        if session is None:
            raise KeyError(f"unknown MCP server: {server_name!r}")

        result = await session.call_tool(tool_name, args)
        text_parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            text_parts.append(text if text is not None else str(block))
        return "\n".join(text_parts), bool(result.isError)

    def openai_tool_schemas(self) -> list[dict[str, Any]]:
        """Translate the pooled tool list into OpenAI function-calling format.

        The LLM sees `name = <server>__<tool>` and the original JSON-Schema
        input shape. We prefix the description with [<server>] so the model
        gets a hint about provenance when picking between similar tools on
        different servers (matters for RQ1 — selection under distractors).
        """
        schemas: list[dict[str, Any]] = []
        for t in self.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.qualified_name,
                        "description": f"[{t.server}] {t.description}".strip(),
                        "parameters": t.input_schema,
                    },
                }
            )
        return schemas

    def tool_by_qualified_name(self, qualified_name: str) -> MCPTool | None:
        for t in self.tools:
            if t.qualified_name == qualified_name:
                return t
        return None
