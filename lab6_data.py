from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
import os
import psycopg2
from decimal import Decimal


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


app = FastAPI()


conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()


@app.get("/convert")
def convert_currency(currency_name: str = Query(...), amount: float = Query(...)):
    cursor.execute("SELECT rate FROM currenci WHERE LOWER(currency_name) = LOWER(%s)", (currency_name,))
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Currency not found")

    rate = result[0]
    converted = round(Decimal(amount) * Decimal(rate), 2)
    return {"converted_amount": float(converted)}


@app.get("/currencies")
def get_all_currencies():
    cursor.execute("SELECT currency_name, rate FROM currenci")
    rows = cursor.fetchall()
    result = [{"currency_name": name, "rate": float(rate)} for name, rate in rows]
    return result
