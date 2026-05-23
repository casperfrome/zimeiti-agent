from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
