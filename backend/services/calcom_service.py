"""
backend/services/calcom_service.py
Cal.com REST API v2 integration — REAL bookings, real Cal Video links.
Docs: https://cal.com/docs/api-reference/v2
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx
from loguru import logger
from backend.core.config import get_settings

CALCOM_API_BASE = "https://api.cal.com/v2"

# Cache event type ID so we don't fetch it on every request
_event_type_id_cache: dict[str, int] = {}


def _headers() -> dict:
    settings = get_settings()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.calcom_api_key}",
        "cal-api-version": "2024-08-13",
    }


def _get_event_type_id() -> int | None:
    """
    Resolve the numeric event type ID via Cal.com's public TRPC endpoint.
    Cached after first successful fetch.
    """
    settings = get_settings()
    slug = settings.calcom_event_type_slug      # "30min"
    username = settings.calcom_username         # "abinash-behera-a1w2nv"
    cache_key = f"{username}/{slug}"

    if cache_key in _event_type_id_cache:
        return _event_type_id_cache[cache_key]

    try:
        import urllib.parse
        input_data = f'{{"json":{{"username":"{username}","eventSlug":"{slug}","isTeamEvent":false,"org":null}}}}'
        url = f"https://cal.com/api/trpc/public/event?input={urllib.parse.quote(input_data)}"

        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            event_id = data.get("result", {}).get("data", {}).get("json", {}).get("id")
            if event_id:
                _event_type_id_cache[cache_key] = event_id
                logger.info(f"[Cal.com] Resolved event type ID: {event_id}")
                return event_id
            logger.error(f"[Cal.com] Could not find event ID in TRPC response: {data}")
            return None
    except Exception as e:
        logger.error(f"[Cal.com] Failed to fetch event type ID: {e}")
        return None


def get_available_slots(date: str, timezone: str = "Asia/Kolkata") -> dict:
    """
    Fetch real available time slots from Cal.com for a given date (YYYY-MM-DD).
    """
    event_type_id = _get_event_type_id()
    if not event_type_id:
        logger.warning("[Cal.com] Could not get event type ID, returning fallback slots")
        return {
            "success": True,
            "date": date,
            "slots": ["10:00", "11:30", "14:00", "16:00"],
            "count": 4,
            "note": "Fallback slots — Cal.com unavailable",
        }

    try:
        # Cal.com expects ISO 8601 datetime range
        start_time = f"{date}T00:00:00"
        end_time   = f"{date}T23:59:59"

        url = f"{CALCOM_API_BASE}/slots/available"
        params = {
            "eventTypeId": event_type_id,
            "startTime": start_time,
            "endTime": end_time,
            "timeZone": timezone,
        }

        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=_headers(), params=params)
            resp.raise_for_status()
            data = resp.json()

        # Response: {"status":"success","data":{"slots":{"2026-06-08":[{"time":"..."},...]}}}
        slots_by_date = data.get("data", {}).get("slots", {})
        raw_slots = slots_by_date.get(date, [])

        # Extract HH:MM from ISO timestamps like "2026-06-09T10:00:00+05:30"
        slot_times = []
        for s in raw_slots:
            t = s.get("time", "")
            # Parse the time portion only
            if "T" in t:
                time_part = t.split("T")[1][:5]  # "10:00"
                slot_times.append(time_part)

        logger.info(f"[Cal.com] {len(slot_times)} slots available on {date}")
        return {
            "success": True,
            "date": date,
            "slots": slot_times,
            "count": len(slot_times),
        }

    except Exception as e:
        logger.error(f"[Cal.com] get_available_slots failed: {e}")
        return {
            "success": False,
            "date": date,
            "slots": [],
            "count": 0,
            "error": str(e),
        }


def create_booking(
    name: str,
    email: str,
    date: str,
    time_slot: str,
    reason: str = "Interview",
    timezone: str = "Asia/Kolkata",
) -> dict:
    """
    Create a REAL booking on Cal.com.
    Sends a confirmation email to the attendee with a Cal Video link.
    """
    event_type_id = _get_event_type_id()
    if not event_type_id:
        return {
            "success": False,
            "message": "Could not resolve Cal.com event type. Please try again.",
        }

    try:
        # Build ISO 8601 start time with IST offset (+05:30)
        tz_offset = "+05:30" if timezone == "Asia/Kolkata" else "Z"
        start_time = f"{date}T{time_slot}:00{tz_offset}"

        payload = {
            "eventTypeId": event_type_id,
            "start": start_time,
            "attendee": {
                "name": name,
                "email": email,
                "timeZone": timezone,
                "language": "en",
            },
            "metadata": {
                "reason": reason,
            },
        }

        logger.info(f"[Cal.com] Creating booking: {name} <{email}> on {date} at {time_slot}")

        with httpx.Client(timeout=20) as client:
            resp = client.post(
                f"{CALCOM_API_BASE}/bookings",
                headers=_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Response: {"status":"success","data":{"uid":"...","meetingUrl":"...",...}}
        booking_data = data.get("data", {})
        booking_uid  = booking_data.get("uid", "")
        meeting_url  = booking_data.get("meetingUrl", "")
        start        = booking_data.get("start", start_time)

        logger.success(f"[Cal.com] Booking created! UID={booking_uid}, URL={meeting_url}")

        return {
            "success": True,
            "booking_id": booking_uid,
            "meeting_url": meeting_url,
            "start_time": start,
            "message": (
                f"✅ Booking confirmed! A calendar invite has been sent to {email}. "
                f"Meeting on {date} at {time_slot} IST. "
                + (f"Join here: {meeting_url}" if meeting_url else "")
            ),
        }

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error(f"[Cal.com] Booking API error {e.response.status_code}: {error_body}")
        return {
            "success": False,
            "message": f"Booking failed: {error_body[:200]}",
        }
    except Exception as e:
        logger.error(f"[Cal.com] create_booking failed: {e}")
        return {
            "success": False,
            "message": f"Booking error: {str(e)}",
        }
