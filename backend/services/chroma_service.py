"""
backend/services/chroma_service.py
Thin wrapper: query ChromaDB and format results for the RAG service.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vectorstore.chroma_manager import get_chroma_manager
from backend.models.chat_models import SourceDocument
from backend.core.config import get_settings
from loguru import logger


def retrieve(query: str, top_k: int | None = None) -> tuple[str, list[SourceDocument]]:
    """
    Retrieve top-K chunks from ChromaDB for a query.

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

    context_parts = []
    sources = []

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        text = r["text"]
        source = meta.get("source", "unknown")
        url = meta.get("url", "")
        doc_type = meta.get("type", "unknown")
        chunk_idx = meta.get("chunk_index", 0)

        context_parts.append(
            f"[Source {i}: {source}]\n{text}"
        )
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
