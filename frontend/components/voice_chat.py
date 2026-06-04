"""
frontend/components/voice_chat.py
Browser-based voice interface using Web Speech API.
- SpeechRecognition  → mic input  (built into Chrome/Edge)
- Fetch /chat        → RAG answer via backend
- SpeechSynthesis    → speaks the answer aloud (built into all browsers)

No extra packages needed. Works immediately in Chrome / Edge.
"""
import streamlit as st
import streamlit.components.v1 as components


def render_voice_chat(backend_url: str = "http://localhost:8000") -> None:
    """Render a self-contained voice chat widget."""

    voice_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    padding: 20px;
    min-height: 420px;
  }}
  .voice-card {{
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border: 1px solid #2563eb44;
    border-radius: 16px;
    padding: 24px;
    max-width: 600px;
    margin: 0 auto;
  }}
  h3 {{
    color: #60a5fa;
    margin-bottom: 6px;
    font-size: 1.1rem;
  }}
  .subtitle {{
    color: #64748b;
    font-size: 0.82rem;
    margin-bottom: 20px;
  }}
  .mic-area {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    margin: 20px 0;
  }}
  #mic-btn {{
    width: 80px; height: 80px;
    border-radius: 50%;
    border: 3px solid #2563eb;
    background: #1e3a5f;
    font-size: 2rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 0 0 rgba(37,99,235,0.4);
  }}
  #mic-btn:hover {{ background: #2563eb33; transform: scale(1.05); }}
  #mic-btn.listening {{
    background: #dc262622;
    border-color: #dc2626;
    animation: pulse 1.2s infinite;
  }}
  @keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(220,38,38,0.5); }}
    70%  {{ box-shadow: 0 0 0 14px rgba(220,38,38,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(220,38,38,0); }}
  }}
  #status {{
    font-size: 0.85rem;
    color: #94a3b8;
    text-align: center;
    min-height: 20px;
  }}
  .msg-box {{
    background: #1e293b;
    border-radius: 10px;
    padding: 12px 16px;
    margin-top: 12px;
    font-size: 0.88rem;
    line-height: 1.5;
    display: none;
  }}
  .msg-box.show {{ display: block; }}
  .label {{
    font-size: 0.72rem;
    color: #475569;
    margin-bottom: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  #you-box {{ border-left: 3px solid #64748b; }}
  #ai-box  {{ border-left: 3px solid #2563eb; }}
  .no-support {{
    background: #431407;
    border: 1px solid #c2410c;
    border-radius: 8px;
    padding: 12px;
    font-size: 0.83rem;
    color: #fed7aa;
    display: none;
  }}
  #stop-btn {{
    background: transparent;
    border: 1px solid #475569;
    color: #94a3b8;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    cursor: pointer;
    display: none;
  }}
  #stop-btn:hover {{ border-color: #94a3b8; color: #e2e8f0; }}
</style>
</head>
<body>
<div class="voice-card">
  <h3>🎙️ Voice Chat with Abinash</h3>
  <p class="subtitle">
    Powered by RAG · Uses browser microphone · Works in Chrome &amp; Edge
  </p>

  <div id="no-support" class="no-support">
    ⚠️ Your browser doesn't support Speech Recognition.
    Please use <strong>Google Chrome</strong> or <strong>Microsoft Edge</strong>.
  </div>

  <div class="mic-area">
    <button id="mic-btn" title="Click to speak">🎤</button>
    <div id="status">Click the mic and ask me anything</div>
    <button id="stop-btn" onclick="stopSpeaking()">⏹ Stop Speaking</button>
  </div>

  <div id="you-box" class="msg-box">
    <div class="label">You said</div>
    <div id="you-text"></div>
  </div>

  <div id="ai-box" class="msg-box">
    <div class="label">Abinash (AI) replied</div>
    <div id="ai-text"></div>
  </div>
</div>

<script>
const BACKEND = "{backend_url}";
const SESSION_ID = "voice_browser_" + Math.random().toString(36).substr(2, 8);

const micBtn  = document.getElementById("mic-btn");
const statusEl = document.getElementById("status");
const youBox  = document.getElementById("you-box");
const aiBox   = document.getElementById("ai-box");
const youText = document.getElementById("you-text");
const aiText  = document.getElementById("ai-text");
const stopBtn = document.getElementById("stop-btn");

// ── Check browser support ──
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SpeechRecognition) {{
  document.getElementById("no-support").style.display = "block";
  micBtn.disabled = true;
  micBtn.style.opacity = "0.3";
}}

// ── Speech Recognition ──
let recognition;
if (SpeechRecognition) {{
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
}}

micBtn.addEventListener("click", () => {{
  if (!recognition) return;
  stopSpeaking();
  recognition.start();
  micBtn.classList.add("listening");
  micBtn.textContent = "🔴";
  statusEl.textContent = "🎤 Listening... speak now";
}});

recognition && (recognition.onresult = async (event) => {{
  const transcript = event.results[0][0].transcript;
  micBtn.classList.remove("listening");
  micBtn.textContent = "🎤";
  statusEl.textContent = "⏳ Getting answer from Abinash's AI...";

  youText.textContent = transcript;
  youBox.classList.add("show");
  aiBox.classList.remove("show");

  try {{
    const response = await fetch(BACKEND + "/chat", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{ message: transcript, session_id: SESSION_ID }})
    }});

    if (!response.ok) throw new Error("Backend returned " + response.status);
    const data = await response.json();
    const rawAnswer = data.answer || "Sorry, I couldn't get an answer.";
    // Strip out the Sources section so it isn't spoken aloud
    const answerForSpeech = rawAnswer.split(/Sources?:/i)[0];

    const answer = answerForSpeech
      .replace(/\*\*|__/g, "")
      .replace(/#+\s/g, "")
      .replace(/`/g, "")
      .replace(/>\s/g, "");

    aiText.textContent = answer;
    aiBox.classList.add("show");
    statusEl.textContent = "🔊 Speaking...";

    speakText(answer);
  }} catch (err) {{
    statusEl.textContent = "❌ Error: " + err.message + " — Is FastAPI running on port 8000?";
  }}
}});

recognition && (recognition.onerror = (e) => {{
  micBtn.classList.remove("listening");
  micBtn.textContent = "🎤";
  if (e.error === "no-speech") {{
    statusEl.textContent = "No speech detected. Click and try again.";
  }} else if (e.error === "not-allowed") {{
    statusEl.textContent = "❌ Microphone access denied. Allow mic in browser settings.";
  }} else {{
    statusEl.textContent = "Error: " + e.error;
  }}
}});

// ── Speech Synthesis (TTS) ──
function speakText(text) {{
  if (!window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.92;
  utterance.pitch = 1.0;
  utterance.volume = 1.0;

  // Pick a natural voice if available
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(v =>
    v.name.includes("Google US English") ||
    v.name.includes("Microsoft David") ||
    v.name.includes("Microsoft Zira") ||
    v.lang === "en-US"
  );
  if (preferred) utterance.voice = preferred;

  utterance.onend = () => {{
    statusEl.textContent = "✅ Done. Click the mic to ask another question.";
    stopBtn.style.display = "none";
  }};

  stopBtn.style.display = "inline-block";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}}

function stopSpeaking() {{
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  stopBtn.style.display = "none";
  statusEl.textContent = "Click the mic and ask me anything";
}}

// Voices load async in some browsers
window.speechSynthesis && window.speechSynthesis.onvoiceschanged;
</script>
</body>
</html>
"""
    components.html(voice_html, height=480, scrolling=False)
