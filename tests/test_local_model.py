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
