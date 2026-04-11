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

# ID адміністратора (Майстра) - ЗАМІНІТЬ НА ВАШ ТЕЛЕГРАМ ID
MASTER_USER_ID = 8603605527  # ВАШ ID Telegram

def get_user_role(user_id: int) -> str:
    """Отримати роль користувача"""
    if user_id == MASTER_USER_ID:
        return 'master'
    return user_roles.get(user_id, 'brigadier')  # за замовчуванням бригадир

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
    
    # Визначаємо роль
    if user_id == MASTER_USER_ID:
        role_text = "👑 Майстер (Адміністратор)"
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *{role_text}*\n\n"
            f"🏭 *Цех ДМТ* - облік працівників цеху ДМТ\n\n"
            f"📋 *Ваші можливості:*\n"
            f"• Відмітка присутності працівників\n"
            f"• Вибір КТУ (0.9 - 1.3)\n"
            f"• Фіксація невиходів (Вщ, В, На, Пр, Нз)\n"
            f"• Перегляд даних за будь-яку дату\n"
            f"• Додавання нових працівників\n"
            f"• 👥 *Управління правами користувачів*\n\n"
            f"Ви можете надавати права іншим користувачам через меню.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    else:
        role_text = "🔧 Бригадир"
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *{role_text}*\n\n"
            f"🏭 *Цех ДМТ* - облік працівників цеху ДМТ\n\n"
            f"📋 *Ваші можливості:*\n"
            f"• Відмітка присутності працівників\n"
            f"• Вибір КТУ (0.9 - 1.3)\n"
            f"• Фіксація невиходів (Вщ, В, На, Пр, Нз)\n"
            f"• Додавання нових працівників\n"
            f"• Перегляд даних за поточну дату\n\n"
            f"⚠️ *Увага!* Ви можете вносити зміни лише за поточну дату.\n"
            f"Для перегляду минулих дат зверніться до Майстра.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    
    if role == 'master':
        help_text = """
❓ *Довідка користувача (👑 Майстер)*

*Основні функції:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток для обліку

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність з вибором КТУ
• 📋 **Відмітити відсутніх** - вибрати статус (Вщ, В, На, Пр, Нз)
• ➕ **Додати працівника** - додати нового працівника
• 🔄 **Синхронізувати** - оновити дані в Google Sheets

*Управління правами:*
• 👥 **Управління правами** - додавання/зміна прав користувачів

*Коефіцієнт КТУ:*
0,9 | 1 | 1,1 | 1,2 | 1,3

*Причини невиходу:*
• Вщ - Вихідний
• В - Відпустка
• На - За свій рахунок
• Пр - Прогул
• Нз - Не з'явився
"""
    else:
        help_text = """
❓ *Довідка користувача (🔧 Бригадир)*

*Основні функції:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток для обліку

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність з вибором КТУ
• 📋 **Відмітити відсутніх** - вибрати статус (Вщ, В, На, Пр, Нз)
• ➕ **Додати працівника** - додати нового працівника
• 🔄 **Синхронізувати** - оновити дані в Google Sheets

*Обмеження:*
• ⚠️ Ви можете вносити зміни лише за *поточну дату*
• Для перегляду минулих дат зверніться до Майстра

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
    
    # Отримуємо список користувачів, які взаємодіяли з ботом
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
        "Тут ви можете:\n"
        "• Додати користувача як Майстра (повні права)\n"
        "• Додати користувача як Бригадира (обмежені права)\n"
        "• Переглянути список всіх користувачів\n"
        "• Видалити користувача\n\n"
        "⚠️ *Увага:* Користувач повинен хоча б раз написати /start боту, щоб з'явитися в списку.",
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
        await callback.message.answer(
            "📝 *Додавання Майстра*\n\n"
            "Введіть ID користувача Telegram, якому хочете дати права Майстра.\n"
            "Як дізнатися ID? Надішліть `/id` будь-якому боту, наприклад @userinfobot.\n\n"
            "Введіть ID:",
            parse_mode="Markdown"
        )
        # Очікуємо відповідь
        @dp.message_handler()
        async def add_master_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                user_roles[target_id] = 'master'
                await msg.answer(f"✅ Користувач з ID `{target_id}` отримав права Майстра!", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Спробуйте ще раз (введіть тільки цифри).")
    
    elif callback.data == "add_brigadier":
        await callback.message.answer(
            "📝 *Додавання Бригадира*\n\n"
            "Введіть ID користувача Telegram, якому хочете дати права Бригадира.\n\n"
            "Введіть ID:",
            parse_mode="Markdown"
        )
        @dp.message_handler()
        async def add_brigadier_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                user_roles[target_id] = 'brigadier'
                await msg.answer(f"✅ Користувач з ID `{target_id}` отримав права Бригадира!", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Спробуйте ще раз (введіть тільки цифри).")
    
    elif callback.data == "list_users":
        if not user_roles:
            await callback.message.answer(
                "📋 *Список користувачів порожній*\n\n"
                "Користувачі з'являться тут, коли вони:\n"
                "1. Напишуть `/start` боту\n"
                "2. Ви додасте їх вручну через меню",
                parse_mode="Markdown"
            )
        else:
            text = "📋 *Список користувачів:*\n\n"
            # Додаємо майстра (адміністратора)
            text += f"• `{MASTER_USER_ID}` - 👑 Майстер (Адміністратор)\n"
            for uid, role in user_roles.items():
                if uid != MASTER_USER_ID:
                    role_icon = "👑 Майстер" if role == 'master' else "🔧 Бригадир"
                    text += f"• `{uid}` - {role_icon}\n"
            await callback.message.answer(text, parse_mode="Markdown")
    
    elif callback.data == "remove_user":
        await callback.message.answer(
            "📝 *Видалення користувача*\n\n"
            "Введіть ID користувача, якого хочете видалити зі списку прав.\n"
            "(Користувач отримає права Бригадира за замовчуванням)\n\n"
            "Введіть ID:",
            parse_mode="Markdown"
        )
        @dp.message_handler()
        async def remove_user_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Не можна видалити права Адміністратора!")
                    return
                if target_id in user_roles:
                    del user_roles[target_id]
                    await msg.answer(f"✅ Користувач з ID `{target_id}` видалений. Тепер він отримає права Бригадира за замовчуванням.", parse_mode="Markdown")
                else:
                    await msg.answer(f"❌ Користувач з ID `{target_id}` не знайдений у списку.", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Спробуйте ще раз (введіть тільки цифри).")
    
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
