# MCP servers used by MCP-Bench

Each task declares which servers it needs in its `servers:` field. The runner
([src/mcp_bench/runner.py](../src/mcp_bench/runner.py) → `build_mcp_configs`)
spawns exactly those servers per task, plus any `--distractors`.

Servers are respawned per task for clean state. Node servers run via `npx -y`
(auto-installed on first use); Python servers via `uvx` (from `uv`).

| Server | Runtime | Launch | External setup |
|---|---|---|---|
| `filesystem` | Node | `npx -y @modelcontextprotocol/server-filesystem <sandbox>` | none — sandboxed to `backend/sandbox/` |
| `sqlite` | Python | `uvx mcp-server-sqlite --db-path <sandbox>/tasks.db` | none |
| `fetch` | Python | `uvx mcp-server-fetch` | none (hits public URLs) |
| `memory` | Node | `npx -y @modelcontextprotocol/server-memory` | none — graph stored at `<sandbox>/memory.json`, wiped per task |
| `github` | Node | `npx -y @modelcontextprotocol/server-github` | **`GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`** |
| `postgres` | Node | `npx -y @modelcontextprotocol/server-postgres <DSN>` | **Docker container** via `setup_postgres.ps1` |

## Per-server notes

### filesystem (14 tools)
`read_text_file`, `write_file`, `edit_file`, `list_directory`, `move_file`,
`search_files`, `directory_tree`, … The server's working directory is set to
the sandbox so the model can use plain relative paths (`notes.txt`).

### sqlite (6 tools)
`read_query`, `write_query`, `create_table`, `list_tables`, `describe_table`,
`append_insight`. Operates on a single DB file; tasks seed it via the
`init_sqlite` setup operator.

### fetch (1 tool)
`fetch` — HTTP GET with optional HTML→Markdown. Non-2xx responses surface as
MCP errors (used by the error-recovery tasks). Pure-Python HTML extraction
fallback warns about missing Node/Readability — harmless.

### memory (9 tools)
Knowledge-graph store: `create_entities`, `create_relations`,
`add_observations`, `read_graph`, `search_nodes`, `open_nodes`, … Storage file
lives in the sandbox and is reset between tasks, so each task starts empty.

### github (read-oriented)
Needs a personal-access token (`GITHUB_PERSONAL_ACCESS_TOKEN`, or `GITHUB_TOKEN`).
Read-only scopes suffice for our tasks. Subject to GitHub API rate limits —
keep github tasks read-only and modest in volume. NOTE: the npm
`@modelcontextprotocol/server-github` package is the original reference
implementation; if it is unavailable, GitHub's official Go server
`github-mcp-server` is the maintained replacement (update `build_mcp_configs`).

### postgres (read-only SQL)
Runs read-only queries against a Postgres instance named by `POSTGRES_DSN`.
Spin up the local test DB first:

```powershell
backend\scripts\setup_postgres.ps1      # starts Docker container + seeds schema
```

The script creates a `mcpbench` database with a small sample schema
(`employees`, `departments`, `salaries`) for tasks to query.
