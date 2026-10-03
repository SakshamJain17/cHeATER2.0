import argparse
import hashlib
import logging
import sys
import threading
from pathlib import Path

from codekey.clipboard import Clipboard
from codekey.config import Config, load_config
from codekey.exceptions import ClipboardError, CodeKeyError
from codekey.hotkeys import HotkeyRunner
from codekey.inserter import type_into_focused_application
from codekey.classifier import TaskType, classify_question, parse_choice_options
from codekey.logger import configure_logging
from codekey.mcq_cursor import (
    is_true_false_choice_pair,
    move_to_mcq_answer,
    move_to_true_false_answer,
)
from codekey.local_model import LocalModelClient
from codekey.solver import Solver
from codekey.screen import read_clipboard_image_text, read_screen_text


class CodeKeyApp:
    def __init__(self, config: Config, logger: logging.Logger, cancel_event: threading.Event | None = None):
        self.config = config
        self.logger = logger
        self.clipboard = Clipboard(config.limits.max_input_chars)
        self.solver = Solver(
            LocalModelClient(config.model),
            config.generation,
            config.limits.max_output_chars,
        )
        self._last_output_digest: str | None = None
        self._digest_lock = threading.Lock()
        self.cancel_event = cancel_event or threading.Event()
        self._state_lock = threading.Lock()
        self._generating = False
        self._typing = False
        self._start_when_ready = False
        self._pending_result = None

    def solve_clipboard(self) -> None:
        self._solve(self._read_clipboard_question)

    def _read_clipboard_question(self) -> str:
        # Image clips can also advertise a URL or alt text; OCR the actual image first.
        image_error = None
        try:
            image_text = read_clipboard_image_text(self.config.limits.max_input_chars)
        except CodeKeyError as error:
            image_text = None
            image_error = error
        if image_text:
            return image_text
        try:
            text = self.clipboard.read_text()
        except ClipboardError:
            text = ""
        if text.strip():
            return text
        if image_error is not None:
            raise image_error
        raise CodeKeyError("Clipboard has no readable text or image. Copy a question first.")

    def solve_screen(self) -> None:
        self._solve(lambda: read_screen_text(self.config.limits.max_input_chars))

    def _solve(self, read_question) -> None:
        with self._state_lock:
            if self._generating or self._typing:
                self.logger.info("An answer is already in progress; ignoring solve hotkey.")
                return
            self._generating = True
            self._start_when_ready = False
            self._pending_result = None
            self.cancel_event.clear()
        try:
            question = read_question()
            if not question.strip():
                raise CodeKeyError("No readable question was found.")
            digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
            with self._digest_lock:
                if digest == self._last_output_digest:
                    raise CodeKeyError("Input contains CodeKey's previous answer, not a question.")

            classification = classify_question(question)
            self.logger.info(
                "Processing %s question; %d labeled options detected.",
                classification.task_type.value,
                len(parse_choice_options(question)),
            )
            result = self.solver.solve(question)
            with self._state_lock:
                self._generating = False
                if self.cancel_event.is_set():
                    self.logger.info("Answer canceled before typing started.")
                    return
                if self._start_when_ready or result.classification.task_type in {
                    TaskType.MCQ, TaskType.TRUE_FALSE,
                }:
                    self._typing = True
                    start_typing = True
                else:
                    self._pending_result = result
                    start_typing = False
            if start_typing:
                self._launch_delivery(result)
            else:
                self.logger.info("Answer ready. Press %s to type it.", self.config.hotkey.type_answer)
        except CodeKeyError as error:
            self.logger.error("%s", error)
        except Exception:
            if self.config.app.debug:
                self.logger.exception("Unexpected failure while processing the clipboard.")
            else:
                self.logger.error("Unexpected failure. Enable app.debug for diagnostic details.")
        finally:
            with self._state_lock:
                self._generating = False

    def request_typing(self) -> None:
        with self._state_lock:
            if self._typing:
                self.logger.info("Already typing the answer.")
                return
            if self._generating:
                self._start_when_ready = True
                self.logger.info("Typing requested; waiting for the answer to finish generating.")
                return
            result = self._pending_result
            if result is None:
                self.logger.info("No answer is ready. Press %s first.", self.config.hotkey.solve)
                return
            self._pending_result = None
            self._typing = True
        self._launch_delivery(result)

    def cancel_current(self) -> None:
        self.cancel_event.set()
        with self._state_lock:
            self._pending_result = None
            self._start_when_ready = False
        self.logger.info("Current answer canceled; CodeKey remains ready.")

    def _launch_delivery(self, result) -> None:
        threading.Thread(
            target=self._deliver_result,
            args=(result,),
            daemon=True,
            name="codekey-type",
        ).start()

    def _deliver_result(self, result) -> None:
        try:
            if self.cancel_event.is_set():
                self.logger.info("Answer canceled before typing started.")
                return
            if result.classification.task_type is TaskType.MCQ:
                self.clipboard.write_text(result.code)
                with self._digest_lock:
                    self._last_output_digest = hashlib.sha256(result.code.encode("utf-8")).hexdigest()
                if is_true_false_choice_pair(getattr(result, "choice_options", None)):
                    target = move_to_mcq_answer(result.code, horizontal=True)
                else:
                    target = move_to_mcq_answer(result.code)
                self.logger.info("Moved the mouse to MCQ option %s at %s.", result.code, target)
            elif result.classification.task_type is TaskType.TRUE_FALSE:
                self.clipboard.write_text(result.code)
                with self._digest_lock:
                    self._last_output_digest = hashlib.sha256(result.code.encode("utf-8")).hexdigest()
                target = move_to_true_false_answer(result.code)
                self.logger.info("Moved the mouse to %s at %s.", result.code, target)
            else:
                self.logger.info("Typing the %s answer into the focused application.", result.classification.task_type.value)
                completed = type_into_focused_application(
                    result.code,
                    self.config.app.typing_interval_seconds,
                    self.cancel_event,
                    preserve_indentation=result.classification.task_type in {
                        TaskType.CODING_PROBLEM, TaskType.DEBUG, TaskType.OPTIMIZE_CODE,
                    },
                )
                self.logger.info("Finished typing the answer." if completed else "Typing canceled.")
        except CodeKeyError as error:
            self.logger.error("%s", error)
        except Exception:
            if self.config.app.debug:
                self.logger.exception("Unexpected failure while processing the clipboard.")
            else:
                self.logger.error("Unexpected failure while typing. Enable app.debug for diagnostic details.")
        finally:
            with self._state_lock:
                self._typing = False


