"""CLI entry point for seeding the Klarnova knowledge base.

    python knowledge-base/ingest.py [--refresh] [--path PATH]

Delegates to ``app.rag.ingest.run_ingest``.
"""
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from app.rag.ingest import run_ingest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Klarnova Chroma collections")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-add documents even if the id already exists",
    )
    parser.add_argument("--path", default=None, help="override sources.yaml path")
    args = parser.parse_args()
    count = run_ingest(refresh=args.refresh, path=args.path)
    print(f"knowledge base ingest complete: {count} document(s) added")
