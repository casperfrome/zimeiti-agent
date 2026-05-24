import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).with_name("视频合成测试.py")


def load_video_script():
    spec = importlib.util.spec_from_file_location("video_synthesis_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_video_size_uses_portrait_preset():
    script = load_video_script()

    assert script.resolve_video_size("portrait_9_16") == (1080, 1920)


def test_resolve_video_size_rejects_unknown_preset():
    script = load_video_script()

    with pytest.raises(ValueError, match="未知的视频比例预设"):
        script.resolve_video_size("wide")


def test_calculate_speech_rate_can_double_speed():
    script = load_video_script()

    assert script.calculate_speech_rate(60, 30) == 2.0


def test_calculate_speech_rate_can_halve_speed():
    script = load_video_script()

    assert script.calculate_speech_rate(30, 60) == 0.5


def test_calculate_speech_rate_rejects_rate_outside_dashscope_range():
    script = load_video_script()

    with pytest.raises(ValueError, match="超出 CosyVoice speech_rate 支持范围"):
        script.calculate_speech_rate(100, 30)


def test_resolve_target_duration_uses_voice_duration_when_unset(monkeypatch):
    script = load_video_script()
    monkeypatch.setattr(script, "TARGET_VIDEO_DURATION_SECONDS", None)

    assert script.resolve_target_duration(12.34) == 12.34


def test_validate_volume_multiplier_accepts_default_voice_volume():
    script = load_video_script()

    assert script.validate_volume_multiplier(script.VOICE_VOLUME, "VOICE_VOLUME") == 1.0


def test_validate_volume_multiplier_rejects_negative_volume():
    script = load_video_script()

    with pytest.raises(ValueError, match="VOICE_VOLUME 必须大于等于 0"):
        script.validate_volume_multiplier(-0.1, "VOICE_VOLUME")
