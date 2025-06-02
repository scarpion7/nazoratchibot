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
import html # O'zgartirish: aiogram.utils.html o'rniga Pythonning standart html modulini import qilamiz

# .env faylidan muhit o'zgaruvchilarini yuklash
load_dotenv()

# --- Bot konfiguratsiyasi ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN_ID = int(os.getenv("BOT_ADMIN_ID"))  # Bot adminining ID'si
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8000))


# Majburiy a'zo bo'lishi kerak bo'lgan kanallar/guruhlar ro'yxati
# MUHIM: 'id' qiymatlarini o'zingizning kanallaringiz/guruhlaringizning haqiqiy ID'lari bilan almashtiring!
# Kanal/guruh ID'sini olish uchun @RawDataBot kabi botlardan foydalanishingiz mumkin.
# Odatda ID'lar -100 bilan boshlanadi.
CHANNELS_TO_SUBSCRIBE = [
    {"name_uz": "TopTanish Rasmiy Kanali", "name_ru": "Официальный канал TopTanish", "url": "https://t.me/ommaviy_tanishuv_kanali", "id": -1002683172524}, # Misol ID
    {"name_uz": "Oila MJM va ayollar", "name_ru": "Семья МЖМ и женщины", "url": "https://t.me/oilamjmchat", "id": -1002430518370}, # Misol ID
    {"name_uz": "MJM JMJ Oila tanishuv", "name_ru": "МЖМ ЖМЖ Семейные Знакомства", "url": "https://t.me/oila_ayollar_mjm_jmj_12_viloyat", "id": -1002474257516},
    {"name_uz": "Tanishuvlar olami", "name_ru": "Мир знакомств", "url": "https://t.me/Tanishuvlar18plus_bot", "id": 7845397405}# Misol ID
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
        # Yangilangan xabar matni: faqat ism va so'ralgan jumlalar
        "not_a_member_multiple": "<b>{user_full_name}</b>, yozish uchun quyidagi kanallar/guruhlarga a'zo bo'lishingiz kerak:\n{missing_channels}\nIltimos, a'zo bo'lib, 'Qayta tekshirish' tugmasini bosing.",
        "all_conditions_met_message": "Siz barcha shartlarni bajardingiz va botdan foydalanishingiz mumkin!",
        "check_again_button": "✅ Qayta tekshirish",
        "error_deleting_message": "Xabarni o'chirishda xato yuz berdi.",
        "admin_notification_channel_check_error": "Kanal a'zoligini tekshirishda xato yuz berdi. Bot kanallarda admin ekanligiga ishonch hosil qiling."
    },
    "ru": {
        "start_welcome": "Привет! Чтобы пользоваться ботом в полной мере, выполните следующие условия:",
        # Yangilangan xabar matni: faqat ism va so'ralgan jumlalar
        "not_a_member_multiple": "<b>{user_full_name}</b>, чтобы писать, вам нужно подписаться на следующие каналы/группы:\n{missing_channels}\nПожалуйста, подпишитесь и нажмите кнопку 'Проверить снова'.",
        "all_conditions_met_message": "Вы выполнили все условия и можете пользоваться ботом!",
        "check_again_button": "✅ Проверить снова",
        "error_deleting_message": "Произошла ошибка при удалении сообщения.",
        "admin_notification_channel_check_error": "Ошибка при проверке членства в канале. Убедитесь, что бот является администратором в каналах."
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
        channel_name = channel_info[f"name_{lang}"]
        try:
            user_status = await bot.get_chat_member(channel_id, user_id)
            if user_status.status not in ["member", "administrator", "creator"]:
                missing_channels_info.append(channel_info)
        except Exception as e:
            print(f"Kanal {channel_name} ({channel_id}) tekshirishda xato: {e}")
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


# --- Handlerlar ---

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Botni ishga tushirish komandasi uchun handler."""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id, state) # Foydalanuvchi tilini olamiz

    # Foydalanuvchining ismini HTML-escape qilamiz
    escaped_user_full_name = html.escape(message.from_user.full_name) # O'zgartirish: html.escape ishlatildi
    # user_profile_link endi ishlatilmaydi


    await message.answer(TEXTS[lang]["start_welcome"])

    # Shartlarni darhol tekshiramiz (faqat kanal a'zoligi)
    all_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    if all_met:
        await message.answer(TEXTS[lang]["all_conditions_met_message"])
    else:
        response_text = ""
        if missing_channels_info:
            missing_names = [c[f"name_{lang}"] for c in missing_channels_info]
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                user_full_name=escaped_user_full_name,
                # user_profile_link endi ishlatilmaydi
                missing_channels="\n".join([f"- {name}" for name in missing_names])
            ) + "\n\n"
        
        await message.answer(response_text.strip(), reply_markup=get_check_keyboard(lang, missing_channels_info))

@dp.callback_query(F.data == "check_membership")
async def check_membership_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """'Qayta tekshirish' tugmasi bosilganda shartlarni qayta tekshirish."""
    user_id = callback_query.from_user.id
    lang = await get_user_lang(user_id, state)

    escaped_user_full_name = html.escape(callback_query.from_user.full_name)

    all_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    if all_met:
        # Agar barcha shartlar bajarilgan bo'lsa
        current_message_text = callback_query.message.html_text
        new_message_text = TEXTS[lang]["all_conditions_met_message"]

        # Agar matn hozirgidan farq qilsa, tahrirlaymiz
        if current_message_text.strip() != new_message_text.strip():
            await callback_query.message.edit_text(new_message_text)
        else:
            # Agar matn bir xil bo'lsa, hech narsa qilmaymiz, shunchaki answer() qilamiz
            pass
    else:
        # Agar shartlar bajarilmagan bo'lsa
        response_text = ""
        if missing_channels_info:
            missing_names = [c[f"name_{lang}"] for c in missing_channels_info]
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                user_full_name=escaped_user_full_name,
                missing_channels="\n".join([f"- {name}" for name in missing_names])
            ) + "\n\n"

        current_message_text = callback_query.message.html_text
        current_reply_markup = callback_query.message.reply_markup
        new_reply_markup = get_check_keyboard(lang, missing_channels_info)

        # Agar matn yoki tugmalar paneli o'zgargan bo'lsa, tahrirlaymiz
        if current_message_text.strip() != response_text.strip() or current_reply_markup != new_reply_markup:
            await callback_query.message.edit_text(response_text.strip(), reply_markup=new_reply_markup)
        else:
            # Agar matn va tugmalar bir xil bo'lsa, xato bermaslik uchun hech narsa qilmaymiz
            pass

    await callback_query.answer() # Callback query ni yopish
@dp.message()
async def handle_all_messages(message: Message, state: FSMContext) -> None:
    """
    Barcha kiruvchi xabarlar uchun umumiy handler.
    Shartlarni tekshiradi va bajarilmasa xabarni o'chiradi.
    """
    user_id = message.from_user.id
    lang = await get_user_lang(user_id, state)

    # Agar komanda bo'lsa (masalan, /start), uni o'tkazib yuboramiz
    if message.text and message.text.startswith('/'):
        return

    # Foydalanuvchining ismini HTML-escape qilamiz
    escaped_user_full_name = html.escape(message.from_user.full_name) # O'zgartirish: html.escape ishlatildi
    # user_profile_link endi ishlatilmaydi


    # Shartlarni tekshiramiz (faqat kanal a'zoligi)
    all_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    if all_met:
        # Barcha shartlar bajarilgan, foydalanuvchi erkin yozishi mumkin.
        # Bu yerda hech narsa qilmaymiz, xabar o'chirilmaydi.
        pass
    else:
        # Shartlar bajarilmagan. Xabarni o'chiramiz va foydalanuvchini xabardor qilamiz.
        await delete_message_after_delay(message)

        response_text = ""
        if missing_channels_info:
            missing_names = [c[f"name_{lang}"] for c in missing_channels_info]
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                user_full_name=escaped_user_full_name,
                # user_profile_link endi ishlatilmaydi
                missing_channels="\n".join([f"- {name}" for name in missing_names])
            ) + "\n\n"
        
        # Shartlar bajarilmaganligi haqida xabar yuboramiz
        await message.answer(response_text.strip(), reply_markup=get_check_keyboard(lang, missing_channels_info))


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
