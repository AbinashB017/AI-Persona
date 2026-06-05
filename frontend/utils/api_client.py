"""
frontend/utils/api_client.py
HTTP client for talking to the FastAPI backend.
"""
import httpx
import os
from typing import Optional

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 300  # seconds (increased to allow Render cold starts)


def chat(message: str, session_id: str = "default") -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(
            f"{BACKEND_URL}/chat",
            json={"message": message, "session_id": session_id},
        )
        resp.raise_for_status()
        return resp.json()


def book_meeting(
    name: str,
    email: str,
    date: str,
    time_slot: str,
    reason: str = "Interview",
    timezone: str = "Asia/Kolkata",
) -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(
            f"{BACKEND_URL}/book-meeting",
            json={
                "name": name,
                "email": email,
                "date": date,
                "time_slot": time_slot,
                "reason": reason,
                "timezone": timezone,
            },
        )
        resp.raise_for_status()
        return resp.json()


def get_availability(date: str, timezone: str = "Asia/Kolkata") -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(
            f"{BACKEND_URL}/availability",
            params={"date": date, "timezone": timezone},
        )
        resp.raise_for_status()
        return resp.json()


def health() -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(f"{BACKEND_URL}/health")
        resp.raise_for_status()
        return resp.json()
