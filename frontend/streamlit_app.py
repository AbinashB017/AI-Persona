"""
frontend/streamlit_app.py
AI Persona — Chat + Voice interface.
"""
import sys, os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import uuid
from dotenv import load_dotenv

load_dotenv()

from frontend.utils import api_client
from frontend.components.sidebar import render_sidebar
from frontend.components.source_citations import render_sources
from frontend.components.voice_chat import render_voice_chat

st.set_page_config(
    page_title="Abinash Behera — AI Persona",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.persona-header {
    background: linear-gradient(135deg, #0f172a, #1e3a5f);
    padding: 20px 24px;
    border-radius: 12px;
    margin-bottom: 16px;
    border: 1px solid #2563eb33;
}
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "mode" not in st.session_state:
    st.session_state.mode = "chat"
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

render_sidebar()

st.markdown("""
<div class="persona-header">
    <h2 style="margin:0;color:#e2e8f0;">🤖 Abinash's AI Representative</h2>
    <p style="margin:4px 0 0;color:#94a3b8;font-size:0.9rem;">
        Ask about Abinash's background, or ask to schedule an interview with him!
    </p>
</div>
""", unsafe_allow_html=True)

col_chat, col_voice, col_spacer = st.columns([1, 1, 6])
with col_chat:
    if st.button("💬 Chat", use_container_width=True,
                 type="primary" if st.session_state.mode == "chat" else "secondary"):
        st.session_state.mode = "chat"
        st.rerun()
with col_voice:
    if st.button("🎙️ Voice", use_container_width=True,
                 type="primary" if st.session_state.mode == "voice" else "secondary"):
        st.session_state.mode = "voice"
        st.rerun()

st.divider()

if st.session_state.mode == "chat":
    # Suggested questions
    if not st.session_state.messages:
        st.markdown("**💡 Try asking:**")
        cols = st.columns(3)
        suggestions = [
            "What projects has Abinash built?",
            "What are Abinash's technical skills?",
            "Tell me about AutoMedRAG",
            "What is Abinash's educational background?",
            "Can we schedule an interview next week?",
            "What times is he available tomorrow?",
        ]
        for i, col in enumerate(cols):
            for q in suggestions[i::3]:
                if col.button(q, key=f"sug_{q}", use_container_width=True):
                    st.session_state.pending_prompt = q
                    st.rerun()

    # Render History
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    render_sources(msg["sources"])

    # Input handling
    prompt = st.chat_input("Ask about Abinash's skills, or schedule a meeting...")
    
    # Override with pending prompt if suggestion was clicked
    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Avoid double rendering if it came from the text input box
        if prompt != st.session_state.messages[-1]["content"] or len(st.session_state.messages) > 1:
             with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
        
        # If it's the very first message from pending prompt, manually render it for immediate feedback
        elif len(st.session_state.messages) == 1:
             with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking..."):
                try:
                    result = api_client.chat(
                        message=prompt,
                        session_id=st.session_state.session_id,
                    )
                    answer = result.get("answer", "Sorry, I couldn't generate a response.")
                    sources = result.get("sources", [])

                    st.markdown(answer)
                    if sources:
                        render_sources(sources)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    })
                except Exception as e:
                    err_msg = f"⚠️ Backend unreachable: `{e}`"
                    st.error(err_msg)

else:
    st.markdown("""
    ### 🎙️ Talk to Abinash's AI Representative
    **How it works:** Click the mic → speak → the AI answers and speaks back.
    *You can even ask me to check Abinash's calendar and book an interview for you!*
    """)
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    render_voice_chat(backend_url=backend_url)
