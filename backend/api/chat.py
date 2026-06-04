"""
backend/api/chat.py — POST /chat
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from backend.models.chat_models import ChatRequest, ChatResponse
from backend.services.rag_service import answer_question
from loguru import logger

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Accept a user message and return a grounded RAG answer with source citations.
    """
    logger.info(f"POST /chat | session={req.session_id} | msg={req.message[:60]}")
    try:
        return answer_question(message=req.message, session_id=req.session_id)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
