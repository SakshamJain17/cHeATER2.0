import logging
from pathlib import Path


LOG_PATH = Path(__file__).resolve().parent.parent / "codekey.log"


def configure_logging(debug: bool = False) -> logging.Logger:
    logger = logging.getLogger("codekey")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        try:
            handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        except OSError:
            handler = logging.NullHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
    return logger
