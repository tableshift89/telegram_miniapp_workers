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

# ID адміністратора
MASTER_USER_ID = 209403052

# Словник доступу до цехів
user_workshop_access = {}  # {user_id: ['DMT', 'Пакування']}

def get_user_role(user_id: int) -> str:
    """Отримати роль користувача"""
    if user_id == MASTER_USER_ID:
        return 'master'
    return user_roles.get(user_id, 'brigadier')

def is_master(user_id: int) -> bool:
    """Перевірити чи користувач майстер"""
    return get_user_role(user_id) == 'master'

def get_workshop_access(user_id: int):
    """Отримати доступ до цехів"""
    if user_id == MASTER_USER_ID:
        return ['DMT', 'Пакування']
    return user_workshop_access.get(user_id, ['DMT'])

def main_keyboard(user_id: int):
    """Головне меню бота"""
    role = get_user_role(user_id)
    role_emoji = "🧢" if role == 'master' else "👒"
    access_workshops = get_workshop_access(user_id)
    
    keyboard = []
    
    # Додаємо кнопки цехів відповідно до доступу
    if 'DMT' in access_workshops:
        keyboard.append([KeyboardButton(text=f"🏭 Цех ДМТ {role_emoji}", web_app=WebAppInfo(url=f"{APP_URL}/workshop/DMT?role={role}&workshop=DMT"))])
    if 'Пакування' in access_workshops:
        keyboard.append([KeyboardButton(text=f"📦 Цех Пакування {role_emoji}", web_app=WebAppInfo(url=f"{APP_URL}/workshop/Пакування?role={role}&workshop=Пакування"))])
    
    keyboard.append([KeyboardButton(text="❓ Допомога")])
    
    # Якщо майстер, додаємо кнопку управління правами
    if role == 'master':
        keyboard.append([KeyboardButton(text="👥 Управління правами")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def admin_keyboard():
    """Клавіатура для управління правами"""
    keyboard = InlineKeyboardMarkup(
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
    return keyboard

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    if user_id == MASTER_USER_ID:
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *🧢 Майстер*\n\n"
            f"🏭 *Управління цехами:*\n"
            f"• Цех ДМТ\n"
            f"• Цех Пакування\n\n"
            f"📋 *Ваші можливості:*\n"
            f"• Всі функції без обмежень\n"
            f"• 👥 Управління правами користувачів\n"
            f"• Призначення доступу до цехів",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    else:
        role = get_user_role(user_id)
        role_emoji = "🧢" if role == 'master' else "👒"
        await message.answer(
            f"🌟 *Вітаю, {username}!*\n\n"
            f"Ви увійшли як *{role_emoji} {role.capitalize()}*\n\n"
            f"⚠️ Ви можете вносити зміни лише за *поточну дату*",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    role_emoji = "🧢" if role == 'master' else "👒"
    access = get_workshop_access(user_id)
    
    workshops = "• " + "\n• ".join(access)
    
    help_text = f"""
❓ *Довідка ({role_emoji} {role.capitalize()})*

*Ваші цехи:*
{workshops}

*В міні-додатку:*
• ✅ **Присутній** - відмітити присутність
• 📋 **Відмітити відсутніх** - вибрати статус
• ➕ **Додати працівника** - додати нового
• 🔄 **Синхронізувати** - оновити дані

{'*Управління правами:*\n• 👥 Управління правами - керування користувачами' if role == 'master' else ''}
{'⚠️ Зміни доступні лише за *поточну дату*' if role != 'master' else ''}
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

@dp.callback_query_handler(lambda c: c.data in ["add_master", "add_brigadier", "list_users", "change_role", "remove_user", "workshop_access", "back_to_main"])
async def role_actions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_master(user_id):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    if callback.data == "add_master":
        await callback.message.answer(
            "📝 *Додавання Майстра 🧢*\n\n"
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
                # За замовчуванням даємо доступ до обох цехів
                user_workshop_access[target_id] = ['DMT', 'Пакування']
                await msg.answer(f"✅ Користувач з ID `{target_id}` отримав права 🧢 Майстра!\n📦 Доступ: ДМТ, Пакування", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "add_brigadier":
        await callback.message.answer(
            "📝 *Додавання Бригадира 👒*\n\n"
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
                # За замовчуванням даємо доступ тільки до ДМТ
                user_workshop_access[target_id] = ['DMT']
                await msg.answer(f"✅ Користувач з ID `{target_id}` отримав права 👒 Бригадира!\n📦 Доступ: ДМТ", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "list_users":
        text = "📋 *Список користувачів:*\n\n"
        text += f"• `{MASTER_USER_ID}` - 🧢 Майстер (Адмін) | Доступ: ДМТ, Пакування\n"
        
        if user_roles:
            for uid, role in user_roles.items():
                if uid != MASTER_USER_ID:
                    icon = "🧢" if role == 'master' else "👒"
                    role_name = "Майстер" if role == 'master' else "Бригадир"
                    access = get_workshop_access(uid)
                    access_str = ", ".join(access)
                    text += f"• `{uid}` - {icon} {role_name} | Доступ: {access_str}\n"
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
                    await msg.answer(f"❌ Користувач `{target_id}` не знайдений. Спочатку додайте його.", parse_mode="Markdown")
                    return
                
                current_role = user_roles[target_id]
                new_role = 'master' if current_role == 'brigadier' else 'brigadier'
                user_roles[target_id] = new_role
                
                icon = "🧢" if new_role == 'master' else "👒"
                role_name = "Майстра" if new_role == 'master' else "Бригадира"
                await msg.answer(f"✅ Роль користувача `{target_id}` змінено на {icon} {role_name}!", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "remove_user":
        await callback.message.answer(
            "❌ *Видалення користувача*\n\n"
            "Введіть ID користувача, якого хочете видалити.\n\n"
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
                    if target_id in user_workshop_access:
                        del user_workshop_access[target_id]
                    await msg.answer(f"✅ Користувач `{target_id}` видалений.", parse_mode="Markdown")
                else:
                    await msg.answer(f"❌ Користувач `{target_id}` не знайдений.", parse_mode="Markdown")
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "workshop_access":
        await callback.message.answer(
            "🏭 *Налаштування доступу до цехів*\n\n"
            "Введіть ID користувача, якому хочете змінити доступ:",
            parse_mode="Markdown"
        )
        
        @dp.message_handler()
        async def workshop_access_get_id(msg: types.Message):
            try:
                target_id = int(msg.text.strip())
                if target_id == MASTER_USER_ID:
                    await msg.answer("❌ Адміністратор має доступ до всіх цехів!")
                    return
                
                if target_id not in user_roles:
                    await msg.answer(f"❌ Користувач `{target_id}` не знайдений. Спочатку додайте його.", parse_mode="Markdown")
                    return
                
                current_access = user_workshop_access.get(target_id, ['DMT'])
                
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Цех ДМТ" + (" ✔" if 'DMT' in current_access else ""), callback_data=f"toggle_DMT_{target_id}")],
                        [InlineKeyboardButton(text="✅ Цех Пакування" + (" ✔" if 'Пакування' in current_access else ""), callback_data=f"toggle_Pack_{target_id}")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="workshop_access_back")]
                    ]
                )
                
                await msg.answer(f"🏭 *Налаштування доступу для `{target_id}`*\n\nПоточний доступ: {', '.join(current_access)}", parse_mode="Markdown", reply_markup=keyboard)
            except:
                await msg.answer("❌ Неправильний ID. Введіть тільки цифри.")
    
    elif callback.data == "back_to_main":
        await callback.message.delete()
        await callback.message.answer(
            "🏠 *Головне меню*",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("toggle_"))
async def toggle_workshop(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_master(user_id):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    action = parts[1]  # DMT or Pack
    target_id = int(parts[2])
    
    if target_id not in user_workshop_access:
        user_workshop_access[target_id] = ['DMT']
    
    if action == "DMT":
        if 'DMT' in user_workshop_access[target_id]:
            user_workshop_access[target_id].remove('DMT')
        else:
            user_workshop_access[target_id].append('DMT')
    elif action == "Pack":
        if 'Пакування' in user_workshop_access[target_id]:
            user_workshop_access[target_id].remove('Пакування')
        else:
            user_workshop_access[target_id].append('Пакування')
    
    current_access = user_workshop_access[target_id]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Цех ДМТ" + (" ✔" if 'DMT' in current_access else ""), callback_data=f"toggle_DMT_{target_id}")],
            [InlineKeyboardButton(text="✅ Цех Пакування" + (" ✔" if 'Пакування' in current_access else ""), callback_data=f"toggle_Pack_{target_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="workshop_access_back")]
        ]
    )
    
    await callback.message.edit_text(
        f"🏭 *Налаштування доступу для `{target_id}`*\n\nПоточний доступ: {', '.join(current_access)}",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "workshop_access_back")
async def workshop_access_back(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "👥 *Управління правами користувачів*\n\nВиберіть дію:",
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
except Exception as g:
    logger.warning(f"⚠️ Could not set bot context: {g}")

__all__ = ['bot', 'dp']
