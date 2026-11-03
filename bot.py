
import os
import json
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

TOKEN = "ضع_التوكن_الجديد_هنا"
ADMIN_ID = 1520960859

DB_FILE = "users.json"
SUNNAH_FILE = "sunnahs.json"
PROGRESS_FILE = "progress.json"


WELCOME_MESSAGE = """📩 أهلاً بك يا {name} في بوت رِسالة 🌿

هل فكرت يومًا أن رسالة قصيرة قد تكون سببًا في تذكير إنسان بسنة من سنن النبي ﷺ؟

من هنا جاءت فكرة رِسالة؛ بوت هدفه نشر الأحاديث النبوية الصحيحة وإحياء السنن المهجورة، لتظل سنة النبي ﷺ حاضرة في حياتنا اليومية.

🌟 ماذا يقدم لك بوت رِسالة؟

📖 أحاديث نبوية: تصفح مجموعة من الأحاديث مع ذكر مصدرها ومعناها بطريقة واضحة.

⏰ تذكيرات دورية: تصلك رسائل تحتوي على أحاديث وسنن نبوية على فترات تختارها بنفسك.

🔔 تحكم كامل: يمكنك تشغيل التذكيرات أو إيقافها وتحديد الوقت المناسب لك.

📚 إحياء السنن المهجورة: نتعرف معًا على سنن نبوية قد غفل عنها كثير من الناس، ونعمل على إحيائها ونشرها.

📢 هل لديك قناة أو مجموعة على تيليجرام؟

لا تجعل الخير يتوقف عندك وحدك!

يمكنك إضافة بوت رِسالة إلى قناتك أو مجموعتك، وربطها به حتى تساهم في نشر الأحاديث النبوية والسنن بين أعضائك بشكل دوري.

🤝 كن سببًا في نشر الخير!

شارك البوت مع أصدقائك، وأضفه إلى مجموعاتك وقنواتك، وادعُ الآخرين للاستفادة منه.

فربما تكون رسالة واحدة سببًا في إحياء سنة، أو تذكير غافل، أو عمل صالح يستمر أثره.

❤️ رِسالة... تذكيرٌ يصل، وخيرٌ ينتشر، وسُنّةٌ تُحيا"""


# =========================
# قاعدة البيانات
# =========================

def load_data():
    default_data = {
        "users": {},
        "welcome_msg": WELCOME_MESSAGE,
        "app_file": None
    }

    if not os.path.exists(DB_FILE):
        save_data(default_data)
        return default_data.copy()

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            data = default_data.copy()

        # الحفاظ على المستخدمين عند وجود قاعدة بيانات قديمة
        if isinstance(data.get("users"), list):
            converted_users = {}

            for item in data["users"]:
                if isinstance(item, dict):
                    user_id = (
                        item.get("id")
                        or item.get("user_id")
                        or item.get("chat_id")
                    )

                    if user_id:
                        converted_users[str(user_id)] = item

            data["users"] = converted_users

        if not isinstance(data.get("users"), dict):
            data["users"] = {}

        if not data.get("welcome_msg"):
            data["welcome_msg"] = WELCOME_MESSAGE

        if "app_file" not in data:
            data["app_file"] = None

        return data

    except Exception as e:
        print(f"[ERROR] Database loading: {e}")
        return default_data.copy()


def save_data(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[ERROR] Database saving: {e}")


def load_sunnahs():
    if not os.path.exists(SUNNAH_FILE):
        return []

    try:
        with open(SUNNAH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Sunnahs loading: {e}")
        return []


def get_current_index():
    if not os.path.exists(PROGRESS_FILE):
        return 0

    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("index", 0)
    except Exception:
        return 0


def save_current_index(index):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"index": index}, f)


# =========================
# تنسيق الأحاديث
# =========================

