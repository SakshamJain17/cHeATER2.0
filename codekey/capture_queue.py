"""Session-only local storage for multi-screen OCR workflows."""

import shutil
import tempfile
import threading
from pathlib import Path

from codekey.exceptions import CodeKeyError
from codekey.screen import capture_screen_image, recognize_image_text


class ScreenCaptureQueue:
    def __init__(self, max_captures: int):
        if max_captures < 1:
            raise ValueError("max_captures must be positive")
        self.max_captures = max_captures
        self._directory = Path(tempfile.mkdtemp(prefix="codekey-captures-"))
        self._paths: list[Path] = []
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._paths)

    def capture(self) -> tuple[Path, int]:
        with self._lock:
            if len(self._paths) >= self.max_captures:
                raise CodeKeyError(
                    f"The screen queue already contains {self.max_captures} captures. "
                    "Process or clear it before capturing another."
                )
            destination = self._directory / f"capture-{len(self._paths) + 1}.png"
            captured = capture_screen_image(destination)
            self._paths.append(captured)
            return captured, len(self._paths)

    def read_combined_text(self, max_chars: int) -> str:
        with self._lock:
            paths = tuple(self._paths)
        if not paths:
            raise CodeKeyError("The screen capture queue is empty.")
        sections = []
        seen = set()
        for index, path in enumerate(paths, start=1):
            text = recognize_image_text(path, max_chars)
            if text in seen:
                continue
            seen.add(text)
            sections.append(f"[Screen capture {index}]\n{text}")
        combined = "\n\n".join(sections)
        if not combined:
            raise CodeKeyError("No readable text was found in the queued captures.")
        if len(combined) > max_chars:
            raise CodeKeyError(
                f"Queued screen text exceeds the {max_chars}-character input limit. "
                "Clear the queue and capture fewer screens."
            )
        return combined

    def clear(self) -> int:
        with self._lock:
            paths = self._paths
            self._paths = []
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return len(paths)

    def close(self) -> None:
        self.clear()
        shutil.rmtree(self._directory, ignore_errors=True)
