"""
backend/api/health.py — GET /health
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from vectorstore.chroma_manager import get_chroma_manager
from backend.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health_check():
    settings = get_settings()
    try:
        chroma = get_chroma_manager()
        stats = chroma.get_collection_stats()
        chroma_status = "ok"
    except Exception as e:
        stats = {}
        chroma_status = f"error: {e}"

    return {
        "status": "ok",
        "persona": settings.persona_name,
        "model": settings.groq_model,
        "chromadb": chroma_status,
        "documents_indexed": stats.get("total_documents", 0),
        "sources": stats.get("unique_sources", []),
    }
