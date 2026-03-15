# pylint: disable=missing-module-docstring

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


async def test_asyncpg_connection():
    """Test that we can establish a connection to the database using asyncpg."""
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    print("Connection established successfully.")
    assert conn is not None
    await conn.close()
    print("Connection closed.")


asyncio.run(test_asyncpg_connection())
