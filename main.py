import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, ChatMemberUpdated
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from urllib.parse import urlparse
from dotenv import load_dotenv

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
    {"name_uz": "TopTanish Rasmiy Kanali", "name_ru": "Официальный канал TopTanish",
     "url": "https://t.me/ommaviy_tanishuv_kanali", "id": -1001234567890},  # Misol ID
    {"name_uz": "Oila MJM Vodiy Guruhi", "name_ru": "Группа Семья МЖМ Долина",
     "url": "https://t.me/oila_mjm_vodiy_12_viloyat_jmj", "id": -1009876543210},  # Misol ID
    {"name_uz": "Ayollar Klubimiz", "name_ru": "Наш Женский Клуб",
     "url": "https://t.me/oila_ayollar_mjm_jmj_12_viloyat", "id": -1001122334455}  # Misol ID
]

# Foydalanuvchilar odam qo'shishi kerak bo'lgan guruh ID'si
# MUHIM: Bu ID'ni ham o'zingizning guruh ID'ingiz bilan almashtiring!
TARGET_GROUP_ID = -1009876543210  # Misol ID
# Agar guruh username'i bo'lsa, shu yerga yozing (agar guruh ochiq bo'lsa)
TARGET_GROUP_USERNAME = "Oila MJM Vodiy Guruhi"  # Misol: "my_awesome_group"
# Agar guruh yopiq bo'lsa va doimiy taklif linki bo'lsa, shu yerga yozing:
TARGET_GROUP_INVITE_LINK = "https://t.me/+your_invite_link"  # Misol: "https://t.me/+AbCdEfGhIjK"

# Har bir foydalanuvchi qo'shishi kerak bo'lgan odam soni
REQUIRED_ADDS = 5

# Bot obyektini yaratish
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# Dispatcher va Memory Storage (ma'lumotlarni xotirada saqlaydi, bot o'chsa o'chadi)
dp = Dispatcher(storage=MemoryStorage())

# Foydalanuvchilarning qo'shgan odamlari sonini saqlash uchun lug'at (vaqtinchalik)
user_added_counts = {}  # {user_id: count}

