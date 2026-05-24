# make_video.py
# Python 3.10+ 建议

import os
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

from PIL import Image, ImageOps

from moviepy import (
    ImageClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
)
from moviepy.audio.fx import AudioLoop, MultiplyVolume


# =====================
# 基础配置
# =====================

SCRIPT_DIR = Path(__file__).resolve().parent

TEXT = """
张雪峰老师，我还记得你，一字一句，把我拉进迷雾里。
"""

IMAGE_DIR = SCRIPT_DIR / "images"
BGM_PATH = SCRIPT_DIR / "bgm.mp3"

OUTPUT_DIR = SCRIPT_DIR / "output"
VOICE_PATH = OUTPUT_DIR / "voice.mp3"
VIDEO_PATH = OUTPUT_DIR / "final_video2.mp4"

# 视频比例预设：通过 VIDEO_RATIO_PRESET 手动切换
VIDEO_RATIO_PRESET = "portrait_9_16"
VIDEO_RATIO_PRESETS = {
    "portrait_9_16": (1080, 1920),
    "landscape_16_9": (1920, 1080),
    "square_1_1": (1080, 1080),
}

# 留空则使用 AI 配音实际时长；填数字则尝试让配音语速匹配该时长
TARGET_VIDEO_DURATION_SECONDS: float | None = None
TTS_DURATION_TOLERANCE_SECONDS = 0.75
MIN_COSYVOICE_SPEECH_RATE = 0.5
MAX_COSYVOICE_SPEECH_RATE = 2.0

FPS = 30

# 图片切换模式：每张图平均分配配音时长
# 例如配音 60 秒，10 张图片，则每张显示 6 秒
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# 配音音量：1.0 为原音量，0.8 降低，1.2 提高
VOICE_VOLUME = 2

# BGM 音量，建议 0.08 ~ 0.25 之间
BGM_VOLUME = 0.08

# CosyVoice 配置
# 阿里云官方示例使用 cosyvoice-v3-flash + longanyang
COSYVOICE_MODEL = "cosyvoice-v3-flash"
COSYVOICE_VOICE = "longanyang"

# endpoint:
# 默认北京地域；如果你用新加坡地域，把 REGION 改成 "sg"
REGION = "cn"  # "cn" or "sg"


# =====================
# 工具函数
# =====================

def ensure_dirs() -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def resolve_video_size(preset: str) -> tuple[int, int]:
    try:
        return VIDEO_RATIO_PRESETS[preset]
    except KeyError as exc:
        available = ", ".join(sorted(VIDEO_RATIO_PRESETS))
        raise ValueError(
            f"未知的视频比例预设: {preset}。可用预设: {available}"
        ) from exc


def resolve_target_duration(voice_duration: float) -> float:
    if voice_duration <= 0:
        raise ValueError("配音音频时长异常。")

    if TARGET_VIDEO_DURATION_SECONDS is None:
        return voice_duration

    if TARGET_VIDEO_DURATION_SECONDS <= 0:
        raise ValueError("TARGET_VIDEO_DURATION_SECONDS 必须大于 0，或设置为 None。")

    return float(TARGET_VIDEO_DURATION_SECONDS)


def calculate_speech_rate(source_duration: float, target_duration: float) -> float:
    if source_duration <= 0:
        raise ValueError("原始配音时长必须大于 0。")
    if target_duration <= 0:
        raise ValueError("目标视频时长必须大于 0。")

    speech_rate = source_duration / target_duration
    if not MIN_COSYVOICE_SPEECH_RATE <= speech_rate <= MAX_COSYVOICE_SPEECH_RATE:
        raise ValueError(
            "目标视频时长超出 CosyVoice speech_rate 支持范围 "
            f"[{MIN_COSYVOICE_SPEECH_RATE}, {MAX_COSYVOICE_SPEECH_RATE}]。"
            f"原始配音 {source_duration:.2f}s，目标时长 {target_duration:.2f}s，"
            f"需要 speech_rate={speech_rate:.2f}。"
        )

    return round(speech_rate, 4)


def validate_volume_multiplier(volume: float, name: str) -> float:
    if volume < 0:
        raise ValueError(f"{name} 必须大于等于 0。")
    return float(volume)


def get_audio_duration(path: str | Path) -> float:
    audio = AudioFileClip(str(path))
    try:
        return float(audio.duration)
    finally:
        audio.close()


def setup_dashscope() -> None:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "没有检测到环境变量 DASHSCOPE_API_KEY。"
            "请先设置阿里云百炼 API Key。"
        )

    dashscope.api_key = api_key

    if REGION == "sg":
        dashscope.base_websocket_api_url = (
            "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"
        )
    else:
        dashscope.base_websocket_api_url = (
            "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
        )


def synthesize_voice(
    text: str,
    output_path: str | Path,
    speech_rate: float = 1.0,
) -> str:
    """
    调用阿里云 CosyVoice 生成旁白 MP3。
    非流式调用：一次性提交完整文本，返回完整音频 bytes。
    """
    setup_dashscope()

    synthesizer = SpeechSynthesizer(
        model=COSYVOICE_MODEL,
        voice=COSYVOICE_VOICE,
        speech_rate=speech_rate,
    )

    audio_bytes = synthesizer.call(text)

    output_path = Path(output_path)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    print(f"AI 配音已生成: {output_path}")
    print(f"CosyVoice speech_rate: {speech_rate}")
    print(f"CosyVoice request_id: {synthesizer.get_last_request_id()}")

    return str(output_path)


