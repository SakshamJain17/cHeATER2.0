import pytest

from codekey.config import load_config
from codekey.exceptions import ConfigurationError


def test_loads_config_and_typing_interval(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "model:\n  path: models/local-model.gguf\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.model.path == tmp_path / "models" / "local-model.gguf"
    assert config.app.typing_interval_seconds == 0.02


def test_accepts_non_python_default_language_setting(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("generation:\n  default_language: c++\n", encoding="utf-8")
    assert load_config(path).generation.output_mode == "code_only"


def test_rejects_online_provider(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("model:\n  provider: online\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="offline"):
        load_config(path)


def test_rejects_invalid_typing_interval(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('app:\n  typing_interval_seconds: -1\n', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Typing interval"):
        load_config(path)


def test_loads_screen_queue_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("model:\n  path: model.gguf\n", encoding="utf-8")
    config = load_config(path)
    assert config.app.max_screen_captures == 5
    assert config.hotkey.capture_screen == "<ctrl>+<shift>+a"
    assert config.hotkey.process_captures == "<ctrl>+<shift>+p"


def test_rejects_excessive_screen_queue(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("app:\n  max_screen_captures: 21\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="max_screen_captures"):
        load_config(path)
