"""Add token usage columns to existing copywrite_versions table.

Run this if you get "no such column: copywrite_versions.<field>" errors
after pulling code that adds token consumption tracking.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "app.db"

NEW_COLUMNS = [
    ("provider_key", "VARCHAR(20)"),
    ("model_id", "VARCHAR(80)"),
    ("prompt_tokens", "INTEGER"),
    ("completion_tokens", "INTEGER"),
    ("total_tokens", "INTEGER"),
    ("prompt_cache_hit_tokens", "INTEGER"),
    ("prompt_cache_miss_tokens", "INTEGER"),
    ("estimated_cost_cny", "FLOAT"),
]

if not DB.exists():
    print(f"Database not found at {DB}")
    raise SystemExit(0)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

# Get existing columns
cur.execute("PRAGMA table_info(copywrite_versions)")
existing = {row[1] for row in cur.fetchall()}

added = 0
for col_name, col_type in NEW_COLUMNS:
    if col_name not in existing:
        cur.execute(f"ALTER TABLE copywrite_versions ADD COLUMN {col_name} {col_type}")
        added += 1
        print(f"  + {col_name} ({col_type})")

conn.commit()
conn.close()
print(f"\nDone. {added} column(s) added.")
