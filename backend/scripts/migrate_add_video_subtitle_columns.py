"""Add subtitle style and thumbnail columns to existing videos table."""
import sys
from pathlib import Path

from sqlalchemy import create_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db_migrations import run_startup_migrations  # noqa: E402

DB = BACKEND_DIR / "data" / "app.db"

if not DB.exists():
    print(f"Database not found at {DB}. First startup will create the table.")
    raise SystemExit(0)

engine = create_engine(f"sqlite:///{DB.as_posix()}")
run_startup_migrations(engine)
print("Done. Video subtitle columns are up to date.")
