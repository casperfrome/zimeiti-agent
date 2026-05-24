"""图片集：分镜拆分（非流式）+ 批量生图（SSE）+ 单张重生（SSE）+ 列表/详情/删除。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from ..ai_client import resolve_model, resolve_prompt
from ..db import SessionLocal, get_db
from ..models import Copywrite, ImageSet, ImageSetItem, Provider
from ..schemas import (
    ImageGenerateRequest,
    ImageSetDetail,
    ImageSetSummary,
    ImageSplitRequest,
    ImageSplitResult,
    PromptItem,
)
from ..services.image_gen import (
    download_to,
    generate_one,
    split_prompts_via_ollama,
)
from ..services.sse import sse_event
from ..services.storage import abs_path, image_set_dir, rel_path, remove_dir

router = APIRouter()


# ---------- non-stream: split ----------

@router.post("/split", response_model=ImageSplitResult)
def split_copywrite(payload: ImageSplitRequest, db: Session = Depends(get_db)):
    c = db.get(Copywrite, payload.copywrite_id)
    if c is None:
        raise HTTPException(404, "copywrite not found")
    if not c.content.strip():
        raise HTTPException(400, "文案内容为空")

    try:
        model = resolve_model(db, payload.split_model_id, purpose="prompt_split")
        prompt = resolve_prompt(db, "image_prompt_split", payload.prompt_id)
        provider = db.get(Provider, model.provider_key)
        if provider is None:
            raise ValueError(f"provider {model.provider_key} not found")
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        prompts = split_prompts_via_ollama(
            c.content,
            ollama_base_url=provider.base_url,
            ollama_model=model.model_id,
            system_prompt=prompt.content,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, str(e))

    return ImageSplitResult(prompts=[PromptItem(**p) for p in prompts])


# ---------- CRUD ----------

@router.get("", response_model=list[ImageSetSummary])
def list_image_sets(
    copywrite_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(ImageSet)
    if copywrite_id is not None:
        q = q.filter(ImageSet.copywrite_id == copywrite_id)
    rows = q.order_by(ImageSet.created_at.desc()).all()
    return [ImageSetSummary.model_validate(r) for r in rows]


@router.get("/{sid}", response_model=ImageSetDetail)
def get_image_set(sid: int, db: Session = Depends(get_db)):
    s = (
        db.query(ImageSet)
        .options(selectinload(ImageSet.items))
        .filter(ImageSet.id == sid)
        .first()
    )
    if s is None:
        raise HTTPException(404, "image set not found")
    return ImageSetDetail.model_validate(s)


@router.delete("/{sid}")
def delete_image_set(sid: int, db: Session = Depends(get_db)):
    s = db.get(ImageSet, sid)
    if s is None:
        raise HTTPException(404, "image set not found")
    if s.dir_path:
        remove_dir(abs_path(s.dir_path))
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------- SSE: generate ----------

@router.post("/generate")
def generate(payload: ImageGenerateRequest):
    """SSE 流式：每完成一张推一条 image 事件；末尾 done。"""

    def event_gen() -> Iterator[str]:
        db = SessionLocal()
        try:
            c = db.get(Copywrite, payload.copywrite_id)
            if c is None:
                yield sse_event("error", {"message": "copywrite not found"})
                return
            if not payload.prompts:
                yield sse_event("error", {"message": "prompts 为空"})
                return

            try:
                image_model = resolve_model(db, payload.image_model_id, purpose="image")
                ali_provider = db.get(Provider, "alibaba")
                if ali_provider is None or not ali_provider.api_key:
                    raise ValueError("阿里云 DashScope API Key 未配置，请到「模型与 Key」设置。")
            except ValueError as e:
                yield sse_event("error", {"message": str(e)})
                return

            # 先建 image_set + items（pending）
            iset = ImageSet(
                copywrite_id=c.id,
                image_model_id=image_model.id,
                split_model_id=payload.split_model_id,
                size=payload.size,
                n_per_prompt=payload.n_per_prompt,
                negative_prompt=payload.negative_prompt,
                prompt_extend=payload.prompt_extend,
                watermark=payload.watermark,
                seed=payload.seed,
                status="running",
            )
            db.add(iset)
            db.flush()

            target_dir = image_set_dir(iset.id)
            iset.dir_path = rel_path(target_dir)

            items: list[ImageSetItem] = []
            for p in payload.prompts:
                for img_idx in range(1, payload.n_per_prompt + 1):
                    it = ImageSetItem(
                        image_set_id=iset.id,
                        scene_index=p.index,
                        image_index=img_idx,
                        prompt=p.prompt,
                        status="pending",
                    )
                    db.add(it)
                    items.append(it)
            db.commit()

            yield sse_event("start", {
                "image_set_id": iset.id,
                "total": len(items),
                "dir_path": iset.dir_path,
            })

            ok_count = 0
            fail_count = 0
            api_key = ali_provider.api_key

            def _run_prompt(prompt_item) -> dict[str, Any]:
                """线程内：调 DashScope + 逐张下载到本地。异常吞掉写入返回值。"""
                try:
                    results = generate_one(
                        api_key=api_key,
                        model_id=image_model.model_id,
                        prompt=prompt_item.prompt,
                        size=payload.size,
                        n=payload.n_per_prompt,
                        negative_prompt=payload.negative_prompt,
                        prompt_extend=payload.prompt_extend,
                        watermark=payload.watermark,
                        seed=payload.seed,
                    )
                except Exception as exc:  # noqa: BLE001
                    return {"prompt_index": prompt_item.index, "api_error": str(exc), "downloads": []}

                downloads: list[dict[str, Any]] = []
                for img_idx, result in enumerate(results, start=1):
                    entry: dict[str, Any] = {
                        "img_idx": img_idx,
                        "url": result["url"],
                        "request_id": result.get("request_id"),
                    }
                    try:
                        dest = target_dir / f"scene_{prompt_item.index:03d}_{img_idx:02d}.png"
                        download_to(result["url"], dest)
                        entry["dest_rel"] = rel_path(dest)
                    except Exception as exc:  # noqa: BLE001
                        entry["error"] = str(exc)
                    downloads.append(entry)
                return {"prompt_index": prompt_item.index, "api_error": None, "downloads": downloads}

            max_workers = max(1, min(len(payload.prompts), 4))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_run_prompt, p) for p in payload.prompts]
                for fut in as_completed(futures):
                    result = fut.result()
                    p_index = result["prompt_index"]

                    if result["api_error"]:
                        msg = result["api_error"]
                        scene_items = [it for it in items if it.scene_index == p_index]
                        for it in scene_items:
                            it.status = "failed"
                            it.error = msg
                        fail_count += len(scene_items)
                        db.commit()
                        for it in scene_items:
                            yield sse_event("item", {
                                "item_id": it.id,
                                "scene_index": it.scene_index,
                                "image_index": it.image_index,
                                "status": "failed",
                                "error": msg,
                            })
                        continue

                    for entry in result["downloads"]:
                        it = next(
                            (x for x in items
                             if x.scene_index == p_index and x.image_index == entry["img_idx"]),
                            None,
                        )
                        if it is None:
                            continue
                        if entry.get("error"):
                            it.status = "failed"
                            it.error = entry["error"]
                            fail_count += 1
                        else:
                            it.file_path = entry["dest_rel"]
                            it.source_url = entry["url"]
                            it.request_id = entry.get("request_id")
                            it.status = "done"
                            ok_count += 1
                        db.commit()

                        yield sse_event("item", {
                            "item_id": it.id,
                            "scene_index": it.scene_index,
                            "image_index": it.image_index,
                            "status": it.status,
                            "file_path": it.file_path,
                            "error": it.error,
                        })

            iset.status = (
                "done" if fail_count == 0
                else ("partial" if ok_count > 0 else "failed")
            )
            db.commit()
            yield sse_event("done", {
                "image_set_id": iset.id,
                "status": iset.status,
                "ok": ok_count,
                "fail": fail_count,
            })
        finally:
            db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ---------- SSE: regenerate single item ----------

@router.post("/{sid}/items/{item_id}/regenerate")
def regenerate_item(sid: int, item_id: int):
    def event_gen() -> Iterator[str]:
        db = SessionLocal()
        try:
            iset = db.get(ImageSet, sid)
            it = db.get(ImageSetItem, item_id)
            if iset is None or it is None or it.image_set_id != sid:
                yield sse_event("error", {"message": "item not found"})
                return

            try:
                image_model = resolve_model(db, iset.image_model_id, purpose="image")
                ali_provider = db.get(Provider, "alibaba")
                if ali_provider is None or not ali_provider.api_key:
                    raise ValueError("阿里云 DashScope API Key 未配置")
            except ValueError as e:
                yield sse_event("error", {"message": str(e)})
                return

            try:
                results = generate_one(
                    api_key=ali_provider.api_key,
                    model_id=image_model.model_id,
                    prompt=it.prompt,
                    size=iset.size,
                    n=1,
                    negative_prompt=iset.negative_prompt,
                    prompt_extend=iset.prompt_extend,
                    watermark=iset.watermark,
                    seed=iset.seed,
                )
                result = results[0]
                target_dir = image_set_dir(iset.id)
                dest = target_dir / f"scene_{it.scene_index:03d}_{it.image_index:02d}.png"
                # 删旧文件
                if it.file_path:
                    try:
                        abs_path(it.file_path).unlink()
                    except FileNotFoundError:
                        pass
                download_to(result["url"], dest)
                it.file_path = rel_path(dest)
                it.source_url = result["url"]
                it.request_id = result.get("request_id")
                it.status = "done"
                it.error = None
            except Exception as exc:  # noqa: BLE001
                it.status = "failed"
                it.error = str(exc)
            db.commit()

            yield sse_event("done", {
                "item_id": it.id,
                "scene_index": it.scene_index,
                "image_index": it.image_index,
                "status": it.status,
                "file_path": it.file_path,
                "error": it.error,
            })
        finally:
            db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
