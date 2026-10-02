import pytest

from codekey import screen
from codekey.exceptions import CodeKeyError


def test_screen_capture_reports_missing_permission(monkeypatch):
    import Quartz
    requested = []
    monkeypatch.setattr(Quartz, "CGPreflightScreenCaptureAccess", lambda: False)
    monkeypatch.setattr(Quartz, "CGRequestScreenCaptureAccess", lambda: requested.append(True) or False)
    with pytest.raises(CodeKeyError, match="Screen Recording permission"):
        screen.read_screen_text(1000)
    assert requested == [True]


def test_copied_png_is_sent_to_ocr(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace

    appkit = ModuleType("AppKit")
    appkit.NSPasteboard = SimpleNamespace(generalPasteboard=lambda: SimpleNamespace(
        dataForType_=lambda kind: b"png data" if kind == "public.png" else None
    ))
    monkeypatch.setitem(sys.modules, "AppKit", appkit)
    monkeypatch.setattr(screen.sys, "platform", "darwin")
    seen = []
    monkeypatch.setattr(screen, "_recognize_image", lambda path, limit: seen.append((path.read_bytes(), limit)) or "B. def")
    assert screen.read_clipboard_image_text(500) == "B. def"
    assert seen == [(b"png data", 500)]


def test_ocr_layout_keeps_question_and_shuffled_choices():
    from types import SimpleNamespace
    from codekey.classifier import TaskType, classify_question, parse_choice_options

    def observation(value, x, y, width):
        box = SimpleNamespace(origin=SimpleNamespace(x=x, y=y),
                              size=SimpleNamespace(width=width, height=0.04))
        return SimpleNamespace(
            topCandidates_=lambda count: [SimpleNamespace(string=lambda: value)],
            boundingBox=lambda: box,
        )

    observations = [
        observation("B. London", 0.62, 0.50, 0.25),
        observation("A. Berlin", 0.62, 0.30, 0.25),
        observation("What is the capital of France?", 0.10, 0.90, 0.70),
        observation("C.", 0.10, 0.50, 0.04),
        observation("Paris", 0.15, 0.50, 0.20),
        observation("D. Rome", 0.10, 0.30, 0.25),
    ]
    text = screen._observations_to_text(observations)
    assert classify_question(text).task_type is TaskType.MCQ
    assert parse_choice_options(text) == {
        "C": "Paris", "B": "London", "D": "Rome", "A": "Berlin"
    }


def test_ocr_circled_letter_layout_from_python_output_question():
    from types import SimpleNamespace
    from codekey.classifier import TaskType, classify_question, parse_choice_options

    def fragment(value, x, y, width):
        box = SimpleNamespace(origin=SimpleNamespace(x=x, y=y),
                              size=SimpleNamespace(width=width, height=0.035))
        return SimpleNamespace(
            topCandidates_=lambda count: [SimpleNamespace(string=lambda: value)],
            boundingBox=lambda: box,
        )

    observations = [
        fragment("What is the output of the following Python code?", .14, .89, .7),
        fragment("1", .06, .76, .02), fragment("x = [1, 2, 3]", .13, .76, .4),
        fragment("2", .06, .70, .02), fragment("y = x", .13, .70, .2),
        fragment("3", .06, .64, .02), fragment("y.append(4)", .13, .64, .3),
        fragment("4", .06, .58, .02), fragment("x.append(5)", .13, .58, .3),
        fragment("5", .06, .52, .02), fragment("print(y)", .13, .52, .2),
        fragment("A", .06, .29, .03), fragment("[1, 2, 3, 4]", .15, .29, .28),
        fragment("B", .55, .29, .03), fragment("[1, 2, 3, 4, 5]", .64, .29, .31),
        fragment("C", .06, .12, .03), fragment("[1, 2, 3, 5]", .15, .12, .28),
        fragment("D", .55, .12, .03), fragment("Error", .64, .12, .2),
    ]
    text = screen._observations_to_text(observations)
    assert classify_question(text).task_type is TaskType.MCQ
    assert parse_choice_options(text)["B"] == "[1, 2, 3, 4, 5]"


def test_spatial_recovery_pairs_circled_labels_with_offset_answers():
    from types import SimpleNamespace

    def fragment(value, x, y, width):
        box = SimpleNamespace(origin=SimpleNamespace(x=x, y=y),
                              size=SimpleNamespace(width=width, height=0.03))
        return SimpleNamespace(
            topCandidates_=lambda count: [SimpleNamespace(string=lambda: value)],
            boundingBox=lambda: box,
        )

    observations = [
        fragment("Ⓐ", .05, .30, .03), fragment("[1, 2, 3, 4]", .15, .325, .28),
        fragment("Ⓑ", .55, .30, .03), fragment("[1, 2, 3, 4, 5]", .64, .325, .30),
        fragment("Ⓒ", .05, .12, .03), fragment("[1, 2, 3, 5]", .15, .145, .28),
        fragment("Ⓓ", .55, .12, .03), fragment("Error", .64, .145, .20),
    ]
    assert screen._recover_spatial_choices(observations) == {
        "A": "[1, 2, 3, 4]", "B": "[1, 2, 3, 4, 5]",
        "C": "[1, 2, 3, 5]", "D": "Error",
    }
