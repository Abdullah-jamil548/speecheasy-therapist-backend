import logging
import sys

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    _configured = True


def get_logger(name: str = "speakeasy") -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
