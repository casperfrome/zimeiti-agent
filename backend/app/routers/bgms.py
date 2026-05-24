"""BGM 库：上传 / 列表 / 改名 / 删除。文件落 backend/data/uploads/bgm/。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BgmTrack
from ..schemas import BgmOut, BgmUpdate
from ..services.storage import BGM_DIR, abs_path, ensure_upload_dirs, rel_path, remove_file, safe_filename
from ..services.video_synth import get_audio_duration

router = APIRouter()

ALLOWED_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def _to_out(b: BgmTrack) -> BgmOut:
    return BgmOut.model_validate(b)


@router.get("", response_model=list[BgmOut])
def list_bgms(db: Session = Depends(get_db)):
    rows = db.query(BgmTrack).order_by(BgmTrack.created_at.desc()).all()
    return [_to_out(b) for b in rows]


@router.post("", response_model=BgmOut)
async def upload_bgm(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    ensure_upload_dirs()
    original = file.filename or "bgm"
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"不支持的音频格式 {ext}，仅支持 {sorted(ALLOWED_EXTS)}")

    display_name = (name or Path(original).stem).strip() or "未命名 BGM"

    # 先创建 DB row 拿到 id 拼文件名，避免冲突
    b = BgmTrack(
        name=display_name,
        file_path="",
        original_filename=original,
    )
    db.add(b)
    db.flush()

    safe = safe_filename(Path(original).stem)
    dest = BGM_DIR / f"{b.id}_{safe}{ext}"
    content = await file.read()
    dest.write_bytes(content)

    try:
        b.duration_seconds = get_audio_duration(dest)
    except Exception:
        b.duration_seconds = None

    b.file_path = rel_path(dest)
    db.commit()
    db.refresh(b)
    return _to_out(b)


@router.put("/{bid}", response_model=BgmOut)
def rename_bgm(bid: int, payload: BgmUpdate, db: Session = Depends(get_db)):
    b = db.get(BgmTrack, bid)
    if b is None:
        raise HTTPException(404, "bgm not found")
    if payload.name.strip():
        b.name = payload.name.strip()
    db.commit()
    db.refresh(b)
    return _to_out(b)


@router.delete("/{bid}")
def delete_bgm(bid: int, db: Session = Depends(get_db)):
    b = db.get(BgmTrack, bid)
    if b is None:
        raise HTTPException(404, "bgm not found")
    if b.file_path:
        remove_file(abs_path(b.file_path))
    db.delete(b)
    db.commit()
    return {"ok": True}
