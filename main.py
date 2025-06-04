import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from urllib.parse import urlparse
from dotenv import load_dotenv
import html # HTML matnlarini escape qilish uchun

# .env faylidan muhit o'zgaruvchilarini yuklash
load_dotenv()

# --- Bot konfiguratsiyasi ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN_ID = int(os.getenv("BOT_ADMIN_ID"))  # Bot adminining ID'si
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEB_SERVER_HOST = "0.0.0.0" # Hostni "0.0.0.0" qilib qoldiring
WEB_SERVER_PORT = int(os.getenv("PORT", 8000))


# Majburiy a'zo bo'lishi kerak bo'lgan kanallar/guruhlar ro'yxati
# MUHIM: 'id' qiymatlarini o'zingizning kanallaringiz/guruhlaringizning haqiqiy ID'lari bilan almashtiring!
# Kanal/guruh ID'sini olish uchun @RawDataBot kabi botlardan foydalanishingiz mumkin.
# Odatda ID'lar -100 bilan boshlanadi.
CHANNELS_TO_SUBSCRIBE = [
    {"name_uz": "TopTanish Rasmiy Kanali", "name_ru": "Официальный канал TopTanish", "url": "https://t.me/ommaviy_tanishuv_kanali", "id": -1002683172524}, # Misol ID
    {"name_uz": "Oila MJM va ayollar", "name_ru": "Семья МЖМ и женщины", "url": "https://t.me/oilamjmchat", "id": -1002430518370}, # Misol ID
    {"name_uz": "MJM JMJ Oila tanishuv", "name_ru": "МЖМ ЖМЖ Семейные Знакомства", "url": "https://t.me/oila_ayollar_mjm_jmj_12_viloyat", "id": -1002571964009}, # Misol ID
    {"name_uz": "MJM MJMJ Oila tanishuv", "name_ru": "МЖМ ЖМЖ Семейные Знакомства", "url": "https://t.me/oila_mjm_vodiy_12_viloyat_jmj", "id": -1002474257516} # Misol ID 
        
]


# A'zoligi tekshirilmasligi kerak bo'lgan ID'lar ro'yxati (bu asosan kanallar/guruhlar uchun)
# Bu yerga ma'lum bir kanal yoki guruhni majburiy a'zolikdan ozod qilish uchun ID'sini kiriting.
EXEMPT_IDS = [
    -1002474257516, # Misol kanal ID'si (bunga a'zolik shart emas)
    6115064055,
    1191351378, # Misol foydalanuvchi ID'si (bu foydalanuvchi uchun cheklov yo'q)
    1087968824      # Misol bot ID'si
] 

# Majburiy kanal/guruh a'zoligi tekshiruvidan ozod qilingan foydalanuvchi ID'lari ro'yxati
# Bu yerga to'g'ridan-to'g'ri yozishga ruxsat berilishi kerak bo'lgan foydalanuvchilarning ID'larini kiriting.
# Misol: [123456789, 987654321]
FREE_ACCESS_USER_IDS = [1191351378, 
                        6115064055,
                        1087968824
] 

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# Dispatcher va Memory Storage (ma'lumotlarni xotirada saqlaydi, bot o'chsa o'chadi)
dp = Dispatcher(storage=MemoryStorage())

