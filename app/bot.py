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
user_roles = {}  # {user_id: 'master' or 'brigadier'}
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

# Тимчасові сховища для очікування вводу
waiting_for_id = {}

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
            f"Ви можете керувати правами користувачів через меню 👥 Управління правами",
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
        f"❓ *Довідка ({role_emoji} {role.capitalize()})*\n\n"
        f"🏭 *Ваші цехи:* {', '.join(access)}\n\n"
        f"📋 *В міні-додатку:*\n"
        f"• ✅ Присутній - відмітити присутність\n"
        f"• 📋 Відмітити відсутніх - вибрати статус (Вщ, В, На, Пр, Нз)\n"
        f"• ➕ Додати працівника - додати нового\n"
        f"• 🔄 Синхронізувати - оновити дані в Google Sheets\n\n"
        f"⚠️ *Обмеження:*\n"
        f"• Бригадир може змінювати дані лише за поточну дату\n"
        f"• Майстер має повний доступ до всіх дат",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user_id)
    )

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
    
    if callback.data == "back_to_main":
        await callback.message.delete()
        await callback.message.answer("🏠 *Головне меню*", parse_mode="Markdown", reply_markup=main_keyboard(user_id))
        await callback.answer()
        return
    
    elif callback.data == "add_master":
        await callback.message.answer(
            "📝 *Додавання Майстра 🧢*\n\n"
            "Введіть ID користувача Telegram.\n"
            "Як дізнатися ID? Надішліть /id боту @userinfobot.\n\n"
            "Введіть ID (тільки цифри):",
            parse_mode="Markdown"
        )
        waiting_for_id[user_id] = 'add_master'
        await callback.answer()
    
    elif callback.data == "add_brigadier":
        await callback.message.answer(
            "📝 *Додавання Бригадира 👒*\n\n"
            "Введіть ID користувача Telegram.\n\n"
            "Введідь ID (тільки цифри):",
            parse_mode="Markdown"
        )
        waiting_for_id[user_id] = 'add_brigadier'
        await callback.answer()
    
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
        
        text += "\n\n💡 *Як дізнатися ID?*\nНадішліть /id боту @userinfobot"
        
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.message.answer("👥 *Управління правами*", parse_mode="Markdown", reply_markup=admin_keyboard())
        await callback.answer()
    
    elif callback.data == "change_role":
        await callback.message.answer(
            "🔄 *Зміна ролі користувача*\n\n"
            "Введіть ID користувача, якому хочете змінити роль:",
            parse_mode="Markdown"
        )
        waiting_for_id[user_id] = 'change_role'
        await callback.answer()
    
    elif callback.data == "remove_user":
        await callback.message.answer(
            "❌ *Видалення користувача*\n\n"
            "Введіть ID користувача, якого хочете видалити:",
            parse_mode="Markdown"
        )
        waiting_for_id[user_id] = 'remove_user'
        await callback.answer()
    
    elif callback.data == "workshop_access":
        await callback.message.answer(
            "🏭 *Налаштування доступу до цехів*\n\n"
            "Введіть ID користувача, якому хочете змінити доступ:",
            parse_mode="Markdown"
        )
        waiting_for_id[user_id] = 'workshop_access'
        await callback.answer()

