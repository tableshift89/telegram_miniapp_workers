import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

current_shift = 8

# Словник для зберігання ролей користувачів
user_roles = {}

# ВАШ ТЕЛЕГРАМ ID - ЗАМІНІТЬ НА СВІЙ!
MASTER_USER_ID = 123456789  # <- СЮДИ ВСТАВТЕ ВАШ ID

def get_user_role(user_id: int) -> str:
    """Отримати роль користувача"""
    if user_id == MASTER_USER_ID:
        return 'master'
    return user_roles.get(user_id, 'brigadier')

def is_master(user_id: int) -> bool:
    """Перевірити чи користувач майстер"""
    return get_user_role(user_id) == 'master'

def main_keyboard(user_id: int):
    """Головне меню бота (залежить від ролі)"""
    role = get_user_role(user_id)
    role_text = "👑 Майстер" if role == 'master' else "🔧 Бригадир"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"🏭 Цех ДМТ ({role_text})", web_app=WebAppInfo(url=f"{APP_URL}/workshop/DMT?role={role}"))],
            [KeyboardButton(text="❓ Допомога")]
        ],
        resize_keyboard=True
    )
    
    # Якщо майстер, додаємо кнопку управління правами
    if role == 'master':
        keyboard.keyboard.append([KeyboardButton(text="👥 Управління правами")])
    
    return keyboard

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    if user_id == MASTER_USER_ID:
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *👑 Майстер (Адміністратор)*\n\n"
            f"🏭 *Цех ДМТ* - облік працівників\n\n"
            f"📋 *Ваші можливості:*\n"
            f"• Всі функції без обмежень\n"
            f"• 👥 Управління правами користувачів\n"
            f"• Перегляд/редагування будь-якої дати",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    else:
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *🔧 Бригадир*\n\n"
            f"🏭 *Цех ДМТ* - облік працівників\n\n"
            f"⚠️ Ви можете вносити зміни лише за *поточну дату*",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    
    if role == 'master':
        help_text = """
❓ *Довідка (👑 Майстер)*

• 🏭 **Цех ДМТ** - відкрити міні-додаток
• 👥 **Управління правами** - керування користувачами

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність
• 📋 **Відмітити відсутніх** - вибрати статус
• ➕ **Додати працівника** - додати нового
• 🔄 **Синхронізувати** - оновити дані
"""
    else:
        help_text = """
❓ *Довідка (🔧 Бригадир)*

• 🏭 **Цех ДМТ** - відкрити міні-додаток

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність
• 📋 **Відмітити відсутніх** - вибрати статус
• ➕ **Додати працівника** - додати нового
• 🔄 **Синхронізувати** - оновити дані

⚠️ Зміни доступні лише за *поточну дату*
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message_handler(lambda msg: msg.text == "👥 Управління правами")
async def manage_roles(message: types.Message):
    user_id = message.from_user.id
    if not is_master(user_id):
        await message.answer("❌ У вас немає прав для цієї дії!")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати Майстра", callback_data="add_master")],
            [InlineKeyboardButton(text="➕ Додати Бригадира", callback_data="add_brigadier")],
            [InlineKeyboardButton(text="📋 Список користувачів", callback_data="list_users")],
            [InlineKeyboardButton(text="❌ Видалити користувача", callback_data="remove_user")]
        ]
    )
    await message.answer(
        "👥 *Управління правами користувачів*\n\n"
        "Виберіть дію:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data in ["add_master", "add_brigadier", "list_users", "remove_user"])
async def role_actions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_master(user_id):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    if callback.data == "add_master":
        await callback.message.answer("Введіть ID користувача для прав Майстра:")
        @dp.message_handler()
        async def add_master_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                user_roles[target_id] = 'master'
                await msg.answer(f"✅ Користувач {target_id} став Майстром!")
            except:
                await msg.answer("❌ Неправильний ID")
    
    elif callback.data == "add_brigadier":
        await callback.message.answer("Введіть ID користувача для прав Бригадира:")
        @dp.message_handler()
        async def add_brigadier_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                user_roles[target_id] = 'brigadier'
                await msg.answer(f"✅ Користувач {target_id} став Бригадиром!")
            except:
                await msg.answer("❌ Неправильний ID")
    
    elif callback.data == "list_users":
        text = "📋 *Список користувачів:*\n\n"
        text += f"• `{MASTER_USER_ID}` - 👑 Майстер (Адмін)\n"
        for uid, role in user_roles.items():
            if uid != MASTER_USER_ID:
                icon = "👑" if role == 'master' else "🔧"
                text += f"• `{uid}` - {icon} {role}\n"
        if len(user_roles) == 0:
            text += "Немає додаткових користувачів"
        await callback.message.answer(text, parse_mode="Markdown")
    
    elif callback.data == "remove_user":
        await callback.message.answer("Введіть ID користувача для видалення:")
        @dp.message_handler()
        async def remove_user_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Не можна видалити Адміністратора!")
                    return
                if target_id in user_roles:
                    del user_roles[target_id]
                    await msg.answer(f"✅ Користувача {target_id} видалено")
                else:
                    await msg.answer(f"❌ Користувач {target_id} не знайдений")
            except:
                await msg.answer("❌ Неправильний ID")
    
    await callback.answer()

@dp.message_handler()
async def echo(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        "🙏 Використовуйте кнопки меню.",
        reply_markup=main_keyboard(user_id)
    )

try:
    Bot.set_current(bot)
    bot._current = bot
    logger.info("✅ Bot context set successfully")
except Exception as e:
    logger.warning(f"⚠️ Could not set bot context: {e}")

__all__ = ['bot', 'dp']
