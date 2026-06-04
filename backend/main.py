"""
backend/main.py
FastAPI application entry point.
Run with: uvicorn backend.main:app --reload --port 8000
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.health import router as health_router
from backend.api.chat import router as chat_router
from backend.api.booking import router as booking_router
from backend.api.phone import router as phone_router
from backend.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle (replaces deprecated @app.on_event)."""
    logger.info(f"🚀 {settings.persona_name} AI Persona API starting...")
    logger.info(f"   Model   : {settings.groq_model}")
    logger.info(f"   ChromaDB: {settings.chroma_persist_dir}")
    logger.info(f"   Docs    : http://localhost:{settings.backend_port}/docs")
    
    # ── Trigger ChromaDB/PyTorch initialization in the background ──
    # This prevents the first chat request from timing out while PyTorch loads
    import threading
    from vectorstore.chroma_manager import get_chroma_manager
    threading.Thread(target=get_chroma_manager, daemon=True).start()
    
    yield
    logger.info("Shutting down API.")


app = FastAPI(
    title=f"{settings.persona_name} — AI Persona API",
    description="RAG-powered AI Persona for answering questions and scheduling interviews.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (allow Streamlit frontend) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(health_router, tags=["Health"])
app.include_router(chat_router, tags=["Chat"])
app.include_router(booking_router, tags=["Booking"])
app.include_router(phone_router, tags=["Phone / Twilio"])
