from sqlalchemy import create_engine, text

from app.db_migrations import run_startup_migrations


def test_startup_migrations_add_video_subtitle_columns_to_existing_sqlite_table(tmp_path):
    db_path = tmp_path / "app.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY,
                copywrite_id INTEGER NOT NULL,
                image_set_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'done'
            )
        """))
        conn.execute(text(
            "INSERT INTO videos (id, copywrite_id, image_set_id, status) "
            "VALUES (1, 16, 1, 'done')"
        ))

    run_startup_migrations(engine)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
        row = conn.execute(text(
            "SELECT subtitle_font_color, subtitle_stroke_color, "
            "subtitle_font_size, thumbnail_path FROM videos WHERE id = 1"
        )).one()

    assert {
        "subtitle_font_color",
        "subtitle_stroke_color",
        "subtitle_font_size",
        "thumbnail_path",
    } <= columns
    assert row.subtitle_font_color == "#FFD400"
    assert row.subtitle_stroke_color == "#000000"
    assert row.subtitle_font_size is None
    assert row.thumbnail_path is None
