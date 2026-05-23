import json
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ..ai_client import (
    get_provider,
    perform_web_search,
    resolve_model,
    resolve_prompt,
    search_status_payload,
    stream_chat,
)
from ..db import SessionLocal, get_db
from ..models import Copywrite, CopywriteVersion
from ..schemas import (
    CopywriteDetail,
    CopywriteSummary,
    CopywriteUpdate,
    GenerateRequest,
    PolishRequest,
)

router = APIRouter()


def _sse(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _title_from_description(desc: str) -> str:
    desc = desc.strip().replace("\n", " ")
    return desc[:30] if len(desc) <= 30 else desc[:30] + "…"


# ---------- CRUD ----------

@router.get("", response_model=list[CopywriteSummary])
def list_copywrites(db: Session = Depends(get_db)):
    subq = (
        db.query(
            CopywriteVersion.copywrite_id,
            func.sum(CopywriteVersion.total_tokens).label("total_tokens"),
            func.sum(CopywriteVersion.estimated_cost_cny).label("estimated_cost_cny"),
        )
        .group_by(CopywriteVersion.copywrite_id)
        .subquery()
    )
    rows = (
        db.query(Copywrite, subq.c.total_tokens, subq.c.estimated_cost_cny)
        .outerjoin(subq, Copywrite.id == subq.c.copywrite_id)
        .order_by(Copywrite.updated_at.desc())
        .all()
    )
    return [
        CopywriteSummary(
            id=c.id,
            title=c.title,
            updated_at=c.updated_at,
            total_tokens=tokens,
            estimated_cost_cny=float(cost) if cost is not None else None,
        )
        for c, tokens, cost in rows
    ]


@router.get("/{cid}", response_model=CopywriteDetail)
def get_copywrite(cid: int, db: Session = Depends(get_db)):
    c = (
        db.query(Copywrite)
        .options(selectinload(Copywrite.versions))
        .filter(Copywrite.id == cid)
        .first()
    )
    if c is None:
        raise HTTPException(404, "copywrite not found")
    return c


@router.put("/{cid}", response_model=CopywriteDetail)
def update_copywrite(cid: int, payload: CopywriteUpdate, db: Session = Depends(get_db)):
    c = db.get(Copywrite, cid)
    if c is None:
        raise HTTPException(404, "copywrite not found")
    c.content = payload.content
    if payload.title is not None:
        c.title = payload.title
    db.add(CopywriteVersion(copywrite_id=c.id, content=payload.content, source="user_edit"))
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{cid}")
def delete_copywrite(cid: int, db: Session = Depends(get_db)):
    c = db.get(Copywrite, cid)
    if c is None:
        raise HTTPException(404, "copywrite not found")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---------- AI streaming ----------

@router.post("/generate")
def generate(payload: GenerateRequest):
    """SSE 流式生成文案，结束后落库为新 Copywrite，返回 done 事件携带 id。"""
    description = payload.description

    def event_gen() -> Iterator[str]:
        db = SessionLocal()
        try:
            try:
                model = resolve_model(db, payload.model_id)
                prompt = resolve_prompt(db, "copywrite_generate", payload.prompt_id)
                provider = get_provider(db, model.provider_key)
            except ValueError as e:
                yield _sse("error", {"message": str(e)})
                return

            try:
                search_status = search_status_payload(enabled=False, used=False, warning=None)
                search_results = []
                if payload.enable_web_search:
                    status, search_results = perform_web_search(description)
                    search_status = search_status_payload(status.enabled, status.used, status.warning)
                    if status.warning:
                        yield _sse("search", search_status)

                buf: list[str] = []
                usage = None
                for event in stream_chat(provider, model.model_id, prompt.content, description, search_results):
                    if event.type == "delta" and event.text:
                        buf.append(event.text)
                        yield _sse("delta", {"text": event.text})
                    elif event.type == "usage":
                        usage = event.usage
            except Exception as e:  # noqa: BLE001
                yield _sse("error", {"message": f"AI 调用失败: {e}"})
                return

            full = "".join(buf).strip()
            c = Copywrite(
                title=_title_from_description(description),
                description=description,
                content=full,
            )
            db.add(c)
            db.flush()
            _token_fields = {
                "provider_key", "model_id", "prompt_tokens",
                "completion_tokens", "total_tokens",
                "prompt_cache_hit_tokens", "prompt_cache_miss_tokens",
                "estimated_cost_cny",
            }
            db.add(CopywriteVersion(
                copywrite_id=c.id,
                content=full,
                source="initial",
                **({k: v for k, v in usage.items() if k in _token_fields} if usage else {}),
            ))
            db.commit()
            yield _sse("done", {"id": c.id, "title": c.title, "usage": usage, "search": search_status})
        finally:
            db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/{cid}/polish")
def polish(cid: int, payload: PolishRequest):
    """SSE 流式润色现有文案，结束后自动落库为 polish 版本。"""

    def event_gen() -> Iterator[str]:
        db = SessionLocal()
        try:
            c = db.get(Copywrite, cid)
            if c is None:
                yield _sse("error", {"message": "copywrite not found"})
                return
            try:
                model = resolve_model(db, payload.model_id)
                prompt = resolve_prompt(db, "copywrite_polish", payload.prompt_id)
                provider = get_provider(db, model.provider_key)
            except ValueError as e:
                yield _sse("error", {"message": str(e)})
                return

            try:
                search_status = search_status_payload(enabled=False, used=False, warning=None)
                search_results = []
                if payload.enable_web_search:
                    status, search_results = perform_web_search(c.content)
                    search_status = search_status_payload(status.enabled, status.used, status.warning)
                    if status.warning:
                        yield _sse("search", search_status)

                buf: list[str] = []
                usage = None
                for event in stream_chat(provider, model.model_id, prompt.content, c.content, search_results):
                    if event.type == "delta" and event.text:
                        buf.append(event.text)
                        yield _sse("delta", {"text": event.text})
                    elif event.type == "usage":
                        usage = event.usage
            except Exception as e:  # noqa: BLE001
                yield _sse("error", {"message": f"AI 调用失败: {e}"})
                return

            full = "".join(buf).strip()
            _token_fields = {
                "provider_key", "model_id", "prompt_tokens",
                "completion_tokens", "total_tokens",
                "prompt_cache_hit_tokens", "prompt_cache_miss_tokens",
                "estimated_cost_cny",
            }
            ver = CopywriteVersion(
                copywrite_id=c.id,
                content=full,
                source="polish",
                **({k: v for k, v in usage.items() if k in _token_fields} if usage else {}),
            )
            db.add(ver)
            db.commit()
            yield _sse("done", {"version_id": ver.id, "usage": usage, "search": search_status})
        finally:
            db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
