from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .utils import runtime_root, ensure_dir

def configure_logging() -> Path:
    log_dir = ensure_dir(runtime_root() / "logs")
    log_file = log_dir / "app.log"
    handler = RotatingFileHandler(
        log_file,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(threadName)s %(message)s"
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    return log_file

def install_excepthook() -> None:
    def _hook(exc_type, exc, tb): # type: ignore[no-untyped-def]
        logging.getLogger("daniya").exception("uncaught_exception", exc_info=(exc_type, exc, tb))
    sys.excepthook = _hook
