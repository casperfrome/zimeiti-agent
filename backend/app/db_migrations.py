from sqlalchemy import Engine, text


VIDEO_COLUMNS = [
    ("subtitle_font_color", "VARCHAR(7) DEFAULT '#FFD400'"),
    ("subtitle_stroke_color", "VARCHAR(7) DEFAULT '#000000'"),
    ("subtitle_font_size", "INTEGER"),
    ("thumbnail_path", "VARCHAR(300)"),
    ("encoding_duration", "FLOAT"),
    ("codec_used", "VARCHAR(30)"),
]


def run_startup_migrations(engine: Engine) -> None:
    """Apply small SQLite-compatible schema updates for existing local databases."""
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ))
        }
        if "videos" not in tables:
            return

        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(videos)"))
        }
        for column_name, column_type in VIDEO_COLUMNS:
            if column_name not in existing:
                conn.execute(text(
                    f"ALTER TABLE videos ADD COLUMN {column_name} {column_type}"
                ))

        conn.execute(text(
            "UPDATE videos SET subtitle_font_color = '#FFD400' "
            "WHERE subtitle_font_color IS NULL OR subtitle_font_color = ''"
        ))
        conn.execute(text(
            "UPDATE videos SET subtitle_stroke_color = '#000000' "
            "WHERE subtitle_stroke_color IS NULL OR subtitle_stroke_color = ''"
        ))
