from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import SystemPrompt
from ..schemas import PromptCreate, PromptOut, PromptUpdate

router = APIRouter()

ALLOWED_FUNCTIONS = {"copywrite_generate", "copywrite_polish"}


@router.get("", response_model=list[PromptOut])
def list_prompts(function_key: str | None = None, db: Session = Depends(get_db)):
    q = db.query(SystemPrompt)
    if function_key:
        q = q.filter(SystemPrompt.function_key == function_key)
    return q.order_by(SystemPrompt.function_key, SystemPrompt.id).all()


@router.post("", response_model=PromptOut)
def create_prompt(payload: PromptCreate, db: Session = Depends(get_db)):
    if payload.function_key not in ALLOWED_FUNCTIONS:
        raise HTTPException(400, f"function_key 必须是 {ALLOWED_FUNCTIONS} 之一")
    p = SystemPrompt(
        function_key=payload.function_key,
        name=payload.name,
        content=payload.content,
        is_default=False,
    )
    db.add(p)
    db.flush()
    if payload.is_default:
        db.query(SystemPrompt).filter(
            SystemPrompt.function_key == payload.function_key,
            SystemPrompt.id != p.id,
        ).update({SystemPrompt.is_default: False})
        p.is_default = True
    db.commit()
    db.refresh(p)
    return p


@router.put("/{pid}", response_model=PromptOut)
def update_prompt(pid: int, payload: PromptUpdate, db: Session = Depends(get_db)):
    p = db.get(SystemPrompt, pid)
    if p is None:
        raise HTTPException(404, "prompt not found")
    if payload.name is not None:
        p.name = payload.name
    if payload.content is not None:
        p.content = payload.content
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{pid}")
def delete_prompt(pid: int, db: Session = Depends(get_db)):
    p = db.get(SystemPrompt, pid)
    if p is None:
        raise HTTPException(404, "prompt not found")
    if p.is_default:
        raise HTTPException(400, "默认 prompt 不可删除，请先把其他 prompt 设为默认")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{pid}/set-default", response_model=PromptOut)
def set_default_prompt(pid: int, db: Session = Depends(get_db)):
    p = db.get(SystemPrompt, pid)
    if p is None:
        raise HTTPException(404, "prompt not found")
    db.query(SystemPrompt).filter(
        SystemPrompt.function_key == p.function_key
    ).update({SystemPrompt.is_default: False})
    p.is_default = True
    db.commit()
    db.refresh(p)
    return p
