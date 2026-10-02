import subprocess
import sys

from codekey.exceptions import ClipboardError


class Clipboard:
    def __init__(self, max_input_chars: int):
        self.max_input_chars = max_input_chars

    def read_text(self) -> str:
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["pbpaste"], capture_output=True, timeout=5, check=True
                )
                text = result.stdout.decode("utf-8", errors="strict")
            else:
                import pyperclip

                text = pyperclip.paste()
        except Exception as error:
            raise ClipboardError("Could not read text from the clipboard.") from error
        if not isinstance(text, str):
            raise ClipboardError("Clipboard content is not text.")
        if len(text) > self.max_input_chars:
            raise ClipboardError(
                f"Clipboard content exceeds the {self.max_input_chars}-character limit."
            )
        return text

    def write_text(self, text: str) -> None:
        try:
            if sys.platform == "darwin":
                subprocess.run(
                    ["pbcopy"], input=text.encode("utf-8"),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5, check=True,
                )
            else:
                import pyperclip

                pyperclip.copy(text)
        except Exception as error:
            raise ClipboardError("Could not copy the answer to the clipboard.") from error