@dp.message_handler()
async def handle_text_input(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in waiting_for_id:
        action = waiting_for_id[user_id]
        del waiting_for_id[user_id]
        
        try:
            target_id = int(message.text.strip())
            
            if action == 'add_master':
                if target_id == MASTER_USER_ID:
                    await message.answer("❌ Це ви! Ви вже Майстер.")
                    return
                user_roles[target_id] = 'master'
                user_workshop_access[target_id] = ['DMT', 'Пакування']
                await message.answer(f"✅ Користувач з ID `{target_id}` отримав права 🧢 Майстра!\n📦 Доступ: ДМТ, Пакування", parse_mode="Markdown")
            
            elif action == 'add_brigadier':
                if target_id == MASTER_USER_ID:
                    await message.answer("❌ Це ви! Ви Майстер, не можете стати Бригадиром.")
                    return
                user_roles[target_id] = 'brigadier'
                user_workshop_access[target_id] = ['DMT']
                await message.answer(f"✅ Користувач з ID `{target_id}` отримав права 👒 Бригадира!\n📦 Доступ: ДМТ", parse_mode="Markdown")
            
            elif action == 'change_role':
                if target_id == MASTER_USER_ID:
                    await message.answer("❌ Не можна змінити роль Адміністратора!")
                    return
                if target_id not in user_roles:
                    await message.answer(f"❌ Користувач `{target_id}` не знайдений. Спочатку додайте його через 'Додати Бригадира' або 'Додати Майстра'.", parse_mode="Markdown")
                    return
                current_role = user_roles[target_id]
                new_role = 'master' if current_role == 'brigadier' else 'brigadier'
                user_roles[target_id] = new_role
                icon = "🧢" if new_role == 'master' else "👒"
                role_name = "Майстра" if new_role == 'master' else "Бригадира"
                await message.answer(f"✅ Роль користувача `{target_id}` змінено на {icon} {role_name}!", parse_mode="Markdown")
            
            elif action == 'remove_user':
                if target_id == MASTER_USER_ID:
                    await message.answer("❌ Не можна видалити Адміністратора!")
                    return
                if target_id in user_roles:
                    del user_roles[target_id]
                    if target_id in user_workshop_access:
                        del user_workshop_access[target_id]
                    await message.answer(f"✅ Користувач `{target_id}` видалений. Тепер він матиме права 👒 Бригадира за замовчуванням.", parse_mode="Markdown")
                else:
                    await message.answer(f"❌ Користувач `{target_id}` не знайдений у списку.", parse_mode="Markdown")
            
            elif action == 'workshop_access':
                if target_id == MASTER_USER_ID:
                    await message.answer("❌ Адміністратор має доступ до всіх цехів!")
                    return
                if target_id not in user_roles:
                    await message.answer(f"❌ Користувач `{target_id}` не знайдений. Спочатку додайте його.", parse_mode="Markdown")
                    return
                
                current_access = user_workshop_access.get(target_id, ['DMT'])
                dmt_status = "✅" if 'DMT' in current_access else "❌"
                pack_status = "✅" if 'Пакування' in current_access else "❌"
                
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=f"{dmt_status} Цех ДМТ", callback_data=f"toggle_DMT_{target_id}")],
                        [InlineKeyboardButton(text=f"{pack_status} Цех Пакування", callback_data=f"toggle_Pack_{target_id}")],
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="workshop_access_back")]
                    ]
                )
                
                await message.answer(f"🏭 *Налаштування доступу для `{target_id}`*\n\nПоточний доступ: {', '.join(current_access)}", parse_mode="Markdown", reply_markup=keyboard)
        
        except ValueError:
            await message.answer("❌ Неправильний ID. Введіть тільки цифри.")
        return
    
    # Якщо не в режимі очікування
    await message.answer("Використовуйте кнопки меню.", reply_markup=main_keyboard(user_id))

@dp.callback_query_handler(lambda c: c.data.startswith("toggle_") or c.data == "workshop_access_back")
async def toggle_workshop(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not is_master(user_id):
        await callback.answer("❌ У вас немає прав!", show_alert=True)
        return
    
    if callback.data == "workshop_access_back":
        await callback.message.delete()
        await callback.message.answer("👥 *Управління правами*", parse_mode="Markdown", reply_markup=admin_keyboard())
        await callback.answer()
        return
    
    parts = callback.data.split("_")
    action = parts[1]
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
    
    dmt_status = "✅" if 'DMT' in current_access else "❌"
    pack_status = "✅" if 'Пакування' in current_access else "❌"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{dmt_status} Цех ДМТ", callback_data=f"toggle_DMT_{target_id}")],
            [InlineKeyboardButton(text=f"{pack_status} Цех Пакування", callback_data=f"toggle_Pack_{target_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="workshop_access_back")]
        ]
    )
    
    await callback.message.edit_text(
        f"🏭 *Налаштування доступу для `{target_id}`*\n\nПоточний доступ: {', '.join(current_access)}",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

try:
    Bot.set_current(bot)
    bot._current = bot
    logger.info("✅ Bot context set successfully")
except Exception as e:
    logger.warning(f"⚠️ Could not set bot context: {e}")

__all__ = ['bot', 'dp']
