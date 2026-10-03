import shutil
import subprocess
import sys
import os
from pathlib import Path

from codekey.config import ModelConfig
from codekey.exceptions import ModelError


class LocalModelClient:
    def __init__(self, config: ModelConfig):
        self.config = config

    def _command_prefix(self) -> list[str]:
        candidate = Path(self.config.binary).expanduser()
        if candidate.is_file():
            return [str(candidate.resolve())]
        installed = shutil.which(self.config.binary)
        if installed:
            return [installed]
        if self.config.binary == "llama-cli" and sys.platform == "darwin":
            project_dir = Path(__file__).resolve().parent.parent
            bundled = sorted((project_dir / "vendor").glob("llama-*/llama-cli"), reverse=True)
            if bundled:
                return [str(bundled[0])]
        if self.config.binary == "llama-cli" and sys.platform == "win32":
            links = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "llama-cli.exe",
                Path(os.environ.get("ProgramFiles", "")) / "WinGet" / "Links" / "llama-cli.exe",
            ]
            for link in links:
                if link.is_file():
                    return [str(link)]
        fallback = shutil.which("llama") if self.config.binary == "llama-cli" else None
        if fallback:
            return [fallback, "cli"]
        raise ModelError(
            "llama.cpp command not found. Install llama.cpp or set model.binary in config.yaml."
        )

    def ensure_ready(self) -> None:
        self._command_prefix()
        if not self.config.path.is_file():
            raise ModelError(f"Local GGUF model not found: {self.config.path}")

    def generate(self, system_prompt: str, prompt: str, temperature: float) -> str:
        self.ensure_ready()
        command = self._command_prefix() + [
            "--model", str(self.config.path),
            "--system-prompt", system_prompt,
            "--prompt", prompt,
            "--predict", str(self.config.max_tokens),
            "--temp", str(temperature),
            "--single-turn", "--simple-io",
            "--no-display-prompt", "--no-show-timings", "--color", "off",
        ]
        try:
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout,
                check=False,
                **options,
            )
        except subprocess.TimeoutExpired as error:
            raise ModelError("The local model timed out. Try a smaller GGUF model.") from error
        except OSError as error:
            raise ModelError("Could not start the local llama.cpp command.") from error
        if result.returncode != 0:
            raise ModelError("The local model failed. Check the GGUF file and llama.cpp installation.")
        answer = result.stdout
        # Recent llama.cpp CLI builds echo the prompt and a startup banner to stdout.
        if prompt in answer:
            answer = answer.rsplit(prompt, 1)[1]
        answer = answer.strip()
        if answer.endswith("Exiting..."):
            answer = answer.removesuffix("Exiting...").strip()
        if not answer:
            raise ModelError("The local model returned an empty answer.")
        return answer
