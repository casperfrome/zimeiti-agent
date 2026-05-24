"""视频合成：SSE 4 阶段（prepare_images / tts / build / done）+ 列表/详情/删除。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..ai_client import resolve_model
from ..db import SessionLocal, get_db
from ..models import BgmTrack, Copywrite, ImageSet, Provider, Video
from ..schemas import VideoCreateRequest, VideoDetail, VideoSummary
from ..services.sse import sse_event
from ..services.storage import abs_path, rel_path, remove_dir, video_dir
from ..services.video_synth import (
    build_slideshow,
    prepare_images,
    resolve_video_size,
    synthesize_voice,
)

router = APIRouter()


@router.get("", response_model=list[VideoSummary])
def list_videos(copywrite_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Video)
    if copywrite_id is not None:
        q = q.filter(Video.copywrite_id == copywrite_id)
    rows = q.order_by(Video.created_at.desc()).all()
    return [VideoSummary.model_validate(r) for r in rows]


@router.get("/{vid}", response_model=VideoDetail)
def get_video(vid: int, db: Session = Depends(get_db)):
    v = db.get(Video, vid)
    if v is None:
        raise HTTPException(404, "video not found")
    return VideoDetail.model_validate(v)


@router.delete("/{vid}")
def delete_video(vid: int, db: Session = Depends(get_db)):
    v = db.get(Video, vid)
    if v is None:
        raise HTTPException(404, "video not found")
    if v.video_path:
        remove_dir(video_dir(v.id))
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.post("")
def create_video(payload: VideoCreateRequest):
    def event_gen() -> Iterator[str]:
        db = SessionLocal()
        try:
            c = db.get(Copywrite, payload.copywrite_id)
            iset = db.get(ImageSet, payload.image_set_id)
            if c is None or iset is None or iset.copywrite_id != c.id:
                yield sse_event("error", {"message": "copywrite / image_set 不匹配"})
                return

            bgm = None
            if payload.bgm_id is not None:
                bgm = db.get(BgmTrack, payload.bgm_id)
                if bgm is None:
                    yield sse_event("error", {"message": "BGM 未找到"})
                    return

            try:
                tts_model = resolve_model(db, payload.tts_model_id, purpose="tts")
                ali_provider = db.get(Provider, "alibaba")
                if ali_provider is None or not ali_provider.api_key:
                    raise ValueError("阿里云 DashScope API Key 未配置")
            except ValueError as e:
                yield sse_event("error", {"message": str(e)})
                return

            done_items = [it for it in iset.items if it.status == "done" and it.file_path]
            if not done_items:
                yield sse_event("error", {"message": "图片集没有可用图片，请先完成图片生成"})
                return

            try:
                video_size = resolve_video_size(payload.video_ratio_preset)
            except ValueError as e:
                yield sse_event("error", {"message": str(e)})
                return

            # 入库 video pending
            v = Video(
                copywrite_id=c.id,
                image_set_id=iset.id,
                bgm_id=bgm.id if bgm else None,
                tts_model_id=tts_model.id,
                tts_voice=payload.tts_voice,
                video_ratio_preset=payload.video_ratio_preset,
                fps=payload.fps,
                voice_volume=payload.voice_volume,
                bgm_volume=payload.bgm_volume,
                target_duration_seconds=payload.target_duration_seconds,
                region=payload.region,
                status="running",
            )
            db.add(v)
            db.flush()

            work_dir = video_dir(v.id)
            yield sse_event("start", {"video_id": v.id})

            try:
                # 阶段 1：图片预处理
                yield sse_event("stage", {"stage": "prepare_images", "progress": 0.05})
                processed = prepare_images(
                    [abs_path(it.file_path) for it in done_items],
                    video_size,
                    work_dir / "processed",
                )
                yield sse_event("stage", {"stage": "prepare_images", "progress": 0.25, "done": True})

                # 阶段 2：TTS
                yield sse_event("stage", {"stage": "tts", "progress": 0.3})
                voice_path = work_dir / "voice.mp3"
                voice_path, voice_duration, rate_used = synthesize_voice(
                    api_key=ali_provider.api_key,
                    model=tts_model.model_id,
                    voice=payload.tts_voice,
                    text=c.content,
                    output_path=voice_path,
                    region=payload.region,
                    target_duration=payload.target_duration_seconds,
                )
                v.voice_path = rel_path(voice_path)
                db.commit()
                yield sse_event("stage", {
                    "stage": "tts", "progress": 0.55, "done": True,
                    "voice_duration": voice_duration, "speech_rate": rate_used,
                })

                # 阶段 3：合成 MP4
                total_duration = payload.target_duration_seconds or voice_duration
                yield sse_event("stage", {"stage": "build", "progress": 0.6})
                output_path = work_dir / "output.mp4"
                bgm_path = abs_path(bgm.file_path) if bgm and bgm.file_path else None
                build_slideshow(
                    image_paths=processed,
                    voice_path=voice_path,
                    bgm_path=bgm_path,
                    output_path=output_path,
                    total_duration=total_duration,
                    fps=payload.fps,
                    voice_volume=payload.voice_volume,
                    bgm_volume=payload.bgm_volume,
                )
                v.video_path = rel_path(output_path)
                v.video_duration = total_duration
                v.status = "done"
                db.commit()

                yield sse_event("done", {
                    "video_id": v.id,
                    "video_path": v.video_path,
                    "video_duration": v.video_duration,
                })
            except Exception as exc:  # noqa: BLE001
                v.status = "failed"
                v.error = str(exc)
                db.commit()
                yield sse_event("error", {"message": str(exc), "video_id": v.id})
        finally:
            db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
