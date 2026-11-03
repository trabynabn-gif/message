"""Railway entry point with channel linking and scheduled delivery fixes."""

import os
import re

import bot

_original_handle_user_messages = bot.handle_user_messages


def _next_source_id(sources):
    index = 1
    while f"src_{index}" in sources:
        index += 1
    return f"src_{index}"


def _extract_username(text):
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
        str(user.id), {"name": user.first_name, "interval": 10, "sources": {}}
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
    # Telegram's modern group forwards use sender_chat; channel forwards use chat.
    source_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    if source_chat is None:
        source_chat = getattr(message, "forward_from_chat", None)
    chat_type = getattr(source_chat, "type", None)

    if source_chat is not None and chat_type in ("channel", "group", "supergroup"):
        source_type = "channel" if chat_type == "channel" else "group"
        _save_source(user, source_chat, source_type)
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
        username = _extract_username(message.text or "")
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

        _save_source(user, chat, actual_source_type)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(
            f"✅ تم ربط {('القناة' if actual_source_type == 'channel' else 'المجموعة')}!\n"
            f"الاسم: {chat.title or chat.username or username}\n"
            f"المعرّف: {chat.id}\n"
            "تأكد أن البوت مضاف ولديه صلاحية النشر."
        )
        return

    # Keep normal messages and admin workflows handled by the original bot.
    await _original_handle_user_messages(update, context)


async def send_scheduled_sunnahs(context):
    data = bot.load_data()
    sunnahs = bot.load_sunnahs()
    if not sunnahs:
        print("[SCHEDULE] No sunnah data loaded; nothing to send.")
        return

    index = bot.get_current_index()
    if not isinstance(index, int) or not 0 <= index < len(sunnahs):
        index = 0
    text = bot.format_sunnah_message(sunnahs[index], index + 1)

    for user_id, user_info in data.get("users", {}).items():
        for source in user_info.get("sources", {}).values():
            if source.get("status") != "active":
                continue
            source_type = source.get("type")
            target = str(user_id) if source_type == "private" else str(source.get("name", "")).strip()
            if not target:
                print(f"[SCHEDULE] Missing target for user {user_id}.")
                continue
            if source_type != "private":
                if "t.me/" in target:
                    username = _extract_username(target)
                    if not username:
                        print(f"[SCHEDULE] Invalid stored Telegram link: {target}")
                        continue
                    target = f"@{username}"
                elif target.lstrip("-").isdigit():
                    target = int(target)
                elif not target.startswith("@"):
                    target = f"@{target}"
            try:
                await context.bot.send_message(chat_id=target, text=text)
                print(f"[SCHEDULE] Sent to {target}")
            except Exception as exc:
                print(f"[SCHEDULE] Failed to send to {target}: {exc}")

    bot.save_current_index((index + 1) % len(sunnahs))


def main():
    # Railway variables take precedence; do not rely on an expired hard-coded token.
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
    bot.send_scheduled_sunnahs = send_scheduled_sunnahs
    bot.main()


bot.handle_user_messages = handle_user_messages
bot.send_scheduled_sunnahs = send_scheduled_sunnahs

if __name__ == "__main__":
    main()
