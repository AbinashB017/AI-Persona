# AI Persona: Abinash Behera

An autonomous AI representative built for Abinash Behera. This project serves as an interactive voice and text agent that acts on Abinash's behalf. It answers questions based on his real resume and GitHub repositories, and it can autonomously check his calendar and schedule interviews.

## 🌟 Features

- **Text Chat (Streamlit):** An interactive UI where users can ask questions about Abinash's background.
- **Web Voice Chat:** A browser-based microphone interface that talks back using text-to-speech.
- **Phone Number Integration (Twilio):** A native PSTN integration allowing users to dial a real phone number to speak with the AI.
- **Retrieval-Augmented Generation (RAG):** Answers are grounded strictly in Abinash's resume and GitHub projects using **ChromaDB**.
- **Autonomous Tool Calling:** Powered by **LangChain**, the AI can autonomously call the **Cal.com** API to check availability and book meetings without human intervention.
- **Hallucination Prevention:** Strict prompts ensure the AI only speaks from retrieved context and never invents facts.

---

## 🏛️ Architecture

The system is separated into a modular Backend and Frontend.

### 1. Backend (FastAPI + LangChain + ChromaDB)
- **Framework:** `FastAPI` serves all REST endpoints (`/chat`, `/booking`, `/phone/incoming`, `/phone/respond`).
- **LLM Engine:** Uses **Groq** (`llama-3.3-70b-versatile`) for ultra-low latency generation, routed through **LangChain's Tool Calling Agent (`AgentExecutor`)**.
- **Vector Database:** `ChromaDB` stores embeddings of the resume and GitHub READMEs, generated using `Sentence-transformers` (`all-MiniLM-L6-v2`).
- **Calendar Tools:** Integrates with `Cal.com` via their API v2 / TRPC to read available slots and dispatch booking requests.
- **Telephony:** Uses a Twilio Webhook architecture (`TwiML`) to parse incoming speech and stream TTS responses back over the phone line.

### 2. Frontend (Streamlit)
- **Framework:** `Streamlit` provides a clean, responsive web interface.
- **Text Mode:** Renders markdown answers and collapsible source citations.
- **Voice Mode:** Uses the browser's native Web Speech API (`SpeechRecognition` & `SpeechSynthesisUtterance`) to record audio, send text to the backend, and speak the response.

---

## 🚀 Local Setup

### Prerequisites
- Python 3.10+
- [Git](https://git-scm.com/)
- API Keys: Groq, Cal.com

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/AbinashB017/AI-Persona.git
cd AI-Persona
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the root directory and add your keys (never commit this file):
```env
PERSONA_NAME=Abinash Behera
GROQ_API_KEY=your_groq_key
CALCOM_API_KEY=your_calcom_key
CALCOM_USERNAME=your_calcom_username
CALCOM_EVENT_TYPE_SLUG=30min
```

### 3. Data Ingestion
Run the ingestion pipeline to embed the resume and download GitHub repositories:
```bash
python -m ingestion.ingest_resume
python -m ingestion.ingest_github
```

### 4. Running the Application
You need two terminals.

**Terminal 1 (Backend):**
```bash
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```bash
streamlit run frontend/streamlit_app.py
```

### 5. Testing the Phone Agent (Twilio)
If you want to call the AI from a real phone:
1. Run `npx ngrok http 8000` to expose your local backend.
2. In your Twilio Console, set your phone number's Webhook URL to: `https://<your-ngrok-url>.ngrok-free.app/phone/incoming`
3. Dial the number! (Or use the included `call_me.py` script to have Twilio call your phone).

---

## 📂 Project Structure

```text
├── backend/
│   ├── api/             # FastAPI routers (chat, booking, phone, health)
│   ├── core/            # Config, Prompts, Memory
│   ├── models/          # Pydantic data models
│   ├── services/        # Logic (RAG, Groq, Chroma, Cal.com)
├── frontend/
│   ├── components/      # UI pieces (sidebar, voice_chat, sources)
│   └── streamlit_app.py # Main UI entrypoint
├── ingestion/           # Data loading scripts (Resume & GitHub)
├── data/                # Raw PDFs and scraped Markdown
├── chroma_db/           # Local vector database (ignored by git)
├── .env                 # Environment variables (ignored by git)
└── requirements.txt     # Python dependencies
```

## 📝 License
This project was developed for the Scaler AI Agent assignment.
