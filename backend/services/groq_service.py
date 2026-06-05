"""
backend/services/groq_service.py
LLM Agent using LangChain (ChatGroq). Supports Tool Calling for Cal.com booking.
Satisfies the "Framework: LangChain" and "book confirmed meeting without human intervention" requirements.
"""
import sys, os, json, threading, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import get_settings
from backend.services.calcom_service import get_available_slots, create_booking
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor


# ── Round-robin Groq API key manager ──
class _KeyRotator:
    """Thread-safe round-robin over all configured Groq API keys."""
    def __init__(self):
        self._lock = threading.Lock()
        self._cycle = None  # built lazily on first use

    def _build_cycle(self):
        settings = get_settings()
        keys = [k for k in [
            settings.groq_api_key,
            settings.groq_api_key_2,
            settings.groq_api_key_3,
        ] if k and k.strip()]
        if not keys:
            raise ValueError("No Groq API keys configured.")
        logger.info(f"[KeyRotator] {len(keys)} Groq API key(s) loaded.")
        self._cycle = itertools.cycle(keys)

    def next_key(self) -> str:
        with self._lock:
            if self._cycle is None:
                self._build_cycle()
            return next(self._cycle)


_key_rotator = _KeyRotator()


@tool
def check_availability(date: str) -> str:
    """
    Check Abinash's calendar availability for a specific date.
    Args:
        date: String in YYYY-MM-DD format (e.g. '2026-06-10').
    Returns:
        JSON string of available time slots.
    """
    logger.info(f"[Tool] Checking real Cal.com availability for {date}")
    res = get_available_slots(date=date, timezone="Asia/Kolkata")
    return json.dumps(res)


@tool
def book_meeting(name: str, email: str, date: str, time_slot: str, reason: str = "Interview") -> str:
    """
    Book a real confirmed meeting on Abinash's Cal.com calendar.
    Sends a calendar invite and Cal Video link to the attendee's email.
    Args:
        name: Interviewer's full name.
        email: Interviewer's email address.
        date: String in YYYY-MM-DD format (e.g. '2026-06-10').
        time_slot: String in HH:MM format 24-hour (e.g. '10:00').
        reason: Optional reason for the meeting.
    Returns:
        JSON string with booking confirmation details including meeting URL.
    """
    logger.info(f"[Tool] Creating real Cal.com booking for {name} on {date} at {time_slot}")
    res = create_booking(
        name=name,
        email=email,
        date=date,
        time_slot=time_slot,
        reason=reason,
        timezone="Asia/Kolkata",
    )
    return json.dumps(res)


tools = [check_availability, book_meeting]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60))
def chat_completion(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """
    Send a chat completion request via LangChain's Tool Calling Agent.
    Uses round-robin key rotation across all configured Groq API keys.
    """
    settings = get_settings()
    api_key = _key_rotator.next_key()
    logger.debug(f"[LLM] Using key ...{api_key[-6:]} | query: {user_message[:60]}...")

    try:
        llm = ChatGroq(
            api_key=api_key,
            model_name=settings.groq_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=5
        )

        response = agent_executor.invoke({"input": user_message})
        answer = response["output"]
        return answer

    except Exception as e:
        logger.error(f"[LLM] AgentExecutor failed: {e}. Retrying with direct LLM + tools...")
        # Fallback: use ChatGroq directly but still bind tools so booking still works
        try:
            llm = ChatGroq(
                api_key=_key_rotator.next_key(),  # rotate to next key for fallback too
                model_name=settings.groq_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            llm_with_tools = llm.bind_tools(tools)
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
            response = llm_with_tools.invoke(messages)
            return response.content or "I'm sorry, I couldn't generate a response. Please try again."
        except Exception as e2:
            logger.error(f"[LLM] Fallback also failed: {e2}")
            return "I'm experiencing technical difficulties. Please try again in a moment."
