"""Environment and constants. Secrets come from .env only."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Every date in the challenge resolves in Europe/Madrid.
MADRID = ZoneInfo("Europe/Madrid")

PROSPER_BASE_URL = os.getenv("PROSPER_BASE_URL", "https://hackspain.getprosperapp.com").rstrip("/")
PROSPER_API_KEY = os.getenv("PROSPER_API_KEY", "")

# Two keys run the whole voice loop: Deepgram hears and speaks, Gemini decides.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# Local test calls carry a call id the platform never issued, so their submissions are captured, not POSTed.
DRY_RUN_SUBMIT = os.getenv("DRY_RUN_SUBMIT", "") == "1"

# A chart note can read like an instruction ("check the appointment on the books before adding another")
# and turned a plain booking into a reschedule on a real call. Off for scored calls; on for a jury demo.
SHOW_CHART_NOTES = os.getenv("SHOW_CHART_NOTES", "") == "1"

# The model that makes the decisions, live and in the text evals alike.
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.6-flash")

ORGANIZERS_DIR = ROOT / "docs" / "organizers"
CALL_LOG_DIR = ROOT / "logs" / "calls"
