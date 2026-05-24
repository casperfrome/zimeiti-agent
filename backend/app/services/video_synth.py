"""视频合成 service：搬运 backend/tests/视频合成测试.py 核心逻辑并参数化。

- synthesize_voice: CosyVoice 配音（可选 speech_rate 校准到目标时长）
- prepare_images: 把图片裁剪/缩放到统一画幅
- build_slideshow: 拼接图片轮播 + BGM + 配音 → MP4
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from PIL import Image, ImageOps
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
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


def resolve_video_size(preset: str) -> tuple[int, int]:
    try:
        return VIDEO_RATIO_PRESETS[preset]
    except KeyError as exc:
        raise ValueError(
            f"未知的视频比例预设: {preset}。可用: {sorted(VIDEO_RATIO_PRESETS)}"
        ) from exc


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


def _tts_call(model: str, voice: str, speech_rate: float, text: str, output: Path) -> None:
    synthesizer = SpeechSynthesizer(model=model, voice=voice, speech_rate=speech_rate)
    audio_bytes = synthesizer.call(text)
    output.write_bytes(audio_bytes)


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
) -> Path:
    if total_duration <= 0:
        raise RuntimeError("视频总时长必须大于 0。")
    if not image_paths:
        raise RuntimeError("没有图片可合成。")

    per_image = total_duration / len(image_paths)

    image_clips = [ImageClip(str(p)).with_duration(per_image) for p in image_paths]

    video = voice_audio = bgm_audio = final_audio = final_video = None
    try:
        video = concatenate_videoclips(image_clips, method="compose")

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
        final_video = video.with_audio(final_audio)

        final_video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )
    finally:
        for clip in (final_video, final_audio, bgm_audio, voice_audio, video, *image_clips):
            if clip is not None:
                try:
                    clip.close()
                except Exception:
                    pass

    return output_path
