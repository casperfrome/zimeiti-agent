from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Copywrite ----------

class CopywriteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    updated_at: datetime


class CopywriteDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    content: str
    created_at: datetime
    updated_at: datetime


class CopywriteUpdate(BaseModel):
    content: str
    title: Optional[str] = None


class GenerateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    description: str = Field(..., min_length=1)
    prompt_id: Optional[int] = None
    model_id: Optional[int] = None  # row id of models table
    enable_web_search: bool = True


class PolishRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    prompt_id: Optional[int] = None
    model_id: Optional[int] = None
    enable_web_search: bool = True


# ---------- SystemPrompt ----------

class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    function_key: str
    name: str
    content: str
    is_default: bool
    updated_at: datetime


class PromptCreate(BaseModel):
    function_key: str
    name: str
    content: str
    is_default: bool = False


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None


# ---------- Provider ----------

class ProviderOut(BaseModel):
    provider_key: str
    display_name: str
    api_key_masked: str
    has_key: bool
    base_url: str


class ProviderUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None


# ---------- Model ----------

class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: int
    provider_key: str
    model_id: str
    display_name: str
    is_default: bool


class ModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider_key: str
    model_id: str
    display_name: str


class ModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: Optional[str] = None
    display_name: Optional[str] = None
