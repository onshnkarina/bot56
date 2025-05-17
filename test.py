import os
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)



class CurrencyManage(StatesGroup):
    choosing_action = State()
    adding_currency_name = State()
    adding_currency_rate = State()
    deleting_currency_name = State()
    updating_currency_name = State()
    updating_currency_rate = State()
    converting_currency_name = State()
    converting_amount = State()



async def is_admin(user_id: int, conn) -> bool:
    result = await conn.fetchrow("SELECT 1 FROM admins WHERE chat_id = $1", str(user_id))
    return result is not None



@dp.message(Command("start"))
async def cmd_start(message: Message):
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        if await is_admin(message.from_user.id, conn):
            text = "/start, /manage_currency, /get_currencies, /convert"
        else:
            text = "/start, /get_currencies, /convert"
    await message.answer(f"Добро пожаловать! Доступные команды: {text}")



@dp.message(Command("get_currencies"))
async def cmd_get_currencies(message: Message):
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT currency_name, rate FROM currencies")
    if rows:
        reply = "Список валют:\n" + "\n".join(f"{r['currency_name']}: {r['rate']} RUB" for r in rows)
    else:
        reply = "Валюты не найдены."
    await message.answer(reply)



@dp.message(Command("manage_currency"))
async def cmd_manage_currency(message: Message, state: FSMContext):
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        if not await is_admin(message.from_user.id, conn):
            await message.answer("Нет доступа к команде")
            return
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Добавить валюту")],
        [KeyboardButton(text="Удалить валюту")],
        [KeyboardButton(text="Изменить курс валюты")]
    ], resize_keyboard=True)
    await message.answer("Выберите действие:", reply_markup=keyboard)
    await state.set_state(CurrencyManage.choosing_action)



@dp.message(CurrencyManage.choosing_action)
async def process_admin_action(message: Message, state: FSMContext):
    if message.text == "Добавить валюту":
        await message.answer("Введите название валюты:")
        await state.set_state(CurrencyManage.adding_currency_name)
    elif message.text == "Удалить валюту":
        await message.answer("Введите название валюты для удаления:")
        await state.set_state(CurrencyManage.deleting_currency_name)
    elif message.text == "Изменить курс валюты":
        await message.answer("Введите название валюты для изменения:")
        await state.set_state(CurrencyManage.updating_currency_name)
    else:
        await message.answer("Неверная команда. Попробуйте снова.")



@dp.message(CurrencyManage.adding_currency_name)
async def add_currency_name(message: Message, state: FSMContext):
    currency = message.text.upper()
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT 1 FROM currencies WHERE currency_name = $1", currency)
        if existing:
            await message.answer("Данная валюта уже существует.")
            await state.clear()
            return
    await state.update_data(currency_name=currency)
    await message.answer("Введите курс к рублю:")
    await state.set_state(CurrencyManage.adding_currency_rate)

@dp.message(CurrencyManage.adding_currency_rate)
async def add_currency_rate(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(',', '.'))
        data = await state.get_data()
        currency = data['currency_name']
        pool = dp["db_pool"]
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO currencies(currency_name, rate) VALUES ($1, $2)", currency, rate)
        await message.answer(f"Валюта {currency} успешно добавлена.")
    except ValueError:
        await message.answer("Неверный формат курса. Введите число.")
    await state.clear()



@dp.message(CurrencyManage.deleting_currency_name)
async def delete_currency(message: Message, state: FSMContext):
    currency = message.text.upper()
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM currencies WHERE currency_name = $1", currency)
    await message.answer(f"Валюта {currency} удалена.")
    await state.clear()


@dp.message(CurrencyManage.updating_currency_name)
async def update_currency_name(message: Message, state: FSMContext):
    currency = message.text.upper()
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM currencies WHERE currency_name = $1", currency)
    if not row:
        await message.answer("Такая валюта не найдена.")
        await state.clear()
        return
    await state.update_data(currency_name=currency)
    await message.answer("Введите новый курс к рублю:")
    await state.set_state(CurrencyManage.updating_currency_rate)


@dp.message(CurrencyManage.updating_currency_rate)
async def update_currency_rate(message: Message, state: FSMContext):
    try:
        new_rate = float(message.text.replace(',', '.'))
        data = await state.get_data()
        currency = data["currency_name"]
        pool = dp["db_pool"]
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE currencies SET rate = $1 WHERE currency_name = $2", new_rate, currency
            )
            if result == "UPDATE 0":
                await message.answer(f"Валюта {currency} не найдена.")
            else:
                await message.answer(f"Курс валюты {currency} успешно обновлён до {new_rate}")
    except ValueError:
        await message.answer("Неверный формат курса. Введите число.")
    await state.clear()



@dp.message(Command("convert"))
async def cmd_convert(message: Message, state: FSMContext):
    await message.answer("Введите название валюты:")
    await state.set_state(CurrencyManage.converting_currency_name)


@dp.message(CurrencyManage.converting_currency_name)
async def process_convert_currency(message: Message, state: FSMContext):
    currency = message.text.upper()
    pool = dp["db_pool"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT rate FROM currencies WHERE currency_name = $1", currency)
    if not row:
        await message.answer("Валюта не найдена.")
        await state.clear()
        return
    await state.update_data(currency_name=currency, rate=row['rate'])
    await message.answer("Введите сумму:")
    await state.set_state(CurrencyManage.converting_amount)


@dp.message(CurrencyManage.converting_amount)
async def process_convert_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))  
        data = await state.get_data()
        rate = float(data['rate'])  
        rub = amount * rate  
        await message.answer(f"{amount} {data['currency_name']} = {rub:.2f} RUB")
    except ValueError:
        await message.answer("Введите корректное число.")
    await state.clear()


if __name__ == '__main__':
    import asyncio

    async def main():
        pool = await asyncpg.create_pool(DB_URL)
        dp["db_pool"] = pool
        try:
            await dp.start_polling(bot)
        finally:
            await pool.close()

    asyncio.run(main())
