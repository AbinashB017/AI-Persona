"""
ingestion/ingest_github.py
Fetch README files and documentation from GitHub repositories,
chunk the content, and store it in ChromaDB.

Supports:
- Public repos (no token needed, 60 req/hr unauthenticated)
- Private repos (requires GITHUB_TOKEN)
- Auto-discovery: fetches all public repos for a username if no specific repos listed
- Fetches: README.md, docs/, wiki content
"""
import os
import sys
import time
import requests
from pathlib import Path
from loguru import logger
from typing import Optional
from base64 import b64decode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import get_settings
from ingestion.chunking import chunk_text
from vectorstore.chroma_manager import get_chroma_manager


# ─────────────────────────────────────────────────────────
# GitHub API helpers
# ─────────────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com"

# Files to look for in each repository (in priority order)
TARGET_FILES = [
    "README.md",
    "README.rst",
    "README.txt",
    "readme.md",
    "docs/README.md",
    "CONTRIBUTING.md",
    "ARCHITECTURE.md",
    "docs/architecture.md",
    "docs/index.md",
]


def _get_headers(token: Optional[str] = None) -> dict:
    """Build GitHub API request headers."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _api_get(url: str, headers: dict, retries: int = 3) -> Optional[dict | list]:
    """
    Make a GitHub API GET request with retry and rate-limit handling.
    Returns parsed JSON or None on failure.
    """
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 403:
                # Rate limited
                reset_time = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset_time - int(time.time()), 1)
                logger.warning(f"GitHub rate limit hit. Waiting {wait}s...")
                time.sleep(min(wait, 60))
            elif resp.status_code == 404:
                logger.debug(f"404 Not Found: {url}")
                return None
            else:
                logger.warning(f"GitHub API {resp.status_code} for {url}")
                return None

        except requests.RequestException as e:
            logger.warning(f"Request error (attempt {attempt + 1}): {e}")
            time.sleep(2**attempt)

    return None


def get_public_repos(username: str, headers: dict) -> list[str]:
    """
    Fetch all public repository names for a GitHub user.
    Returns list of 'username/reponame' strings.
    """
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API_BASE}/users/{username}/repos?per_page=100&page={page}&type=public"
        data = _api_get(url, headers)
        if not data or not isinstance(data, list):
            break
        repos.extend(f"{username}/{r['name']}" for r in data if not r.get("fork", False))
        if len(data) < 100:
            break
        page += 1

    logger.info(f"Found {len(repos)} public repos for '{username}'")
    return repos


def fetch_file_content(repo: str, file_path: str, headers: dict) -> Optional[str]:
    """
    Fetch raw content of a file from a GitHub repo.
    Returns decoded text or None if not found.
    """
    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{file_path}"
    data = _api_get(url, headers)
    if not data or not isinstance(data, dict):
        return None

    encoding = data.get("encoding", "")
    content = data.get("content", "")

    if encoding == "base64":
        try:
            return b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to decode {file_path} in {repo}: {e}")
            return None

    return content if content else None


def fetch_repo_metadata(repo: str, headers: dict) -> dict:
    """Fetch repo metadata: description, topics, language, stars."""
    url = f"{GITHUB_API_BASE}/repos/{repo}"
    data = _api_get(url, headers) or {}
    return {
        "description": data.get("description") or "",
        "language": data.get("language") or "",
        "stars": data.get("stargazers_count", 0),
        "topics": ", ".join(data.get("topics", [])),
        "html_url": data.get("html_url", f"https://github.com/{repo}"),
        "updated_at": data.get("updated_at", ""),
    }


def ingest_repository(
    repo: str,
    headers: dict,
    chroma,
    save_dir: str = "data/github_docs",
    force_reingest: bool = False,
) -> int:
    """
    Ingest all relevant documentation files from a single repository.

    Args:
        repo: "owner/reponame" string
        headers: GitHub API headers
        chroma: ChromaManager instance
        save_dir: Local directory to cache fetched files
        force_reingest: Clear old chunks for this repo before re-ingesting

    Returns:
        Number of chunks stored.
    """
    logger.info(f"━━ Processing repo: {repo} ━━")

    if force_reingest:
        chroma.delete_by_source(f"github/{repo}")

    # ── Repo metadata ──
    meta = fetch_repo_metadata(repo, headers)
    repo_url = meta["html_url"]
    owner, repo_name = repo.split("/", 1)

    total_chunks = 0
    save_path = Path(save_dir) / owner / repo_name
    save_path.mkdir(parents=True, exist_ok=True)

    # ── Inject a synthetic "repo overview" chunk from metadata ──
    if meta["description"]:
        overview_text = (
            f"Repository: {repo_name}\n"
            f"Owner: {owner}\n"
            f"Description: {meta['description']}\n"
            f"Primary Language: {meta['language']}\n"
            f"Topics: {meta['topics']}\n"
            f"Stars: {meta['stars']}\n"
            f"URL: {repo_url}\n"
            f"Last Updated: {meta['updated_at']}"
        )
        overview_chunks = chunk_text(
            text=overview_text,
            source=f"github/{repo}",
            doc_type="github_readme",
            url=repo_url,
            extra_metadata={"file": "repo_overview", "repo": repo},
        )
        if overview_chunks:
            chroma.add_documents(
                documents=[c["text"] for c in overview_chunks],
                metadatas=[c["metadata"] for c in overview_chunks],
                ids=[c["id"] for c in overview_chunks],
            )
            total_chunks += len(overview_chunks)

    # ── Fetch documentation files ──
    for file_path in TARGET_FILES:
        content = fetch_file_content(repo, file_path, headers)
        if not content:
            continue

        logger.info(f"  ✓ Found: {file_path} ({len(content)} chars)")

        # Save locally for inspection
        local_file = save_path / file_path.replace("/", "_")
        local_file.write_text(content, encoding="utf-8")

        source_name = f"github/{repo}/{file_path}"
        file_url = f"{repo_url}/blob/main/{file_path}"

        chunks = chunk_text(
            text=content,
            source=source_name,
            doc_type="github_readme",
            url=file_url,
            extra_metadata={"repo": repo, "file": file_path, "owner": owner},
        )

        if chunks:
            chroma.add_documents(
                documents=[c["text"] for c in chunks],
                metadatas=[c["metadata"] for c in chunks],
                ids=[c["id"] for c in chunks],
            )
            total_chunks += len(chunks)

        time.sleep(0.5)  # polite rate limiting

    logger.success(f"  Repo '{repo}': {total_chunks} chunks stored.")
    return total_chunks


def ingest_github(
    repos: Optional[list[str]] = None,
    force_reingest: bool = False,
) -> dict:
    """
    Main entry point for GitHub ingestion.

    Args:
        repos: List of 'owner/repo' strings. If None, reads from settings.
        force_reingest: Re-ingest even if already stored.

    Returns:
        Dict of {repo: chunk_count}
    """
    settings = get_settings()
    headers = _get_headers(settings.github_token)
    chroma = get_chroma_manager()

    # ── Determine repos to ingest ──
    if repos is None:
        repos = settings.github_repo_list

    if not repos and settings.github_username:
        logger.info(
            f"No specific repos configured. Fetching all public repos "
            f"for user: {settings.github_username}"
        )
        repos = get_public_repos(settings.github_username, headers)

    if not repos:
        logger.error(
            "No repos to ingest. Set GITHUB_REPOS or GITHUB_USERNAME in .env"
        )
        return {}

    logger.info(f"Starting GitHub ingestion for {len(repos)} repos...")

    results = {}
    for repo in repos:
        try:
            count = ingest_repository(
                repo=repo,
                headers=headers,
                chroma=chroma,
                force_reingest=force_reingest,
            )
            results[repo] = count
        except Exception as e:
            logger.error(f"Failed to ingest '{repo}': {e}")
            results[repo] = 0

    logger.success(
        f"GitHub ingestion complete. "
        f"Total repos: {len(repos)}, "
        f"Total chunks: {sum(results.values())}"
    )
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest GitHub repos into ChromaDB")
    parser.add_argument(
        "--repos",
        nargs="+",
        help="Specific repos to ingest (owner/repo format)",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingestion (clears old chunks)",
    )
    args = parser.parse_args()

    results = ingest_github(repos=args.repos, force_reingest=args.force)
    print("\n📊 Ingestion Summary:")
    for repo, count in results.items():
        print(f"  {repo}: {count} chunks")
    print(f"\n✅ Total: {sum(results.values())} chunks")
