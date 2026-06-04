"""
backend/core/memory.py
Per-session conversation memory using LangChain.
Sessions are stored in-process (dict). For multi-process deployments, swap with Redis.
"""
from loguru import logger
import threading

# Use langchain_community for stable import across version mismatches
try:
    from langchain_community.memory import ConversationBufferWindowMemory
except ImportError:
    from langchain.memory import ConversationBufferWindowMemory

_sessions: dict[str, ConversationBufferWindowMemory] = {}
_lock = threading.Lock()


def get_memory(session_id: str, window_k: int = 10) -> ConversationBufferWindowMemory:
    """Return (or create) a memory object for the given session_id."""
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = ConversationBufferWindowMemory(
                k=window_k,
                memory_key="chat_history",
                return_messages=True,
                human_prefix="User",
                ai_prefix="Abinash AI",
            )
            logger.debug(f"Created new memory for session: {session_id}")
        return _sessions[session_id]


def clear_memory(session_id: str) -> None:
    with _lock:
        if session_id in _sessions:
            del _sessions[session_id]
            logger.debug(f"Cleared memory for session: {session_id}")


def get_history_text(session_id: str) -> str:
    """Return conversation history as a formatted string for prompt injection."""
    mem = get_memory(session_id)
    messages = mem.chat_memory.messages
    if not messages:
        return ""
    lines = []
    for msg in messages:
        role = "User" if msg.type == "human" else "Abinash AI"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def save_exchange(session_id: str, human_msg: str, ai_msg: str) -> None:
    mem = get_memory(session_id)
    mem.chat_memory.add_user_message(human_msg)
    mem.chat_memory.add_ai_message(ai_msg)


def list_sessions() -> list[str]:
    with _lock:
        return list(_sessions.keys())