# --- Matnlar lug'ati ---
TEXTS = {
    "uz": {
        "start_welcome": "Assalomu alaykum! Botdan to'liq foydalanish uchun quyidagi shartlarni bajaring:",
        "not_a_member_multiple": "<b>{user_full_name}</b>, yozish uchun quyidagi kanallar/guruhlarga a'zo bo'lishingiz kerak:\n{missing_channels}\nIltimos, a'zo bo'lib, 'Qayta tekshirish' tugmasini bosing.",
        "all_conditions_met_message": "Siz barcha shartlarni bajardingiz va botdan foydalanishingiz mumkin!",
        "check_again_button": "✅ Qayta tekshirish",
        "error_deleting_message": "Xabarni o'chirishda xato yuz berdi.",
        "admin_notification_channel_check_error": "Kanal a'zoligini tekshirishda xato yuz berdi. Bot kanallarda admin ekanligiga ishonch hosil qiling.",
        "admin_new_message_notification": "Yangi ariza keldi:\n\nFoydalanuvchi: {user_full_name} (<a href='tg://user?id={user_id}'>{user_id}</a>)\n\nXabar: {message_text}",
        "admin_reply_button": "Javob qaytarish",
        "user_message_received": "Xabaringiz adminga yuborildi. Tez orada javob olasiz.",
        "admin_reply_prompt": "Foydalanuvchiga yubormoqchi bo'lgan xabaringizni yozing:",
        "admin_reply_sent": "Xabar foydalanuvchiga yuborildi.",
        "admin_reply_error": "Xabarni yuborishda xato yuz berdi: {error}",
        "unknown_command": "Noma'lum buyruq.",
        "invalid_reply_format": "Noto'g'ri javob formati. Iltimos, /reply komandasidan keyin foydalanuvchi ID'sini va xabarni kiriting."
    },
    "ru": {
        "start_welcome": "Привет! Чтобы пользоваться ботом в полной мере, выполните следующие условия:",
        "not_a_member_multiple": "<b>{user_full_name}</b>, чтобы писать, вам нужно подписаться на следующие каналы/группы:\n{missing_channels}\nПожалуйста, подпишитесь и нажмите кнопку 'Проверить снова'.",
        "all_conditions_met_message": "Вы выполнили все условия и можете пользоваться ботом!",
        "check_again_button": "✅ Проверить снова",
        "error_deleting_message": "Произошла ошибка при удалении сообщения.",
        "admin_notification_channel_check_error": "Ошибка при проверке членства в канале. Убедитесь, что бот является администратором в каналах.",
        "admin_new_message_notification": "Новая заявка получена:\n\nПользователь: {user_full_name} (<a href='tg://user?id={user_id}'>{user_id}</a>)\n\nСообщение: {message_text}",
        "admin_reply_button": "Ответить",
        "user_message_received": "Ваше сообщение отправлено админу. Вы получите ответ в ближайшее время.",
        "admin_reply_prompt": "Напишите сообщение, которое вы хотите отправить пользователю:",
        "admin_reply_sent": "Сообщение отправлено пользователю.",
        "admin_reply_error": "Произошла ошибка при отправке сообщения: {error}",
        "unknown_command": "Неизвестная команда.",
        "invalid_reply_format": "Неверный формат ответа. Пожалуйста, используйте команду /reply с ID пользователя и сообщением."
    }
}

# --- Yordamchi funksiyalar ---

async def get_user_lang(user_id: int, state: FSMContext) -> str:
    """Foydalanuvchining tilini FSM kontekstidan oladi, topilmasa 'uz' qaytaradi."""
    user_data = await state.get_data()
    return user_data.get("lang", "uz")

async def check_all_channel_memberships(user_id: int, lang: str) -> tuple[bool, list]:
    """
    Foydalanuvchining barcha majburiy kanallar/guruhlarga a'zoligini tekshiradi.
    Qaytadi: (barcha_shartlar_bajarildimi, a'zo_bo'lmagan_kanallar_info_listasi)
    """
    missing_channels_info = []
    for channel_info in CHANNELS_TO_SUBSCRIBE:
        channel_id = channel_info["id"]

        # Agar kanal ID'si EXEMPT_IDS ro'yxatida bo'lsa, tekshirmaymiz
        if channel_id in EXEMPT_IDS:
            continue
        
        # Agar ID foydalanuvchi ID'si bo'lsa (ya'ni botning o'zi), uni avtomatik a'zo deb hisoblaymiz
        # Bu qism avvalgi kodda botning o'zini tekshirishdan ozod qilish uchun edi.
        if isinstance(channel_id, int) and channel_id > 0: # User ID'lar pozitiv butun sonlar bo'ladi
            if user_id == channel_id:
                continue 
        
        try:
            user_status = await bot.get_chat_member(channel_id, user_id)
            if user_status.status not in ["member", "administrator", "creator"]:
                missing_channels_info.append(channel_info)
        except Exception as e:
            print(f"Kanal {channel_info[f'name_{lang}']} ({channel_id}) tekshirishda xato: {e}")
            # Adminni xabardor qilish
            await bot.send_message(BOT_ADMIN_ID, TEXTS[lang]["admin_notification_channel_check_error"])
            missing_channels_info.append(channel_info) # Xato bo'lsa ham a'zo emas deb hisoblaymiz
    
    return not missing_channels_info, missing_channels_info

