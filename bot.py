"""Compatibility shim loading the maintained bot implementation.

The Railway service runs from the repository root, so this module deliberately
loads resala_bot/bot.py instead of duplicating the bot implementation here.
"""

import importlib.util
from pathlib import Path

_impl_path = Path(__file__).resolve().parent / "resala_bot" / "bot.py"
_spec = importlib.util.spec_from_file_location("_resala_bot_impl", _impl_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load bot implementation from {_impl_path}")
_impl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)

# Re-export the bot API expected by railway.py and existing callers.
for _name in dir(_impl):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_impl, _name)


def main():
    # railway.py can inject the Railway token/admin ID and patched handlers on
    # this shim; copy those values into the implementation before startup.
    _impl.TOKEN = TOKEN
    _impl.ADMIN_ID = ADMIN_ID
    _impl.handle_user_messages = handle_user_messages
    _impl.send_scheduled_sunnahs = send_scheduled_sunnahs
    _impl.main()


if __name__ == "__main__":
    main()
