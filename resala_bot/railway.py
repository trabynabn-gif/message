"""Railway entry point for deployments whose Root Directory is resala_bot."""

import os
import re

import bot
from persistent_storage import install as install_persistent_storage

install_persistent_storage(bot)
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
    match = re.search(r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([^\s/?#]+)", value, re.IGNORECASE)
    if not match:
        return None
    username = match.group(1).strip(".,!?;:)>]")
    if username.startswith("+") or username.lower() in {"joinchat", "c"}:
        return None
    return username if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username) else None


def _save_source(user, chat, source_type):
    data = bot.load_data()
    users = data.setdefault("users", {})
    user_data = users.setdefault(str(user.id), {"name": user.first_name, "interval": 1440, "sources": {}})
    sources = user_data.setdefault("sources", {})
    chat_id = str(chat.id)
    title = chat.title or chat.username or chat_id
    for source in sources.values():
        if str(source.get("name")) == chat_id:
            source.update(name=chat_id, title=title, type=source_type, status="active")
            bot.save_data(data)
            return
    sources[_next_source_id(sources)] = {"name": chat_id, "title": title, "type": source_type, "status": "active"}
    bot.save_data(data)


def _target(user_id, source):
    if source.get("type") == "private":
        return str(user_id)
    value = str(source.get("name", "")).strip()
    if not value:
        return None
    if "t.me/" in value:
        username = _public_username(value)
        return f"@{username}" if username else None
    if value.lstrip("-").isdigit():
        return int(value)
    return value if value.startswith("@") else f"@{value}"


async def _handle_admin_pending(update, context):
    user, message = update.effective_user, update.effective_message
    if user is None or message is None or user.id != bot.ADMIN_ID:
        return False
    if context.user_data.get("waiting_welcome"):
        text = message.text
        if not text or not text.strip():
            await message.reply_text("أرسل نصًا غير فارغ لرسالة الترحيب.")
            return True
        try:
            data = bot.load_data()
            data["welcome_msg"] = text
            bot.save_data(data)
        except Exception as exc:
            print(f"[ADMIN] Failed to save welcome message: {exc}")
            await message.reply_text("❌ لم أتمكن من حفظ الرسالة. راجع سجل التشغيل.")
            return True
        context.user_data.pop("waiting_welcome", None)
        context.user_data.pop("waiting_source_type", None)
        context.user_data.pop("waiting_broadcast", None)
        await message.reply_text("✅ تم حفظ رسالة الترحيب الجديدة بنجاح!")
        return True
    if context.user_data.get("waiting_broadcast"):
        text = message.text
        if not text or not text.strip():
            await message.reply_text("أرسل نصًا غير فارغ للإذاعة.")
            return True
        mode = context.user_data.get("waiting_broadcast")
        data = bot.load_data()
        targets = set()
        for user_id, user_info in data.get("users", {}).items():
            for source in user_info.get("sources", {}).values():
                if source.get("status") != "active":
                    continue
                if mode == "private" and source.get("type") != "private":
                    continue
                target = _target(user_id, source)
                if target is not None:
                    targets.add(target)
        sent = failed = 0
        for target in targets:
            try:
                await context.bot.send_message(chat_id=target, text=text)
                sent += 1
            except Exception as exc:
                failed += 1
                print(f"[ADMIN] Broadcast failed for {target}: {exc}")
        context.user_data.pop("waiting_broadcast", None)
        await message.reply_text(f"📣 انتهت الإذاعة. وصل الإرسال إلى {sent} وجهة وتعذّر إلى {failed}.")
        return True
    return False


async def handle_user_messages(update, context):
    message, user = update.effective_message, update.effective_user
    if message is None or user is None:
        return
    if await _handle_admin_pending(update, context):
        return
    origin = getattr(message, "forward_origin", None)
    source_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    if source_chat is None:
        source_chat = getattr(message, "forward_from_chat", None)
    source_type = getattr(source_chat, "type", None)
    if source_chat is not None and source_type in ("channel", "group", "supergroup"):
        kind = "channel" if source_type == "channel" else "group"
        _save_source(user, source_chat, kind)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(f"✅ تم ربط الـ {kind} بنجاح!\nالاسم: {source_chat.title or source_chat.username or source_chat.id}\nالمعرّف: {source_chat.id}")
        return
    waiting_type = context.user_data.get("waiting_source_type")
    if waiting_type in ("channel", "group"):
        username = _public_username(message.text or "")
        if not username:
            await message.reply_text("أرسل رابطًا عامًا بصيغة https://t.me/username أو @username.")
            return
        try:
            chat = await context.bot.get_chat(f"@{username}")
        except Exception as exc:
            print(f"[LINK] Failed resolving @{username}: {exc}")
            await message.reply_text("تعذّر الوصول للرابط. تحقق من الاسم وأضف البوت للقناة/المجموعة.")
            return
        actual_type = getattr(chat, "type", None)
        if actual_type not in ("channel", "group", "supergroup"):
            await message.reply_text("الرابط لا يشير إلى قناة أو مجموعة.")
            return
        actual_type = "channel" if actual_type == "channel" else "group"
        if actual_type != waiting_type:
            await message.reply_text("نوع الرابط لا يطابق اختيارك؛ اختر النوع الصحيح وأعد الإرسال.")
            return
        _save_source(user, chat, actual_type)
        context.user_data.pop("waiting_source_type", None)
        await message.reply_text(f"✅ تم ربط {('القناة' if actual_type == 'channel' else 'المجموعة')}!\nالاسم: {chat.title or chat.username or username}\nالمعرّف: {chat.id}")
        return
    await _original_handle_user_messages(update, context)


async def send_scheduled_sunnahs(context):
    data, sunnahs = bot.load_data(), bot.load_sunnahs()
    if not sunnahs:
        print("[SCHEDULE] Sunnah data is empty or unavailable.")
        return
    index = bot.get_current_index()
    if not isinstance(index, int) or not 0 <= index < len(sunnahs):
        index = 0
    text = bot.format_sunnah_message(sunnahs[index], index + 1)
    for user_id, info in data.get("users", {}).items():
        for source in info.get("sources", {}).values():
            if source.get("status") != "active":
                continue
            target = _target(user_id, source)
            if target is None:
                continue
            try:
                await context.bot.send_message(chat_id=target, text=text)
            except Exception as exc:
                print(f"[SCHEDULE] Failed to send to {target}: {exc}")
    bot.save_current_index((index + 1) % len(sunnahs))


def main():
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in Railway Variables before deployment.")
    bot.TOKEN = token
    admin_id = (os.environ.get("ADMIN_ID") or "").strip()
    if admin_id:
        try:
            bot.ADMIN_ID = int(admin_id)
        except ValueError as exc:
            raise RuntimeError("ADMIN_ID must be your numeric Telegram user ID.") from exc
    bot.handle_user_messages = handle_user_messages
    bot.send_scheduled_sunnahs = send_scheduled_sunnahs
    bot.main()


bot.handle_user_messages = handle_user_messages
bot.send_scheduled_sunnahs = send_scheduled_sunnahs

if __name__ == "__main__":
    main()
