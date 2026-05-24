from pathlib import Path
import wave

import pytest
from PIL import Image
from moviepy import ImageClip

from app.services import video_synth


class FakeSpeechSynthesizer:
    response = None
    audio = None
    calls = []

    def __init__(self, model, voice, speech_rate):
        self.model = model
        self.voice = voice
        self.speech_rate = speech_rate
        type(self).calls.append(
            {"model": model, "voice": voice, "speech_rate": speech_rate}
        )

    def call(self, text):
        self.text = text
        return type(self).audio

    def get_response(self):
        return type(self).response


@pytest.fixture(autouse=True)
def fake_synthesizer(monkeypatch):
    FakeSpeechSynthesizer.response = None
    FakeSpeechSynthesizer.audio = None
    FakeSpeechSynthesizer.calls = []
    monkeypatch.setattr(video_synth, "SpeechSynthesizer", FakeSpeechSynthesizer)


def test_tts_call_reports_dashscope_failure_when_audio_is_none(tmp_path: Path):
    FakeSpeechSynthesizer.audio = None
    FakeSpeechSynthesizer.response = {
        "header": {"event": "task-failed"},
        "code": "InvalidVoice",
        "message": "voice not found",
        "request_id": "rid-123",
    }
    output = tmp_path / "voice.mp3"

    with pytest.raises(RuntimeError) as exc_info:
        video_synth._tts_call(
            "cosyvoice-v3-flash",
            "longanyang",
            1.0,
            "hello",
            output,
        )

    message = str(exc_info.value)
    assert "DashScope TTS 合成失败" in message
    assert "code=InvalidVoice" in message
    assert "message=voice not found" in message
    assert "request_id=rid-123" in message
    assert "event=task-failed" in message
    assert not output.exists()


def test_tts_call_rejects_empty_audio_without_writing_file(tmp_path: Path):
    FakeSpeechSynthesizer.audio = b""
    output = tmp_path / "voice.mp3"

    with pytest.raises(RuntimeError, match="未返回音频数据"):
        video_synth._tts_call("cosyvoice-v3-flash", "longanyang", 1.0, "hello", output)

    assert not output.exists()


def test_tts_call_writes_audio_bytes(tmp_path: Path):
    FakeSpeechSynthesizer.audio = b"audio"
    output = tmp_path / "voice.mp3"

    video_synth._tts_call("cosyvoice-v3-flash", "longanyang", 1.25, "hello", output)

    assert output.read_bytes() == b"audio"
    assert FakeSpeechSynthesizer.calls == [
        {"model": "cosyvoice-v3-flash", "voice": "longanyang", "speech_rate": 1.25}
    ]


def test_validate_tts_voice_allows_v3_system_voice():
    video_synth.validate_tts_voice("cosyvoice-v3-flash", "longanyang")


def test_validate_tts_voice_allows_v3_model_specific_voice():
    video_synth.validate_tts_voice("cosyvoice-v3-flash", "longxiaochun_v3")


def test_validate_tts_voice_rejects_v3_voice_without_model_suffix():
    with pytest.raises(ValueError) as exc_info:
        video_synth.validate_tts_voice("cosyvoice-v3-flash", "longxiaochun")

    message = str(exc_info.value)
    assert "longxiaochun" in message
    assert "cosyvoice-v3-flash" in message
    assert "longxiaochun_v3" in message


def test_validate_tts_voice_rejects_v35_with_v3_system_voice():
    with pytest.raises(ValueError) as exc_info:
        video_synth.validate_tts_voice("cosyvoice-v3.5-flash", "longanyang")

    message = str(exc_info.value)
    assert "cosyvoice-v3.5-flash" in message
    assert "longanyang" in message
    assert "CosyVoice V3" in message


def test_tts_call_validates_model_voice_before_dashscope_call(tmp_path: Path):
    output = tmp_path / "voice.mp3"

    with pytest.raises(ValueError, match="不支持系统音色"):
        video_synth._tts_call(
            "cosyvoice-v3.5-flash",
            "longanyang",
            1.0,
            "hello",
            output,
        )

    assert FakeSpeechSynthesizer.calls == []