def get_check_keyboard(lang: str, missing_channels_info: list) -> InlineKeyboardMarkup:
    """
    Foydalanuvchiga shartlarni bajarish uchun tugmalar panelini yaratadi.
    """
    keyboard = []

    # Agar a'zo bo'linmagan kanallar bo'lsa, ular uchun tugmalar qo'shamiz
    for channel_info in missing_channels_info:
        # Faqat URL mavjud bo'lsa tugmani qo'shamiz
        if channel_info.get("url"):
            keyboard.append([InlineKeyboardButton(text=channel_info[f"name_{lang}"], url=channel_info["url"])])
    
    # Qayta tekshirish tugmasi
    keyboard.append([InlineKeyboardButton(text=TEXTS[lang]["check_again_button"], callback_data="check_membership")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def delete_message_after_delay(message: Message, delay: int = 0.1):
    """Xabarni qisqa muddatdan keyin o'chiradi."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        print(f"Xabarni o'chirishda xato yuz berdi: {e}")
        # Agar xabar o'chirilmasa, adminni xabardor qilish
        # await bot.send_message(BOT_ADMIN_ID, TEXTS["uz"]["error_deleting_message"])

async def process_message_for_admin(message: Message, lang: str):
    """
    Foydalanuvchining xabarini adminga yuboradi.
    """
    user_id = message.from_user.id
    
    # Foydalanuvchining ismini HTML-escape qilamiz va profiliga havola beramiz
    user_full_name_html = html.escape(message.from_user.full_name)
    user_profile_link = f"<a href='tg://user?id={user_id}'>{user_full_name_html}</a>"

    message_text_html = html.escape(message.text) if message.text else "<i>(media fayl)</i>"

    admin_notification_text = TEXTS[lang]["admin_new_message_notification"].format(
        user_full_name=user_profile_link,
        user_id=user_id,
        message_text=message_text_html
    )
    reply_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[lang]["admin_reply_button"],
                    callback_data=f"reply_to_user:{user_id}"
                )
            ]
        ]
    )

    if message.text:
        await bot.send_message(
            chat_id=BOT_ADMIN_ID,
            text=admin_notification_text,
            reply_markup=reply_keyboard
        )
    elif message.photo:
        await bot.send_photo(
            chat_id=BOT_ADMIN_ID,
            photo=message.photo[-1].file_id, # Eng yuqori sifatli fotosurat
            caption=admin_notification_text, # Captioni notifikatsiya matni bilan to'ldiramiz
            reply_markup=reply_keyboard
        )
    elif message.video:
        await bot.send_video(
            chat_id=BOT_ADMIN_ID,
            video=message.video.file_id,
            caption=admin_notification_text,
            reply_markup=reply_keyboard
        )
    elif message.document:
        await bot.send_document(
            chat_id=BOT_ADMIN_ID,
            document=message.document.file_id,
            caption=admin_notification_text,
            reply_markup=reply_keyboard
        )
    elif message.voice:
        await bot.send_voice(
            chat_id=BOT_ADMIN_ID,
            voice=message.voice.file_id,
            caption=admin_notification_text,
            reply_markup=reply_keyboard
        )
    elif message.sticker:
        await bot.send_sticker(
            chat_id=BOT_ADMIN_ID,
            sticker=message.sticker.file_id,
            caption=admin_notification_text, # Stikerlarga caption ba'zida qo'llash qiyin, lekin urinib ko'ramiz
            reply_markup=reply_keyboard
        )
    # Boshqa media turlari uchun ham shunga o'xshash qismlarni qo'shishingiz mumkin (masalan, Audio, VideoNote)
    else:
        # Agar boshqa turdagi media bo'lsa, uni yuborish
        # Shuningdek, ma'lumotni loglarga yozish
        print(f"Adminga yuborilishi kerak bo'lgan noma'lum xabar turi: {message.content_type}")
        await bot.send_message(
            chat_id=BOT_ADMIN_ID,
            text=f"Yangi ariza keldi (noma'lum tur):\n\nFoydalanuvchi: {user_profile_link}\n\nType: {message.content_type}",
            reply_markup=reply_keyboard
        )

    await message.answer(TEXTS[lang]["user_message_received"])

# --- Handlerlar ---

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Botni ishga tushirish komandasi uchun handler."""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id, state) # Foydalanuvchi tilini olamiz

    # Foydalanuvchining ismini HTML-escape qilamiz va profiliga havola beramiz
    user_full_name_linked = f"<a href='tg://user?id={user_id}'>{html.escape(message.from_user.full_name)}</a>"


    await message.answer(TEXTS[lang]["start_welcome"])

    # --- YANGI QISM: Foydalanuvchi FREE_ACCESS_USER_IDS ro'yxatida bo'lsa, shartlarni tekshirmaymiz ---
    if user_id in FREE_ACCESS_USER_IDS:
        await message.answer(TEXTS[lang]["all_conditions_met_message"])
        return
    # --- YANGI QISM TUGADI ---

    # Shartlarni darhol tekshiramiz (faqat kanal a'zoligi)
    all_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    if all_met:
        await message.answer(TEXTS[lang]["all_conditions_met_message"])
    else:
        response_text = ""
        if missing_channels_info:
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                user_full_name=user_full_name_linked,
                missing_channels="\n".join([f"- {c[f'name_{lang}']}" for c in missing_channels_info])
            )
        
        await message.answer(response_text.strip(), reply_markup=get_check_keyboard(lang, missing_channels_info))

