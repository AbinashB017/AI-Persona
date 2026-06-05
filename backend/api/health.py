"""
backend/api/health.py — GET /health
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from backend.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health_check():
    settings = get_settings()
    
    docs = 0
    sources = []
    chroma_status = "lazy-loaded"
    
    # Fast path: Read directly from ChromaDB's underlying SQLite database
    # This avoids initializing the massive PyTorch library just for a health check!
    db_path = os.path.join(settings.chroma_persist_dir, "chroma.sqlite3")
    if os.path.exists(db_path):
        try:
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                docs = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
                source_rows = conn.execute("SELECT DISTINCT string_value FROM embedding_metadata WHERE key='source'").fetchall()
                sources = [row[0] for row in source_rows if row[0]]
                chroma_status = "ready (fast-stats)"
        except Exception as e:
            chroma_status = f"error reading sqlite: {e}"
    else:
        chroma_status = "database not found"

    return {
        "status": "ok",
        "persona": settings.persona_name,
        "model": settings.groq_model,
        "chromadb": chroma_status,
        "documents_indexed": docs,
        "sources": sources,
    }
