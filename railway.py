"""Railway entry point with robust Telegram channel/group linking."""

import re
from urllib.parse import urlparse

import bot


def _next_source_id(sources):
    index = 1
    while f"src_{index}" in sources:
        index += 1
    return f"src_{index}"


def _public_username(text):
    """Return a public Telegram username from @name or a t.me/name URL."""
    value = (text or "").strip().rstrip(".,!?;:)>]")
    if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", value):
        return value[1:]

    # Accept a bare public URL or a URL embedded in a short message.
    match = re.search(r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([^\s/?#]+)", value, re.I)
    if not match:
        return None
    username = match.group(1).strip(".,!?;:)>]")
    # Invite links and private channel paths do not expose a public username.
    if username.startswith("+") or username.lower() == "joinchat" or username.lower() == "c":
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        return None
    return username


async def handle_user_messages(update, context):
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    # Support both current Bot API forward_origin and the legacy field.
    origin = getattr(message, "forward_origin", None)
    source_chat = getattr(origin, "chat", None)
    if source_chat is None:
        source_chat = getattr(message, "forward_from_chat", None)

    if source_chat is not None:
        chat_type = getattr(source_chat, "type", None)
        if chat_type in ("channel", "group", "supergroup"):
            data = bot.load_data()
            users = data.setdefault("users", {})
            user_id = str(user.id)
            user_data = users.setdefault(
                user_id,
                {
                    "name": user.first_name,
                    "interval": 10,
                    "sources": {},
                },
            )
            sources = user_data.setdefault("sources", {})
            title = (
                getattr(source_chat, "title", None)
                or getattr(source_chat, "username", None)
                or str(source_chat.id)
            )
            source_kind = "channel" if chat_type == "channel" else "group"
            source_chat_id = str(source_chat.id)

            # Avoid creating duplicate entries when the same source is forwarded again.
            existing = next(
                (
                    item
                    for item in sources.values()
                    if str(item.get("name")) == source_chat_id
                    and item.get("type") == source_kind
                ),
                None,
            )
            if existing is None:
                sources[_next_source_id(sources)] = {
                    "name": source_chat_id,
                    "title": title,
                    "type": source_kind,
                    "status": "active",
                }
                bot.save_data(data)

            await message.reply_text(
                f"✅ تم ربط الـ {source_kind} بنجاح!\n"
                f"الاسم: {title}\n"
                f"الايدي: {source_chat_id}\n"
                "تأكد أن البوت لديه صلاحية النشر فيها."
            )
            return

    # Direct public usernames/links are accepted only after the user chose
    # channel/group linking. Private invite links cannot be resolved by username.
    waiting_type = context.user_data.get("waiting_source_type")
    text = message.text or ""
    username = _public_username(text) if waiting_type else None
    if username:
        data = bot.load_data()
        users = data.setdefault("users", {})
        user_id = str(user.id)
        user_data = users.setdefault(
            user_id,
            {
                "name": user.first_name,
                "interval": 10,
                "sources": {},
            },
        )
        sources = user_data.setdefault("sources", {})
        existing = next(
            (
                item
                for item in sources.values()
                if str(item.get("name", "")).lstrip("@").lower() == username.lower()
                and item.get("type") == waiting_type
            ),
            None,
        )
        if existing is None:
            sources[_next_source_id(sources)] = {
                "name": f"@{username}",
                "title": f"@{username}",
                "type": waiting_type,
                "status": "active",
            }
            bot.save_data(data)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط {('القناة' if waiting_type == 'channel' else 'المجموعة')} @{username}.\n"
            "تأكد أن البوت مضاف ولديه صلاحية النشر."
        )
        return

    # Keep existing handling for other messages and show a useful response for
    # private invite links, which Telegram does not let bots resolve to chat IDs.
    if waiting_type and ("t.me/+" in text or "joinchat/" in text):
        await message.reply_text(
            "رابط الدعوة الخاص لا يكشف معرّف القناة/المجموعة للبوت. "
            "أرسل رسالة مُحوّلة من المصدر، أو استخدم @username إذا كان عامًا."
        )
        return

    await bot.handle_user_messages(update, context)


bot.handle_user_messages = handle_user_messages

if __name__ == "__main__":
    bot.main()
