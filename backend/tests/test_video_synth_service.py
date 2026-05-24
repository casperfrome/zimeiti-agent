from pathlib import Path

import pytest

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
            "bad-voice",
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
