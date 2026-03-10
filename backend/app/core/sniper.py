"""
Course Sniper — polls the Rutgers SOC API for open sections and sends
an SMS via Twilio when a watched section opens up.
"""

import os
import logging
from datetime import datetime

import requests as http_requests
from twilio.rest import Client as TwilioClient

from ..database import SessionLocal
from .. import models

log = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

TERM_LABELS = {"9": "Fall", "1": "Spring", "7": "Summer", "0": "Winter"}

SOC_OPEN_URL = "https://sis.rutgers.edu/soc/api/openSections.json"
SOC_COURSES_URL = "https://sis.rutgers.edu/soc/api/courses.json"


def _twilio_client() -> TwilioClient | None:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        log.warning("Twilio env vars not configured — SMS will not be sent.")
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_sms(to_number: str, body: str) -> bool:
    client = _twilio_client()
    if not client:
        return False
    try:
        client.messages.create(to=to_number, from_=TWILIO_FROM_NUMBER, body=body)
        return True
    except Exception as exc:
        log.error("Twilio SMS failed: %s", exc)
        return False


def _fetch_open_indices(year: str, term: str, campus: str) -> set[str]:
    """Returns a set of open section index strings for the given term."""
    try:
        resp = http_requests.get(
            SOC_OPEN_URL,
            params={"year": year, "term": term, "campus": campus},
            timeout=10,
        )
        resp.raise_for_status()
        return set(str(idx) for idx in resp.json())
    except Exception as exc:
        log.error("Failed to fetch open sections (year=%s term=%s): %s", year, term, exc)
        return set()


def fetch_sections_for_subject(subject: str, year: str, term: str, campus: str) -> list[dict]:
    """
    Returns a list of section dicts for all courses under a subject.
    Each dict has: index, sectionNumber, openStatus, instructors, meetingTimes, courseNumber, courseTitle
    """
    try:
        resp = http_requests.get(
            SOC_COURSES_URL,
            params={"year": year, "term": term, "campus": campus, "subject": subject},
            timeout=15,
        )
        resp.raise_for_status()
        courses = resp.json()
    except Exception as exc:
        log.error("Failed to fetch SOC courses (subject=%s): %s", subject, exc)
        return []

    sections = []
    for course in courses:
        course_num = str(course.get("courseNumber", "")).strip()
        course_title = course.get("expandedTitle") or course.get("title", "")
        for sec in course.get("sections", []):
            instructors = [
                i.get("name", "") for i in sec.get("instructors", []) if i.get("name")
            ]
            meeting_times = [
                {
                    "day": mt.get("meetingDay", ""),
                    "start": mt.get("startTime", ""),
                    "end": mt.get("endTime", ""),
                    "building": mt.get("buildingCode", ""),
                    "room": mt.get("roomNumber", ""),
                }
                for mt in sec.get("meetingTimes", [])
            ]
            sections.append({
                "index": str(sec.get("index", "")),
                "sectionNumber": str(sec.get("number", "")),
                "openStatus": bool(sec.get("openStatus", False)),
                "instructors": instructors,
                "meetingTimes": meeting_times,
                "courseNumber": course_num,
                "courseTitle": course_title,
            })
    return sections


def poll_snipes() -> None:
    """
    Called by APScheduler every 2 minutes.
    Checks all active un-notified snipes and sends an SMS if a section opened.
    """
    db = SessionLocal()
    try:
        active = (
            db.query(models.Snipe)
            .filter(models.Snipe.active == True, models.Snipe.notified_at == None)
            .all()
        )
        if not active:
            return

        # Group by (year, term, campus) to batch SOC API calls
        groups: dict[tuple, list] = {}
        for snipe in active:
            key = (snipe.year, snipe.term, snipe.campus)
            groups.setdefault(key, []).append(snipe)

        for (year, term, campus), snipes in groups.items():
            open_indices = _fetch_open_indices(year, term, campus)
            if not open_indices:
                continue

            for snipe in snipes:
                if snipe.section_index not in open_indices:
                    continue

                term_label = TERM_LABELS.get(term, term)
                msg = (
                    f"[RU Planner] SEAT OPEN! {snipe.course_code} "
                    f"section {snipe.section_number} (index {snipe.section_index}) "
                    f"for {term_label} {year} just opened. "
                    f"Register NOW at webreg.rutgers.edu before it fills!"
                )
                sent = send_sms(snipe.phone_number, msg)
                if sent:
                    snipe.notified_at = datetime.utcnow()
                    log.info(
                        "Notified user %s: %s sec %s",
                        snipe.user_id, snipe.course_code, snipe.section_index,
                    )

        db.commit()
    except Exception as exc:
        log.error("poll_snipes error: %s", exc)
        db.rollback()
    finally:
        db.close()
