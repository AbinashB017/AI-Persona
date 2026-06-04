"""
backend/api/phone.py
Twilio Webhook Integration for PSTN Phone Calls.
Satisfies the "Provide a phone number we can call" requirement.

Flow:
1. Twilio receives a phone call -> POST /phone/incoming
2. We return TwiML to <Say> a greeting and <Gather> speech.
3. User speaks -> Twilio transcribes -> POST /phone/respond
4. We route text to our RAG Tool-Calling Agent.
5. We return TwiML to <Say> the answer and <Gather> more speech.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, Request, Response
from loguru import logger
from backend.services.rag_service import answer_question
from backend.core.prompts import SYSTEM_PROMPT
from backend.core.config import get_settings
from xml.sax.saxutils import escape

router = APIRouter()


def build_twiml(text: str, gather_action: str = "/phone/respond") -> str:
    """Helper to build Twilio XML (TwiML) with a neural voice and speech gathering."""
    # Escape XML characters to prevent crashes
    safe_text = escape(text)
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna-Neural">{safe_text}</Say>
    <Gather input="speech" action="{gather_action}" speechTimeout="auto" hints="Abinash, resume, projects, schedule, interview">
    </Gather>
</Response>"""
    return xml


@router.post("/phone/incoming")
async def phone_incoming(request: Request):
    """Triggered by Twilio when a user calls the phone number."""
    settings = get_settings()
    logger.info("Incoming phone call received via Twilio!")
    
    greeting = (
        f"Hi, I am {settings.persona_name}'s AI representative. "
        f"I can answer questions about his background or schedule an interview. "
        f"How can I help you today?"
    )
    
    twiml = build_twiml(greeting)
    return Response(content=twiml, media_type="application/xml")


@router.post("/phone/respond")
async def phone_respond(request: Request):
    """Triggered by Twilio after it transcribes the user's speech."""
    form_data = await request.form()
    user_speech = form_data.get("SpeechResult", "").strip()
    call_sid = form_data.get("CallSid", "default_call")
    
    logger.info(f"[Phone] User said: '{user_speech}' (Call: {call_sid})")

    if not user_speech:
        # User was silent or STT failed. Prompt them again.
        twiml = build_twiml("I'm sorry, I didn't catch that. Could you please repeat?")
        return Response(content=twiml, media_type="application/xml")

    settings = get_settings()
    system = SYSTEM_PROMPT.format(
        persona_name=settings.persona_name,
        persona_tagline=settings.persona_tagline,
    )
    
    # Instruct agent to keep answers very short for phone calls
    phone_system = system + "\n\nCRITICAL: Keep your answers VERY short (1-2 sentences). You are speaking over a phone line. Do not use formatting like asterisks or bullet points."

    try:
        # Route through our full RAG Pipeline + Tool-Calling Agent
        chat_response = answer_question(
            message=user_speech,
            session_id=call_sid,
            override_system_prompt=phone_system,
        )
        answer = chat_response.answer
        
        # Strip sources section so it is not spoken over the phone
        answer = answer.split("Sources:")[0].split("Source:")[0]
        # Clean up any leftover markdown that TTS shouldn't pronounce
        answer = answer.replace("*", "").replace("#", "").replace("`", "")
        
        logger.info(f"[Phone] AI replied: {answer}")
    except Exception as e:
        logger.error(f"[Phone] Agent error: {e}")
        answer = "I'm having a little trouble connecting right now, but you can always email Abinash directly."

    twiml = build_twiml(answer)
    return Response(content=twiml, media_type="application/xml")
