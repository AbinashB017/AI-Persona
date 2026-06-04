"""
voice/livekit_agent.py
LiveKit voice agent: Deepgram STT → RAG backend → Deepgram TTS (Aura).
Abinash speaks in first person AS HIMSELF via the voice persona.

Run with:
    pip install livekit-agents livekit-plugins-deepgram livekit-plugins-openai
    python voice/livekit_agent.py start

Requires in .env:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    DEEPGRAM_API_KEY
    GROQ_API_KEY  (used as LLM shim via Groq's OpenAI-compatible API)
    BACKEND_URL
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import deepgram
from livekit.plugins import openai as lk_openai   # used with Groq's OpenAI-compatible API

from voice.prompts import VOICE_INTRO, VOICE_SYSTEM_PROMPT
from backend.core.config import get_settings

settings = get_settings()


async def query_backend(text: str, session_id: str = "voice_session") -> str:
    """Send text to FastAPI /chat and return clean plain-text answer."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.backend_url}/chat",
                json={"message": text, "session_id": session_id},
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "I couldn't find an answer to that.")
            # Strip markdown — TTS reads symbols literally
            answer = (answer
                      .replace("**", "").replace("*", "")
                      .replace("##", "").replace("#", "")
                      .replace("`", "").replace("> ", ""))
            return answer
    except Exception as e:
        logger.error(f"Backend query failed: {e}")
        return "I'm having trouble connecting. Please try again in a moment."


class PersonaAssistant(VoiceAssistant):
    """VoiceAssistant where Abinash speaks as himself via the RAG backend."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_id = f"voice_{id(self)}"

    async def on_user_speech_committed(self, user_msg: llm.ChatMessage):
        """Called on committed speech — routes to RAG, bypasses shim LLM entirely."""
        user_text = user_msg.content
        logger.info(f"[Voice] User: {user_text}")
        answer = await query_backend(user_text, self._session_id)
        logger.info(f"[Voice] Abinash answers: {answer[:80]}...")
        await self.say(answer, allow_interruptions=True)


async def entrypoint(ctx: JobContext):
    logger.info(f"Voice agent connected to room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # ── STT + TTS: Deepgram ──
    stt = deepgram.STT(api_key=settings.deepgram_api_key)
    tts = deepgram.TTS(
        api_key=settings.deepgram_api_key,
        model="aura-asteria-en",  # natural female voice (Abinash's AI persona)
    )

    # ── LLM shim: Groq via OpenAI-compatible API ──
    # VoiceAssistant requires an LLM object but we override on_user_speech_committed
    # so it's never actually called. Using Groq's OpenAI-compatible endpoint.
    shim_llm = lk_openai.LLM(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    assistant = PersonaAssistant(
        stt=stt,
        llm=shim_llm,
        tts=tts,
        chat_ctx=llm.ChatContext().append(
            role="system",
            text=VOICE_SYSTEM_PROMPT,
        ),
    )

    assistant.start(ctx.room)
    await asyncio.sleep(1)
    await assistant.say(VOICE_INTRO, allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
        )
    )
