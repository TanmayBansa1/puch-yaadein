import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

AUTH_TOKEN: str | None = os.getenv("AUTH_TOKEN")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8086"))
DB_PATH: str = os.getenv("DB_PATH", "./memory.db")

if not AUTH_TOKEN:
    raise RuntimeError("AUTH_TOKEN must be set in environment (.env)")