# --- Matnlar lug'ati ---
TEXTS = {
    "uz": {
        "start_welcome": "Assalomu alaykum! Botdan to'liq foydalanish uchun quyidagi shartlarni bajaring:",
        "not_a_member_multiple": "Siz quyidagi kanallar/guruhlarga a'zo emassiz:\n{missing_channels}\nIltimos, a'zo bo'lib, 'Qayta tekshirish' tugmasini bosing.",
        "needs_more_adds": "Siz botdan foydalanish uchun guruhga yana <b>{count}</b> ta odam qo'shishingiz kerak. Odam qo'shish uchun guruhga o'ting va do'stlaringizni qo'shing.",
        "all_conditions_met_message": "Siz barcha shartlarni bajardingiz va botdan foydalanishingiz mumkin!",
        "check_again_button": "✅ Qayta tekshirish",
        "group_add_button": "Guruhga odam qo'shish",
        "error_deleting_message": "Xabarni o'chirishda xato yuz berdi.",
        "admin_notification_new_add": "Yangi qo'shuvchi: {inviter_name} ({inviter_id})\nQo'shilganlar soni: {count}",
        "admin_notification_target_group_error": "Guruhga odam qo'shishni hisoblashda xato yuz berdi. Bot {TARGET_GROUP_ID} guruhida admin ekanligiga va 'A'zolarni boshqarish' huquqiga ega ekanligiga ishonch hosil qiling.",
        "admin_notification_channel_check_error": "Kanal a'zoligini tekshirishda xato yuz berdi. Bot kanallarda admin ekanligiga ishonch hosil qiling."
    },
    "ru": {
        "start_welcome": "Привет! Чтобы пользоваться ботом в полной мере, выполните следующие условия:",
        "not_a_member_multiple": "Вы не подписаны на следующие каналы/группы:\n{missing_channels}\nПожалуйста, подпишитесь и нажмите кнопку 'Проверить снова'.",
        "needs_more_adds": "Вам нужно добавить еще <b>{count}</b> человек в группу, чтобы пользоваться ботом. Перейдите в группу и добавьте друзей.",
        "all_conditions_met_message": "Вы выполнили все условия и можете пользоваться ботом!",
        "check_again_button": "✅ Проверить снова",
        "group_add_button": "Добавить людей в группу",
        "error_deleting_message": "Произошла ошибка при удалении сообщения.",
        "admin_notification_new_add": "Новый добавивший: {inviter_name} ({inviter_id})\nКоличество добавлений: {count}",
        "admin_notification_target_group_error": "Ошибка при подсчете добавлений в группу. Убедитесь, что бот является администратором в группе {TARGET_GROUP_ID} и имеет право 'Управление участниками'.",
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
            missing_channels_info.append(channel_info)  # Xato bo'lsa ham a'zo emas deb hisoblaymiz

    return not missing_channels_info, missing_channels_info


async def check_user_conditions(user_id: int, lang: str) -> tuple[bool, list, int]:
    """
    Foydalanuvchining barcha shartlarni (kanal a'zoligi va odam qo'shish) bajarganligini tekshiradi.
    Qaytadi: (barcha_shartlar_bajarildimi, a'zo_bo'lmagan_kanallar_info_listasi, qo'shilishi_kerak_bo'lgan_odamlar_soni)
    """
    # 1. Kanal a'zoligi tekshiruvi
    channels_met, missing_channels_info = await check_all_channel_memberships(user_id, lang)

    # 2. Odam qo'shish soni tekshiruvi
    added_count = user_added_counts.get(user_id, 0)
    adds_needed = max(0, REQUIRED_ADDS - added_count)  # 0 dan kam bo'lmasligi uchun

    all_conditions_met = channels_met and (adds_needed <= 0)

    return all_conditions_met, missing_channels_info, adds_needed


def get_check_keyboard(lang: str, missing_channels_info: list, adds_needed: int) -> InlineKeyboardMarkup:
    """
    Foydalanuvchiga shartlarni bajarish uchun tugmalar panelini yaratadi.
    """
    keyboard = []

    # Agar a'zo bo'linmagan kanallar bo'lsa, ular uchun tugmalar qo'shamiz
    for channel_info in missing_channels_info:
        keyboard.append([InlineKeyboardButton(text=channel_info[f"name_{lang}"], url=channel_info["url"])])

    # Agar odam qo'shish kerak bo'lsa, guruhga o'tish tugmasini qo'shamiz
    if adds_needed > 0:
        # Guruhga taklif linkini ishlatishni afzal ko'ramiz
        group_link = TARGET_GROUP_INVITE_LINK if TARGET_GROUP_INVITE_LINK else f"https://t.me/{TARGET_GROUP_USERNAME}"
        keyboard.append([InlineKeyboardButton(text=TEXTS[lang]["group_add_button"], url=group_link)])

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
    lang = await get_user_lang(user_id, state)  # Foydalanuvchi tilini olamiz

    await message.answer(TEXTS[lang]["start_welcome"])

    # Shartlarni darhol tekshiramiz
    all_met, missing_channels_info, adds_needed = await check_user_conditions(user_id, lang)

    if all_met:
        await message.answer(TEXTS[lang]["all_conditions_met_message"])
    else:
        response_text = ""
        if missing_channels_info:
            missing_names = [c[f"name_{lang}"] for c in missing_channels_info]
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                missing_channels="\n".join([f"- {name}" for name in missing_names])) + "\n\n"
        if adds_needed > 0:
            response_text += TEXTS[lang]["needs_more_adds"].format(count=adds_needed) + "\n\n"

        await message.answer(response_text.strip(),
                             reply_markup=get_check_keyboard(lang, missing_channels_info, adds_needed))


@dp.callback_query(F.data == "check_membership")
async def check_membership_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """'Qayta tekshirish' tugmasi bosilganda shartlarni qayta tekshirish."""
    user_id = callback_query.from_user.id
    lang = await get_user_lang(user_id, state)

    all_met, missing_channels_info, adds_needed = await check_user_conditions(user_id, lang)

    if all_met:
        await callback_query.message.edit_text(TEXTS[lang]["all_conditions_met_message"])
    else:
        response_text = ""
        if missing_channels_info:
            missing_names = [c[f"name_{lang}"] for c in missing_channels_info]
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                missing_channels="\n".join([f"- {name}" for name in missing_names])) + "\n\n"
        if adds_needed > 0:
            response_text += TEXTS[lang]["needs_more_adds"].format(count=adds_needed) + "\n\n"

        await callback_query.message.edit_text(response_text.strip(),
                                               reply_markup=get_check_keyboard(lang, missing_channels_info,
                                                                               adds_needed))

    await callback_query.answer()  # Callback query ni yopish


