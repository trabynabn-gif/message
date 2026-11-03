"""Railway entry point that supports Telegram's current forward-origin fields."""

import bot


async def handle_user_messages(update, context):
    message = update.effective_message
    user = update.effective_user
    origin = getattr(message, "forward_origin", None) if message else None
    source_chat = getattr(origin, "chat", None)

    # Newer Telegram Bot API versions expose forwarded channel/group details
    # through forward_origin rather than the deprecated forward_from_chat.
    if source_chat is not None and user is not None:
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
            source_id = f"src_{len(sources) + 1}"
            while source_id in sources:
                source_id = f"src_{int(source_id.rsplit('_', 1)[1]) + 1}"

            title = (
                getattr(source_chat, "title", None)
                or getattr(source_chat, "username", None)
                or str(source_chat.id)
            )
            source_kind = "channel" if chat_type == "channel" else "group"
            sources[source_id] = {
                "name": str(source_chat.id),
                "title": title,
                "type": source_kind,
                "status": "active",
            }
            bot.save_data(data)
            await message.reply_text(
                f"✅ تم ربط الـ {source_kind} بنجاح!\n"
                f"الاسم: {title}\n"
                f"الايدي: {source_chat.id}\n"
                "تأكد أن البوت لديه صلاحية النشر فيها."
            )
            return

    # Keep the existing behavior for text links and legacy forwarded messages.
    await bot.handle_user_messages(update, context)


bot.handle_user_messages = handle_user_messages

if __name__ == "__main__":
    bot.main()
