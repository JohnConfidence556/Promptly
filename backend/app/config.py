from dotenv import load_dotenv
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from backend/.env
load_dotenv(BASE_DIR / ".env")

# Retrieve the Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "openai/gpt-oss-120b"

# Validate the API key
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please check your .env file.")


# Origins allowed to call the API from a browser (comma-separated).
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# Each build writes its files into its own folder under here.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "workspace" / "builds"

# SQLite file. Override with DATABASE_PATH (for example a persistent disk in production).
DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        Path(__file__).resolve().parent.parent / "data" / "app.db",
    )
)

# Daily limits that protect the free AI quota on a public deployment.
DAILY_RUN_LIMIT_PER_USER = int(os.getenv("DAILY_RUN_LIMIT_PER_USER", "5"))
DAILY_RUN_LIMIT_TOTAL = int(os.getenv("DAILY_RUN_LIMIT_TOTAL", "60"))