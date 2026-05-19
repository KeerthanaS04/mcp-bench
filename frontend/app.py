"""
MCP-Bench frontend — Gradio app to be deployed as a Hugging Face Space.

Builds five tabs from precomputed results JSON produced by the backend:
  1. Leaderboard — sortable table: model x metric
  2. Task explorer — browse tasks, see per-model traces side-by-side
  3. Failure analysis — top failure patterns with examples
  4. Provider comparison — same model across providers (RQ3)
  5. (Phase 4 stretch) Try it live — pick a model + task, run live

Implementation lands in Phase 3 once the backend has produced results to render.
For now this is a placeholder so the structure is in place.
"""

import gradio as gr


def _placeholder():
    return (
        "MCP-Bench frontend is under construction.\n\n"
        "Phase 3 will populate this with the leaderboard, task explorer, "
        "failure analysis, and provider comparison views."
    )


with gr.Blocks(title="MCP-Bench") as demo:
    gr.Markdown("# MCP-Bench")
    gr.Markdown(
        "Evaluation suite for MCP tool-use reliability in open-source LLM agents."
    )
    gr.Textbox(value=_placeholder(), label="Status", lines=4, interactive=False)


if __name__ == "__main__":
    demo.launch()
