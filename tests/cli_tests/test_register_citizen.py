import asyncio
import csv

import httpx
from faker import Faker

API_URL = "http://localhost:8000/api/v1/auth/citizen-register"

CSV_FILE = "citizen_credentials.csv"

fake = Faker()


def generate_citizens(n=100):
    citizens = []

    for _ in range(n):
        username = fake.unique.user_name() + "@citizen.com"

        citizen = {
            "username": username,
            "password": fake.password(length=10, special_chars=False),
            "name": fake.name(),
            "phone_number": fake.msisdn()[:10],
            "email": username,
            "home_address": fake.address().replace("\n", ", "),
        }

        citizens.append(citizen)

    return citizens


def save_to_csv(citizens, filename=CSV_FILE):
    fieldnames = [
        "username",
        "password",
        "name",
        "phone_number",
        "email",
        "home_address",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(citizens)

    print(f"Saved {len(citizens)} records to {filename}")


async def send_request(client, citizen):
    try:
        response = await client.post(API_URL, json=citizen)
        print(f"{citizen['username']} -> {response.status_code}")

        if response.status_code not in (200, 201):
            print("Error:", response.text)

    except Exception as e:
        print(f"Error for {citizen['username']}: {e}")


async def bulk_add():
    citizens = generate_citizens(10)

    save_to_csv(citizens)

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [send_request(client, citizen) for citizen in citizens]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(bulk_add())