@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=True), F.chat.id == TARGET_GROUP_ID)
async def handle_new_chat_members(event: ChatMemberUpdated):
    """
    Guruhga yangi a'zolar qo'shilganda hisoblagichni yangilash uchun handler.
    Faqatgina TARGET_GROUP_ID dagi o'zgarishlarni tinglaydi.
    """
    try:
        # Agar foydalanuvchi guruhga yangi qo'shilgan bo'lsa (oldin a'zo emas edi, endi a'zo)
        if event.old_chat_member.status in ["left", "kicked",
                                            "restricted"] and event.new_chat_member.status == "member":
            inviter_id = event.from_user.id  # Kim qo'shgan bo'lsa, o'sha foydalanuvchining ID'si
            added_user_id = event.new_chat_member.user.id  # Qo'shilgan foydalanuvchining ID'si

            # Botning o'zini yoki foydalanuvchi o'zini o'zi qo'shganini hisoblamaymiz
            if inviter_id == added_user_id or inviter_id == bot.id:
                return

            # Hisoblagichni oshiramiz
            user_added_counts[inviter_id] = user_added_counts.get(inviter_id, 0) + 1
            print(
                f"Foydalanuvchi {inviter_id} {added_user_id} ni qo'shdi. Jami qo'shilganlar: {user_added_counts[inviter_id]}")

            # Qo'shgan foydalanuvchiga xabar berish (ixtiyoriy)
            # Bu yerda adminni xabardor qilamiz
            inviter_name = event.from_user.full_name
            lang = "uz"  # Admin uchun tilni belgilash
            await bot.send_message(BOT_ADMIN_ID, TEXTS[lang]["admin_notification_new_add"].format(
                inviter_name=inviter_name,
                inviter_id=inviter_id,
                count=user_added_counts[inviter_id]
            ))
    except Exception as e:
        print(f"Guruhga odam qo'shishni hisoblashda xato: {e}")
        # Adminni xabardor qilish
        await bot.send_message(BOT_ADMIN_ID, TEXTS["uz"]["admin_notification_target_group_error"].format(
            TARGET_GROUP_ID=TARGET_GROUP_ID))


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

    # Shartlarni tekshiramiz
    all_met, missing_channels_info, adds_needed = await check_user_conditions(user_id, lang)

    if all_met:
        # Barcha shartlar bajarilgan, foydalanuvchi erkin yozishi mumkin.
        # Bu yerda hech narsa qilmaymiz, xabar o'chirilmaydi.
        # Agar xabarga javob berish kerak bo'lsa, shu yerga qo'shing.
        pass
    else:
        # Shartlar bajarilmagan. Xabarni o'chiramiz va foydalanuvchini xabardor qilamiz.
        await delete_message_after_delay(message)

        response_text = ""
        if missing_channels_info:
            missing_names = [c[f"name_{lang}"] for c in missing_channels_info]
            response_text += TEXTS[lang]["not_a_member_multiple"].format(
                missing_channels="\n".join([f"- {name}" for name in missing_names])) + "\n\n"
        if adds_needed > 0:
            response_text += TEXTS[lang]["needs_more_adds"].format(count=adds_needed) + "\n\n"

        # Shartlar bajarilmaganligi haqida xabar yuboramiz
        await message.answer(response_text.strip(),
                             reply_markup=get_check_keyboard(lang, missing_channels_info, adds_needed))


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