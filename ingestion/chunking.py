"""
ingestion/chunking.py
Text splitting strategies for resume and GitHub README content.
Uses LangChain's RecursiveCharacterTextSplitter for semantic-friendly splits.
"""
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import get_settings


def get_text_splitter(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> RecursiveCharacterTextSplitter:
    """
    Return a configured RecursiveCharacterTextSplitter.
    Reads defaults from settings if not provided.
    """
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.rag_chunk_size,
        chunk_overlap=chunk_overlap or settings.rag_chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
        strip_whitespace=True,
    )


def clean_text(text: str) -> str:
    """
    Basic text cleaning:
    - Collapse excess whitespace/newlines
    - Remove non-printable characters
    - Normalize unicode dashes and quotes
    """
    # Normalize unicode
    text = text.encode("utf-8", errors="ignore").decode("utf-8")
    # Replace fancy quotes/dashes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "--")
    # Remove control characters except newline/tab
    text = re.sub(r"[^\x09\x0a\x20-\x7e\x80-\xff]", " ", text)
    # Collapse 3+ newlines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def chunk_text(
    text: str,
    source: str,
    doc_type: str,
    url: str = "",
    extra_metadata: dict | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    """
    Split text into chunks and attach rich metadata.

    Args:
        text: The raw document text.
        source: Human-readable source name (e.g., "resume.pdf", "github/myrepo/README.md")
        doc_type: One of: "resume", "github_readme", "github_doc"
        url: Optional URL for linking back to the source.
        extra_metadata: Any additional metadata key-value pairs.
        chunk_size: Override default chunk size.
        chunk_overlap: Override default overlap.

    Returns:
        List of dicts with keys: {text, metadata, id}
    """
    text = clean_text(text)
    if not text:
        logger.warning(f"Empty text for source: {source}")
        return []

    splitter = get_text_splitter(chunk_size, chunk_overlap)
    chunks = splitter.split_text(text)

    result = []
    for i, chunk in enumerate(chunks):
        if len(chunk.strip()) < 20:  # skip tiny fragments
            continue

        chunk_id = f"{doc_type}__{source}__{i:04d}".replace("/", "_").replace(" ", "_")
        metadata = {
            "source": source,
            "type": doc_type,
            "url": url,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "char_count": len(chunk),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        result.append(
            {
                "text": chunk,
                "metadata": metadata,
                "id": chunk_id,
            }
        )

    logger.info(f"Chunked '{source}' → {len(result)} chunks (from {len(text)} chars)")
    return result


def chunk_documents(
    documents: list[dict],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    """
    Chunk multiple documents in batch.

    Args:
        documents: List of dicts with keys: {text, source, type, url, metadata (optional)}

    Returns:
        Flat list of chunks across all documents.
    """
    all_chunks = []
    for doc in documents:
        chunks = chunk_text(
            text=doc["text"],
            source=doc["source"],
            doc_type=doc["type"],
            url=doc.get("url", ""),
            extra_metadata=doc.get("metadata"),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        all_chunks.extend(chunks)

    logger.success(f"Total chunks from {len(documents)} documents: {len(all_chunks)}")
    return all_chunks
