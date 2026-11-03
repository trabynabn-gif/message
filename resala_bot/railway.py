"""Entry point for deployments whose Railway root is resala_bot/."""

import re

import bot


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


def _save_source(user, chat, source_type):
    data = bot.load_data()
    users = data.setdefault("users", {})
    user_data = users.setdefault(
        str(user.id),
        {"name": user.first_name, "interval": 1440, "sources": {}},
    )
    sources = user_data.setdefault("sources", {})
    chat_id = str(chat.id)
    title = chat.title or chat.username or chat_id

    for source in sources.values():
        if str(source.get("name")) == chat_id:
            source.update(name=chat_id, title=title, type=source_type, status="active")
            bot.save_data(data)
            return

    source_id = _next_source_id(sources)
    sources[source_id] = {
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
    source_chat = getattr(origin, "chat", None) or getattr(message, "forward_from_chat", None)
    if source_chat is not None and getattr(source_chat, "type", None) in (
        "channel", "group", "supergroup"
    ):
        source_type = "channel" if source_chat.type == "channel" else "group"
        _save_source(user, source_chat, source_type)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط الـ {source_type} بنجاح!\n"
            f"الاسم: {source_chat.title or source_chat.username or source_chat.id}\n"
            f"المعرّف: {source_chat.id}"
        )
        return

    waiting_type = context.user_data.get("waiting_source_type")
    if waiting_type in ("channel", "group"):
        username = _public_username(message.text or "")
        if not username:
            await message.reply_text(
                "أرسل رابطًا عامًا بصيغة https://t.me/username أو @username."
            )
            return
        try:
            chat = await context.bot.get_chat(f"@{username}")
        except Exception as exc:
            print(f"[LINK] Could not resolve @{username}: {exc}")
            await message.reply_text(
                "تعذر الوصول للرابط. تأكد من صحة اسم المستخدم وأن البوت مضاف للقناة/المجموعة."
            )
            return

        actual_type = getattr(chat, "type", None)
        if actual_type not in ("channel", "group", "supergroup"):
            await message.reply_text("الرابط لا يشير إلى قناة أو مجموعة.")
            return
        actual_source_type = "channel" if actual_type == "channel" else "group"
        if actual_source_type != waiting_type:
            await message.reply_text("نوع الرابط لا يطابق الاختيار. اختر النوع الصحيح وحاول مرة أخرى.")
            return

        _save_source(user, chat, actual_source_type)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط {('القناة' if actual_source_type == 'channel' else 'المجموعة')} بنجاح!\n"
            f"الاسم: {chat.title or chat.username or username}\n"
            f"المعرّف: {chat.id}\n"
            "تأكد من إضافة البوت ومنحه صلاحية النشر."
        )
        return

    await bot.handle_user_messages(update, context)


bot.handle_user_messages = handle_user_messages

if __name__ == "__main__":
    bot.main()