@dp.callback_query(F.data == "check_membership")
async def check_membership_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """'Qayta tekshirish' tugmasi bosilganda shartlarni qayta tekshirish."""
    user_id = callback_query.from_user.id
    lang = await get_user_lang(user_id, state)

    user_full_name_linked = f"<a href='tg://user?id={user_id}'>{html.escape(callback_query.from_user.full_name)}</a>"

    # --- YANGI QISM: Foydalanuvchi FREE_ACCESS_USER_IDS ro'yxatida bo'lsa, shartlarni tekshirmaymiz ---
    if user_id in FREE_ACCESS_USER_IDS:
        current_message_text = callback_query.message.html_text
        new_message_text = TEXTS[lang]["all_conditions_met_message"]
        if current_message_text.strip() != new_message_text.strip():
            await callback_query.message.edit_text(new_message_text)
        await callback_query.answer()
        return
    # --- YANGI QISM TUGADI ---

    all_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    if all_met:
        current_message_text = callback_query.message.html_text
        new_message_text = TEXTS[lang]["all_conditions_met_message"]

        if current_message_text.strip() != new_message_text.strip():
            await callback_query.message.edit_text(new_message_text)
        else:
            pass # Matn bir xil bo'lsa hech narsa qilmaymiz

    else:
        response_text = ""
        if missing_channels_info:
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                user_full_name=user_full_name_linked,
                missing_channels="\n".join([f"- {c[f'name_{lang}']}" for c in missing_channels_info])
            )

        current_message_text = callback_query.message.html_text
        current_reply_markup = callback_query.message.reply_markup
        new_reply_markup = get_check_keyboard(lang, missing_channels_info)

        if current_message_text.strip() != response_text.strip() or current_reply_markup != new_reply_markup:
            await callback_query.message.edit_text(response_text.strip(), reply_markup=new_reply_markup)
        else:
            pass # Matn va tugmalar bir xil bo'lsa hech narsa qilmaymiz

    await callback_query.answer() # Callback query ni yopish

@dp.message(F.text, F.chat.type == "private", F.from_user.id == BOT_ADMIN_ID)
async def admin_reply_to_user(message: Message, state: FSMContext):
    """Adminning foydalanuvchiga javob berish funksiyasi."""
    lang = await get_user_lang(message.from_user.id, state)
    
    # Matnni '/reply USER_ID XABAR' formatida kutamiz
    parts = message.text.split(maxsplit=2) # '/reply', 'USER_ID', 'XABAR'
    
    if len(parts) < 3 or parts[0] != "/reply":
        await message.answer(TEXTS[lang]["invalid_reply_format"])
        return

    try:
        target_user_id = int(parts[1])
        reply_text = parts[2]
    except ValueError:
        await message.answer(TEXTS[lang]["invalid_reply_format"])
        return

    try:
        await bot.send_message(target_user_id, f"<b>Admin javobi:</b>\n\n{html.escape(reply_text)}")
        await message.answer(TEXTS[lang]["admin_reply_sent"])
    except Exception as e:
        await message.answer(TEXTS[lang]["admin_reply_error"].format(error=e))


