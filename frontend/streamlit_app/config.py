import os
from pathlib import Path

from dotenv import load_dotenv

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=FRONTEND_ROOT / ".env")

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
