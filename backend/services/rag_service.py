"""
backend/services/rag_service.py
Core RAG pipeline: retrieve context -> build prompt -> call Groq -> return answer + sources.
For booking/availability intent: bypass RAG shortcut and route directly to the booking agent.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.chroma_service import retrieve
from backend.services.groq_service import chat_completion
from backend.core.prompts import SYSTEM_PROMPT, RAG_PROMPT, BOOKING_SYSTEM_PROMPT, BOOKING_KEYWORDS
from backend.core.memory import get_history_text, save_exchange
from backend.core.config import get_settings
from backend.models.chat_models import ChatResponse, SourceDocument
from loguru import logger


def _is_booking_intent(message: str) -> bool:
    """
    Detect if the user's message is about booking a meeting or checking availability.
    Checks for booking keywords in a case-insensitive way.
    """
    msg_lower = message.lower()
    return any(keyword in msg_lower for keyword in BOOKING_KEYWORDS)


def answer_question(message: str, session_id: str = "default", override_system_prompt: str = None) -> ChatResponse:
    """
    Full RAG pipeline with booking intent routing:

    - If message is a BOOKING request:
        1. Skip RAG retrieval shortcut entirely
        2. Pass conversation history to the booking agent
        3. Let LangChain agent call check_availability / book_meeting tools
        4. Return agent's response (no sources -- it's a live booking)

    - If message is a RAG question:
        1. Retrieve relevant chunks from ChromaDB
        2. Build prompt with context + conversation history
        3. Call Groq LLM
        4. Return structured response with sources

    Args:
        message: User's question or booking request
        session_id: Session ID for conversation memory
        override_system_prompt: Optional custom system prompt (useful for voice/phone)

    Returns:
        ChatResponse with answer and source citations
    """
    settings = get_settings()

    logger.info(f"[RAG] Query: '{message[:60]}' | Session: {session_id}")

    # ── Booking Intent Detection ──
    if _is_booking_intent(message):
        logger.info("[RAG] Booking intent detected -- routing to booking agent")
        history = get_history_text(session_id)

        # Build the agent input: conversation history + current request
        if history:
            agent_input = f"CONVERSATION HISTORY:\n{history}\n\nCURRENT REQUEST: {message}"
        else:
            agent_input = message

        booking_system = override_system_prompt or BOOKING_SYSTEM_PROMPT

        answer = chat_completion(
            system_prompt=booking_system,
            user_message=agent_input,
            temperature=0.1,
            max_tokens=512,
        )

        save_exchange(session_id, message, answer)
        logger.success("[RAG] Booking agent responded.")

        return ChatResponse(
            answer=answer,
            sources=[],
            session_id=session_id,
            retrieval_count=0,
        )

    # ── Step 1: Retrieve context (RAG path) ──
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

    if history:
        rag_user_msg = f"CONVERSATION HISTORY:\n{history}\n\n{rag_user_msg}"

    # ── Step 4: Call Groq ──
    if not context:
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
