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

# ID майстра (замініть на ваш Telegram ID)
MASTER_USER_ID = 8603605527  # ВАШ ID Telegram

def get_user_role(user_id: int) -> str:
    """Отримати роль користувача"""
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
    
    # Встановлюємо роль
    if user_id == MASTER_USER_ID:
        user_roles[user_id] = 'master'
        role_text = "👑 Майстер"
    else:
        user_roles[user_id] = 'brigadier'
        role_text = "🔧 Бригадир"
    
    welcome_text = f"""
🌟 *Вітаю, {username}!*

Ви увійшли як *{role_text}*

🏭 *Цех ДМТ* - облік працівників цеху ДМТ

📋 *Можливості:*
• Відмітка присутності працівників
• Вибір КТУ (0.9 - 1.3)
• Фіксація невиходів (Вщ, В, На, Пр, Нз)
• Перегляд даних за будь-яку дату {'' if user_id == MASTER_USER_ID else '(тільки перегляд)'}
• Додавання нових працівників {'' if user_id == MASTER_USER_ID else '(тільки для Майстра)'}

{'' if user_id == MASTER_USER_ID else '⚠️ *Увага!* Ви маєте права лише на внесення даних за поточний день.'}
    """
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    
    help_text = f"""
❓ *Довідка користувача ({'👑 Майстер' if role == 'master' else '🔧 Бригадир'})*

*Основні функції:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток для обліку

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність з вибором КТУ
• 📋 **Відмітити відсутніх** - вибрати статус (Вщ, В, На, Пр, Нз)
• ➕ **Додати працівника** - додати нового працівника {'(тільки для Майстра)' if role != 'master' else ''}
• 🔄 **Синхронізувати** - оновити дані в Google Sheets

*Коефіцієнт КТУ:*
0,9 | 1 | 1,1 | 1,2 | 1,3

*Причини невиходу:*
• Вщ - Вихідний
• В - Відпустка
• На - За свій рахунок
• Пр - Прогул
• Нз - Не з'явився
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
            [InlineKeyboardButton(text="📋 Список користувачів", callback_data="list_users")]
        ]
    )
    await message.answer("👥 *Управління правами користувачів*\n\nВиберіть дію:", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data in ["add_master", "add_brigadier", "list_users"])
async def role_actions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_master(user_id):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    if callback.data == "add_master":
        await callback.message.answer("Введіть ID користувача Telegram, якому хочете дати права Майстра:\n(Можна дізнатися через @userinfobot)")
        
        @dp.message_handler()
        async def add_master_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                user_roles[target_id] = 'master'
                await msg.answer(f"✅ Користувач {target_id} отримав права Майстра!")
            except:
                await msg.answer("❌ Неправильний ID. Спробуйте ще раз.")
    
    elif callback.data == "add_brigadier":
        await callback.message.answer("Введіть ID користувача Telegram, якому хочете дати права Бригадира:")
        
        @dp.message_handler()
        async def add_brigadier_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                user_roles[target_id] = 'brigadier'
                await msg.answer(f"✅ Користувач {target_id} отримав права Бригадира!")
            except:
                await msg.answer("❌ Неправильний ID. Спробуйте ще раз.")
    
    elif callback.data == "list_users":
        if not user_roles:
            await callback.message.answer("📋 Список користувачів порожній")
        else:
            text = "📋 *Список користувачів:*\n\n"
            for uid, role in user_roles.items():
                role_icon = "👑 Майстер" if role == 'master' else "🔧 Бригадир"
                text += f"• `{uid}` - {role_icon}\n"
            await callback.message.answer(text, parse_mode="Markdown")
    
    await callback.answer()

@dp.message_handler()
async def echo(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        "🙏 Будь ласка, використовуйте кнопки меню для навігації.",
        reply_markup=main_keyboard(user_id)
    )

try:
    Bot.set_current(bot)
    bot._current = bot
    logger.info("✅ Bot context set successfully")
except Exception as e:
    logger.warning(f"⚠️ Could not set bot context: {e}")

__all__ = ['bot', 'dp']
