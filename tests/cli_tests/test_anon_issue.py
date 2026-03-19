"""Tests for anon issue."""

import asyncio

import httpx

BASE_URL = "http://localhost:8000"
ANON_ISSUE_URL = f"{BASE_URL}/api/v1/issues/anon-create"
contact_less_payload = {"issue_type": 1, "description": "Pole Dhalyo", "is_anonymous": True}
payload = {
    "issue_type": 1,
    "description": "Pole Dhalyo",
    "contact_no": "985207412",
    "issue_location": "Kathmandu, Nepal",
    "latitude": 27.70,
    "longitude": 85.324,
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
}


async def send_request():
    """Send a POST request to create an anonymous issue."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(ANON_ISSUE_URL, json=payload, headers=headers)
        print(response.status_code)
        print(response.json())


asyncio.run(send_request())
