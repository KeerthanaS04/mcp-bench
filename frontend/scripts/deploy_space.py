"""
Deploy the MCP-Bench Gradio app to a Hugging Face Space.

Runs the bundle step first (so data/ reflects the latest backend artifacts),
then creates / updates the Space at
`<your-hf-username>/mcp-bench-leaderboard` and uploads everything the Space
needs: app.py, requirements.txt, README.md (with the HF Spaces YAML
frontmatter), data/, and scripts/.

Requires HF_TOKEN with write scope in .env.

    uv run python frontend/scripts/deploy_space.py
    uv run python frontend/scripts/deploy_space.py --dry-run   # bundle only
    uv run python frontend/scripts/deploy_space.py --repo-id keerthanaSubru57/mcp-bench-leaderboard
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND = REPO_ROOT / "frontend"
BUNDLE_SCRIPT = FRONTEND / "scripts" / "bundle.py"

DEFAULT_REPO_ID = "keerthanaSubru57/mcp-bench-leaderboard"

# Things we don't want in the Space's git history.
IGNORE = [
    ".venv/*", "**/__pycache__/*", "*.pyc",
    ".python-version", "pyproject.toml", "uv.lock",
    ".env", "*.docx", "~$*",
]


def run_bundle() -> int:
    print("running bundle.py to refresh data/ ...")
    proc = subprocess.run([sys.executable, str(BUNDLE_SCRIPT)])
    return proc.returncode


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="<user>/<space-name>")
    p.add_argument("--dry-run", action="store_true", help="bundle but do not push")
    args = p.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    rc = run_bundle()
    if rc != 0:
        print(f"bundle failed (exit {rc}) — aborting deploy.")
        return rc

    if args.dry_run:
        print("dry-run: skipping HF push.")
        return 0

    token = os.getenv("HF_TOKEN")
    if not token:
        print("HF_TOKEN not set in .env — cannot push.")
        return 2

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub missing. Install with: uv add huggingface_hub")
        return 3

    api = HfApi(token=token)
    print(f"creating / verifying Space: {args.repo_id}")
    api.create_repo(
        args.repo_id,
        repo_type="space",
        space_sdk="gradio",
        exist_ok=True,
        private=False,
    )

    print(f"uploading {FRONTEND} -> Space {args.repo_id}")
    api.upload_folder(
        folder_path=str(FRONTEND),
        repo_id=args.repo_id,
        repo_type="space",
        commit_message="MCP-Bench v0.1 leaderboard frontend",
        ignore_patterns=IGNORE,
    )
    print(f"\ndone. visit https://huggingface.co/spaces/{args.repo_id}")
    print("HF will rebuild the Space; first build takes ~2-3 minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
