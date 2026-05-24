"""Add `purpose` column to models table for per-purpose default model.

`purpose` 值：chat / image / tts / prompt_split。
现有 deepseek/kimi 模型行刷为 'chat'（即原有"默认模型"概念）。
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "app.db"

if not DB.exists():
    print(f"Database not found at {DB} — 首次启动会由 create_all 自动建表，无需迁移。")
    raise SystemExit(0)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

cur.execute("PRAGMA table_info(models)")
existing = {row[1] for row in cur.fetchall()}

if "purpose" not in existing:
    cur.execute("ALTER TABLE models ADD COLUMN purpose VARCHAR(20) DEFAULT 'chat'")
    cur.execute("UPDATE models SET purpose='chat' WHERE purpose IS NULL OR purpose=''")
    conn.commit()
    print("  + purpose VARCHAR(20)  (现有模型已设为 chat)")
else:
    print("  purpose 列已存在，跳过。")

conn.close()
print("Done.")
