"""Tests for issue create."""

import asyncio

import httpx

BASE_URL = "http://localhost:8000"
ISSUE_URL = f"{BASE_URL}/api/v1/issues/create"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjozMDMsImV4cCI6MTc3ODQxMTEwNn0.fpo-jY_WK-dAuwfHlDM3_W1rrtURYiEb3TagPTVjHdE"  # noqa: E501
headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
}
useragent = (
    "BattinalaApp/1.0 (Linux; Android 10; SM-N960F Build/QP1A.190711.020; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/88.0.4324.181 Mobile Safari/537.36"
)
headers["User-Agent"] = useragent


async def create_issue():
    """Create an issue with photos and JSON data."""
    with open("tests/cli_tests/pole_1.jpg", "rb") as photo_file:
        files = [
            (
                "photos",
                ("STEP_2.png", photo_file, "image/png"),
            ),
            (
                "issue_create",
                (
                    None,
                    '{"issue_type":1,"description":"tangled wires","contact_no":"999999999","issue_location":"thamel", "latitude": 27.6847791, "longitude": 85.3144442}',  # noqa: E501
                    "application/json",
                ),
            ),
        ]
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(ISSUE_URL, headers=headers, files=files)
            print(response.status_code)
            print(response.text)


asyncio.run(create_issue())
