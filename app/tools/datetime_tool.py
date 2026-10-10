"""Deterministic local date, time, and calendar utilities for Windows 11.

Follows Workstream C requirements:
- Strictly local clock and OS timezone (zero LLM reliance for current time/date queries).
- Natural bilingual Indonesian and English formatting.
- Fully testable with injection/override of reference datetimes.
"""

from datetime import datetime
from typing import Optional


# Indonesian weekday and month names
INDONESIAN_DAYS = {
    0: "Senin",
    1: "Selasa",
    2: "Rabu",
    3: "Kamis",
    4: "Jumat",
    5: "Sabtu",
    6: "Minggu",
}
_ID_WEEKDAYS = INDONESIAN_DAYS

INDONESIAN_MONTHS = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}
_ID_MONTHS = INDONESIAN_MONTHS


def get_current_time(
    language: str = "id",
    lang: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Returns the current formatted time.

    Args:
        language: 'id' for Indonesian, 'en' for English.
        lang: Alias for language.
        now: Optional datetime for deterministic testing.
    """
    effective_lang = lang or language
    dt = now or datetime.now()
    is_id = effective_lang.lower().startswith("id")

    if is_id:
        hour = dt.hour
        minute = dt.minute
        if 4 <= hour < 10:
            period = "pagi"
        elif 10 <= hour < 15:
            period = "siang"
        elif 15 <= hour < 18:
            period = "sore"
        else:
            period = "malam"
        # e.g., "Sekarang pukul 09.05 pagi, sir."
        return f"Sekarang pukul {hour:02d}.{minute:02d} {period}, sir."
    else:
        # e.g., "It is 2:30 PM, sir."
        time_str = dt.strftime("%I:%M %p").lstrip("0")
        return f"It is {time_str}, sir."


def get_current_date(
    language: str = "id",
    lang: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Returns the current formatted full date with weekday.

    Args:
        language: 'id' for Indonesian, 'en' for English.
        lang: Alias for language.
        now: Optional datetime for deterministic testing.
    """
    effective_lang = lang or language
    dt = now or datetime.now()
    is_id = effective_lang.lower().startswith("id")

    if is_id:
        weekday = _ID_WEEKDAYS.get(dt.weekday(), "Hari ini")
        month = _ID_MONTHS.get(dt.month, str(dt.month))
        # e.g., "Hari ini adalah Sabtu, 10 Oktober 2026, sir."
        return f"Hari ini adalah {weekday}, {dt.day} {month} {dt.year}, sir."
    else:
        en_date_str = dt.strftime("%A, %B %d, %Y")
        return f"Today is {en_date_str}, sir."


def get_current_day_of_week(
    language: str = "id",
    lang: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Returns just the current day of the week.

    Args:
        language: 'id' for Indonesian, 'en' for English.
        lang: Alias for language.
        now: Optional datetime for deterministic testing.
    """
    effective_lang = lang or language
    dt = now or datetime.now()
    is_id = effective_lang.lower().startswith("id")

    if is_id:
        weekday = _ID_WEEKDAYS.get(dt.weekday(), "Hari ini")
        return f"Hari ini adalah hari {weekday}, sir."
    else:
        day_str = dt.strftime("%A")
        return f"Today is {day_str}, sir."
