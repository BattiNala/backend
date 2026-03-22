import asyncio

import httpx

BASE_URL = "http://localhost:8000"
TEAM_URL = f"{BASE_URL}/api/v1/team/create-team"
ACCESS_TOKEN = ""

teams = [
    {
        "team_name": "Durbarmarg",
        "base_latitude": 27.7116,
        "base_longitude": 85.3173,
        "coverage_radius_km": 8,
    },
    {
        "team_name": "Ratna Park",
        "base_latitude": 27.7066,
        "base_longitude": 85.3145,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Baneshwor",
        "base_latitude": 27.6928,
        "base_longitude": 85.3420,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Maharajgunj",
        "base_latitude": 27.7395,
        "base_longitude": 85.3312,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Teku",
        "base_latitude": 27.6919,
        "base_longitude": 85.3015,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Patan",
        "base_latitude": 27.6669,
        "base_longitude": 85.3247,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Bhaktapur",
        "base_latitude": 27.6710,
        "base_longitude": 85.4298,
        "coverage_radius_km": 8,
    },
    {
        "team_name": "Kuleshwor",
        "base_latitude": 27.6943,
        "base_longitude": 85.2846,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Kirtipur",
        "base_latitude": 27.6781,
        "base_longitude": 85.2775,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Balaju",
        "base_latitude": 27.7352,
        "base_longitude": 85.3051,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Jorpati",
        "base_latitude": 27.7281,
        "base_longitude": 85.3724,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Thimi",
        "base_latitude": 27.6822,
        "base_longitude": 85.3878,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Pulchowk",
        "base_latitude": 27.6786,
        "base_longitude": 85.3165,
        "coverage_radius_km": 6,
    },
    {
        "team_name": "Lagankhel",
        "base_latitude": 27.6674,
        "base_longitude": 85.3230,
        "coverage_radius_km": 6,
    },
]

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


async def main():
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        for team in teams:
            try:
                res = await client.post(TEAM_URL, json=team)
                res.raise_for_status()
                print(f"Created: {team['team_name']}")
            except httpx.HTTPStatusError as e:
                print(f"Failed: {team['team_name']} -> {e.response.status_code} {e.response.text}")
            except Exception as e:
                print(f"Error: {team['team_name']} -> {str(e)}")

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
