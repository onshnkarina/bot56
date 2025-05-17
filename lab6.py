from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import os
from dotenv import load_dotenv


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()

async def get_connection():
    return await asyncpg.connect(DATABASE_URL)


class CurrencyInput(BaseModel):
    currency_name: str
    rate: float

class CurrencyUpdate(BaseModel):
    currency_name: str
    rate: float

class CurrencyDelete(BaseModel):
    currency_name: str

async def currency_exists(conn, name: str) -> bool:
    result = await conn.fetchrow(
        "SELECT 1 FROM currenci WHERE LOWER(currency_name) = LOWER($1)",
        name
    )
    return result is not None


@app.post("/load")
async def load_currency(data: CurrencyInput):
    conn = await get_connection()
    try:
        if await currency_exists(conn, data.currency_name):
            raise HTTPException(status_code=400, detail="Currency already exists.")
        await conn.execute(
            "INSERT INTO currenci (currency_name, rate) VALUES ($1, $2)",
            data.currency_name, data.rate
        )
        return {"message": "Currency added successfully."}
    finally:
        await conn.close()


@app.post("/update_currency")
async def update_currency(data: CurrencyUpdate):
    conn = await get_connection()
    try:
        if not await currency_exists(conn, data.currency_name):
            raise HTTPException(status_code=404, detail="Currency not found.")
        await conn.execute(
            "UPDATE currenci SET rate = $1 WHERE LOWER(currency_name) = LOWER($2)",
            data.rate, data.currency_name 
        )
        return {"message": "Currency updated successfully."}
    finally:
        await conn.close()


@app.post("/delete")
async def delete_currency(data: CurrencyDelete):
    conn = await get_connection()
    try:
        if not await currency_exists(conn, data.currency_name):
            raise HTTPException(status_code=404, detail="Currency not found.")
        await conn.execute(
            "DELETE FROM currenci WHERE LOWER(currency_name) = LOWER($1)",
            data.currency_name
        )
        return {"message": "Currency deleted successfully."}
    finally:
        await conn.close()
