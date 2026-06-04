"""
backend/api/health.py — GET /health
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from vectorstore.chroma_manager import get_chroma_manager
from backend.core.config import get_settings

router = APIRouter()


from vectorstore.chroma_manager import _chroma_manager

@router.get("/health")
def health_check():
    settings = get_settings()
    
    # Do NOT initialize chroma here, as it triggers a massive 5-minute PyTorch load
    # which will cause Render's health check to timeout.
    if _chroma_manager is not None:
        try:
            stats = _chroma_manager.get_collection_stats()
            chroma_status = "ready"
            docs = stats.get("total_documents", 0)
            sources = stats.get("unique_sources", [])
        except Exception as e:
            chroma_status = f"error: {e}"
            docs = 0
            sources = []
    else:
        chroma_status = "lazy-loaded (waiting for first query)"
        docs = 0
        sources = []

    return {
        "status": "ok",
        "persona": settings.persona_name,
        "model": settings.groq_model,
        "chromadb": chroma_status,
        "documents_indexed": docs,
        "sources": sources,
    }
