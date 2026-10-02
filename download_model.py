"""One-time download of the free local GGUF model."""

import hashlib
import sys
from pathlib import Path
from urllib.request import Request, urlopen


MODEL_NAME = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/"
    "2ab9f8f42af02fc212effaef7c4850c885e965f4/" + MODEL_NAME
)
MODEL_SHA256 = "cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    target = Path(__file__).resolve().parent / "models" / MODEL_NAME
    target.parent.mkdir(exist_ok=True)
    if target.is_file() and sha256(target) == MODEL_SHA256:
        print("Local model is already installed and verified.")
        return 0
    if target.exists():
        print(f"Existing model has the wrong checksum: {target}", file=sys.stderr)
        return 1

    temporary = target.with_suffix(".part")
    print("Downloading the 1.12 GB model. This is required only once per computer.")
    try:
        request = Request(MODEL_URL, headers={"User-Agent": "CodeKey/0.2"})
        with urlopen(request, timeout=30) as response, temporary.open("wb") as destination:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                destination.write(block)
        if sha256(temporary) != MODEL_SHA256:
            raise ValueError("Downloaded model checksum did not match the official file.")
        temporary.replace(target)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        print(f"Model download failed: {error}", file=sys.stderr)
        return 1
    print(f"Model installed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
