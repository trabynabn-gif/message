
if __name__ == "__main__":
    main()
EOF

python bot.py
cat << 'EOF' > bot.py
import os
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = "8731924379:AAGAw-Fk6fmgfy4cXd5sjorTJkgMeNVFdWg"
ADMIN_ID = 1520960859  
DB_FILE = "users.json"
SUNNAH_FILE = "sunnahs.json"
PROGRESS_FILE = "progress.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data.get("users"), list):
                    return {
                        "users": {},
                        "welcome_msg": "Welcome to 'Resala' bot 📖✨",
                        "app_file": None
                    }
                return data
        except Exception:
            pass
            
    return {
        "users": {},
        "welcome_msg": "Welcome to 'Resala' bot 📖✨",
        "app_file": None
    }

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_sunnahs():
    if not os.path.exists(SUNNAH_FILE):
        return []
    with open(SUNNAH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_current_index():
    if not os.path.exists(PROGRESS_FILE):
        return 0
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("index", 0)
    except:
        return 0

def save_current_index(index):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"index": index}, f)

def format_sunnah_message(sunnah, index):
    raw_text = sunnah.get('text', '')
    
    # تنظيف وقص أي جملة تخص رقم الحديث من داخل النص برمجياً وبشكل قاطع
    clean_text = re.sub(r'\(حديث رقم.*?\)', '', raw_text).strip()
    clean_text = re.sub(r'حديث رقم.*', '', clean_text).strip()
    clean_text = re.sub(r'\(رسالة.*?\)', '', clean_text).strip()

    text_body = (
        "💌:رسـالــة\n"
        "ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ\n"
        f"{clean_text}\n"
        "ـــــــ...\n"
        "المعنا..\n"
        f"{sunnah.get('meaning', '')}\n"
        "ـــــــ...\n"
        f"[{sunnah.get('source', '')}]"
    )
    # صيغة العرض الجديدة بالأسفل: (رسالة X) بدون نجوم
    return text_body + f"\n\n(رسالة {index})"

async def set_bot_commands(application):
    commands = [BotCommand("start", "Start Bot 🚀")]
    await application.bot.set_my_commands(commands)

