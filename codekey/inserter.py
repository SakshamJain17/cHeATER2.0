import sys
import threading
import time

from codekey.exceptions import CodeKeyError


def _replace_auto_indent(keyboard, key) -> None:
    """Select indentation inserted by the target editor after Enter."""
    if sys.platform == "darwin":
        keyboard.press(key.cmd)
        keyboard.press(key.shift)
        keyboard.press(key.left)
        keyboard.release(key.left)
        keyboard.release(key.shift)
        keyboard.release(key.cmd)
    else:
        keyboard.press(key.shift)
        keyboard.press(key.home)
        keyboard.release(key.home)
        keyboard.release(key.shift)


def type_into_focused_application(
    text: str,
    interval_seconds: float = 0.02,
    cancel_event: threading.Event | None = None,
    preserve_indentation: bool = False,
) -> bool:
    """Type gradually without changing the clipboard."""
    if sys.platform not in {"darwin", "win32"}:
        raise CodeKeyError("Typing answers is supported on macOS and Windows.")
    try:
        from pynput.keyboard import Controller, Key

        keyboard = Controller()
        lines = text.expandtabs(4).split("\n")
        for index, line in enumerate(lines):
            if cancel_event is not None and cancel_event.is_set():
                return False
            if index:
                keyboard.press(Key.enter)
                keyboard.release(Key.enter)
                time.sleep(interval_seconds)
                if preserve_indentation:
                    _replace_auto_indent(keyboard, Key)
                    if not line:
                        # Replace selected whitespace without deleting the newline
                        # when an editor did not insert any indentation.
                        keyboard.type(" ")
                        keyboard.press(Key.backspace)
                        keyboard.release(Key.backspace)
            for char in line:
                if cancel_event is not None and cancel_event.is_set():
                    return False
                keyboard.type(char)
                time.sleep(interval_seconds)
        return True
    except Exception as error:
        raise CodeKeyError(
            "Could not type the answer. Check Accessibility permission and keep the target app focused."
        ) from error
