"""
backend/services/rag_service.py
Core RAG pipeline: retrieve context → build prompt → call Groq → return answer + sources.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.chroma_service import retrieve
from backend.services.groq_service import chat_completion
from backend.core.prompts import SYSTEM_PROMPT, RAG_PROMPT
from backend.core.memory import get_history_text, save_exchange
from backend.core.config import get_settings
from backend.models.chat_models import ChatResponse, SourceDocument
from loguru import logger


def answer_question(message: str, session_id: str = "default", override_system_prompt: str = None) -> ChatResponse:
    """
    Full RAG pipeline:
    1. Retrieve relevant chunks from ChromaDB
    2. Build prompt with context + conversation history
    3. Call Groq LLM
    4. Save exchange to memory
    5. Return structured response

    Args:
        message: User's question
        session_id: Session ID for conversation memory
        override_system_prompt: Optional custom system prompt (useful for voice/phone)

    Returns:
        ChatResponse with answer and source citations
    """
    settings = get_settings()

    # ── Step 1: Retrieve context ──
    logger.info(f"[RAG] Query: '{message[:60]}' | Session: {session_id}")
    context, sources = retrieve(message, top_k=settings.rag_top_k)

    # ── Step 2: Build system prompt ──
    if override_system_prompt:
        system = override_system_prompt
    else:
        system = SYSTEM_PROMPT.format(
            persona_name=settings.persona_name,
            persona_tagline=settings.persona_tagline,
        )

    # ── Step 3: Build user message with context + history ──
    history = get_history_text(session_id)

    rag_user_msg = RAG_PROMPT.substitute(
        context=context if context else "No relevant context found in knowledge base.",
        question=message,
    )

    # Prepend recent conversation history so the LLM is aware of context
    if history:
        rag_user_msg = f"CONVERSATION HISTORY:\n{history}\n\n{rag_user_msg}"

    # ── Step 4: Call Groq ──
    if not context:
        # No retrieval results — instruct LLM to say so
        answer = (
            f"I don't have specific information about that in my knowledge base. "
            f"You can reach {settings.persona_name} directly at avinashapms@gmail.com "
            f"or schedule an interview using the booking feature."
        )
        sources = []
    else:
        answer = chat_completion(
            system_prompt=system,
            user_message=rag_user_msg,
            temperature=0.2,
            max_tokens=1024,
        )

    # ── Step 5: Persist to memory ──
    save_exchange(session_id, message, answer)

    logger.success(f"[RAG] Answer generated. Sources: {len(sources)}")

    return ChatResponse(
        answer=answer,
        sources=sources,
        session_id=session_id,
        retrieval_count=len(sources),
    )