def format_sunnah_message(sunnah, index):
    raw_text = sunnah.get("text", "")

    clean_text = re.sub(
        r"\(حديث رقم.*?\)", "", raw_text
    ).strip()

    clean_text = re.sub(
        r"حديث رقم.*", "", clean_text
    ).strip()

    clean_text = re.sub(
        r"\(رسالة.*?\)", "", clean_text
    ).strip()

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

    return text_body + f"\n\n(رسالة {index})"


# =========================
# أوامر البوت
# =========================

async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Start Bot 🚀")
    ]

    await application.bot.set_my_commands(commands)


# =========================
# إرسال الأحاديث الدورية
# =========================

async def send_scheduled_sunnahs(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    sunnahs = load_sunnahs()

    if not sunnahs:
        return

    index = get_current_index()

    if index >= len(sunnahs):
        index = 0

    chosen = sunnahs[index]
    formatted_msg = format_sunnah_message(chosen, index + 1)

    save_current_index((index + 1) % len(sunnahs))

    for chat_id, user_info in data.get("users", {}).items():
        sources = user_info.get("sources", {})

        for s_id, s_info in sources.items():
            if s_info.get("status") != "active":
                continue

            target = (
                chat_id
                if s_info.get("type") == "private"
                else s_info.get("name")
            )

            if not target:
                continue

            try:
                if "t.me/" in str(target):
                    target = "@" + str(target).rstrip("/").split("/")[-1]

                elif (
                    not str(target).startswith("@")
                    and not str(target).startswith("-")
                    and s_info.get("type") != "private"
                ):
                    target = "@" + str(target)

                await context.bot.send_message(
                    chat_id=target,
                    text=formatted_msg
                )

            except Exception as e:
                print(f"[ERROR] Failed to send to {target}: {e}")


# =========================
# القائمة الرئيسية
# =========================

def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("📖 تصفح الأحاديث", callback_data="next_sunnah")],
        [InlineKeyboardButton("⏱️ تعديل وقت التذكير", callback_data="set_time")],
        [InlineKeyboardButton("📢 القنوات والمجموعات", callback_data="sources")],
        [InlineKeyboardButton("🎛️ التحكم (المصادر)", callback_data="control_panel")],
        [InlineKeyboardButton("ℹ️ حول البوت", callback_data="about")],
        [InlineKeyboardButton("📱 تحميل التطبيق", callback_data="app")],
        [InlineKeyboardButton("📞 تواصل معنا", url=f"tg://user?id={ADMIN_ID}")]
    ]

    if user_id == ADMIN_ID:
        keyboard.append([
            InlineKeyboardButton(
                "⚙️ إعدادات المالك",
                callback_data="admin_panel"
            )
        ])

    return InlineKeyboardMarkup(keyboard)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✏️ تعديل رسالة الترحيب",
                callback_data="adm_edit_wel"
            )
        ],
        [
            InlineKeyboardButton(
                "♻️ استعادة رسالة الترحيب الافتراضية",
                callback_data="adm_reset_wel"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 معرفة عدد المستخدمين",
                callback_data="adm_users_count"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 إذاعة رسالة",
                callback_data="adm_broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "📱 رفع ملف التطبيق",
                callback_data="adm_upload_app"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 الرجوع للقائمة الرئيسية",
                callback_data="main_menu"
            )
        ]
    ])


# =========================
# بدء البوت
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user = update.effective_user
    chat_id = str(user.id)

    data = load_data()

    if chat_id not in data["users"]:
        data["users"][chat_id] = {
            "name": user.first_name,
            "interval": 10,
            "sources": {
                "private": {
                    "name": "المحادثة الخاصة",
                    "type": "private",
                    "status": "active"
                }
            }
        }

        save_data(data)

    template = data.get("welcome_msg") or WELCOME_MESSAGE

    welcome_text = template.replace(
        "{name}",
        user.first_name or "صديقي"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard(user.id)
    )

    rm_msg = await update.message.reply_text(
        "OK",
        reply_markup=ReplyKeyboardRemove()
    )

    await context.bot.delete_message(
        chat_id=chat_id,
        message_id=rm_msg.message_id
    )


