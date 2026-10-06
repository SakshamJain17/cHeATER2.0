from pathlib import Path

import pytest

from codekey import capture_queue
from codekey.capture_queue import ScreenCaptureQueue
from codekey.exceptions import CodeKeyError


def test_queue_captures_and_combines_unique_ocr(monkeypatch):
    queue = ScreenCaptureQueue(3)

    def capture(destination):
        destination = Path(destination)
        destination.write_bytes(b"png")
        return destination

    texts = iter(("first page", "second page", "second page"))
    monkeypatch.setattr(capture_queue, "capture_screen_image", capture)
    monkeypatch.setattr(capture_queue, "recognize_image_text", lambda path, limit: next(texts))
    try:
        assert queue.capture()[1] == 1
        assert queue.capture()[1] == 2
        assert queue.capture()[1] == 3
        assert queue.read_combined_text(1000) == (
            "[Screen capture 1]\nfirst page\n\n"
            "[Screen capture 2]\nsecond page"
        )
        assert queue.clear() == 3
        assert queue.count == 0
    finally:
        queue.close()


def test_queue_enforces_capture_limit(monkeypatch):
    queue = ScreenCaptureQueue(1)
    monkeypatch.setattr(
        capture_queue,
        "capture_screen_image",
        lambda destination: Path(destination),
    )
    try:
        queue.capture()
        with pytest.raises(CodeKeyError, match="already contains 1"):
            queue.capture()
    finally:
        queue.close()


def test_empty_queue_is_not_processed():
    queue = ScreenCaptureQueue(2)
    try:
        with pytest.raises(CodeKeyError, match="queue is empty"):
            queue.read_combined_text(100)
    finally:
        queue.close()
