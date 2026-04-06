import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Головне меню
def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Цех ДМТ", web_app=WebAppInfo(url=f"{os.getenv('APP_URL')}/workshop/DMT"))],
            [types.KeyboardButton(text="Цех Пакування", web_app=WebAppInfo(url=f"{os.getenv('APP_URL')}/workshop/Пакування"))],
            [types.KeyboardButton(text="☀️ Зміна")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Вітаю! Оберіть цех для роботи з персоналом:", reply_markup=main_keyboard())

@dp.message(lambda msg: msg.text == "☀️ Зміна")
async def select_shift(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="8 годин", callback_data="shift_8")],
            [InlineKeyboardButton(text="9 годин", callback_data="shift_9")]
        ]
    )
    await message.answer("Оберіть зміну (години роботи):", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("shift_"))
async def set_shift(callback: types.CallbackQuery):
    shift = int(callback.data.split("_")[1])
    # Зберігаємо в БД вибрану зміну для цеху (можна спростити: глобально)
    from app.database import set_current_shift
    set_current_shift(None, shift)  # None = глобальна зміна
    await callback.answer(f"Зміна {shift} годин обрана")
    await callback.message.answer(f"✅ Встановлено {shift}-годинну зміну", reply_markup=main_keyboard())
