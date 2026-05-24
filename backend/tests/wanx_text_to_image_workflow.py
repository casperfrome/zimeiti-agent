"""
Manual Wanx text-to-image workflow.

Workflow:
1. Put a long copywriting text in LONG_COPY_TEXT.
2. Ask local Ollama qwen3:8b to split it into image prompts.
3. Generate images with Alibaba Cloud DashScope wanx2.0-t2i-turbo.
4. Download every returned image URL immediately and write a manifest.

This file intentionally does not start with test_ because real generation costs
money and should not run as part of pytest.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import requests
from dashscope import ImageSynthesis


# =====================
# Manual controls
# =====================

LONG_COPY_TEXT = """
清晨的城市还没有完全醒来，年轻的创业者独自走进一间小小的工作室。
桌上摊着写满修改痕迹的计划书，墙上贴着一张被反复涂改的路线图。
他打开电脑，屏幕的冷光照亮疲惫却坚定的脸。
午后，团队成员陆续赶来，他们围在白板前争论、推翻、重写方案。
夜晚的窗外灯火连成一片，他站在天台上看着远处的高楼，终于露出笑容。
这一刻，他明白真正改变命运的不是突然出现的机会，而是每一次不肯放弃的选择。
"""

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output" / "wanx_images"

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_TIMEOUT_SECONDS = 120

IMAGE_MODEL = "wanx2.0-t2i-turbo"
IMAGE_SIZE = "1024*1024"
IMAGES_PER_PROMPT = 1
NEGATIVE_PROMPT = "低清晰度，畸形，文字水印，logo，多余手指，脸部崩坏，过曝，欠曝"
PROMPT_EXTEND = True
WATERMARK = False
SEED: int | None = None

DOWNLOAD_TIMEOUT_SECONDS = 120
DRY_RUN_SPLIT_ONLY = False


SPLIT_SYSTEM_PROMPT = """
你是专业短视频分镜和文生图提示词工程师。

任务：
把用户输入的一大段中文文案拆成若干个适合文生图模型生成画面的提示词。

硬性输出要求：
1. 只输出 JSON，不要输出 Markdown、解释、注释、代码块或多余文本。
2. JSON 顶层结构必须是：
   {"prompts":[{"index":1,"prompt":"..."}]}
3. index 从 1 开始递增，必须是整数。
4. prompt 必须是中文，可以包含少量英文摄影术语。
5. 每条 prompt 必须小于等于 750 个中文字符，给图像模型 800 字限制留余量。
6. 每条 prompt 描述一个可直接生成的静态画面，不要写镜头运动、转场、配音或字幕。
7. 每条 prompt 都要包含主体、环境、动作/状态、构图、光线、风格、画幅氛围。
8. 不要生成任何政治、色情、血腥、侵权角色或真实名人相关内容。

