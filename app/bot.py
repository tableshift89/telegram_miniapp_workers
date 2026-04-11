import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ID адміністратора
MASTER_USER_ID = 209403052

# Словники для зберігання даних
user_roles = {}
user_workshop_access = {}

def get_user_role(user_id: int) -> str:
    if user_id == MASTER_USER_ID:
        return 'master'
    return user_roles.get(user_id, 'brigadier')

def get_workshop_access(user_id: int):
    if user_id == MASTER_USER_ID:
        return ['DMT', 'Пакування']
    return user_workshop_access.get(user_id, ['DMT'])

def main_keyboard(user_id: int):
    role = get_user_role(user_id)
    role_emoji = "🧢" if role == 'master' else "👒"
    access = get_workshop_access(user_id)
    
    keyboard = []
    
    if 'DMT' in access:
        keyboard.append([KeyboardButton(text=f"🏭 Цех ДМТ {role_emoji}", web_app=WebAppInfo(url=f"{APP_URL}/workshop/DMT?role={role}"))])
    if 'Пакування' in access:
        keyboard.append([KeyboardButton(text=f"📦 Цех Пакування {role_emoji}", web_app=WebAppInfo(url=f"{APP_URL}/workshop/Пакування?role={role}"))])
    
    keyboard.append([KeyboardButton(text="❓ Допомога")])
    
    if role == 'master':
        keyboard.append([KeyboardButton(text="👥 Управління правами")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати Майстра", callback_data="add_master")],
            [InlineKeyboardButton(text="➕ Додати Бригадира", callback_data="add_brigadier")],
            [InlineKeyboardButton(text="📋 Список користувачів", callback_data="list_users")],
            [InlineKeyboardButton(text="🔄 Змінити роль", callback_data="change_role")],
            [InlineKeyboardButton(text="❌ Видалити користувача", callback_data="remove_user")],
            [InlineKeyboardButton(text="🏭 Доступ до цехів", callback_data="workshop_access")],
            [InlineKeyboardButton(text="🔙 Головне меню", callback_data="back_to_main")]
        ]
    )

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.first_name or message.from_user.username
    
    if user_id == MASTER_USER_ID:
        await message.answer(
            f"🌟 Вітаю, {username}!\n\n"
            f"Ви увійшли як 🧢 Майстер\n\n"
            f"🏭 Доступні цехи:\n"
            f"• Цех ДМТ\n"
            f"• Цех Пакування\n\n"
            f"Ви можете керувати правами користувачів через меню.",
            reply_markup=main_keyboard(user_id)
        )
    else:
        role = get_user_role(user_id)
        role_emoji = "🧢" if role == 'master' else "👒"
        await message.answer(
            f"🌟 Вітаю, {username}!\n\n"
            f"Ви увійшли як {role_emoji} {role.capitalize()}\n\n"
            f"⚠️ Ви можете вносити зміни лише за поточну дату.",
            reply_markup=main_keyboard(user_id)
        )

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    role_emoji = "🧢" if role == 'master' else "👒"
    access = get_workshop_access(user_id)
    
    await message.answer(
        f"❓ Довідка ({role_emoji} {role.capitalize()})\n\n"
        f"Ваші цехи: {', '.join(access)}\n\n"
        f"В міні-додатку:\n"
        f"• ✅ Присутній - відмітити присутність\n"
        f"• 📋 Відмітити відсутніх - вибрати статус\n"
        f"• ➕ Додати працівника - додати нового\n"
        f"• 🔄 Синхронізувати - оновити дані",
        reply_markup=main_keyboard(user_id)
    )

@dp.message_handler(lambda msg: msg.text == "👥 Управління правами")
async def manage_roles(message: types.Message):
    user_id = message.from_user.id
    if not (user_id == MASTER_USER_ID or get_user_role(user_id) == 'master'):
        await message.answer("❌ У вас немає прав для цієї дії!")
        return
    
    await message.answer(
        "👥 Управління правами користувачів\n\nВиберіть дію:",
        reply_markup=admin_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data in ["add_master", "add_brigadier", "list_users", "change_role", "remove_user", "workshop_access", "back_to_main"])
async def role_actions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not (user_id == MASTER_USER_ID or get_user_role(user_id) == 'master'):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    if callback.data == "back_to_main":
        await callback.message.delete()
        await callback.message.answer("Головне меню", reply_markup=main_keyboard(user_id))
        await callback.answer()
        return
    
    await callback.message.answer("Функція в розробці. Незабаром буде доступна.")
    await callback.answer()

@dp.message_handler()
async def echo(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        "Використовуйте кнопки меню.",
        reply_markup=main_keyboard(user_id)
    )

try:
    Bot.set_current(bot)
    bot._current = bot
    logger.info("Bot context set successfully")
except Exception as e:
    logger.warning(f"Could not set bot context: {e}")

__all__ = ['bot', 'dp']
