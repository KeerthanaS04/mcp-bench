# MCP-Bench · Frontend

Gradio application for the MCP-Bench leaderboard, task explorer, failure analysis, and provider-comparison views. Designed to be deployed as a Hugging Face Space in Phase 3.

## Status

Phase 0 — placeholder only. Implementation lands in Phase 3.

## Local run (when implemented)

```powershell
cd frontend
uv sync
uv run python app.py
```

Opens at http://127.0.0.1:7860.

## Deploy to Hugging Face Space

Phase 3 — instructions TBD. The plan: push this directory (plus bundled `data/results.json` from the backend) to an HF Space repo.

## Data flow

The frontend reads precomputed JSON produced by the backend's eval runs. Specifically:

- `../backend/results/*.json` — per-(model, task) results
- `../backend/traces/*.jsonl` — full conversation traces

At deploy time, these will be bundled into `frontend/data/` for the HF Space.
