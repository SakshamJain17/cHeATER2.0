import threading

from codekey import inserter


def test_cancel_stops_typing_but_does_not_touch_clipboard(monkeypatch):
    cancel = threading.Event()
    typed = []

    class Keyboard:
        def type(self, char):
            typed.append(char)
            cancel.set()

    monkeypatch.setattr("pynput.keyboard.Controller", Keyboard)
    monkeypatch.setattr(inserter.time, "sleep", lambda seconds: None)

    assert inserter.type_into_focused_application("long answer", 0, cancel) is False
    assert typed == ["l"]


def test_code_typing_replaces_editor_auto_indent(monkeypatch):
    import sys
    from types import SimpleNamespace
    from pynput.keyboard import Key

    events = []
    class Keyboard:
        def press(self, key):
            events.append(("press", key))
        def release(self, key):
            events.append(("release", key))
        def type(self, char):
            events.append(("type", char))

    monkeypatch.setattr(inserter.sys, "platform", "darwin")
    monkeypatch.setattr("pynput.keyboard.Controller", Keyboard)
    monkeypatch.setattr(inserter.time, "sleep", lambda seconds: None)
    assert inserter.type_into_focused_application("if True:\n    print(1)", 0, preserve_indentation=True)
    newline = events.index(("press", Key.enter))
    assert events[newline + 1] == ("release", Key.enter)
    assert events[newline + 2:newline + 8] == [
        ("press", Key.cmd), ("press", Key.shift), ("press", Key.left),
        ("release", Key.left), ("release", Key.shift), ("release", Key.cmd),
    ]
    assert events[newline + 8:newline + 12] == [("type", " ")] * 4
