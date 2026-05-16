import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()


def db_query(query, params=(), fetch=False, commit=False):
    conn = mysql.connector.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("SSH_HOST"),
        port=3306,
        database=os.getenv("DB_NAME")
    )
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
        return cursor.fetchall() if fetch else None
    finally:
        cursor.close()
        conn.close()