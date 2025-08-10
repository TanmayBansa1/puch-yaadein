import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

AUTH_TOKEN: str | None = os.getenv("AUTH_TOKEN")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8086"))
DB_PATH: str = os.getenv("DB_PATH", "./memory.db")
USER_PHONE: str | None = os.getenv("USER_PHONE")

if not AUTH_TOKEN:
    raise RuntimeError("AUTH_TOKEN must be set in environment (.env)")
if not USER_PHONE:
    raise RuntimeError("USER_PHONE must be set in environment (.env) as countrycode+number, e.g., 919876543210")


