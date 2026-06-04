"""
ingestion/ingest_resume.py
Parse a PDF resume, extract text, chunk it, and store in ChromaDB.

Supports:
- PyMuPDF (fitz) for PDF parsing — best quality
- Falls back to plain text if .txt file is provided
"""
import fitz  # PyMuPDF
import os
import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.chunking import chunk_text
from vectorstore.chroma_manager import get_chroma_manager


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF using PyMuPDF.
    Preserves paragraph structure via block-level extraction.

    Returns:
        Full text as a single string.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")

    logger.info(f"Opening PDF: {pdf_path}")
    doc = fitz.open(str(path))
    pages_text = []

    for page_num, page in enumerate(doc, start=1):
        # Extract text blocks sorted by position (top-to-bottom, left-to-right)
        blocks = page.get_text("blocks", sort=True)
        page_text = "\n".join(
            block[4].strip() for block in blocks if block[4].strip()
        )
        if page_text:
            pages_text.append(f"--- Page {page_num} ---\n{page_text}")
        logger.debug(f"  Page {page_num}: {len(page_text)} chars extracted")

    doc.close()
    full_text = "\n\n".join(pages_text)
    logger.info(f"PDF extraction complete. Total chars: {len(full_text)}")
    return full_text


def extract_text_from_txt(txt_path: str) -> str:
    """Fallback: read plain text file."""
    path = Path(txt_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume TXT not found: {txt_path}")
    return path.read_text(encoding="utf-8")


def ingest_resume(
    resume_path: str = "data/resume.pdf",
    force_reingest: bool = False,
) -> int:
    """
    Main entry point for resume ingestion.

    Args:
        resume_path: Path to the resume PDF or TXT file.
        force_reingest: If True, deletes existing resume chunks before re-ingesting.

    Returns:
        Number of chunks stored.
    """
    path = Path(resume_path)
    source_name = path.name  # e.g., "resume.pdf"

    chroma = get_chroma_manager()

    # ── Optional: clear old resume chunks ──
    if force_reingest:
        logger.info(f"Force re-ingest: removing existing chunks for '{source_name}'")
        chroma.delete_by_source(source_name)

    # ── Extract text ──
    if path.suffix.lower() == ".pdf":
        raw_text = extract_text_from_pdf(str(path))
    elif path.suffix.lower() in (".txt", ".md"):
        raw_text = extract_text_from_txt(str(path))
    else:
        raise ValueError(f"Unsupported resume format: {path.suffix}")

    if not raw_text.strip():
        logger.error("No text extracted from resume. Aborting.")
        return 0

    # ── Chunk ──
    chunks = chunk_text(
        text=raw_text,
        source=source_name,
        doc_type="resume",
        url="",
        extra_metadata={"file_path": str(path.resolve())},
    )

    if not chunks:
        logger.error("No chunks generated. Check resume content.")
        return 0

    # ── Store in ChromaDB ──
    chroma.add_documents(
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
        ids=[c["id"] for c in chunks],
    )

    logger.success(f"Resume ingested: {len(chunks)} chunks stored from '{source_name}'")
    return len(chunks)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest resume into ChromaDB")
    parser.add_argument(
        "--path", default="data/resume.pdf", help="Path to resume PDF or TXT"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-ingestion (clears old chunks)"
    )
    args = parser.parse_args()

    count = ingest_resume(resume_path=args.path, force_reingest=args.force)
    print(f"\n✅ Done. {count} chunks stored.")