# =========================
# معالج الأزرار
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    chat_id = str(user.id)
    data = load_data()

    # عرض حديث جديد
    if query.data == "next_sunnah":
        sunnahs = load_sunnahs()

        if not sunnahs:
            await query.answer(
                "⚠️ ملف الأحاديث غير موجود أو فارغ!",
                show_alert=True
            )
            return

        index = get_current_index()

        if index >= len(sunnahs):
            index = 0

        chosen = sunnahs[index]
        formatted_msg = format_sunnah_message(chosen, index + 1)

        save_current_index((index + 1) % len(sunnahs))

        await query.edit_message_text(
            text=formatted_msg,
            reply_markup=main_menu_keyboard(user.id)
        )

    # حول البوت
    elif query.data == "about":
        text = (
            "📖 **عن بوت رِسالة:**\n\n"
            "الحياة السريعة أهلت الكثير من السنن النبوية العظيمة "
            "التي كان يحرص عليها النبي ﷺ في يومه وليلته، "
            "فأصبحت منسية أو مهجورة بين الناس.\n\n"
            "💡 **فكرة البوت:**\n"
            "هذا المشروع وُجد ليكون رفيقك اليومي ومذكرك الدائم. "
            "يقوم البوت بإرسال سنن نبوية صحيحة وثابتة بشكل منتظم."
        )

        keyboard = [[
            InlineKeyboardButton(
                "🔙 الرجوع للقائمة الرئيسية",
                callback_data="main_menu"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # تعديل وقت التذكير
    elif query.data == "set_time":
        text = (
            "⏱️ **اختر وقت التذكير المناسب لك:**\n"
            "حدد الفاصل الزمني لإرسال التذكيرات والسنن:"
        )

        keyboard = [
            [
                InlineKeyboardButton("10 دقائق", callback_data="t_10"),
                InlineKeyboardButton("15 دقيقة", callback_data="t_15")
            ],
            [
                InlineKeyboardButton("30 دقيقة", callback_data="t_30"),
                InlineKeyboardButton("1 ساعة", callback_data="t_60")
            ],
            [
                InlineKeyboardButton("2 ساعات", callback_data="t_120"),
                InlineKeyboardButton("4 ساعات", callback_data="t_240")
            ],
            [
                InlineKeyboardButton("8 ساعات", callback_data="t_480"),
                InlineKeyboardButton("12 ساعة", callback_data="t_720")
            ],
            [
                InlineKeyboardButton("24 ساعة", callback_data="t_1440")
            ],
            [
                InlineKeyboardButton(
                    "🔙 الرجوع للقائمة الرئيسية",
                    callback_data="main_menu"
                )
            ]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("t_"):
        minutes = int(query.data.split("_")[1])

        if chat_id in data["users"]:
            data["users"][chat_id]["interval"] = minutes
            save_data(data)

        text = (
            f"✅ تم حفظ الوقت بنجاح ({minutes} دقيقة)!\n"
            "وسيتم إرسال التذكيرات بالفاصل الزمني الجديد."
        )

        keyboard = [[
            InlineKeyboardButton(
                "🔙 الرجوع للقائمة الرئيسية",
                callback_data="main_menu"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # إدارة المصادر
    elif query.data == "sources":
        text = (
            "📢 **إدارة القنوات والمجموعات:**\n"
            "اختر المكان الذي تريد ربط التذكيرات به:"
        )

        keyboard = [
            [InlineKeyboardButton("👥 مجموعة", callback_data="src_group")],
            [InlineKeyboardButton("📢 قناة", callback_data="src_channel")],
            [InlineKeyboardButton("💬 المحادثة هنا (الخاص)", callback_data="src_private")],
            [InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "src_group":
        context.user_data["waiting_source_type"] = "group"

        text = (
            "📌 **ربط مجموعة:**\n"
            "أرسل الآن رابط مجموعتك أو قم بتوجيه رسالة "
            "(Forward) من المجموعة هنا، وسيقوم البوت بجلب المعرف وربطها تلقائياً."
        )

        keyboard = [[
            InlineKeyboardButton("🔙 الرجوع", callback_data="sources")
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "src_channel":
        context.user_data["waiting_source_type"] = "channel"

        text = (
            "📌 **ربط قناة:**\n"
            "أرسل الآن رابط قناتك أو قم بتوجيه رسالة "
            "(Forward) من القناة هنا، وسيقوم البوت بجلب المعرف وربطها تلقائياً."
        )

        keyboard = [[
            InlineKeyboardButton("🔙 الرجوع", callback_data="sources")
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "src_private":
        if chat_id in data["users"]:
            data["users"][chat_id]["sources"]["private"] = {
                "name": "المحادثة الخاصة",
                "type": "private",
                "status": "active"
            }
            save_data(data)

        text = "✅ **تم تفعيل المحادثة الخاصة بنجاح!**"

        keyboard = [[
            InlineKeyboardButton(
                "🔙 الرجوع للقائمة الرئيسية",
                callback_data="main_menu"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # لوحة التحكم بالمصادر
    elif query.data == "control_panel":
        text = (
            "🎛️ **لوحة التحكم بالمصادر:**\n"
            "اختر القسم الذي تريد إدارته:"
        )

        keyboard = [
            [
                InlineKeyboardButton("👥 المجموعات", callback_data="ctrl_groups"),
                InlineKeyboardButton("📢 القنوات", callback_data="ctrl_channels")
            ],
            [
                InlineKeyboardButton("💬 المحادثة الخاصة", callback_data="ctrl_private")
            ],
            [
                InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "ctrl_private":
        p_status = (
            data["users"]
            .get(chat_id, {})
            .get("sources", {})
            .get("private", {})
            .get("status", "active")
        )

        status_text = "🟢 مفعل (يعمل)" if p_status == "active" else "🔴 متوقف"
        toggle_btn_text = "🔴 إيقاف البوت" if p_status == "active" else "🟢 تشغيل البوت"

        text = (
            f"💬 **المحادثة الخاصة:**\n"
            f"• الحالة الحالية: {status_text}"
        )

        keyboard = [
            [InlineKeyboardButton(toggle_btn_text, callback_data="toggle_private")],
            [InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "toggle_private":
        if (
            chat_id in data["users"]
            and "private" in data["users"][chat_id]["sources"]
        ):
            curr = data["users"][chat_id]["sources"]["private"]["status"]

            data["users"][chat_id]["sources"]["private"]["status"] = (
                "inactive" if curr == "active" else "active"
            )

            save_data(data)

        p_status = (
            data["users"]
            .get(chat_id, {})
            .get("sources", {})
            .get("private", {})
            .get("status", "active")
        )

        status_text = "🟢 مفعل (يعمل)" if p_status == "active" else "🔴 متوقف"
        toggle_btn_text = "🔴 إيقاف البوت" if p_status == "active" else "🟢 تشغيل البوت"

        text = (
            f"✅ **تم تحديث الحالة بنجاح!**\n\n"
            f"💬 **المحادثة الخاصة:**\n"
            f"• الحالة الحالية: {status_text}"
        )

        keyboard = [
            [InlineKeyboardButton(toggle_btn_text, callback_data="toggle_private")],
            [InlineKeyboardButton("🔙 الرجوع للتحكم", callback_data="control_panel")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data in ["ctrl_groups", "ctrl_channels"]:
        st_type = "group" if query.data == "ctrl_groups" else "channel"
        user_sources = data["users"].get(chat_id, {}).get("sources", {})

        keyboard = []

        for s_id, s_info in user_sources.items():
            if s_info.get("type") == st_type:
                status_icon = "🟢" if s_info.get("status") == "active" else "🔴"
                s_name = s_info.get("title", s_info.get("name"))

                keyboard.append([
                    InlineKeyboardButton(
                        f"{s_name} {status_icon}",
                        callback_data=f"toggle_{s_id}"
                    ),
                    InlineKeyboardButton(
                        "🗑️ حذف",
                        callback_data=f"del_{s_id}"
                    )
                ])

        if not keyboard:
            keyboard.append([
                InlineKeyboardButton(
                    "لا توجد مصادر مضافة بعد",
                    callback_data="control_panel"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 الرجوع للتحكم",
                callback_data="control_panel"
            )
        ])

        title = (
            "👥 **إدارة المجموعات:**"
            if st_type == "group"
            else "📢 **إدارة القنوات:**"
        )

        await query.edit_message_text(
            f"{title}\nيمكنك التبديل بين تشغيل/إيقاف أو الحذف:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("toggle_"):
        s_id = query.data[len("toggle_"):]

        if (
            chat_id in data["users"]
            and s_id in data["users"][chat_id]["sources"]
        ):
            current_status = data["users"][chat_id]["sources"][s_id]["status"]

            new_status = (
                "inactive" if current_status == "active" else "active"
            )

            data["users"][chat_id]["sources"][s_id]["status"] = new_status
            save_data(data)

        text = "✅ تم تحديث حالة المصدر بنجاح!"

        keyboard = [[
            InlineKeyboardButton(
                "🔙 الرجوع للتحكم",
                callback_data="control_panel"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("del_"):
        s_id = query.data[len("del_"):]

        if (
            chat_id in data["users"]
            and s_id in data["users"][chat_id]["sources"]
        ):
            del data["users"][chat_id]["sources"][s_id]
            save_data(data)

        text = "🗑️ تم إزالة وحذف المصدر بنجاح!"

        keyboard = [[
            InlineKeyboardButton(
                "🔙 الرجوع للتحكم",
                callback_data="control_panel"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # تحميل التطبيق
    elif query.data == "app":
        app_file = data.get("app_file")

        if app_file:
            text = "📱 تطبيق 'رِسالة' جاهز للتحميل عبر الملف المرفق أدناه 🚀"

            await context.bot.send_document(
                chat_id=chat_id,
                document=app_file,
                caption="تطبيق رِسالة الرسمي 📱"
            )

        else:
            text = (
                "📱 نعمل حالياً على تطوير تطبيق 'رِسالة' "
                "للهواتف الذكية، وسوف يتم إخبارك فور إطلاقه رسمياً!"
            )

        keyboard = [[
            InlineKeyboardButton(
                "🔙 الرجوع للقائمة الرئيسية",
                callback_data="main_menu"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # لوحة المالك
    elif query.data == "admin_panel" and user.id == ADMIN_ID:
        await query.edit_message_text(
            "⚙️ **إعدادات المالك:**\nاختر الإجراء المطلوب للإدارة:",
            reply_markup=admin_keyboard()
        )

    # تعديل رسالة الترحيب
    elif query.data == "adm_edit_wel" and user.id == ADMIN_ID:
        context.user_data["waiting_welcome"] = True

        keyboard = [
            [
                InlineKeyboardButton(
                    "❌ إلغاء التعديل",
                    callback_data="cancel_welcome_edit"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 رجوع لإعدادات المالك",
                    callback_data="admin_panel"
                )
            ]
        ]

        await query.edit_message_text(
            "✏️ تعديل رسالة الترحيب\n\n"
            "أرسل الآن رسالة الترحيب الجديدة.\n\n"
            "يمكنك استخدام {name} لعرض اسم المستخدم.\n\n"
            "📌 سيتم حفظ الرسالة تلقائيًا واستخدامها عند بدء البوت.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # إلغاء تعديل الترحيب
    elif query.data == "cancel_welcome_edit" and user.id == ADMIN_ID:
        context.user_data.pop("waiting_welcome", None)

        await query.edit_message_text(
            "⚙️ **إعدادات المالك:**",
            reply_markup=admin_keyboard()
        )

    # استعادة الترحيب الافتراضي
    elif query.data == "adm_reset_wel" and user.id == ADMIN_ID:
        data["welcome_msg"] = WELCOME_MESSAGE
        save_data(data)

        context.user_data.pop("waiting_welcome", None)

        await query.edit_message_text(
            "✅ تمت استعادة رسالة الترحيب الافتراضية وحفظها.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 إعدادات المالك",
                        callback_data="admin_panel"
                    )
                ]
            ])
        )

    # عدد المستخدمين
    elif query.data == "adm_users_count" and user.id == ADMIN_ID:
        total_users = len(data["users"])

        text = (
            "📊 **إحصائيات المستخدمين:**\n\n"
            f"• إجمالي المستخدمين: `{total_users}` مستخدم."
        )

        keyboard = [[
            InlineKeyboardButton(
                "🔙 رجوع لإعدادات المالك",
                callback_data="admin_panel"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # الإذاعة
    elif query.data == "adm_broadcast" and user.id == ADMIN_ID:
        text = "📢 **اختر نوع الإذاعة المطلوبة:**"

        keyboard = [
            [InlineKeyboardButton("إذاعة الكل", callback_data="bc_all")],
            [InlineKeyboardButton("إذاعة المحادثة الخاصة", callback_data="bc_private")],
            [InlineKeyboardButton("🔙 رجوع لإعدادات المالك", callback_data="admin_panel")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("bc_") and user.id == ADMIN_ID:
        bc_type = query.data.split("_")[1]
        context.user_data["waiting_broadcast"] = bc_type

        text = f"✍️ أرسل الآن نص رسالة الإذاعة لنوع: **{bc_type}**"

        keyboard = [[
            InlineKeyboardButton(
                "🔙 إلغاء",
                callback_data="adm_broadcast"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # رفع التطبيق
    elif query.data == "adm_upload_app" and user.id == ADMIN_ID:
        context.user_data["waiting_app_file"] = True

        text = (
            "📱 أرسل الآن ملف التطبيق (.apk) في رسالة مباشرة "
            "لكي يتم حفظه وربطه بزر تحميل التطبيق."
        )

        keyboard = [[
            InlineKeyboardButton(
                "🔙 رجوع لإعدادات المالك",
                callback_data="admin_panel"
            )
        ]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # الرجوع للقائمة الرئيسية
    elif query.data == "main_menu":
        context.user_data.clear()

        template = data.get("welcome_msg") or WELCOME_MESSAGE

        welcome_text = template.replace(
            "{name}",
            user.first_name or "صديقي"
        )

        await query.edit_message_text(
            f"{welcome_text}\n\nالقائمة الرئيسية:",
            reply_markup=main_menu_keyboard(user.id)
        )


# =========================
# استقبال رسائل المستخدمين والمالك
# =========================

async def handle_user_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    chat_id = str(user.id)

    if not update.message:
        return

    text = update.message.text or update.message.caption or ""
    data = load_data()

    # حفظ رسالة الترحيب الجديدة
    # يجب أن تكون هذه المعالجة قبل معالجة الروابط والتحويلات
    if user.id == ADMIN_ID and context.user_data.get("waiting_welcome"):

        if not text.strip():
            await update.message.reply_text(
                "⚠️ لا يمكن حفظ رسالة ترحيب فارغة. أرسل النص مرة أخرى."
            )
            return

        if len(text) > 4000:
            await update.message.reply_text(
                "⚠️ الرسالة طويلة جدًا. أرسل رسالة أقصر من 4000 حرف."
            )
            return

        data["welcome_msg"] = text
        save_data(data)

        context.user_data.pop("waiting_welcome", None)

        await update.message.reply_text(
            "✅ تم تحديث رسالة الترحيب وحفظها بنجاح!\n\n"
            "ستظهر الرسالة الجديدة للمستخدمين عند بدء البوت.\n"
            "ولا تحتاج إلى إعادة تشغيل البوت."
        )
        return

    # معالجة الرسالة المحولة من القنوات والمجموعات
    if update.message.forward_from_chat:
        f_chat = update.message.forward_from_chat
        f_id = str(f_chat.id)

        target_name = (
            f"@{f_chat.username}"
            if f_chat.username
            else f_id
        )

        f_title = f_chat.title or target_name
        f_type = "channel" if f_chat.type == "channel" else "group"

        source_id = "src_" + str(
            len(data["users"].get(chat_id, {}).get("sources", {})) + 1
        )

        if chat_id in data["users"]:
            data["users"][chat_id]["sources"][source_id] = {
                "name": target_name,
                "title": f_title,
                "type": f_type,
                "status": "active"
            }

            save_data(data)

        await update.message.reply_text(
            f"✅ تم ربط الـ {f_type} بنجاح عبر التوجيه!\n"
            f"الاسم: `{f_title}`\n"
            f"المعرف: `{target_name}`\n\n"
            "📌 تأكد أن البوت مشرف (Admin) في القناة/المجموعة."
        )
        return

    # معالجة رابط القناة أو المجموعة
    if context.user_data.get("waiting_source_type"):
        st_type = context.user_data["waiting_source_type"]
        context.user_data.pop("waiting_source_type", None)

        target_input = text.strip()

        if "t.me/" in target_input:
            target_input = (
                "@"
                + target_input.rstrip("/").split("/")[-1]
            )

        elif (
            not target_input.startswith("@")
            and not target_input.startswith("-")
        ):
            target_input = "@" + target_input

        source_id = "src_" + str(
            len(data["users"].get(chat_id, {}).get("sources", {})) + 1
        )

        if chat_id in data["users"]:
            data["users"][chat_id]["sources"][source_id] = {
                "name": target_input,
                "title": target_input,
                "type": st_type,
                "status": "active"
            }

            save_data(data)

        await update.message.reply_text(
            "✅ تم إضافة القناة/المجموعة بنجاح من خلال الرابط:\n"
            f"`{target_input}`\n\n"
            "📌 تأكد أن البوت مشرف (Admin) في القناة/المجموعة."
        )
        return

    # استقبال الإذاعة
    if user.id == ADMIN_ID:
        if context.user_data.get("waiting_broadcast"):
            bc_type = context.user_data["waiting_broadcast"]

            context.user_data.pop("waiting_broadcast", None)

            await update.message.reply_text(
                f"🚀 تم استلام رسالة الإذاعة ({bc_type})."
            )
            return


# =========================
# استقبال ملف التطبيق
# =========================

async def handle_admin_documents(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    if user.id != ADMIN_ID:
        return

    data = load_data()

    if (
        context.user_data.get("waiting_app_file")
        and update.message.document
    ):
        file_id = update.message.document.file_id

        data["app_file"] = file_id
        save_data(data)

        context.user_data.pop("waiting_app_file", None)

        await update.message.reply_text(
            "✅ تم حفظ ملف التطبيق وربطه بزر التحميل بنجاح!"
        )


# =========================
# تشغيل البوت
# =========================

def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(set_bot_commands)
        .build()
    )

    job_queue = application.job_queue

    job_queue.run_repeating(
        send_scheduled_sunnahs,
        interval=600,
        first=10
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_user_messages
        )
    )

    application.add_handler(
        MessageHandler(
            filters.FORWARDED,
            handle_user_messages
        )
    )

    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            handle_admin_documents
        )
    )

    print("Bot Resala is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