@dp.message()
async def handle_all_messages(message: Message, state: FSMContext) -> None:
    """
    Barcha kiruvchi xabarlar uchun umumiy handler.
    Shartlarni tekshiradi va bajarilmasa xabarni o'chiradi.
    Agar shartlar bajarilgan bo'lsa yoki foydalanuvchi ozod qilingan bo'lsa, xabarni adminga yuboradi.
    """
    user_id = message.from_user.id
    lang = await get_user_lang(user_id, state)

    # Agar komanda bo'lsa (masalan, /start yoki /reply), uni o'tkazib yuboramiz
    if message.text and message.text.startswith('/'):
        # Agar admin emas va /reply komandasini ishlatgan bo'lsa, ogohlantirish berish
        if user_id != BOT_ADMIN_ID and message.text.startswith('/reply'):
            await message.answer(TEXTS[lang]["unknown_command"])
        return

    # Foydalanuvchi FREE_ACCESS_USER_IDS ro'yxatida bo'lsa, shartlarni tekshirmaymiz
    if user_id in FREE_ACCESS_USER_IDS:
        await process_message_for_admin(message, lang)
        return

    # Foydalanuvchining ismini HTML-escape qilamiz va profiliga havola beramiz
    user_full_name_linked = f"<a href='tg://user?id={user_id}'>{html.escape(message.from_user.full_name)}</a>"


    # Shartlarni tekshiramiz (faqat kanal a'zoligi)
    all_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    if all_met:
        # Barcha shartlar bajarilgan, foydalanuvchi erkin yozishi mumkin.
        # Xabarni adminga yuboramiz.
        await process_message_for_admin(message, lang)
    else:
        # Shartlar bajarilmagan. Xabarni o'chiriramiz va foydalanuvchini xabardor qilamiz.
        await delete_message_after_delay(message)

        response_text = ""
        if missing_channels_info:
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                user_full_name=user_full_name_linked,
                missing_channels="\n".join([f"- {c[f'name_{lang}']}" for c in missing_channels_info])
            )
        
        # Shartlar bajarilmaganligi haqida xabar yuboramiz
        await message.answer(response_text.strip(), reply_markup=get_check_keyboard(lang, missing_channels_info))

@dp.callback_query(F.data.startswith("reply_to_user:"))
async def process_admin_reply_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Admin xabarga javob berish tugmasini bosganda."""
    user_id_to_reply = int(callback_query.data.split(":")[1])
    lang = await get_user_lang(callback_query.from_user.id, state)

    # Admin qaysi foydalanuvchiga javob berayotganini eslab qolish
    await state.set_data({"admin_reply_target_user_id": user_id_to_reply, "lang": lang})

    await callback_query.message.answer(TEXTS[lang]["admin_reply_prompt"])
    await callback_query.answer() # Callback query ni yopish

# --- Botni ishga tushirish ---
async def main() -> None:
    if WEBHOOK_URL:
        app = web.Application()
        parsed_url = urlparse(WEBHOOK_URL)
        webhook_path_for_handler = parsed_url.path if parsed_url.path else "/"

        webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_requests_handler.register(app, path=webhook_path_for_handler)
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
        await site.start()

        print(f"Webhook URL: {WEBHOOK_URL}")
        await bot.set_webhook(WEBHOOK_URL)
        print("Bot started and listening via webhook...")

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()
            await bot.session.close()
            await dp.storage.close()
            print("Bot stopped and resources released.")

    else:
        print("Bot started and listening via polling...")
        try:
            await dp.start_polling(bot)
        finally:
            await dp.storage.close()
            await bot.session.close()
            print("Bot stopped and resources released.")


if __name__ == "__main__":
    asyncio.run(main())
