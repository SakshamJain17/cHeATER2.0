import logging
import sys
import threading
import time
from collections.abc import Callable

from codekey.exceptions import CodeKeyError


class HotkeyRunner:
    def __init__(
        self,
        solve_hotkey: str,
        screen_hotkey: str,
        type_hotkey: str,
        cancel_hotkey: str,
        stop_hotkey: str,
        cooldown_seconds: float,
        solve_callback: Callable[[], None],
        screen_callback: Callable[[], None],
        type_callback: Callable[[], None],
        cancel_callback: Callable[[], None],
        logger: logging.Logger,
    ):
        self.solve_hotkey = solve_hotkey
        self.screen_hotkey = screen_hotkey
        self.type_hotkey = type_hotkey
        self.cancel_hotkey = cancel_hotkey
        self.stop_hotkey = stop_hotkey
        self.cooldown_seconds = cooldown_seconds
        self.solve_callback = solve_callback
        self.screen_callback = screen_callback
        self.type_callback = type_callback
        self.cancel_callback = cancel_callback
        self.logger = logger
        self._worker_lock = threading.Lock()
        self._last_trigger = float("-inf")
        self._trigger_lock = threading.Lock()
        self._stop_requested = threading.Event()

    def trigger(self, callback=None) -> None:
        with self._trigger_lock:
            now = time.monotonic()
            if self._worker_lock.locked():
                self.logger.info("A request is already in progress; ignoring hotkey.")
                return
            if now - self._last_trigger < self.cooldown_seconds:
                self.logger.info("Hotkey cooldown active; ignoring repeated trigger.")
                return
            self._last_trigger = now
            self._worker_lock.acquire()
        threading.Thread(target=self._run, args=(callback or self.solve_callback,), daemon=True, name="codekey-solve").start()

    def _run(self, callback) -> None:
        try:
            callback()
        finally:
            self._worker_lock.release()

    def run(self) -> None:
        if sys.platform == "darwin":
            from ApplicationServices import AXIsProcessTrusted
            if not AXIsProcessTrusted():
                raise CodeKeyError(
                    "macOS Accessibility permission is needed for the global hotkey. "
                    "Enable Terminal (or Python) in System Settings > Privacy & Security "
                    "> Accessibility, then launch CodeKey again."
                )
        try:
            from pynput.keyboard import GlobalHotKeys, KeyCode
        except ImportError as error:
            raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from error

        self.logger.info(
            "READY. Clipboard: %s; screen: %s; type: %s; cancel: %s; stop: %s.",
            self.solve_hotkey, self.screen_hotkey, self.type_hotkey, self.cancel_hotkey, self.stop_hotkey,
        )
        self.logger.info("macOS may require Input Monitoring permission for the global hotkey.")
        if sys.platform == "darwin" and self.solve_hotkey == "<alt>+/":
            from Quartz import (
                CGEventGetFlags,
                CGEventGetIntegerValueField,
                kCGEventFlagMaskAlternate,
                kCGEventFlagMaskControl,
                kCGEventFlagMaskShift,
                kCGEventKeyDown,
                kCGEventKeyUp,
                kCGKeyboardEventKeycode,
            )

            class MacSlashHotKeys(GlobalHotKeys):
                def canonical(self, key):
                    # Option changes the character produced by the physical slash key.
                    # Match its macOS virtual key code so the shortcut works in Notes.
                    if isinstance(key, KeyCode) and key.vk == 44:
                        return KeyCode.from_char("/")
                    return super().canonical(key)

            listener_type = MacSlashHotKeys
            def intercept(event_type, event):
                if event_type in (kCGEventKeyDown, kCGEventKeyUp):
                    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                    flags = CGEventGetFlags(event)
                    if keycode == 44 and flags & kCGEventFlagMaskAlternate:
                        return None
                    if (
                        self.screen_hotkey == "<ctrl>+<shift>+s"
                        and keycode == 1
                        and flags & kCGEventFlagMaskControl
                        and flags & kCGEventFlagMaskShift
                    ):
                        return None
                return event

            listener_options = {"darwin_intercept": intercept}
        else:
            listener_type = GlobalHotKeys
            listener_options = {}

        def cancel() -> None:
            self.cancel_callback()

        def stop() -> None:
            self.cancel_callback()
            self._stop_requested.set()
            self.logger.info("Stop hotkey pressed. CodeKey is shutting down.")
            listener.stop()

        hotkeys = {
            self.solve_hotkey: self.trigger,
            self.screen_hotkey: lambda: self.trigger(self.screen_callback),
            self.type_hotkey: self.type_callback,
            self.cancel_hotkey: cancel,
            self.stop_hotkey: stop,
        }
        with listener_type(hotkeys, **listener_options) as listener:
            listener.join()
        if not self._stop_requested.is_set():
            raise CodeKeyError("The global hotkey listener stopped unexpectedly.")
