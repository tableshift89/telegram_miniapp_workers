import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from dotenv import load_dotenv
from datetime import datetime

# Завантаження змінних середовища
load_dotenv()

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

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
🌟 *Вітаю в боті обліку робітників!*

Я допоможу вести облік присутності працівників у цехах:
• 🏭 **Цех ДМТ**
• 📦 **Цех Пакування**

*Як користуватись:*
1️⃣ Оберіть потрібний цех
2️⃣ Відмітьте присутніх працівників з вибором КТУ
3️⃣ Для відсутніх оберіть причину (Вщ, Пр, На, Нз)
4️⃣ Перегляньте результат через кнопку 📊 Результат

*Коефіцієнт КТУ:*
0,9 | 1 | 1,1 | 1,2 | 1,3

*Причини невиходу:*
• Вщ - відпустка
• Пр - прогул
• На - навчання
• Нз - неявка з поважної причини
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
    
    # Зберігаємо в БД
    from app.database import set_current_shift_db
    set_current_shift_db(shift)
    
    await callback_query.answer(f"✅ Зміна {shift} годин встановлена")
    await callback_query.message.edit_text(
        f"✅ *Встановлено {shift}-годинну робочу зміну*\n\n"
        f"Тепер всі відмітки присутності будуть з {shift} годинами.",
        parse_mode="Markdown"
    )
    
    # Показуємо головне меню
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
            "📭 *Немає даних про відмічання за сьогодні*\n\n"
            "Будь ласка, відмітьте працівників у міні-додатку.",
            parse_mode="Markdown"
        )
        return
    
    # Формуємо звіт
    today = datetime.now().strftime("%d.%m.%Y")
    text = f"📊 *ЗВІТ ЗА {today}*\n"
    text += "─" * 20 + "\n\n"
    
    # Групуємо за статусами
    present = []
    vacation = []
    sick = []
    study = []
    no_show = []
    
    for row in report:
        status = row["status"]
        if status == "present":
            present.append(row)
        elif status == "Вщ":
            vacation.append(row)
        elif status == "Пр":
            sick.append(row)
        elif status == "На":
            study.append(row)
        elif status == "Нз":
            no_show.append(row)
    
    # Присутні
    if present:
        text += "✅ *ПРИСУТНІ:*\n"
        for p in present:
            text += f"  • {p['fullname']} | КТУ: {p['ktu']} | {p['shift_hours']} год\n"
        text += "\n"
    
    # Відпустка
    if vacation:
        text += "🏖️ *ВІДПУСТКА (Вщ):*\n"
        for v in vacation:
            text += f"  • {v['fullname']}\n"
        text += "\n"
    
    # Прогул
    if sick:
        text += "😷 *ПРОГУЛ (Пр):*\n"
        for s in sick:
            text += f"  • {s['fullname']}\n"
        text += "\n"
    
    # Навчання
    if study:
        text += "📚 *НАВЧАННЯ (На):*\n"
        for st in study:
            text += f"  • {st['fullname']}\n"
        text += "\n"
    
    # Неявка
    if no_show:
        text += "❌ *НЕЯВКА (Нз):*\n"
        for ns in no_show:
            text += f"  • {ns['fullname']}\n"
        text += "\n"
    
    # Підрахунки
    total = len(report)
    text += "─" * 20 + "\n"
    text += f"📈 *ВСЬОГО:* {total} працівників\n"
    text += f"✅ Присутні: {len(present)}\n"
    text += f"❌ Відсутні: {total - len(present)}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda msg: msg.text == "❓ Допомога")
async def help_command(message: types.Message):
    """Допомога"""
    help_text = """
❓ *Довідка користувача*

*Основні функції:*
• 🏭 **Цех ДМТ** - відкрити міні-додаток для цеху ДМТ
• 📦 **Цех Пакування** - відкрити міні-додаток для цеху Пакування
• ☀️ **Зміна** - вибрати 8 або 9 годин робочої зміни
• 📊 **Результат** - переглянути звіт за сьогодні

*В міні-додатку:*
• ➕ **Додати** - додати нового працівника
• ✅ **Присутній** - відмітити присутність з вибором КТУ
• ❓ **Інше** - вибрати причину відсутності (Вщ, Пр, На, Нз)
• 📊 **Показати результат** - переглянути таблицю

*Коефіцієнт КТУ:*
0,9 - мінімальний | 1 - базовий | 1,1 | 1,2 | 1,3 - максимальний

*Причини невиходу:*
• Вщ - щорічна відпустка
• Пр - прогул без поважної причини
• На - навчання/підвищення кваліфікації
• Нз - неявка з поважної причини

*Автор:* Система обліку персоналу v1.0
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message_handler()
async def echo(message: types.Message):
    """Обробник невідомих повідомлень"""
    await message.answer(
        "🙏 Будь ласка, використовуйте кнопки меню для навігації.",
        reply_markup=main_keyboard()
    )