def test_tts_call_rejects_invalid_v3_voice_before_dashscope_call(tmp_path: Path):
    output = tmp_path / "voice.mp3"

    with pytest.raises(ValueError, match="longxiaochun_v3"):
        video_synth._tts_call(
            "cosyvoice-v3-flash",
            "longxiaochun",
            1.0,
            "hello",
            output,
        )

    assert FakeSpeechSynthesizer.calls == []


def test_subtitle_style_uses_yellow_text_with_black_stroke_by_default():
    style = video_synth.normalize_subtitle_style()

    assert style.font_color == "#FFD400"
    assert style.stroke_color == "#000000"
    assert style.font_size is None


def test_subtitle_style_rejects_invalid_hex_colors():
    with pytest.raises(ValueError, match="subtitle_font_color"):
        video_synth.normalize_subtitle_style(font_color="yellow")

    with pytest.raises(ValueError, match="subtitle_stroke_color"):
        video_synth.normalize_subtitle_style(stroke_color="#000")


def test_auto_subtitle_font_size_uses_video_dimensions():
    assert video_synth.resolve_subtitle_font_size((1080, 1920), None) == 65
    assert video_synth.resolve_subtitle_font_size((320, 180), None) == 28
    assert video_synth.resolve_subtitle_font_size((1080, 1920), 48) == 48


def test_split_subtitle_sentences_preserves_sentence_punctuation():
    text = "第一句。第二句！Third sentence?  尾句"

    assert video_synth.split_subtitle_sentences(text) == [
        "第一句。",
        "第二句！",
        "Third sentence?",
        "尾句",
    ]


def test_build_subtitle_segments_returns_empty_for_blank_text():
    assert video_synth.build_subtitle_segments("   ", 12.0) == []


def test_build_subtitle_segments_distributes_duration_by_text_length():
    segments = video_synth.build_subtitle_segments("短句。更长的一句话。", 10.0)

    assert len(segments) == 2
    assert segments[0].start == 0
    assert segments[0].duration == pytest.approx(3.0, rel=1e-3)
    assert segments[1].start == pytest.approx(3.0, rel=1e-3)
    assert segments[1].duration == pytest.approx(7.0, rel=1e-3)
    assert segments[1].start + segments[1].duration == pytest.approx(10.0)


def test_save_video_thumbnail_writes_jpeg_from_clip(tmp_path: Path):
    source = tmp_path / "source.jpg"
    thumbnail = tmp_path / "thumbnail.jpg"
    Image.new("RGB", (64, 48), (255, 210, 0)).save(source)
    clip = ImageClip(str(source)).with_duration(1)

    try:
        video_synth.save_video_thumbnail(clip, thumbnail)
    finally:
        clip.close()

    assert thumbnail.exists()
    with Image.open(thumbnail) as img:
        assert img.size == (64, 48)
        assert img.mode == "RGB"


def test_build_slideshow_accepts_subtitles_and_writes_thumbnail(tmp_path: Path):
    image = tmp_path / "image.jpg"
    voice = tmp_path / "voice.wav"
    output = tmp_path / "output.mp4"
    thumbnail = tmp_path / "thumbnail.jpg"
    Image.new("RGB", (96, 96), (20, 30, 40)).save(image)
    write_silent_wav(voice, duration_seconds=0.25)

    video_synth.build_slideshow(
        image_paths=[image],
        voice_path=voice,
        bgm_path=None,
        output_path=output,
        total_duration=0.25,
        fps=5,
        subtitle_text="Preview subtitle.",
        subtitle_font_color="#FFD400",
        subtitle_stroke_color="#000000",
        subtitle_font_size=24,
        thumbnail_path=thumbnail,
    )

    assert output.exists()
    assert thumbnail.exists()


def write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 8000) -> None:
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frame_count)
