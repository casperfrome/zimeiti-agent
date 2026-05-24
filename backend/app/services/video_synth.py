"""视频合成 service：搬运 backend/tests/视频合成测试.py 核心逻辑并参数化。

- synthesize_voice: CosyVoice 配音（可选 speech_rate 校准到目标时长）
- prepare_images: 把图片裁剪/缩放到统一画幅
- build_slideshow: 拼接图片轮播 + BGM + 配音 → MP4
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any, Iterable

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from PIL import Image, ImageOps
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
)
from moviepy.audio.fx import AudioLoop, MultiplyVolume


VIDEO_RATIO_PRESETS = {
    "portrait_9_16":  (1080, 1920),
    "landscape_16_9": (1920, 1080),
    "square_1_1":     (1080, 1080),
}

TTS_DURATION_TOLERANCE_SECONDS = 0.75
MIN_COSYVOICE_SPEECH_RATE = 0.5
MAX_COSYVOICE_SPEECH_RATE = 2.0
DEFAULT_SUBTITLE_FONT_COLOR = "#FFD400"
DEFAULT_SUBTITLE_STROKE_COLOR = "#000000"
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
COSYVOICE_V3_SYSTEM_VOICES = {
    "longanyang",
    "longxiaochun_v3",
}
COSYVOICE_V2_SYSTEM_VOICES = {
    "longxiaochun_v2",
    "longanyang_v2",
}
COSYVOICE_SYSTEM_VOICES = COSYVOICE_V2_SYSTEM_VOICES | COSYVOICE_V3_SYSTEM_VOICES
COSYVOICE_DEPRECATED_V3_VOICE_ALIASES = {
    "longxiaochun": "longxiaochun_v3",
    "longjing": "longxiaochun_v3",
    "longhua": "longxiaochun_v3",
}


@dataclass(frozen=True)
class SubtitleStyle:
    font_color: str = DEFAULT_SUBTITLE_FONT_COLOR
    stroke_color: str = DEFAULT_SUBTITLE_STROKE_COLOR
    font_size: int | None = None


@dataclass(frozen=True)
class SubtitleSegment:
    text: str
    start: float
    duration: float


def resolve_video_size(preset: str) -> tuple[int, int]:
    try:
        return VIDEO_RATIO_PRESETS[preset]
    except KeyError as exc:
        raise ValueError(
            f"未知的视频比例预设: {preset}。可用: {sorted(VIDEO_RATIO_PRESETS)}"
        ) from exc


def _normalize_hex_color(value: str, field_name: str) -> str:
    if not HEX_COLOR_RE.match(value):
        raise ValueError(f"{field_name} 必须是 #RRGGBB 格式。")
    return value.upper()


def normalize_subtitle_style(
    *,
    font_color: str = DEFAULT_SUBTITLE_FONT_COLOR,
    stroke_color: str = DEFAULT_SUBTITLE_STROKE_COLOR,
    font_size: int | None = None,
) -> SubtitleStyle:
    if font_size is not None and font_size <= 0:
        raise ValueError("subtitle_font_size 必须大于 0，或留空使用自动字号。")
    return SubtitleStyle(
        font_color=_normalize_hex_color(font_color, "subtitle_font_color"),
        stroke_color=_normalize_hex_color(stroke_color, "subtitle_stroke_color"),
        font_size=font_size,
    )


def resolve_subtitle_font_size(
    video_size: tuple[int, int],
    font_size: int | None,
) -> int:
    if font_size is not None:
        if font_size <= 0:
            raise ValueError("subtitle_font_size 必须大于 0，或留空使用自动字号。")
        return int(font_size)
    return max(28, min(84, round(min(video_size) * 0.06)))


def resolve_subtitle_stroke_width(font_size: int) -> int:
    return max(2, round(font_size * 0.08))


def split_subtitle_sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in SENTENCE_RE.finditer(text) if m.group(0).strip()]


def build_subtitle_segments(text: str, total_duration: float) -> list[SubtitleSegment]:
    if total_duration <= 0:
        return []
    sentences = split_subtitle_sentences(text)
    if not sentences:
        return []

    weights = [max(1, len(re.sub(r"\s+", "", item))) for item in sentences]
    total_weight = sum(weights)
    start = 0.0
    segments: list[SubtitleSegment] = []
    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        if index == len(sentences) - 1:
            duration = total_duration - start
        else:
            duration = total_duration * weight / total_weight
        segments.append(SubtitleSegment(sentence, start, duration))
        start += duration
    return segments


def resolve_subtitle_font_path() -> str | None:
    configured = os.getenv("SUBTITLE_FONT_PATH")
    if configured and Path(configured).exists():
        return configured

    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def make_subtitle_clips(
    *,
    text: str,
    total_duration: float,
    video_size: tuple[int, int],
    style: SubtitleStyle,
) -> list[TextClip]:
    font_size = resolve_subtitle_font_size(video_size, style.font_size)
    stroke_width = resolve_subtitle_stroke_width(font_size)
    font_path = resolve_subtitle_font_path()
    caption_width = int(video_size[0] * 0.86)
    bottom_margin = int(video_size[1] * 0.08)

    clips: list[TextClip] = []
    for segment in build_subtitle_segments(text, total_duration):
        clip = TextClip(
            font=font_path,
            text=segment.text,
            font_size=font_size,
            size=(caption_width, None),
            color=style.font_color,
            stroke_color=style.stroke_color,
            stroke_width=stroke_width,
            method="caption",
            text_align="center",
            horizontal_align="center",
            vertical_align="center",
            transparent=True,
            duration=segment.duration,
        )
        top = max(0, video_size[1] - bottom_margin - clip.h)
        clips.append(clip.with_start(segment.start).with_position(("center", top)))
    return clips


def save_video_thumbnail(video_clip: Any, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = video_clip.get_frame(0)
    Image.fromarray(frame).convert("RGB").save(output_path, quality=90)
    return output_path


def calculate_speech_rate(source: float, target: float) -> float:
    if source <= 0 or target <= 0:
        raise ValueError("时长必须大于 0。")
    rate = source / target
    if not MIN_COSYVOICE_SPEECH_RATE <= rate <= MAX_COSYVOICE_SPEECH_RATE:
        raise ValueError(
            f"目标时长超出 CosyVoice speech_rate 支持范围 "
            f"[{MIN_COSYVOICE_SPEECH_RATE}, {MAX_COSYVOICE_SPEECH_RATE}]。"
            f"原始 {source:.2f}s，目标 {target:.2f}s，需要 rate={rate:.2f}。"
        )
    return round(rate, 4)


def validate_tts_voice(model: str, voice: str) -> None:
    if model.startswith("cosyvoice-v3") and not model.startswith("cosyvoice-v3.5"):
        if voice not in COSYVOICE_V3_SYSTEM_VOICES:
            suggestion = COSYVOICE_DEPRECATED_V3_VOICE_ALIASES.get(voice)
            if suggestion:
                raise ValueError(
                    f"音色 {voice} 不支持 {model}，请选择 {suggestion} 或其他 V3 音色。"
                )
            raise ValueError(
                f"音色 {voice} 不支持 {model}，请选择 longanyang、longxiaochun_v3 等 V3 音色。"
            )

    if model.startswith("cosyvoice-v2") and voice not in COSYVOICE_V2_SYSTEM_VOICES:
        raise ValueError(
            f"音色 {voice} 不支持 {model}，请选择 longxiaochun_v2 或 longanyang_v2。"
        )

    if model.startswith("cosyvoice-v3.5") and voice in COSYVOICE_SYSTEM_VOICES:
        raise ValueError(
            f"{model} 不支持系统音色 {voice}。"
            "CosyVoice V3.5 需要使用复刻/声音设计音色；"
            "当前页面请选择 CosyVoice V3 或 V2 模型来使用 longanyang/longxiaochun 等系统音色。"
        )


def get_audio_duration(path: str | Path) -> float:
    audio = AudioFileClip(str(path))
    try:
        return float(audio.duration)
    finally:
        audio.close()


def _setup_dashscope(api_key: str, region: str) -> None:
    if not api_key:
        raise RuntimeError("阿里云 DashScope API Key 未配置，请到「模型与 Key」设置。")
    dashscope.api_key = api_key
    if region == "sg":
        dashscope.base_websocket_api_url = (
            "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"
        )
    else:
        dashscope.base_websocket_api_url = (
            "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
        )


def _safe_response_field(response: Any, key: str) -> Any:
    if response is None:
        return None
    if isinstance(response, dict):
        return response.get(key)
    return getattr(response, key, None)


def _format_tts_failure(response: Any) -> str:
    if response is None:
        return "未返回音频数据"

    header = _safe_response_field(response, "header")
    code = (
        _safe_response_field(response, "code")
        or _safe_response_field(response, "error_code")
        or _safe_response_field(header, "code")
        or _safe_response_field(header, "error_code")
    )
    message = (
        _safe_response_field(response, "message")
        or _safe_response_field(response, "error_message")
        or _safe_response_field(header, "message")
        or _safe_response_field(header, "error_message")
    )
    request_id = (
        _safe_response_field(response, "request_id")
        or _safe_response_field(header, "request_id")
    )
    task_id = (
        _safe_response_field(response, "task_id")
        or _safe_response_field(header, "task_id")
    )
    event = _safe_response_field(response, "event") or _safe_response_field(header, "event")

    parts = []
    for name, value in (
        ("code", code),
        ("message", message),
        ("request_id", request_id),
        ("task_id", task_id),
        ("event", event),
    ):
        if value:
            parts.append(f"{name}={value}")

    if parts:
        return "，".join(parts)
    return f"未返回音频数据，response={response!r}"


def _tts_call(model: str, voice: str, speech_rate: float, text: str, output: Path) -> None:
    validate_tts_voice(model, voice)
    synthesizer = SpeechSynthesizer(model=model, voice=voice, speech_rate=speech_rate)
    audio_bytes = synthesizer.call(text)
    if not isinstance(audio_bytes, (bytes, bytearray)) or not audio_bytes:
        response = synthesizer.get_response()
        raise RuntimeError(f"DashScope TTS 合成失败：{_format_tts_failure(response)}")
    output.write_bytes(bytes(audio_bytes))


def synthesize_voice(
    *,
    api_key: str,
    model: str,
    voice: str,
    text: str,
    output_path: Path,
    region: str = "cn",
    target_duration: float | None = None,
) -> tuple[Path, float, float]:
    """返回 (voice_path, voice_duration, speech_rate_used)。"""
    _setup_dashscope(api_key, region)

    if not text.strip():
        raise RuntimeError("配音文案为空。")

    # 第一次按 1.0 倍速合成
    baseline = output_path.with_name(f"{output_path.stem}_baseline{output_path.suffix}")
    _tts_call(model, voice, 1.0, text, baseline)
    baseline_duration = get_audio_duration(baseline)

    if target_duration is None or abs(baseline_duration - target_duration) <= TTS_DURATION_TOLERANCE_SECONDS:
        baseline.replace(output_path)
        final_duration = get_audio_duration(output_path)
        return output_path, final_duration, 1.0

    rate = calculate_speech_rate(baseline_duration, target_duration)
    _tts_call(model, voice, rate, text, output_path)
    final_duration = get_audio_duration(output_path)
    # 清理 baseline
    try:
        baseline.unlink()
    except FileNotFoundError:
        pass
    return output_path, final_duration, rate


def prepare_images(
    image_paths: Iterable[str | Path],
    video_size: tuple[int, int],
    work_dir: Path,
) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for index, src in enumerate(image_paths, start=1):
        dest = work_dir / f"{index:03d}.jpg"
        img = Image.open(src).convert("RGB")
        img = ImageOps.fit(
            img, video_size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        img.save(dest, quality=95)
        out.append(dest)
    return out


def _validate_volume(value: float, name: str) -> float:
    if value < 0:
        raise ValueError(f"{name} 必须大于等于 0。")
    return float(value)


def build_slideshow(
    *,
    image_paths: list[Path],
    voice_path: Path,
    bgm_path: Path | None,
    output_path: Path,
    total_duration: float,
    fps: int = 30,
    voice_volume: float = 1.0,
    bgm_volume: float = 0.1,
    subtitle_text: str = "",
    subtitle_font_color: str = DEFAULT_SUBTITLE_FONT_COLOR,
    subtitle_stroke_color: str = DEFAULT_SUBTITLE_STROKE_COLOR,
    subtitle_font_size: int | None = None,
    thumbnail_path: Path | None = None,
) -> Path:
    if total_duration <= 0:
        raise RuntimeError("视频总时长必须大于 0。")
    if not image_paths:
        raise RuntimeError("没有图片可合成。")

    per_image = total_duration / len(image_paths)

    image_clips = [ImageClip(str(p)).with_duration(per_image) for p in image_paths]

    subtitle_style = normalize_subtitle_style(
        font_color=subtitle_font_color,
        stroke_color=subtitle_stroke_color,
        font_size=subtitle_font_size,
    )

    video = subtitled_video = voice_audio = bgm_audio = final_audio = final_video = None
    subtitle_clips: list[TextClip] = []
    try:
        video = concatenate_videoclips(image_clips, method="compose")
        if subtitle_text.strip():
            subtitle_clips = make_subtitle_clips(
                text=subtitle_text,
                total_duration=total_duration,
                video_size=(video.w, video.h),
                style=subtitle_style,
            )
            if subtitle_clips:
                subtitled_video = CompositeVideoClip(
                    [video, *subtitle_clips],
                    size=(video.w, video.h),
                )
        video_for_output = subtitled_video or video

        voice_audio = AudioFileClip(str(voice_path)).with_effects([
            MultiplyVolume(_validate_volume(voice_volume, "voice_volume")),
        ])

        audio_tracks = [voice_audio]
        if bgm_path is not None and Path(bgm_path).exists():
            bgm_audio = AudioFileClip(str(bgm_path)).with_effects([
                AudioLoop(duration=total_duration),
                MultiplyVolume(_validate_volume(bgm_volume, "bgm_volume")),
            ])
            audio_tracks.insert(0, bgm_audio)

        final_audio = CompositeAudioClip(audio_tracks)
        final_video = video_for_output.with_audio(final_audio)

        if thumbnail_path is not None:
            save_video_thumbnail(final_video, thumbnail_path)

        final_video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )
    finally:
        for clip in (
            final_video,
            final_audio,
            bgm_audio,
            voice_audio,
            subtitled_video,
            video,
            *subtitle_clips,
            *image_clips,
        ):
            if clip is not None:
                try:
                    clip.close()
                except Exception:
                    pass

    return output_path
