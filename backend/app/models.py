from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.utcnow()


class Copywrite(Base):
    __tablename__ = "copywrites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    versions: Mapped[list["CopywriteVersion"]] = relationship(
        back_populates="copywrite",
        cascade="all, delete-orphan",
        order_by="CopywriteVersion.id.desc()",
    )


class CopywriteVersion(Base):
    __tablename__ = "copywrite_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    copywrite_id: Mapped[int] = mapped_column(ForeignKey("copywrites.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))  # initial / user_edit / polish
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Token usage for AI-generated versions
    provider_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_cache_hit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_cache_miss_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_cny: Mapped[float | None] = mapped_column(Float, nullable=True)

    copywrite: Mapped[Copywrite] = relationship(back_populates="versions")


class SystemPrompt(Base):
    __tablename__ = "system_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    function_key: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Provider(Base):
    __tablename__ = "providers"

    provider_key: Mapped[str] = mapped_column(String(20), primary_key=True)  # deepseek / kimi
    display_name: Mapped[str] = mapped_column(String(40))
    api_key: Mapped[str] = mapped_column(String(200), default="")
    base_url: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_key: Mapped[str] = mapped_column(ForeignKey("providers.provider_key"))
    model_id: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(80))
    # chat / image / tts / prompt_split  — is_default 在同 purpose 内唯一
    purpose: Mapped[str] = mapped_column(String(20), default="chat", index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BgmTrack(Base):
    __tablename__ = "bgm_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    file_path: Mapped[str] = mapped_column(String(300))  # 相对 UPLOAD_ROOT
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ImageSet(Base):
    __tablename__ = "image_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    copywrite_id: Mapped[int] = mapped_column(ForeignKey("copywrites.id", ondelete="CASCADE"), index=True)
    image_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"), nullable=True)
    split_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"), nullable=True)

    # 生成参数快照
    size: Mapped[str] = mapped_column(String(20), default="1024*1024")
    n_per_prompt: Mapped[int] = mapped_column(Integer, default=1)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    prompt_extend: Mapped[bool] = mapped_column(Boolean, default=True)
    watermark: Mapped[bool] = mapped_column(Boolean, default=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/done/failed/partial
    dir_path: Mapped[str] = mapped_column(String(300), default="")  # 相对 UPLOAD_ROOT
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    items: Mapped[list["ImageSetItem"]] = relationship(
        back_populates="image_set",
        cascade="all, delete-orphan",
        order_by="ImageSetItem.scene_index, ImageSetItem.image_index",
    )


class ImageSetItem(Base):
    __tablename__ = "image_set_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_set_id: Mapped[int] = mapped_column(ForeignKey("image_sets.id", ondelete="CASCADE"), index=True)
    scene_index: Mapped[int] = mapped_column(Integer)
    image_index: Mapped[int] = mapped_column(Integer, default=1)
    prompt: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 相对 UPLOAD_ROOT
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/done/failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    image_set: Mapped[ImageSet] = relationship(back_populates="items")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    copywrite_id: Mapped[int] = mapped_column(ForeignKey("copywrites.id", ondelete="CASCADE"), index=True)
    image_set_id: Mapped[int] = mapped_column(ForeignKey("image_sets.id"))
    bgm_id: Mapped[int | None] = mapped_column(ForeignKey("bgm_tracks.id"), nullable=True)
    tts_model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"), nullable=True)

    tts_voice: Mapped[str] = mapped_column(String(80), default="longanyang")
    video_ratio_preset: Mapped[str] = mapped_column(String(20), default="portrait_9_16")
    fps: Mapped[int] = mapped_column(Integer, default=30)
    voice_volume: Mapped[float] = mapped_column(Float, default=1.0)
    bgm_volume: Mapped[float] = mapped_column(Float, default=0.1)
    target_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    region: Mapped[str] = mapped_column(String(10), default="cn")
    subtitle_font_color: Mapped[str] = mapped_column(String(7), default="#FFD400")
    subtitle_stroke_color: Mapped[str] = mapped_column(String(7), default="#000000")
    subtitle_font_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/done/failed
    voice_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    video_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    encoding_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