风格偏好：
电影感，真实摄影，高细节，情绪清晰，画面干净，适合短视频分镜。
"""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_manifest(manifest: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def _short_text(text: str, max_len: int = 500) -> str:
    text = text.replace("\r", "").strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def split_prompts_with_ollama(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        raise ValueError("LONG_COPY_TEXT 不能为空。")

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SPLIT_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": text.strip()},
        ],
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"调用本地 Ollama 失败：{exc}。请确认 Ollama 已启动，且模型 {OLLAMA_MODEL!r} 已拉取。"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Ollama 返回的不是 JSON：{_short_text(response.text)}") from exc

    content = ((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError(f"Ollama 响应缺少 message.content：{json.dumps(data, ensure_ascii=False)[:800]}")

    try:
        payload = json.loads(_strip_json_text(content))
    except ValueError as exc:
        raise RuntimeError(f"Ollama 输出不是合法 JSON：{_short_text(content)}") from exc

    return validate_prompts(payload)


def validate_prompts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    prompts = payload.get("prompts") if isinstance(payload, dict) else None
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("Ollama 输出必须包含非空数组字段 prompts。")

    validated: list[dict[str, Any]] = []
    for expected_index, item in enumerate(prompts, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"prompts[{expected_index - 1}] 必须是对象。")

        index = item.get("index", expected_index)
        prompt = item.get("prompt")
        if not isinstance(index, int):
            raise ValueError(f"第 {expected_index} 条 prompt 的 index 必须是整数。")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"第 {expected_index} 条 prompt 不能为空。")

        prompt = prompt.strip()
        if len(prompt) > 750:
            raise ValueError(f"第 {expected_index} 条 prompt 长度为 {len(prompt)}，超过 750 字。")

        validated.append({"index": expected_index, "prompt": prompt})

    return validated


def _safe_get_field(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    try:
        return getattr(obj, key)
    except (AttributeError, KeyError):
        return None


def _dashscope_result_to_dict(result: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key in ("url", "orig_prompt", "actual_prompt", "code", "message"):
        value = _safe_get_field(result, key)
        if value is not None:
            data[key] = value
    return data


def _response_error_message(response: Any) -> str:
    status_code = _safe_get_field(response, "status_code")
    code = _safe_get_field(response, "code")
    message = _safe_get_field(response, "message")
    request_id = _safe_get_field(response, "request_id")
    return (
        "DashScope 图像生成失败："
        f"status_code={status_code}, code={code}, message={message}, request_id={request_id}"
    )


def generate_images_for_prompt(prompt_item: dict[str, Any]) -> list[dict[str, Any]]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("没有检测到环境变量 DASHSCOPE_API_KEY，请先设置阿里云 DashScope API Key。")

    kwargs: dict[str, Any] = {
        "model": IMAGE_MODEL,
        "prompt": prompt_item["prompt"],
        "negative_prompt": NEGATIVE_PROMPT,
        "api_key": api_key,
        "n": IMAGES_PER_PROMPT,
        "size": IMAGE_SIZE,
        "prompt_extend": PROMPT_EXTEND,
        "watermark": WATERMARK,
    }
    if SEED is not None:
        kwargs["seed"] = SEED

    response = ImageSynthesis.call(**kwargs)
    if _safe_get_field(response, "status_code") != HTTPStatus.OK:
        raise RuntimeError(_response_error_message(response))

    output = _safe_get_field(response, "output")
    results = _safe_get_field(output, "results") if output is not None else None
    if not results:
        raise RuntimeError(f"DashScope 响应没有返回图片结果：request_id={_safe_get_field(response, 'request_id')}")

    image_records: list[dict[str, Any]] = []
    for image_number, result in enumerate(results, start=1):
        result_data = _dashscope_result_to_dict(result)
        url = result_data.get("url")
        if not url:
            raise RuntimeError(
                f"DashScope 第 {image_number} 张图片缺少 url：request_id={_safe_get_field(response, 'request_id')}"
            )

        image_records.append(
            {
                "scene_index": prompt_item["index"],
                "image_index": image_number,
                "request_id": _safe_get_field(response, "request_id"),
                "task_id": _safe_get_field(output, "task_id"),
                "task_status": _safe_get_field(output, "task_status"),
                "url": url,
                "orig_prompt": result_data.get("orig_prompt"),
                "actual_prompt": result_data.get("actual_prompt"),
            }
        )

    return image_records


def download_image(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"下载图片失败：{url}，错误：{exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if content_type and "image" not in content_type.lower():
        raise RuntimeError(f"下载 URL 返回的不是图片：content_type={content_type}, url={url}")

    path.write_bytes(response.content)


def main() -> None:
    manifest: dict[str, Any] = {
        "created_at": _now_iso(),
        "source_text": LONG_COPY_TEXT.strip(),
        "config": {
            "ollama_base_url": OLLAMA_BASE_URL,
            "ollama_model": OLLAMA_MODEL,
            "image_model": IMAGE_MODEL,
            "image_size": IMAGE_SIZE,
            "images_per_prompt": IMAGES_PER_PROMPT,
            "negative_prompt": NEGATIVE_PROMPT,
            "prompt_extend": PROMPT_EXTEND,
            "watermark": WATERMARK,
            "seed": SEED,
            "dry_run_split_only": DRY_RUN_SPLIT_ONLY,
        },
        "prompts": [],
        "images": [],
        "failures": [],
    }

    print("Step 1/2: calling local Ollama to split image prompts...")
    prompts = split_prompts_with_ollama(LONG_COPY_TEXT)
    manifest["prompts"] = prompts
    _write_manifest(manifest)

    print(f"Generated {len(prompts)} image prompts:")
    for item in prompts:
        print(f"{item['index']:03d}. {item['prompt']}")

    if DRY_RUN_SPLIT_ONLY:
        print(f"DRY_RUN_SPLIT_ONLY=True, manifest written to {OUTPUT_DIR / 'manifest.json'}")
        return

    print("Step 2/2: calling DashScope Wanx and downloading images...")
    for prompt_item in prompts:
        try:
            records = generate_images_for_prompt(prompt_item)
            for record in records:
                output_path = OUTPUT_DIR / f"scene_{record['scene_index']:03d}_{record['image_index']:02d}.png"
                download_image(record["url"], output_path)
                record["path"] = str(output_path)
                manifest["images"].append(record)
                print(f"Saved image: {output_path}")
        except Exception as exc:  # noqa: BLE001 - keep processing the remaining prompts.
            failure = {
                "scene_index": prompt_item["index"],
                "prompt": prompt_item["prompt"],
                "error": str(exc),
                "failed_at": _now_iso(),
            }
            manifest["failures"].append(failure)
            print(f"Failed scene {prompt_item['index']:03d}: {exc}", file=sys.stderr)
        finally:
            _write_manifest(manifest)

    if manifest["failures"]:
        print(
            f"Finished with {len(manifest['failures'])} failure(s). "
            f"See {OUTPUT_DIR / 'manifest.json'}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"All images saved. Manifest: {OUTPUT_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
