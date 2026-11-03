"""Railway entry point with verified Telegram channel/group linking."""

import os
import re

import bot

# Capture the original handler before installing this wrapper. Delegating to
# bot.handle_user_messages after patching would recurse forever and prevent
# admin welcome-message edits from being saved.
_original_handle_user_messages = bot.handle_user_messages


def _next_source_id(sources):
    index = 1
    while f"src_{index}" in sources:
        index += 1
    return f"src_{index}"


def _public_username(text):
    value = (text or "").strip().rstrip(".,!?;:)>]")
    if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", value):
        return value[1:]
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
    return username if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username) else None


def _store_source(user, chat, source_type):
    data = bot.load_data()
    users = data.setdefault("users", {})
    user_id = str(user.id)
    user_data = users.setdefault(
        user_id, {"name": user.first_name, "interval": 10, "sources": {}}
    )
    sources = user_data.setdefault("sources", {})
    chat_id = str(chat.id)
    title = chat.title or chat.username or chat_id
    for source in sources.values():
        if str(source.get("name")) == chat_id:
            source.update(name=chat_id, title=title, type=source_type, status="active")
            bot.save_data(data)
            return
    sources[_next_source_id(sources)] = {
        "name": chat_id,
        "title": title,
        "type": source_type,
        "status": "active",
    }
    bot.save_data(data)


async def handle_user_messages(update, context):
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    origin = getattr(message, "forward_origin", None)
    source_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    if source_chat is None:
        source_chat = getattr(message, "forward_from_chat", None)
    chat_type = getattr(source_chat, "type", None)

    if source_chat is not None and chat_type in ("channel", "group", "supergroup"):
        source_type = "channel" if chat_type == "channel" else "group"
        _store_source(user, source_chat, source_type)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط الـ {source_type} بنجاح!\n"
            f"الاسم: {source_chat.title or source_chat.username or source_chat.id}\n"
            f"المعرّف: {source_chat.id}\n"
            "تأكد أن البوت مضاف ولديه صلاحية النشر."
        )
        return

    waiting_type = context.user_data.get("waiting_source_type")
    if waiting_type in ("channel", "group"):
        username = _public_username(message.text or "")
        if username is None:
            await message.reply_text(
                "أرسل رابطًا عامًا بصيغة https://t.me/username أو @username. "
                "روابط الدعوة الخاصة لا تكفي وحدها للربط."
            )
            return
        try:
            chat = await context.bot.get_chat(f"@{username}")
        except Exception as exc:
            print(f"[LINK] Failed resolving @{username}: {exc}")
            await message.reply_text(
                "تعذّر الوصول للرابط. تحقق من اسم المستخدم وأضف البوت إلى القناة/المجموعة."
            )
            return

        actual_type = getattr(chat, "type", None)
        if actual_type not in ("channel", "group", "supergroup"):
            await message.reply_text("الرابط لا يشير إلى قناة أو مجموعة.")
            return
        actual_source_type = "channel" if actual_type == "channel" else "group"
        if actual_source_type != waiting_type:
            await message.reply_text("نوع الرابط لا يطابق اختيارك؛ اختر النوع الصحيح وأعد الإرسال.")
            return
        _store_source(user, chat, actual_source_type)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط {('القناة' if actual_source_type == 'channel' else 'المجموعة')}!\n"
            f"الاسم: {chat.title or chat.username or username}\n"
            f"المعرّف: {chat.id}\n"
            "تأكد أن البوت مضاف ولديه صلاحية النشر."
        )
        return

    # Crucial: keep all other message states (including waiting_welcome) flowing
    # through the original bot handler, without recursion.
    await _original_handle_user_messages(update, context)


def main():
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing token: set TELEGRAM_BOT_TOKEN in Railway Variables.")
    bot.TOKEN = token
    admin_id = (os.environ.get("ADMIN_ID") or "").strip()
    if admin_id:
        try:
            bot.ADMIN_ID = int(admin_id)
        except ValueError as exc:
            raise RuntimeError("ADMIN_ID must be a numeric Telegram user ID.") from exc
    bot.handle_user_messages = handle_user_messages
    bot.main()


bot.handle_user_messages = handle_user_messages

if __name__ == "__main__":
    main()
