from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Model, Provider
from ..schemas import ModelCreate, ModelOut, ModelUpdate, ProviderOut, ProviderUpdate

router = APIRouter()


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def _provider_to_out(p: Provider) -> ProviderOut:
    return ProviderOut(
        provider_key=p.provider_key,
        display_name=p.display_name,
        api_key_masked=_mask(p.api_key),
        has_key=bool(p.api_key),
        base_url=p.base_url,
    )


# ---------- providers ----------

@router.get("/providers", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)):
    return [_provider_to_out(p) for p in db.query(Provider).all()]


@router.put("/providers/{provider_key}", response_model=ProviderOut)
def update_provider(provider_key: str, payload: ProviderUpdate, db: Session = Depends(get_db)):
    p = db.get(Provider, provider_key)
    if p is None:
        raise HTTPException(404, "provider not found")
    if payload.api_key is not None:
        p.api_key = payload.api_key
    if payload.base_url is not None:
        p.base_url = payload.base_url
    db.commit()
    db.refresh(p)
    return _provider_to_out(p)


# ---------- models ----------

@router.get("/models", response_model=list[ModelOut])
def list_models(
    provider_key: str | None = None,
    purpose: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Model)
    if provider_key:
        q = q.filter(Model.provider_key == provider_key)
    if purpose:
        q = q.filter(Model.purpose == purpose)
    return q.order_by(Model.purpose, Model.provider_key, Model.id).all()


@router.post("/models", response_model=ModelOut)
def create_model(payload: ModelCreate, db: Session = Depends(get_db)):
    if db.get(Provider, payload.provider_key) is None:
        raise HTTPException(400, f"provider {payload.provider_key} not found")
    m = Model(
        provider_key=payload.provider_key,
        model_id=payload.model_id,
        display_name=payload.display_name,
        purpose=payload.purpose,
        is_default=False,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.put("/models/{mid}", response_model=ModelOut)
def update_model(mid: int, payload: ModelUpdate, db: Session = Depends(get_db)):
    m = db.get(Model, mid)
    if m is None:
        raise HTTPException(404, "model not found")
    if payload.model_id is not None:
        m.model_id = payload.model_id
    if payload.display_name is not None:
        m.display_name = payload.display_name
    db.commit()
    db.refresh(m)
    return m


@router.delete("/models/{mid}")
def delete_model(mid: int, db: Session = Depends(get_db)):
    m = db.get(Model, mid)
    if m is None:
        raise HTTPException(404, "model not found")
    if m.is_default:
        raise HTTPException(400, "默认模型不可删除，请先把其他模型设为默认")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.post("/models/{mid}/set-default", response_model=ModelOut)
def set_default_model(mid: int, db: Session = Depends(get_db)):
    m = db.get(Model, mid)
    if m is None:
        raise HTTPException(404, "model not found")
    db.query(Model).filter(Model.purpose == m.purpose).update({Model.is_default: False})
    m.is_default = True
    db.commit()
    db.refresh(m)
    return m
