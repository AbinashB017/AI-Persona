"""
ingestion/run_ingestion.py
Master ingestion runner — run this once to populate ChromaDB.

Usage:
    python ingestion/run_ingestion.py                  # ingest everything
    python ingestion/run_ingestion.py --resume-only    # resume only
    python ingestion/run_ingestion.py --github-only    # GitHub only
    python ingestion/run_ingestion.py --force          # clear & re-ingest all
"""
import os
import sys

# Suppress TF/Keras conflict BEFORE any other imports
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import argparse
import time
from loguru import logger

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.ingest_resume import ingest_resume
from ingestion.ingest_github import ingest_github
from vectorstore.chroma_manager import get_chroma_manager


def main():
    parser = argparse.ArgumentParser(description="AI Persona — Ingestion Pipeline")
    parser.add_argument("--resume-only", action="store_true")
    parser.add_argument("--github-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="Clear existing data first")
    parser.add_argument(
        "--resume-path",
        default="data/resume.pdf",
        help="Path to resume PDF (default: data/resume.pdf)",
    )
    parser.add_argument(
        "--repos",
        nargs="+",
        help="Override GITHUB_REPOS: list of owner/repo strings",
        default=None,
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  AI Persona — Knowledge Ingestion Pipeline")
    logger.info("=" * 60)

    start = time.time()
    summary = {}

    # ── Resume ──
    if not args.github_only:
        logger.info("\n[1/2] Ingesting Resume...")
        try:
            n = ingest_resume(
                resume_path=args.resume_path,
                force_reingest=args.force,
            )
            summary["resume"] = n
        except FileNotFoundError as e:
            logger.error(str(e))
            logger.error(f"Place your resume PDF at: {args.resume_path}")
            summary["resume"] = 0

    # ── GitHub ──
    if not args.resume_only:
        logger.info("\n[2/2] Ingesting GitHub Repositories...")
        github_results = ingest_github(
            repos=args.repos,
            force_reingest=args.force,
        )
        summary["github"] = github_results

    # ── Final stats ──
    elapsed = round(time.time() - start, 1)
    chroma = get_chroma_manager()
    stats = chroma.get_collection_stats()

    logger.info("\n" + "=" * 60)
    logger.success("  Ingestion Complete!")
    logger.info(f"  Time elapsed       : {elapsed}s")
    logger.info(f"  Resume chunks      : {summary.get('resume', 'skipped')}")
    if "github" in summary:
        gh = summary["github"]
        logger.info(f"  GitHub repos       : {len(gh)}")
        logger.info(f"  GitHub chunks      : {sum(gh.values())}")
    logger.info(f"  Total in ChromaDB  : {stats['total_documents']}")
    logger.info(f"  Unique sources     : {len(stats.get('unique_sources', []))}")
    logger.info("=" * 60)

    # ── Quick retrieval test ──
    logger.info("\n🔍 Running quick retrieval test...")
    results = chroma.query("What are Abinash's skills and projects?", top_k=3)
    if results:
        logger.success(f"Retrieval working ✅  — got {len(results)} chunks")
        for i, r in enumerate(results, 1):
            logger.info(
                f"  [{i}] source={r['metadata']['source']} | "
                f"dist={r['distance']} | "
                f"preview={r['text'][:80].strip()}..."
            )
    else:
        logger.warning("Retrieval returned no results — check ingestion above.")


if __name__ == "__main__":
    main()
