"""Railway entry point with verified Telegram channel/group linking."""

import re
from urllib.parse import urlparse

import bot


def _next_source_id(sources):
    index = 1
    while f"src_{index}" in sources:
        index += 1
    return f"src_{index}"


def _public_username(text):
    """Extract a public Telegram username from @name or a t.me URL."""
    value = (text or "").strip().rstrip(".,!?;:)>]")
    if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", value):
        return value[1:]

    # Accept links with or without scheme and www, including links inside text.
    match = re.search(
        r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([^\s/?#]+)",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None

    username = match.group(1).strip(".,!?;:)>]")
    if username.startswith("+") or username.lower() in {"joinchat", "c"}:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        return None
    return username


def _store_source(user, chat, source_kind):
    data = bot.load_data()
    users = data.setdefault("users", {})
    user_id = str(user.id)
    user_data = users.setdefault(
        user_id,
        {"name": user.first_name, "interval": 10, "sources": {}},
    )
    sources = user_data.setdefault("sources", {})
    chat_id = str(chat.id)

    # Re-linking the same chat updates its title rather than making duplicates.
    for source in sources.values():
        if str(source.get("name")) == chat_id:
            source.update(
                {
                    "name": chat_id,
                    "title": chat.title or chat.username or chat_id,
                    "type": source_kind,
                    "status": "active",
                }
            )
            bot.save_data(data)
            return

    sources[_next_source_id(sources)] = {
        "name": chat_id,
        "title": chat.title or chat.username or chat_id,
        "type": source_kind,
        "status": "active",
    }
    bot.save_data(data)


async def handle_user_messages(update, context):
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    # Telegram's current API provides forward_origin; older updates may expose
    # forward_from_chat. Either way, store the actual chat ID, not a link.
    origin = getattr(message, "forward_origin", None)
    source_chat = getattr(origin, "chat", None)
    if source_chat is None:
        source_chat = getattr(message, "forward_from_chat", None)

    if source_chat is not None:
        chat_type = getattr(source_chat, "type", None)
        if chat_type in ("channel", "group", "supergroup"):
            source_kind = "channel" if chat_type == "channel" else "group"
            _store_source(user, source_chat, source_kind)
            context.user_data.pop("waiting_source_type", None)
            await message.reply_text(
                f"✅ تم ربط الـ {source_kind} بنجاح!\n"
                f"الاسم: {source_chat.title or source_chat.username or source_chat.id}\n"
                f"المعرّف: {source_chat.id}\n"
                "تأكد أن البوت لديه صلاحية النشر فيها."
            )
            return

    waiting_type = context.user_data.get("waiting_source_type")
    text = message.text or ""

    # Only treat a link as a source after the user selected channel/group.
    if waiting_type in ("channel", "group"):
        username = _public_username(text)
        if username is None:
            await message.reply_text(
                "أرسل رابطًا عامًا بصيغة https://t.me/username أو @username. "
                "روابط الدعوة الخاصة لا تحتوي على معرّف يمكن للبوت استخدامه."
            )
            return

        try:
            # Resolve and validate via Telegram, then persist the actual chat ID.
            chat = await context.bot.get_chat(f"@{username}")
        except Exception as exc:
            print(f"[LINK] Could not resolve public Telegram username @{username}: {exc}")
            await message.reply_text(
                "لم أتمكن من الوصول إلى هذا الرابط. تأكد أن اسم المستخدم صحيح "
                "وأن القناة/المجموعة عامة، ثم أضف البوت إليها."
            )
            return

        actual_type = getattr(chat, "type", None)
        if actual_type not in ("channel", "group", "supergroup"):
            await message.reply_text("الرابط لا يشير إلى قناة أو مجموعة Telegram.")
            return

        actual_kind = "channel" if actual_type == "channel" else "group"
        if actual_kind != waiting_type:
            await message.reply_text(
                f"هذا الرابط يعود إلى {actual_kind} وليس {waiting_type}. "
                "ارجع واختر النوع الصحيح ثم أرسل الرابط مرة أخرى."
            )
            return

        _store_source(user, chat, actual_kind)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط {('القناة' if actual_kind == 'channel' else 'المجموعة')} بنجاح!\n"
            f"الاسم: {chat.title or chat.username or username}\n"
            f"المعرّف: {chat.id}\n"
            "تأكد أن البوت مضاف ولديه صلاحية النشر."
        )
        return

    # Preserve the bot's existing handling for other message flows.
    await bot.handle_user_messages(update, context)


# bot.main() registers this patched function as the text and forward handler.
bot.handle_user_messages = handle_user_messages

if __name__ == "__main__":
    bot.main()
