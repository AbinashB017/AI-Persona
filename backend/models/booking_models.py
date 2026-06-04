"""
backend/models/booking_models.py
Pydantic request/response models for POST /book-meeting
"""
from pydantic import BaseModel, Field
from typing import Optional


class BookingRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Interviewer's full name")
    email: str = Field(..., description="Interviewer's email address")  # str avoids email-validator dep
    date: str = Field(..., description="Preferred date in YYYY-MM-DD format")
    time_slot: str = Field(..., description="Preferred time e.g. '10:00' (24h, IST)")
    reason: Optional[str] = Field(default="Interview", description="Purpose of the meeting")
    timezone: str = Field(default="Asia/Kolkata", description="Timezone string")


class BookingResponse(BaseModel):
    success: bool
    booking_id: Optional[str] = None
    meeting_url: Optional[str] = None
    start_time: Optional[str] = None
    message: str
