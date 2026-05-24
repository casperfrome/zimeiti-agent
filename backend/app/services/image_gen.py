"""图片生成 service：搬运 backend/tests/wanx_text_to_image_workflow.py 核心逻辑并参数化。

- split_prompts_via_ollama: 调本地 Ollama 把长文案拆分为分镜 prompts
- generate_one: 调 DashScope ImageSynthesis 生成单个 prompt 的图片
- download_to: 下载 URL 到本地路径
"""
from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, Iterator

import requests
from dashscope import ImageSynthesis

from .storage import abs_path, image_set_dir, rel_path

OLLAMA_TIMEOUT_SECONDS = 120
DOWNLOAD_TIMEOUT_SECONDS = 120


def _strip_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _short(text: str, max_len: int = 500) -> str:
    text = text.replace("\r", "").strip()
    return text if len(text) <= max_len else f"{text[:max_len]}..."


def _validate_prompts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    prompts = payload.get("prompts") if isinstance(payload, dict) else None
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("Ollama 输出必须包含非空数组字段 prompts。")

    validated: list[dict[str, Any]] = []
    for expected_index, item in enumerate(prompts, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"prompts[{expected_index - 1}] 必须是对象。")
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"第 {expected_index} 条 prompt 不能为空。")
        prompt = prompt.strip()
        if len(prompt) > 750:
            raise ValueError(f"第 {expected_index} 条 prompt 长度 {len(prompt)} 超过 750 字。")
        validated.append({"index": expected_index, "prompt": prompt})
    return validated


def split_prompts_via_ollama(
    text: str,
    *,
    ollama_base_url: str,
    ollama_model: str,
    system_prompt: str,
) -> list[dict[str, Any]]:
    if not text.strip():
        raise ValueError("文案内容为空。")

    url = f"{ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": ollama_model,
        "stream": False,
        "think": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": text.strip()},
        ],
    }

    try:
        response = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"调用本地 Ollama 失败：{exc}。请确认 Ollama 已启动，且模型 {ollama_model!r} 已拉取。"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Ollama 返回的不是 JSON：{_short(response.text)}") from exc

    content = ((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError(
            f"Ollama 响应缺少 message.content：{json.dumps(data, ensure_ascii=False)[:800]}"
        )

    try:
        parsed = json.loads(_strip_json_text(content))
    except ValueError as exc:
        raise RuntimeError(f"Ollama 输出不是合法 JSON：{_short(content)}") from exc

    return _validate_prompts(parsed)


def _safe_field(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def generate_one(
    *,
    api_key: str,
    model_id: str,
    prompt: str,
    size: str = "1024*1024",
    n: int = 1,
    negative_prompt: str = "",
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """返回一组 {url, request_id, orig_prompt, actual_prompt}。"""
    if not api_key:
        raise RuntimeError("阿里云 DashScope API Key 未配置，请到「模型与 Key」设置。")

    kwargs: dict[str, Any] = {
        "model": model_id,
        "prompt": prompt,
        "api_key": api_key,
        "n": n,
        "size": size,
        "prompt_extend": prompt_extend,
        "watermark": watermark,
    }
    if negative_prompt:
        kwargs["negative_prompt"] = negative_prompt
    if seed is not None:
        kwargs["seed"] = seed

    response = ImageSynthesis.call(**kwargs)
    if _safe_field(response, "status_code") != HTTPStatus.OK:
        raise RuntimeError(
            "DashScope 图像生成失败："
            f"status_code={_safe_field(response, 'status_code')}, "
            f"code={_safe_field(response, 'code')}, "
            f"message={_safe_field(response, 'message')}, "
            f"request_id={_safe_field(response, 'request_id')}"
        )

    output = _safe_field(response, "output")
    results = _safe_field(output, "results") if output is not None else None
    if not results:
        raise RuntimeError(
            f"DashScope 没有返回图片结果：request_id={_safe_field(response, 'request_id')}"
        )

    out: list[dict[str, Any]] = []
    for r in results:
        url = _safe_field(r, "url")
        if not url:
            raise RuntimeError("DashScope 结果缺少 url 字段。")
        out.append({
            "url": url,
            "request_id": _safe_field(response, "request_id"),
            "orig_prompt": _safe_field(r, "orig_prompt"),
            "actual_prompt": _safe_field(r, "actual_prompt"),
        })
    return out


def download_to(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"下载图片失败：{url}，错误：{exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if content_type and "image" not in content_type.lower():
        raise RuntimeError(f"下载 URL 返回的不是图片：content_type={content_type}, url={url}")

    dest.write_bytes(response.content)
