import logging
from typing import Any

LOGGER = logging.getLogger("basler_vision")


def is_debug_enabled(config: Any) -> bool:
    if isinstance(config, dict):
        return bool(config.get("debug", config.get("verbose", False)))

    if isinstance(config, (list, tuple)):
        return any(is_debug_enabled(item) for item in config)

    return bool(config)


def _emit_via_callback(message: str, config: Any) -> bool:
    if not isinstance(config, dict):
        return False

    callback = config.get("status_callback") or config.get("log_callback")
    if not callable(callback):
        return False

    try:
        callback(message)
    except Exception:
        LOGGER.debug("Status callback failed.", exc_info=True)
    return True


def log_step(source: str, message: str, config: Any = None, always: bool = False) -> None:
    debug_enabled = is_debug_enabled(config)
    if debug_enabled:
        rendered = f"[{source}] {message}"
        level = logging.DEBUG
    elif always:
        rendered = f"[status] - {message}"
        level = logging.INFO
    else:
        return

    if _emit_via_callback(rendered, config):
        return

    LOGGER.log(level, rendered)