def synthesize_voice_for_target_duration(
    text: str,
    output_path: str | Path,
) -> tuple[str, float]:
    output_path = Path(output_path)

    if TARGET_VIDEO_DURATION_SECONDS is None:
        voice_path = synthesize_voice(text, output_path)
        voice_duration = get_audio_duration(voice_path)
        return voice_path, resolve_target_duration(voice_duration)

    baseline_path = output_path.with_name(f"{output_path.stem}_baseline{output_path.suffix}")
    synthesize_voice(text, baseline_path, speech_rate=1.0)
    baseline_duration = get_audio_duration(baseline_path)
    target_duration = resolve_target_duration(baseline_duration)

    if abs(baseline_duration - target_duration) <= TTS_DURATION_TOLERANCE_SECONDS:
        baseline_path.replace(output_path)
        print(
            "标准语速配音已接近目标时长，"
            f"实际 {baseline_duration:.2f}s，目标 {target_duration:.2f}s。"
        )
        return str(output_path), target_duration

    speech_rate = calculate_speech_rate(baseline_duration, target_duration)
    voice_path = synthesize_voice(text, output_path, speech_rate=speech_rate)
    adjusted_duration = get_audio_duration(voice_path)
    print(
        "已按目标时长调整配音语速，"
        f"原始 {baseline_duration:.2f}s，调整后 {adjusted_duration:.2f}s，"
        f"目标 {target_duration:.2f}s。"
    )
    return voice_path, target_duration


def list_images(image_dir: str | Path) -> list[str]:
    paths = sorted(
        p for p in Path(image_dir).iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not paths:
        raise RuntimeError(f"图片目录为空或没有支持的图片格式: {image_dir}")

    return [str(p) for p in paths]


def prepare_image(
    image_path: str | Path,
    output_path: str | Path,
    video_size: tuple[int, int],
) -> str:
    """
    把图片裁剪/缩放到统一视频尺寸。
    ImageOps.fit 会保持比例，并裁掉多余部分，避免黑边。
    """
    img = Image.open(image_path).convert("RGB")
    img = ImageOps.fit(
        img,
        video_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    img.save(output_path, quality=95)
    return str(output_path)


def prepare_images(
    image_paths: list[str],
    video_size: tuple[int, int],
) -> list[str]:
    processed_dir = Path(OUTPUT_DIR) / "processed_images"
    processed_dir.mkdir(parents=True, exist_ok=True)

    processed_paths = []

    for index, image_path in enumerate(image_paths, start=1):
        output_path = processed_dir / f"{index:03d}.jpg"
        processed_paths.append(prepare_image(image_path, output_path, video_size))

    return processed_paths


def build_slideshow_video(
    image_paths: list[str],
    voice_path: str | Path,
    bgm_path: str | Path,
    output_path: str | Path,
    total_duration: float,
) -> str:
    """
    生成图片轮播视频：
    1. 使用目标总时长
    2. 每张图片平均分配时长
    3. 图片按顺序拼接
    4. BGM 循环到视频长度，并降低音量
    5. 配音 + BGM 混音
    6. 输出 MP4
    """
    if total_duration <= 0:
        raise RuntimeError("视频总时长必须大于 0。")

    per_image_duration = total_duration / len(image_paths)

    image_clips = [
        ImageClip(path).with_duration(per_image_duration)
        for path in image_paths
    ]

    video = None
    voice_audio = None
    bgm_audio = None
    final_audio = None
    final_video = None

    try:
        video = concatenate_videoclips(image_clips, method="compose")

        voice_audio = AudioFileClip(str(voice_path)).with_effects([
            MultiplyVolume(validate_volume_multiplier(VOICE_VOLUME, "VOICE_VOLUME")),
        ])
        bgm_audio = AudioFileClip(str(bgm_path))

        # BGM 循环到视频总时长，并降低音量
        bgm_audio = bgm_audio.with_effects([
            AudioLoop(duration=total_duration),
            MultiplyVolume(validate_volume_multiplier(BGM_VOLUME, "BGM_VOLUME")),
        ])

        # 合成最终音频：BGM + AI 配音
        final_audio = CompositeAudioClip([
            bgm_audio,
            voice_audio,
        ])

        final_video = video.with_audio(final_audio)

        final_video.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )
    finally:
        # 主动释放资源，避免 Windows 上文件被占用
        for clip in [
            final_video,
            final_audio,
            bgm_audio,
            voice_audio,
            video,
            *image_clips,
        ]:
            if clip is not None:
                clip.close()

    print(f"视频已生成: {output_path}")
    return output_path


def main() -> None:
    ensure_dirs()

    video_size = resolve_video_size(VIDEO_RATIO_PRESET)
    image_paths = list_images(IMAGE_DIR)
    processed_images = prepare_images(image_paths, video_size)

    voice_path, total_duration = synthesize_voice_for_target_duration(TEXT, VOICE_PATH)

    build_slideshow_video(
        image_paths=processed_images,
        voice_path=voice_path,
        bgm_path=BGM_PATH,
        output_path=VIDEO_PATH,
        total_duration=total_duration,
    )


if __name__ == "__main__":
    main()
