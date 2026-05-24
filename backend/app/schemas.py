from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Copywrite ----------

class CopywriteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    updated_at: datetime
    total_tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_cny: float | None = None


class CopywriteDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    content: str
    created_at: datetime
    updated_at: datetime
    total_tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_cny: float | None = None
    versions: list["CopywriteVersionOut"] = []


class CopywriteVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    content: str
    created_at: datetime
    provider_key: str | None = None
    model_id: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    estimated_cost_cny: float | None = None


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
    purpose: str
    is_default: bool


class ModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider_key: str
    model_id: str
    display_name: str
    purpose: str = "chat"


class ModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: Optional[str] = None
    display_name: Optional[str] = None


# ---------- BGM ----------

class BgmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    file_path: str
    duration_seconds: float | None = None
    original_filename: str
    created_at: datetime


class BgmUpdate(BaseModel):
    name: str


# ---------- ImageSet ----------

class PromptItem(BaseModel):
    index: int
    prompt: str


class ImageSplitRequest(BaseModel):
    copywrite_id: int
    split_model_id: Optional[int] = None
    prompt_id: Optional[int] = None


class ImageSplitResult(BaseModel):
    prompts: list[PromptItem]


class ImageGenerateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    copywrite_id: int
    prompts: list[PromptItem]
    image_model_id: Optional[int] = None
    split_model_id: Optional[int] = None
    size: str = "1024*1024"
    n_per_prompt: int = 1
    negative_prompt: str = ""
    prompt_extend: bool = True
    watermark: bool = False
    seed: Optional[int] = None


class ImageItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scene_index: int
    image_index: int
    prompt: str
    file_path: str | None = None
    source_url: str | None = None
    request_id: str | None = None
    status: str
    error: str | None = None


class ImageSetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: int
    copywrite_id: int
    image_model_id: int | None = None
    size: str
    n_per_prompt: int
    status: str
    dir_path: str
    created_at: datetime


class ImageSetDetail(ImageSetSummary):
    split_model_id: int | None = None
    negative_prompt: str
    prompt_extend: bool
    watermark: bool
    seed: int | None = None
    error: str | None = None
    items: list[ImageItemOut] = []


# ---------- Video ----------

class VideoCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    copywrite_id: int
    image_set_id: int
    bgm_id: Optional[int] = None
    tts_model_id: Optional[int] = None
    tts_voice: str = "longanyang"
    video_ratio_preset: str = "portrait_9_16"
    fps: int = 30
    voice_volume: float = 1.0
    bgm_volume: float = 0.1
    target_duration_seconds: Optional[float] = None
    region: str = "cn"
    subtitle_font_color: str = "#FFD400"
    subtitle_stroke_color: str = "#000000"
    subtitle_font_size: Optional[int] = None


class VideoSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: int
    copywrite_id: int
    image_set_id: int
    bgm_id: int | None = None
    status: str
    video_path: str | None = None
    thumbnail_path: str | None = None
    video_duration: float | None = None
    created_at: datetime


class VideoDetail(VideoSummary):
    tts_model_id: int | None = None
    tts_voice: str
    video_ratio_preset: str
    fps: int
    voice_volume: float
    bgm_volume: float
    target_duration_seconds: float | None = None
    region: str
    subtitle_font_color: str = "#FFD400"
    subtitle_stroke_color: str = "#000000"
    subtitle_font_size: int | None = None
    voice_path: str | None = None
    error: str | None = None
