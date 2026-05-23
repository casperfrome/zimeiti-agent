from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

HOST = "127.0.0.1"
PORT = 8000

SEED_DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
