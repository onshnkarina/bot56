import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN2")
CURRENCY_MANAGER_URL = os.getenv("CURRENCY_MANAGER_URL")
DATA_MANAGER_URL = os.getenv("DATA_MANAGER_URL")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class CurrencyState(StatesGroup):
    waiting_for_name = State()
    waiting_for_rate = State()

class DeleteCurrencyState(StatesGroup):
    waiting_for_name = State()

class UpdateCurrencyState(StatesGroup):
    waiting_for_name = State()
    waiting_for_rate = State()

class ConvertState(StatesGroup):
    waiting_for_currency = State()
    waiting_for_amount = State()


@dp.message(Command("start"))
async def start_command(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/manage_currency")],
            [KeyboardButton(text="/get_currencies")],
            [KeyboardButton(text="/convert")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Выберите команду:", reply_markup=kb)



@dp.message(Command("manage_currency"))
async def manage_currency(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Добавить валюту")],
            [KeyboardButton(text="Удалить валюту")],
            [KeyboardButton(text="Изменить курс валюты")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Выберите действие:", reply_markup=kb)



@dp.message(lambda msg: msg.text == "Добавить валюту")
async def add_currency_name(message: types.Message, state: FSMContext):
    await message.answer("Введите название валюты:")
    await state.set_state(CurrencyState.waiting_for_name)


@dp.message(CurrencyState.waiting_for_name)
async def receive_currency_name(message: types.Message, state: FSMContext):
    currency = message.text.strip().upper()  
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DATA_MANAGER_URL}/currencies") as resp:
            currencies = await resp.json()
            if any(c["currency_name"] == currency for c in currencies):
                await message.answer("Данная валюта уже существует.")
                await state.clear()
                return

    await state.update_data(currency_name=currency)
    await message.answer("Введите курс к рублю:")
    await state.set_state(CurrencyState.waiting_for_rate)



@dp.message(CurrencyState.waiting_for_rate)
async def receive_currency_rate(message: types.Message, state: FSMContext):
    try:
        rate = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число.")
        return

    data = await state.get_data()
    currency = data["currency_name"]

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CURRENCY_MANAGER_URL}/load", json={"currency_name": currency, "rate": rate}) as resp:
            if resp.status == 400:
                await message.answer("Валюта уже существует, попробуйте обновить курс через соответствующую команду.")
                await state.clear()
                return

    await message.answer(f"Валюта {currency.upper()} успешно добавлена с курсом {rate}.")
    await state.clear()



@dp.message(lambda msg: msg.text == "Удалить валюту")
async def delete_currency(message: types.Message, state: FSMContext):
    await message.answer("Введите название валюты:")
    await state.set_state(DeleteCurrencyState.waiting_for_name)

@dp.message(DeleteCurrencyState.waiting_for_name)
async def delete_currency_name(message: types.Message, state: FSMContext):
    currency = message.text.lower()
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CURRENCY_MANAGER_URL}/delete", json={"currency_name": currency}) as resp:
            if resp.status == 404:
                await message.answer("Такой валюты не существует.")
            else:
                await message.answer(f"Валюта {currency.upper()} удалена.")
    await state.clear()



@dp.message(lambda msg: msg.text == "Изменить курс валюты")
async def update_currency(message: types.Message, state: FSMContext):
    await message.answer("Введите название валюты:")
    await state.set_state(UpdateCurrencyState.waiting_for_name)


@dp.message(UpdateCurrencyState.waiting_for_name)
async def update_currency_name(message: types.Message, state: FSMContext):
    await state.update_data(currency_name=message.text.lower())
    await message.answer("Введите новый курс:")
    await state.set_state(UpdateCurrencyState.waiting_for_rate)


@dp.message(UpdateCurrencyState.waiting_for_rate)
async def update_currency_rate(message: types.Message, state: FSMContext):
    try:
        rate = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректное число.")
        return

    data = await state.get_data()
    currency = data["currency_name"]

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CURRENCY_MANAGER_URL}/update_currency", json={"currency_name": currency, "rate": rate}) as resp:
            if resp.status == 404:
                await message.answer("Валюта не найдена.")
            else:
                await message.answer(f"Курс для {currency.upper()} обновлён.")
    await state.clear()



@dp.message(Command("get_currencies"))
async def get_currencies(message: types.Message):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DATA_MANAGER_URL}/currencies") as resp:
            if resp.status != 200:
                await message.answer("Ошибка при получении данных.")
                return
            currencies = await resp.json()
            text = "\n".join([f"{c['currency_name'].upper()}: {c['rate']}" for c in currencies])
            await message.answer(f"Список валют:\n{text}" if currencies else "Список валют пуст.")



@dp.message(Command("convert"))
async def convert_currency(message: types.Message, state: FSMContext):
    await message.answer("Введите название валюты:")
    await state.set_state(ConvertState.waiting_for_currency)


@dp.message(ConvertState.waiting_for_currency)
async def convert_currency_amount(message: types.Message, state: FSMContext):
    await state.update_data(currency_name=message.text.lower())
    await message.answer("Введите сумму:")
    await state.set_state(ConvertState.waiting_for_amount)


@dp.message(ConvertState.waiting_for_amount)
async def convert_currency_result(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректную сумму.")
        return

    data = await state.get_data()
    currency = data["currency_name"]

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DATA_MANAGER_URL}/convert", params={"currency_name": currency, "amount": amount}) as resp:
            if resp.status == 404:
                await message.answer("Такая валюта не найдена.")
            else:
                result = await resp.json()
                await message.answer(f"{amount} {currency.upper()} = {result['converted_amount']:.2f} RUB")


    await state.clear()


if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot))
