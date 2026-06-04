"""
backend/api/booking.py — POST /book-meeting
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from backend.models.booking_models import BookingRequest, BookingResponse
from backend.services.calcom_service import create_booking, get_available_slots
from loguru import logger

router = APIRouter()


@router.post("/book-meeting", response_model=BookingResponse)
def book_meeting(req: BookingRequest) -> BookingResponse:
    """
    Create a meeting booking via Cal.com.
    """
    logger.info(f"POST /book-meeting | {req.name} | {req.date} {req.time_slot}")
    try:
        result = create_booking(
            name=req.name,
            email=req.email,
            date=req.date,
            time_slot=req.time_slot,
            reason=req.reason or "Interview",
            timezone=req.timezone,
        )
        return BookingResponse(
            success=result["success"],
            booking_id=result.get("booking_id"),
            meeting_url=result.get("meeting_url"),
            start_time=result.get("start_time"),
            message=result.get("message", ""),
        )
    except Exception as e:
        logger.error(f"Booking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/availability")
def get_availability(date: str, timezone: str = "Asia/Kolkata"):
    """
    Check available slots for a given date (YYYY-MM-DD).
    """
    logger.info(f"GET /availability | date={date}")
    try:
        return get_available_slots(date=date, timezone=timezone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
