"""Compatibility shim loading the maintained bot implementation."""

import importlib.util
from pathlib import Path

from resala_bot.persistent_storage import install as install_persistent_storage

_impl_path = Path(__file__).resolve().parent / "resala_bot" / "bot.py"
_spec = importlib.util.spec_from_file_location("_resala_bot_impl", _impl_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load bot implementation from {_impl_path}")
_impl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)
install_persistent_storage(_impl)

# Re-export the bot API expected by railway.py and existing callers.
for _name in dir(_impl):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_impl, _name)


def main():
    # railway.py may inject token/admin settings and patched handlers here.
    _impl.TOKEN = TOKEN
    _impl.ADMIN_ID = ADMIN_ID
    _impl.handle_user_messages = handle_user_messages
    _impl.send_scheduled_sunnahs = send_scheduled_sunnahs
    _impl.main()


if __name__ == "__main__":
    main()
