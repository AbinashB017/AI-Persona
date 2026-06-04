"""
backend/models/chat_models.py
Pydantic request/response models for POST /chat
"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: str = Field(default="default", description="Session ID for conversation memory")


class SourceDocument(BaseModel):
    source: str
    doc_type: str
    url: Optional[str] = ""
    chunk_index: int = 0
    excerpt: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceDocument] = []
    session_id: str
    retrieval_count: int = 0
