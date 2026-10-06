import subprocess

import pytest

from codekey.config import ModelConfig
from codekey.exceptions import ModelError
from codekey.local_model import LocalModelClient


def test_local_model_uses_installed_file_without_network(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    monkeypatch.setattr("codekey.local_model.shutil.which", lambda name: "/bin/llama-cli")
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "Loading model...\n> question\nB\n\nExiting...", "")

    monkeypatch.setattr("codekey.local_model.subprocess.run", fake_run)
    client = LocalModelClient(ModelConfig("llama_cpp", model, "llama-cli", 60, 32))
    assert client.generate("system", "question", 0.1) == "B"
    assert commands[0][0][:3] == ["/bin/llama-cli", "--model", str(model)]
    assert commands[0][1]["timeout"] == 60


def test_local_model_requires_gguf_file(tmp_path, monkeypatch):
    monkeypatch.setattr("codekey.local_model.shutil.which", lambda name: "/bin/llama-cli")
    client = LocalModelClient(ModelConfig("llama_cpp", tmp_path / "missing.gguf", "llama-cli", 60, 32))
    with pytest.raises(ModelError, match="not found"):
        client.ensure_ready()


def test_windows_model_finds_winget_link(tmp_path, monkeypatch):
    from codekey import local_model

    link = tmp_path / "Microsoft" / "WinGet" / "Links" / "llama-cli.exe"
    link.parent.mkdir(parents=True)
    link.write_bytes(b"runner")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(local_model.sys, "platform", "win32")
    monkeypatch.setattr(local_model.shutil, "which", lambda name: None)
    client = LocalModelClient(ModelConfig("llama_cpp", tmp_path / "model.gguf", "llama-cli", 60, 32))
    assert client._command_prefix() == [str(link)]


def test_windows_model_does_not_open_console(tmp_path, monkeypatch):
    from codekey import local_model

    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    monkeypatch.setattr(local_model.sys, "platform", "win32")
    monkeypatch.setattr(local_model.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(local_model.shutil, "which", lambda name: "llama-cli.exe")
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "answer", "")

    monkeypatch.setattr(local_model.subprocess, "run", fake_run)
    client = LocalModelClient(ModelConfig("llama_cpp", model, "llama-cli", 60, 32))
    assert client.generate("system", "question", 0.1) == "answer"
    assert seen["creationflags"] == 0x08000000
