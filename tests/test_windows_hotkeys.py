import logging

from codekey import hotkeys


def test_windows_registers_text_hotkeys_without_screen_ocr(monkeypatch):
    registered = {}

    class Listener:
        def __init__(self, mapping, **options):
            registered.update(mapping)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def join(self):
            registered["<ctrl>+<shift>+q"]()

        def stop(self):
            pass

    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    monkeypatch.setattr("pynput.keyboard.GlobalHotKeys", Listener)
    runner = hotkeys.HotkeyRunner(
        "<alt>+/", "<ctrl>+<shift>+i", "<ctrl>+<shift>+t",
        "<ctrl>+<shift>+x", "<ctrl>+<shift>+q", 1.5,
        lambda: None, lambda: None, lambda: None, lambda: None,
        logging.getLogger("test-hotkeys"),
    )
    runner.run()
    assert "<alt>+/" in registered
    assert "<ctrl>+<shift>+t" in registered
    assert "<ctrl>+<shift>+i" not in registered
