import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from dotenv import load_dotenv
from datetime import datetime
import json

# Завантаження змінних середовища
load_dotenv()

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

# Створюємо екземпляри бота та диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Глобальна змінна для збереження вибраної зміни
current_shift = 8

def main_keyboard():
    """Головне меню бота"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏭 Цех ДМТ", web_app=WebAppInfo(url=f"{APP_URL}/workshop/DMT"))],
            [KeyboardButton(text="📦 Цех Пакування", web_app=WebAppInfo(url=f"{APP_URL}/workshop/Пакування"))],
            [KeyboardButton(text="📝 Рецепт", web_app=WebAppInfo(url=f"{APP_URL}/recipe"))],
            [KeyboardButton(text="☀️ Зміна"), KeyboardButton(text="📊 Результат")],
            [KeyboardButton(text="❓ Допомога")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Обробник команди /start"""
    welcome_text = """
🌟 *Вітаю в боті обліку робітників та рецептур!*

*Основні функції:*
• 🏭 **Цех ДМТ** - облік працівників цеху ДМТ
• 📦 **Цех Пакування** - облік працівників цеху Пакування
• 📝 **Рецепт** - калькулятор рецептури та замовлення продуктів
• ☀️ **Зміна** - вибір 8 або 9 годин робочої зміни
• 📊 **Результат** - перегляд звіту за сьогодні

*Коефіцієнт КТУ:* 0,9 | 1 | 1,1 | 1,2 | 1,3
*Причини невиходу:* Вщ (відпустка), Пр (прогул), На (навчання), Нз (неявка)
    """
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message_handler(lambda msg: msg.text == "☀️ Зміна")
async def select_shift(message: types.Message):
    """Вибір зміни (годин роботи)"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🕗 8 годин", callback_data="shift_8")],
            [InlineKeyboardButton(text="🕘 9 годин", callback_data="shift_9")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ]
    )
    await message.answer("⏰ *Виберіть тривалість робочої зміни:*", 
                        parse_mode="Markdown", 
                        reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("shift_"))
async def set_shift(callback_query: types.CallbackQuery):
    """Встановлення вибраної зміни"""
    global current_shift
    shift = int(callback_query.data.split("_")[1])
    current_shift = shift
    
    from app.database import set_current_shift_db
    set_current_shift_db(shift)
    
    await callback_query.answer(f"✅ Зміна {shift} годин встановлена")
    await callback_query.message.edit_text(
        f"✅ *Встановлено {shift}-годинну робочу зміну*",
        parse_mode="Markdown"
    )
    await callback_query.message.answer("Повертаюсь до головного меню...", reply_markup=main_keyboard())

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery):
    """Повернення до головного меню"""
    await callback_query.message.delete()
    await callback_query.message.answer("Головне меню:", reply_markup=main_keyboard())
    await callback_query.answer()

@dp.message_handler(lambda msg: msg.text == "📊 Результат")
async def show_result(message: types.Message):
    """Показати результат відмічання за сьогодні"""
    from app.database import get_attendance_report
    
    report = get_attendance_report()
    
    if not report:
        await message.answer(
            "📭 *Немає даних про відмічання за сьогодні*",
            parse_mode="Markdown"
        )
        return
    
    today = datetime.now().strftime("%d.%m.%Y")
    text = f"📊 *ЗВІТ ЗА {today}*\n"
    text += "─" * 20 + "\n\n"
    
    present = [r for r in report if r['status'] == 'present']
    vacation = [r for r in report if r['status'] == 'Вщ']
    sick = [r for r in report if r['status'] == 'Пр']
    study = [r for r in report if r['status'] == 'На']
    no_show = [r for r in report if r['status'] == 'Нз']
    
    if present:
        text += "✅ *ПРИСУТНІ:*\n"
        for p in present:
            text += f"  • {p['fullname']} | КТУ: {p['ktu']} | {p['shift_hours']} год\n"
        text += "\n"
    
    if vacation:
        text += "🏖️ *ВІДПУСТКА (Вщ):*\n"
        for v in vacation:
            text += f"  • {v['fullname']}\n"
        text += "\n"
    
    if sick:
        text += "😷 *ПРОГУЛ (Пр):*\n"
        for s in sick:
            text += f"  • {s['fullname']}\n"
        text += "\n"
    
    if study:
        text += "📚 *НАВЧАННЯ (На):*\n"
        for st in study:
            text += f"  • {st['fullname']}\n"
        text += "\n"
    
    if no_show:
        text += "❌ *НЕЯВКА (Нз):*\n"
        for ns in no_show:
            text += f"  • {ns['fullname']}\n"
        text += "\n"
    
    text += "─" * 20 + "\n"
    text += f"📈 *ВСЬОГО:* {len(report)} працівників\n"
    text += f"✅ Присутні: {len(present)}\n"
    text += f"❌ Відсутні: {len(report) - len(present)}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    """Допомога"""
    help_text = """
❓ *Довідка користувача*

*Облік працівників:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток для цеху ДМТ
• 📦 **Цех Пакування** - відкрити міні-додаток для цеху Пакування
• ☀️ **Зміна** - вибрати 8 або 9 годин робочої зміни
• 📊 **Результат** - переглянути звіт за сьогодні

*Рецептура:*
• 📝 **Рецепт** - калькулятор рецептури (80% основа + 10% + 10%)
• Виберіть продукт та введіть кількість в кг
• Натисніть "Замовити в склад" для відправки замовлення

*Коефіцієнт КТУ:*
0,9 - мінімальний | 1 - базовий | 1,1 | 1,2 | 1,3 - максимальний

*Причини невиходу:*
• Вщ - щорічна відпустка
• Пр - прогул без поважної причини
• На - навчання/підвищення кваліфікації
• Нз - неявка з поважної причини
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message_handler(content_types=['web_app_data'])
async def handle_web_app_data(message: types.Message):
    """Обробник даних з Web App (замовлення)"""
    data = message.web_app_data.data
    
    try:
        order = json.loads(data)
        if order.get('type') == 'order':
            await message.answer(
                f"✅ *Замовлення прийнято!*\n\n"
                f"📦 *Продукт:* {order['product']}\n"
                f"⚖️ *Кількість:* {order['weight']} кг\n\n"
                f"📋 Деталі замовлення відправлені на склад.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error processing web app data: {e}")

@dp.message_handler()
async def echo(message: types.Message):
    """Обробник невідомих повідомлень"""
    await message.answer(
        "🙏 Будь ласка, використовуйте кнопки меню для навігації.",
        reply_markup=main_keyboard()
    )

# Встановлення контексту
try:
    Bot.set_current(bot)
    bot._current = bot
    logger.info("✅ Bot context set successfully")
except Exception as e:
    logger.warning(f"⚠️ Could not set bot context: {e}")

__all__ = ['bot', 'dp']
