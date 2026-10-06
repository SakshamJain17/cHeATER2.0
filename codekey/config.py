from dataclasses import dataclass
from pathlib import Path

import yaml

from codekey.exceptions import ConfigurationError


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    path: Path
    binary: str
    timeout: float
    max_tokens: int


@dataclass(frozen=True)
class HotkeyConfig:
    screen: str
    capture_screen: str
    process_captures: str
    clear_captures: str
    solve: str
    type_answer: str
    cancel: str
    stop: str


@dataclass(frozen=True)
class LimitsConfig:
    max_input_chars: int
    max_output_chars: int


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    output_mode: str


@dataclass(frozen=True)
class AppConfig:
    typing_interval_seconds: float
    cooldown_seconds: float
    max_screen_captures: int
    debug: bool


@dataclass(frozen=True)
class Config:
    model: ModelConfig
    hotkey: HotkeyConfig
    limits: LimitsConfig
    generation: GenerationConfig
    app: AppConfig


def _section(data: dict, key: str) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section '{key}' must be a mapping.")
    return value


def _boolean(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ConfigurationError(f"{name} must be true or false.")


def load_config(path: str | Path) -> Config:
    config_path = Path(path).expanduser().resolve()
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file) or {}
    except OSError as error:
        raise ConfigurationError(f"Cannot read configuration file: {config_path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid YAML in configuration file: {error}") from error

    if not isinstance(data, dict):
        raise ConfigurationError("The configuration root must be a mapping.")

    model = _section(data, "model")
    hotkey = _section(data, "hotkey")
    limits = _section(data, "limits")
    generation = _section(data, "generation")
    app = _section(data, "app")
    try:
        binary = str(model.get("binary", "llama-cli"))
        if "/" in binary or "\\" in binary:
            binary = str((config_path.parent / binary).resolve())
        config = Config(
            model=ModelConfig(
                provider=str(model.get("provider", "llama_cpp")),
                path=(config_path.parent / str(model.get("path", "models/model.gguf"))).resolve(),
                binary=binary,
                timeout=float(model.get("timeout", 300)),
                max_tokens=int(model.get("max_tokens", 2048)),
            ),
            hotkey=HotkeyConfig(
                screen=str(hotkey.get("screen", "<ctrl>+<shift>+s")),
                capture_screen=str(hotkey.get("capture_screen", "<ctrl>+<shift>+a")),
                process_captures=str(hotkey.get("process_captures", "<ctrl>+<shift>+p")),
                clear_captures=str(hotkey.get("clear_captures", "<ctrl>+<shift>+d")),
                solve=str(hotkey.get("solve", "<alt>+<shift>+p")),
                type_answer=str(hotkey.get("type_answer", "<ctrl>+<shift>+t")),
                cancel=str(hotkey.get("cancel", "<ctrl>+<shift>+x")),
                stop=str(hotkey.get("stop", "<ctrl>+<shift>+q")),
            ),
            limits=LimitsConfig(
                max_input_chars=int(limits.get("max_input_chars", 12000)),
                max_output_chars=int(limits.get("max_output_chars", 30000)),
            ),
            generation=GenerationConfig(
                temperature=float(generation.get("temperature", 0.1)),
                output_mode=str(generation.get("output_mode", "code_only")),
            ),
            app=AppConfig(
                typing_interval_seconds=float(app.get("typing_interval_seconds", 0.02)),
                cooldown_seconds=float(app.get("cooldown_seconds", 1.5)),
                max_screen_captures=int(app.get("max_screen_captures", 5)),
                debug=_boolean(app.get("debug", False), "app.debug"),
            ),
        )
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"Invalid configuration value: {error}") from error

    if config.model.provider != "llama_cpp":
        raise ConfigurationError("Only the offline llama.cpp provider is supported.")
    if not config.model.binary.strip() or config.model.timeout <= 0 or config.model.max_tokens <= 0:
        raise ConfigurationError("Model binary, timeout, and max_tokens must be valid.")
    if config.limits.max_input_chars <= 0 or config.limits.max_output_chars <= 0:
        raise ConfigurationError("Input and output limits must be positive.")
    if not 0 <= config.generation.temperature <= 2:
        raise ConfigurationError("Generation temperature must be between 0 and 2.")
    if config.generation.output_mode not in {"code_only", "code_and_explanation"}:
        raise ConfigurationError("output_mode must be code_only or code_and_explanation.")
    if config.app.cooldown_seconds < 0:
        raise ConfigurationError("Cooldown must not be negative.")
    if not 1 <= config.app.max_screen_captures <= 20:
        raise ConfigurationError("max_screen_captures must be between 1 and 20.")
    if not 0 <= config.app.typing_interval_seconds <= 1:
        raise ConfigurationError("Typing interval must be between 0 and 1 second.")
    shortcuts = (
        config.hotkey.screen, config.hotkey.capture_screen,
        config.hotkey.process_captures, config.hotkey.clear_captures,
        config.hotkey.solve, config.hotkey.type_answer,
        config.hotkey.cancel, config.hotkey.stop,
    )
    if not all(shortcut.strip() for shortcut in shortcuts):
        raise ConfigurationError("Hotkeys must not be empty.")
    if len(set(shortcuts)) != len(shortcuts):
        raise ConfigurationError("Hotkeys must differ.")
    return config
