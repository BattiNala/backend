import asyncio
import csv
import random
import string

import httpx

BASE_URL = "http://localhost:8000"
CREATE_URL = f"{BASE_URL}/api/v1/employee/add-staff"
ACCESS_TOKEN = ""

TEAMS = [
    {"team_name": "Durbarmarg", "team_id": 1, "department_name": "Electricity"},
    {"team_name": "Ratna Park", "team_id": 2, "department_name": "Electricity"},
    {"team_name": "Baneshwor", "team_id": 3, "department_name": "Electricity"},
    {"team_name": "Maharajgunj", "team_id": 4, "department_name": "Electricity"},
    {"team_name": "Teku", "team_id": 5, "department_name": "Electricity"},
    {"team_name": "Patan", "team_id": 6, "department_name": "Electricity"},
    {"team_name": "Bhaktapur", "team_id": 7, "department_name": "Electricity"},
    {"team_name": "Kuleshwor", "team_id": 8, "department_name": "Electricity"},
    {"team_name": "Kirtipur", "team_id": 9, "department_name": "Electricity"},
    {"team_name": "Balaju", "team_id": 10, "department_name": "Electricity"},
    {"team_name": "Jorpati", "team_id": 11, "department_name": "Electricity"},
    {"team_name": "Thimi", "team_id": 12, "department_name": "Electricity"},
    {"team_name": "Pulchowk", "team_id": 13, "department_name": "Electricity"},
    {"team_name": "Lagankhel", "team_id": 14, "department_name": "Electricity"},
]


def clean(text: str) -> str:
    return text.lower().replace(" ", "")


def generate_password(length=10):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(random.choice(chars) for _ in range(length))


async def create_employees():
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    csv_rows = []

    async with httpx.AsyncClient(timeout=30) as client:
        user_counter = 1

        for team in TEAMS:
            team_slug = clean(team["team_name"])
            dept_slug = clean(team["department_name"])

            for i in range(1, 6):
                email = f"user{i}@{team_slug}.{dept_slug}.gov"
                password = generate_password()

                payload = {
                    "name": f"User {i} {team['team_name']}",
                    "email": email,
                    "phone_number": f"980000{user_counter:04d}",
                    "team_id": team["team_id"],
                    "current_status": "available",
                    "password": password,
                }

                try:
                    response = await client.post(
                        f"{CREATE_URL}",
                        json=payload,
                        headers=headers,
                    )

                    if response.status_code in (200, 201):
                        print(f"Created: {email}")
                    else:
                        print(f"Failed: {email} -> {response.status_code} {response.text}")

                except Exception as e:
                    print(f"Error for {email}: {e}")

                csv_rows.append([email, password])
                user_counter += 1

                await asyncio.sleep(1)

    with open("employees.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["email", "password"])
        writer.writerows(csv_rows)

    print("\n📁 CSV saved as employees.csv")


if __name__ == "__main__":
    asyncio.run(create_employees())
