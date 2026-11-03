"""Compatibility shim loading the maintained bot implementation.

Railway's repository-root Procfile runs railway.py, which imports this module.
The implementation and durable JSON storage live under resala_bot/.
"""

import importlib.util
from pathlib import Path

from resala_bot.persistent_storage import install as _install_persistent_storage

_IMPL_PATH = Path(__file__).resolve().parent / "resala_bot" / "bot.py"
_SPEC = importlib.util.spec_from_file_location("_resala_bot_impl", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load bot implementation from {_IMPL_PATH}")
_IMPL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_IMPL)
_install_persistent_storage(_IMPL)

for _name in dir(_IMPL):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_IMPL, _name)


def main():
    """Forward patched config/handlers from the shim into the implementation."""
    _IMPL.TOKEN = TOKEN
    _IMPL.ADMIN_ID = ADMIN_ID
    _IMPL.handle_user_messages = handle_user_messages
    _IMPL.send_scheduled_sunnahs = send_scheduled_sunnahs
    _IMPL.main()


if __name__ == "__main__":
    main()
