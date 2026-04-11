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

# Словник для зберігання ролей користувачів (в реальному проекті зберігати в БД)
user_roles = {}

# ВАШ ТЕЛЕГРАМ ID
MASTER_USER_ID = 209403052

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

def admin_keyboard():
    """Клавіатура для управління правами"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати Майстра", callback_data="add_master")],
            [InlineKeyboardButton(text="➕ Додати Бригадира", callback_data="add_brigadier")],
            [InlineKeyboardButton(text="📋 Список користувачів", callback_data="list_users")],
            [InlineKeyboardButton(text="🔄 Змінити роль", callback_data="change_role")],
            [InlineKeyboardButton(text="❌ Видалити користувача", callback_data="remove_user")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ]
    )
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
            f"• Перегляд/редагування будь-якої дати\n\n"
            f"Ви можете надавати права іншим користувачам через меню '👥 Управління правами'.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    else:
        role = get_user_role(user_id)
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *🔧 {role.capitalize()}*\n\n"
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

*Основні функції:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток
• 👥 **Управління правами** - керування користувачами

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність
• 📋 **Відмітити відсутніх** - вибрати статус
• ➕ **Додати працівника** - додати нового
• 🔄 **Синхронізувати** - оновити дані

*Управління правами:*
• ➕ Додати Майстра - надати повні права
• ➕ Додати Бригадира - надати обмежені права
• 📋 Список користувачів - перегляд всіх
• 🔄 Змінити роль - змінити права існуючого
• ❌ Видалити користувача - скинути права
"""
    else:
        help_text = """
❓ *Довідка (🔧 Бригадир)*

*Основні функції:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність
• 📋 **Відмітити відсутніх** - вибрати статус
• ➕ **Додати працівника** - додати нового
• 🔄 **Синхронізувати** - оновити дані

⚠️ *Обмеження:*
• Зміни доступні лише за *поточну дату*
• Для перегляду минулих дат зверніться до Майстра
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message_handler(lambda msg: msg.text == "👥 Управління правами")
async def manage_roles(message: types.Message):
    user_id = message.from_user.id
    if not is_master(user_id):
        await message.answer("❌ У вас немає прав для цієї дії!")
        return
    
    await message.answer(
        "👥 *Управління правами користувачів*\n\n"
        "Виберіть дію:",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data in ["add_master", "add_brigadier", "list_users", "change_role", "remove_user", "back_to_menu"])
async def role_actions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_master(user_id):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    if callback.data == "add_master":
        await callback.message.answer(
            "📝 *Додавання Майстра*\n\n"
            "Введіть ID користувача Telegram.\n"
            "Як дізнатися ID? Надішліть `/id` боту @userinfobot.\n\n"
            "Введіть ID:",
            parse_mode="Markdown"
        )
        
        @dp.message_handler()
        async def add_master_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Це ви! Ви вже Майстер.")
                    return
                user_roles[target_id] = 'master'
                await msg.answer(f"✅ Користувач з ID `{target_id}` отримав права 👑 Майстра!", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "add_brigadier":
        await callback.message.answer(
            "📝 *Додавання Бригадира*\n\n"
            "Введіть ID користувача Telegram:\n\n"
            "Введіть ID:",
            parse_mode="Markdown"
        )
        
        @dp.message_handler()
        async def add_brigadier_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Це ви! Ви Майстер, не можете стати Бригадиром.")
                    return
                user_roles[target_id] = 'brigadier'
                await msg.answer(f"✅ Користувач з ID `{target_id}` отримав права 🔧 Бригадира!", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "list_users":
        text = "📋 *Список користувачів:*\n\n"
        text += f"• `{MASTER_USER_ID}` - 👑 Майстер (Адміністратор)\n"
        
        if user_roles:
            for uid, role in user_roles.items():
                if uid != MASTER_USER_ID:
                    icon = "👑" if role == 'master' else "🔧"
                    role_name = "Майстер" if role == 'master' else "Бригадир"
                    text += f"• `{uid}` - {icon} {role_name}\n"
        else:
            text += "\n*Немає додаткових користувачів*"
        
        text += "\n\n💡 *Як дізнатися ID?*\nНадішліть `/id` боту @userinfobot"
        
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.message.answer("👥 *Управління правами*", reply_markup=admin_keyboard())
    
    elif callback.data == "change_role":
        await callback.message.answer(
            "🔄 *Зміна ролі користувача*\n\n"
            "Введіть ID користувача, якому хочете змінити роль:",
            parse_mode="Markdown"
        )
        
        @dp.message_handler()
        async def change_role_get_id(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Не можна змінити роль Адміністратора!")
                    return
                
                if target_id not in user_roles:
                    await msg.answer(f"❌ Користувач `{target_id}` не знайдений. Спочатку додайте його через 'Додати Бригадира' або 'Додати Майстра'.", parse_mode="Markdown")
                    return
                
                current_role = user_roles[target_id]
                new_role = 'master' if current_role == 'brigadier' else 'brigadier'
                user_roles[target_id] = new_role
                
                role_name = "Майстра" if new_role == 'master' else "Бригадира"
                await msg.answer(f"✅ Роль користувача `{target_id}` змінено на {role_name}!", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "remove_user":
        await callback.message.answer(
            "❌ *Видалення користувача*\n\n"
            "Введіть ID користувача, якого хочете видалити.\n"
            "Після видалення він отримає права Бригадира за замовчуванням.\n\n"
            "Введіть ID:",
            parse_mode="Markdown"
        )
        
        @dp.message_handler()
        async def remove_user_handler(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Не можна видалити Адміністратора!")
                    return
                if target_id in user_roles:
                    del user_roles[target_id]
                    await msg.answer(f"✅ Користувач `{target_id}` видалений. Тепер він матиме права 🔧 Бригадира за замовчуванням.", parse_mode="Markdown")
                else:
                    await msg.answer(f"❌ Користувач `{target_id}` не знайдений у списку.", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "back_to_menu":
        await callback.message.edit_text(
            "👥 *Управління правами користувачів*\n\n"
            "Виберіть дію:",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
    
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
