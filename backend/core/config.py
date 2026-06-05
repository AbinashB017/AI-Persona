"""
backend/core/config.py
Centralized settings loaded from .env via pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Persona ---
    persona_name: str = "Abinash"
    persona_tagline: str = "AI Engineer & Solutions Architect"

    # --- Groq ---
    groq_api_key: str
    groq_api_key_2: Optional[str] = None
    groq_api_key_3: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"

    # --- GitHub ---
    github_token: Optional[str] = None
    github_repos: str = ""          # comma-separated owner/repo strings
    github_username: str = ""

    # --- ChromaDB ---
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection_name: str = "ai_persona"

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- RAG ---
    rag_top_k: int = 5
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    conversation_memory_window: int = 10

    # --- Cal.com ---
    calcom_api_key: Optional[str] = None
    calcom_event_type_slug: str = "30min"
    calcom_username: str = ""

    # --- LiveKit ---
    livekit_url: Optional[str] = None
    livekit_api_key: Optional[str] = None
    livekit_api_secret: Optional[str] = None

    # --- ElevenLabs ---
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None

    # --- Deepgram ---
    deepgram_api_key: Optional[str] = None

    # --- Backend ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_url: str = "http://localhost:8000"

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def github_repo_list(self) -> list[str]:
        """Return list of 'owner/repo' strings from comma-separated env var."""
        if not self.github_repos:
            return []
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — import this everywhere."""
    return Settings()
