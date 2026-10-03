import logging
from types import ModuleType

from codekey import logger as codekey_logger
from codekey import app as codekey_app
from codekey.app import main


def test_startup_error_is_logged_without_console_output(tmp_path, monkeypatch, capsys):
    log = logging.getLogger("codekey")
    original_handlers = log.handlers[:]
    for handler in original_handlers:
        log.removeHandler(handler)
    monkeypatch.setattr(codekey_logger, "LOG_PATH", tmp_path / "codekey.log")
    try:
        assert main(["--config", str(tmp_path / "missing.yaml")]) == 1
        assert capsys.readouterr() == ("", "")
        assert "Cannot read configuration file" in (tmp_path / "codekey.log").read_text()
    finally:
        for handler in log.handlers[:]:
            log.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            log.addHandler(handler)


def test_macos_python_helper_uses_background_activation_policy(monkeypatch):
    policies = []

    class Application:
        @classmethod
        def sharedApplication(cls):
            return cls()

        def setActivationPolicy_(self, policy):
            policies.append(policy)

    appkit = ModuleType("AppKit")
    appkit.NSApplication = Application
    appkit.NSApplicationActivationPolicyProhibited = 2
    monkeypatch.setitem(__import__("sys").modules, "AppKit", appkit)
    monkeypatch.setattr(codekey_app.sys, "platform", "darwin")

    codekey_app._hide_macos_process_from_dock()

    assert policies == [2]
