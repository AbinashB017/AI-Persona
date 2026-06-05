"""
backend/services/chroma_service.py
Thin wrapper: query ChromaDB and format results for the RAG service.
Includes resume-priority fallback: personal fact queries always include resume chunks.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vectorstore.chroma_manager import get_chroma_manager
from backend.models.chat_models import SourceDocument
from backend.core.config import get_settings
from loguru import logger

# Keywords that indicate a personal/biographical question — should always include resume
_PERSONAL_KEYWORDS = [
    "cgpa", "gpa", "grade", "score", "marks", "percentage",
    "education", "degree", "college", "university", "iiit", "b.tech",
    "age", "phone", "email", "contact", "address", "location",
    "certif", "course", "skill", "language", "experience", "work",
    "intern", "job", "compan", "achiev", "award", "hobby",
]


def _needs_resume(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _PERSONAL_KEYWORDS)


def retrieve(query: str, top_k: int | None = None) -> tuple[str, list[SourceDocument]]:
    """
    Retrieve top-K chunks from ChromaDB for a query.

    If the query is about personal/biographical facts and no resume chunk
    appears in the top-K results, inject the top 2 resume chunks so that
    facts like CGPA, contact info, and education are never missed.

    Returns:
        (context_string, list_of_SourceDocument)
    """
    settings = get_settings()
    k = top_k or settings.rag_top_k
    chroma = get_chroma_manager()
    results = chroma.query(query, top_k=k)

    if not results:
        logger.warning(f"No results retrieved for query: '{query[:60]}'")
        return "", []

    # ── Resume-priority fallback ──
    has_resume = any(r["metadata"].get("source") == "resume.pdf" for r in results)
    if not has_resume and _needs_resume(query):
        logger.info("[Retrieve] Personal query but no resume chunk in top-K. Injecting resume chunks.")
        try:
            resume_results = chroma.query(query, top_k=2, where={"source": "resume.pdf"})
            if resume_results:
                # Prepend resume chunks, drop the lowest-ranked general result(s) to keep total = k
                seen_ids = {r["id"] for r in results}
                new_resume = [r for r in resume_results if r["id"] not in seen_ids]
                results = new_resume + results
                # Trim back to top_k to keep context size manageable
                results = results[:k]
        except Exception as e:
            logger.warning(f"[Retrieve] Resume fallback failed: {e}")

    context_parts = []
    sources = []

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        text = r["text"]
        source = meta.get("source", "unknown")
        url = meta.get("url", "")
        doc_type = meta.get("type", "unknown")
        chunk_idx = meta.get("chunk_index", 0)

        context_parts.append(f"[Source {i}: {source}]\n{text}")
        sources.append(
            SourceDocument(
                source=source,
                doc_type=doc_type,
                url=url,
                chunk_index=chunk_idx,
                excerpt=text[:200],
            )
        )

    context = "\n\n---\n\n".join(context_parts)
    return context, sources