def _check_model(config: Config, logger: logging.Logger) -> None:
    LocalModelClient(config.model).ensure_ready()
    logger.info("Local model and llama.cpp are ready.")


def _project_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local-first terminal coding assistant")
    parser.add_argument("--config", default=str(_project_dir() / "config.yaml"), help="Path to config.yaml")
    parser.add_argument("--check", action="store_true", help="Check local runner and GGUF model, then exit")
    parser.add_argument("--screen-ocr", action="store_true", help="Print OCR text and candidates from the main screen for troubleshooting")
    args = parser.parse_args(argv)

    logger = configure_logging()
    try:
        config = load_config(args.config)
        logger = configure_logging(config.app.debug)
        if sys.platform not in {"darwin", "win32"}:
            raise CodeKeyError("CodeKey currently supports macOS and Windows.")
        if args.check:
            _check_model(config, logger)
            return 0
        if args.screen_ocr:
            print(read_screen_text(config.limits.max_input_chars, diagnostics=True))
            return 0
        _check_model(config, logger)
        cancel_event = threading.Event()
        app = CodeKeyApp(config, logger, cancel_event)
        runner = HotkeyRunner(
            config.hotkey.solve,
            config.hotkey.screen,
            config.hotkey.type_answer,
            config.hotkey.cancel,
            config.hotkey.stop,
            config.app.cooldown_seconds,
            app.solve_clipboard,
            app.solve_screen,
            app.request_typing,
            app.cancel_current,
            logger,
        )
        runner.run()
    except CodeKeyError as error:
        logging.getLogger("codekey").error("%s", error)
        return 1
    except KeyboardInterrupt:
        logging.getLogger("codekey").info("CodeKey stopped.")
        return 0
    except Exception as error:
        logger = logging.getLogger("codekey")
        if "config" in locals() and config.app.debug:
            logger.exception("CodeKey could not start.")
        else:
            logger.error("CodeKey could not start: %s", error)
        return 1
    return 0