async def send_scheduled_sunnahs(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    sunnahs = load_sunnahs()
    if not sunnahs:
        return

    index = get_current_index()
    chosen = sunnahs[index]
    formatted_msg = format_sunnah_message(chosen, index + 1)
    
    save_current_index((index + 1) % len(sunnahs))

    for chat_id, user_info in data.get("users", {}).items():
        sources = user_info.get("sources", {})
        for s_id, s_info in sources.items():
            if s_info.get("status") == "active":
                target = chat_id if s_info.get("type") == "private" else s_info.get("name")
                if target:
                    try:
                        if "t.me/" in target:
                            target = "@" + target.rstrip("/").split("/")[-1]
                        elif not target.startswith("@") and not target.startswith("-") and s_info.get("type") != "private":
                            target = "@" + target

                        await context.bot.send_message(chat_id=target, text=formatted_msg)
                        print(f"[SUCCESS] Sent clean message to target: {target}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send to {target}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    chat_id = str(user.id)
    data = load_data()
    
    if chat_id not in data["users"]:
        data["users"][chat_id] = {
            "name": user.first_name, 
            "interval": 1440,
            "sources": {
                "private": {"name": "المحادثة الخاصة", "type": "private", "status": "active"}
            }
        }
        save_data(data)
        try:
            admin_msg = f"New user joined:\nName: {user.first_name}\nID: {chat_id}"
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        except Exception as e:
            print(e)

    keyboard = [
        [InlineKeyboardButton("📖 تصفح الأحاديث", callback_data="next_sunnah")],
        [InlineKeyboardButton("⏱️ تعديل وقت التذكير", callback_data="set_time")],
        [InlineKeyboardButton("📢 القنوات والمجموعات", callback_data="sources")],
        [InlineKeyboardButton("🎛️ التحكم (المصادر)", callback_data="control_panel")],
        [InlineKeyboardButton("ℹ️ حول البوت", callback_data="about")],
        [InlineKeyboardButton("📱 تحميل التطبيق", callback_data="app")],
        [InlineKeyboardButton("📞 تواصل معنا", url=f"tg://user?id={ADMIN_ID}")]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ إعدادات المالك", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    template = data.get("welcome_msg", "مرحباً بك يا {name} 👋")
    welcome_text = template.replace("{name}", user.first_name)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    rm_msg = await update.message.reply_text("OK", reply_markup=ReplyKeyboardRemove())
    await context.bot.delete_message(chat_id=chat_id, message_id=rm_msg.message_id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    chat_id = str(user.id)
    data = load_data()
    
    if query.data == "next_sunnah":
        sunnahs = load_sunnahs()
        if sunnahs:
            index = get_current_index()
            if index >= len(sunnahs):
                index = 0
            
            chosen = sunnahs[index]
            formatted_msg = format_sunnah_message(chosen, index + 1)
            save_current_index((index + 1) % len(sunnahs))
            
            keyboard = [
                [InlineKeyboardButton("📖 حديث جديد (التالي)", callback_data="next_sunnah")],
                [InlineKeyboardButton("⏱️ تعديل وقت التذكير", callback_data="set_time")],
                [InlineKeyboardButton("📢 القنوات والمجموعات", callback_data="sources")],
                [InlineKeyboardButton("🎛️ التحكم (المصادر)", callback_data="control_panel")],
                [InlineKeyboardButton("ℹ️ حول البوت", callback_data="about")],
                [InlineKeyboardButton("📱 تحميل التطبيق", callback_data="app")],
                [InlineKeyboardButton("📞 تواصل معنا", url=f"tg://user?id={ADMIN_ID}")]
            ]
            if user.id == ADMIN_ID:
                keyboard.append([InlineKeyboardButton("⚙️ إعدادات المالك", callback_data="admin_panel")])
                
            await query.edit_message_text(formatted_msg, reply_markup=InlineKeyboardMarkup(keyboard))
            
    elif query.data == "about":
        text = (
            "📖 **عن بوت رِسالة:**\n\n"
            "الحياة السريعة أهلت الكثير من السنن النبوية العظيمة التي كان يحرص عليها النبي ﷺ في يومه وليلته، فأصبحت منسية أو مهجورة بين الناس.\n\n"
            "💡 **فكرة البوت:**\n"
            "هذا المشروع وُجد ليكون رفيقك اليومي ومذكرك الدائم. يقوم البوت بإرسال سنن نبوية صحيحة وثابتة بشكل منتظم."
        )
        keyboard = [[InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "set_time":
        text = "⏱️ **اختر وقت التذكير المناسب لك:**\nحدد الفاصل الزمني لإرسال التذكيرات والسنن:"
        keyboard = [
            [InlineKeyboardButton("10 دقائق", callback_data="t_10"), InlineKeyboardButton("15 دقيقة", callback_data="t_15")],
            [InlineKeyboardButton("30 دقيقة", callback_data="t_30"), InlineKeyboardButton("1 ساعة", callback_data="t_60")],
            [InlineKeyboardButton("2 ساعات", callback_data="t_120"), InlineKeyboardButton("4 ساعات", callback_data="t_240")],
            [InlineKeyboardButton("8 ساعات", callback_data="t_480"), InlineKeyboardButton("12 ساعة", callback_data="t_720")],
            [InlineKeyboardButton("24 ساعة", callback_data="t_1440")],
            [InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("t_"):
        minutes = int(query.data.split("_")[1])
        if chat_id in data["users"]:
            data["users"][chat_id]["interval"] = minutes
            save_data(data)
            
        text = f"✅ تم حفظ الوقت بنجاح ({minutes} دقيقة)! وسيتم إرسال التذكيرات بالفاصل الزمني الجديد."
        keyboard = [[InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "sources":
        text = "📢 **إدارة القنوات والمجموعات:**\nاختر المكان الذي تريد ربط التذكيرات به:"
        keyboard = [
            [InlineKeyboardButton("👥 مجموعة", callback_data="src_group")],
            [InlineKeyboardButton("📢 قناة", callback_data="src_channel")],
            [InlineKeyboardButton("💬 المحادثة هنا (الخاص)", callback_data="src_private")],
            [InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "src_group":
        context.user_data["waiting_source_type"] = "group"
        text = "📌 **ربط مجموعة:**\nأرسل الآن رابط مجموعتك أو قم بتوجيه رسالة (Forward) من المجموعة هنا، وسيقوم البوت بجلب المعرف وربطها تلقائياً."
        keyboard = [[InlineKeyboardButton("🔙 الرجوع", callback_data="sources")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "src_channel":
        context.user_data["waiting_source_type"] = "channel"
        text = "📌 **ربط قناة:**\nأرسل الآن رابط قناتك أو قم بتوجيه رسالة (Forward) من القناة هنا، وسيقوم البوت بجلب المعرف وربطها تلقائياً."
        keyboard = [[InlineKeyboardButton("🔙 الرجوع", callback_data="sources")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "src_private":
        if chat_id in data["users"]:
            data["users"][chat_id]["sources"]["private"] = {"name": "المحادثة الخاصة", "type": "private", "status": "active"}
            save_data(data)
        text = "✅ **تم تفعيل المحادثة الخاصة بنجاح!**"
        keyboard = [[InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "control_panel":
        text = "🎛️ **لوحة التحكم بالمصادر:**\nاختر القسم الذي تريد إدارته:"
        keyboard = [
            [InlineKeyboardButton("👥 المجموعات", callback_data="ctrl_groups"), InlineKeyboardButton("📢 القنوات", callback_data="ctrl_channels")],
            [InlineKeyboardButton("💬 المحادثة الخاصة", callback_data="ctrl_private")],
            [InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "ctrl_private":
        p_status = data["users"].get(chat_id, {}).get("sources", {}).get("private", {}).get("status", "active")
        status_text = "🟢 مفعل (يعمل)" if p_status == "active" else "🔴 متوقف"
        toggle_btn_text = "🔴 إيقاف البوت" if p_status == "active" else "🟢 تشغيل البوت"
        
        text = f"💬 **المحادثة الخاصة:**\n• الحالة الحالية: {status_text}"
        keyboard = [
            [InlineKeyboardButton(toggle_btn_text, callback_data="toggle_private")],
            [InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "toggle_private":
        if chat_id in data["users"] and "private" in data["users"][chat_id]["sources"]:
            curr = data["users"][chat_id]["sources"]["private"]["status"]
            data["users"][chat_id]["sources"]["private"]["status"] = "inactive" if curr == "active" else "active"
            save_data(data)
        
        p_status = data["users"].get(chat_id, {}).get("sources", {}).get("private", {}).get("status", "active")
        status_text = "🟢 مفعل (يعمل)" if p_status == "active" else "🔴 متوقف"
        toggle_btn_text = "🔴 إيقاف البوت" if p_status == "active" else "🟢 تشغيل البوت"
        
        text = f"✅ **تم تحديث الحالة بنجاح!**\n\n💬 **المحادثة الخاصة:**\n• الحالة الحالية: {status_text}"
        keyboard = [
            [InlineKeyboardButton(toggle_btn_text, callback_data="toggle_private")],
            [InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data in ["ctrl_groups", "ctrl_channels"]:
        st_type = "group" if query.data == "ctrl_groups" else "channel"
        user_sources = data["users"].get(chat_id, {}).get("sources", {})
        
        keyboard = []
        for s_id, s_info in user_sources.items():
            if s_info.get("type") == st_type:
                status_icon = "🟢" if s_info.get("status") == "active" else "🔴"
                s_name = s_info.get('title', s_info.get('name'))
                keyboard.append([
                    InlineKeyboardButton(f"{s_name} {status_icon}", callback_data=f"toggle_{s_id}"),
                    InlineKeyboardButton("🗑️ حذف", callback_data=f"del_{s_id}")
                ])
        
        if not keyboard:
            keyboard.append([InlineKeyboardButton("لا توجد مصادر مضافة بعد", callback_data="control_panel")])
            
        keyboard.append([InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")])
        title = "👥 **إدارة المجموعات:**" if st_type == "group" else "📢 **إدارة القنوات:**"
        await query.edit_message_text(f"{title}\nيمكنك التبديل بين تشغيل/إيقاف أو الحذف:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("toggle_"):
        s_id = query.data.split("_")[1]
        if chat_id in data["users"] and s_id in data["users"][chat_id]["sources"]:
            current_status = data["users"][chat_id]["sources"][s_id]["status"]
            new_status = "inactive" if current_status == "active" else "active"
            data["users"][chat_id]["sources"][s_id]["status"] = new_status
            save_data(data)
            
        text = "✅ تم تحديث حالة المصدر بنجاح!"
        keyboard = [[InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("del_"):
        s_id = query.data.split("_")[1]
        if chat_id in data["users"] and s_id in data["users"][chat_id]["sources"]:
            del data["users"][chat_id]["sources"][s_id]
            save_data(data)
            
        text = "🗑️ تم إزالة وحذف المصدر بنجاح!"
        keyboard = [[InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "app":
        app_file = data.get("app_file")
        if app_file:
            text = "📱 تطبيق 'رِسالة' جاهز للتحميل عبر الملف المرفق أدناه 🚀"
            await context.bot.send_document(chat_id=chat_id, document=app_file, caption="تطبيق رِسالة الرسمي 📱")
            keyboard = [[InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            text = "📱 نعمل حالياً على تطوير تطبيق 'رِسالة' للهواتف الذكية، وسوف يتم إخبارك فور إطلاقه رسمياً!"
            keyboard = [[InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "admin_panel" and user.id == ADMIN_ID:
        text = "⚙️ **إعدادات المالك:**\nاختر الإجراء المطلوب للإدارة:"
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب", callback_data="adm_edit_wel")],
            [InlineKeyboardButton("📊 معرفة عدد المستخدمين", callback_data="adm_users_count")],
            [InlineKeyboardButton("📢 إذاعة رسالة", callback_data="adm_broadcast")],
            [InlineKeyboardButton("📱 رفع ملف التطبيق", callback_data="adm_upload_app")],
            [InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_users_count" and user.id == ADMIN_ID:
        total_users = len(data["users"])
        text = f"📊 **إحصائيات المستخدمين:**\n\n• إجمالي المستخدمين: `{total_users}` مستخدم."
        keyboard = [[InlineKeyboardButton("🔙 رجوع لإعدادات المالك", callback_data="admin_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_broadcast" and user.id == ADMIN_ID:
        text = "📢 **اختر نوع الإذاعة المطلوبة:**"
        keyboard = [
            [InlineKeyboardButton("إذاعة الكل", callback_data="bc_all")],
            [InlineKeyboardButton("إذاعة المحادثة الخاصة", callback_data="bc_private")],
            [InlineKeyboardButton("🔙 رجوع لإعدادات المالك", callback_data="admin_panel")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("bc_") and user.id == ADMIN_ID:
        bc_type = query.data.split("_")[1]
        context.user_data["waiting_broadcast"] = bc_type
        text = f"✍️ أرسل الآن نص رسالة الإذاعة لنوع: **{bc_type}**"
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="adm_broadcast")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_upload_app" and user.id == ADMIN_ID:
        context.user_data["waiting_app_file"] = True
        text = "📱 أرسل الآن ملف التطبيق (.apk) في رسالة مباشرة لكي يتم حفظه وربطه بزر تحميل التطبيق."
        keyboard = [[InlineKeyboardButton("🔙 رجوع لإعدادات المالك", callback_data="admin_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_edit_wel" and user.id == ADMIN_ID:
        context.user_data["waiting_welcome"] = True
        text = "✏️ أرسل نص رسالة الترحيب الجديدة الآن."
        keyboard = [[InlineKeyboardButton("🔙 رجوع لإعدادات المالك", callback_data="admin_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "main_menu":
        context.user_data.clear()
        keyboard = [
            [InlineKeyboardButton("📖 تصفح الأحاديث", callback_data="next_sunnah")],
            [InlineKeyboardButton("⏱️ تعديل وقت التذكير", callback_data="set_time")],
            [InlineKeyboardButton("📢 القنوات والمجموعات", callback_data="sources")],
            [InlineKeyboardButton("🎛️ التحكم (المصادر)", callback_data="control_panel")],
            [InlineKeyboardButton("ℹ️ حول البوت", callback_data="about")],
            [InlineKeyboardButton("📱 تحميل التطبيق", callback_data="app")],
            [InlineKeyboardButton("📞 تواصل معنا", url=f"tg://user?id={ADMIN_ID}")]
        ]
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("⚙️ إعدادات المالك", callback_data="admin_panel")])
            
        template = data.get("welcome_msg", "مرحباً بك يا {name} 👋")
        welcome_text = template.replace("{name}", user.first_name)
        await query.edit_message_text(f"{welcome_text}\n\nالقائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = str(user.id)
    text = update.message.text
    data = load_data()
    
    if update.message.forward_from_chat:
        f_chat = update.message.forward_from_chat
        f_id = str(f_chat.id)
        f_title = f_chat.title or f_chat.username or f"قناة/مجموعة {f_id}"
        f_type = "channel" if f_chat.type == "channel" else "group"
        
        source_id = "src_" + str(len(data["users"].get(chat_id, {}).get("sources", {})) + 1)
        if chat_id in data["users"]:
            data["users"][chat_id]["sources"][source_id] = {
                "name": f_id,
                "title": f_title,
                "type": f_type,
                "status": "active"
            }
            save_data(data)
            
        await update.message.reply_text(f"✅ تم ربط الـ {f_type} بنجاح!\nالاسم: `{f_title}`\nالايدي: `{f_id}`\n\nوتم تفعيل النشر التلقائي فيها!")
        return

    if context.user_data.get("waiting_source_type"):
        st_type = context.user_data["waiting_source_type"]
        context.user_data.clear()
        
        source_id = "src_" + str(len(data["users"].get(chat_id, {}).get("sources", {})) + 1)
        if chat_id in data["users"]:
            data["users"][chat_id]["sources"][source_id] = {
                "name": text,
                "title": text,
                "type": st_type,
                "status": "active"
            }
            save_data(data)
            
        await update.message.reply_text(f"✅ تم إضافة القناة/المجموعة بنجاح:\n`{text}`\n\nتأكد أن البوت (مشرف / Admin) في القناة وإلا فلن يستطيع النشر فيها.")
        return

    if user.id == ADMIN_ID:
        if context.user_data.get("waiting_welcome"):
            data["welcome_msg"] = text
            save_data(data)
            context.user_data.clear()
            await update.message.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!")
            return
            
        if context.user_data.get("waiting_broadcast"):
            bc_type = context.user_data["waiting_broadcast"]
            context.user_data.clear()
            await update.message.reply_text(f"🚀 جاري بدء الإذاعة ({bc_type}) بنجاح للمستخدمين...")
            return

async def handle_admin_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    data = load_data()
    if context.user_data.get("waiting_app_file") and update.message.document:
        file_id = update.message.document.file_id
        data["app_file"] = file_id
        save_data(data)
        context.user_data.clear()
        await update.message.reply_text("✅ تم حفظ ملف التطبيق وربطه بزر التحميل بنجاح!")
        return

def main():
    application = Application.builder().token(TOKEN).post_init(set_bot_commands).build()
    
    # ضبط الفاصل الزمني الافتراضي للإرسال التلقائي (600 ثانية = 10 دقائق)
    job_queue = application.job_queue
    job_queue.run_repeating(send_scheduled_sunnahs, interval=600, first=10)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))
    application.add_handler(MessageHandler(filters.FORWARDED, handle_user_messages))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_admin_documents))
    
    print("Bot Resala is running with 10-min interval & '(رسالة X)' format...")
    application.run_polling()

if __name__ == "__main__":
    main()
EOF

python bot.py
exit
