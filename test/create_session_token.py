import asyncio
import webbrowser
import aiohttp

API_URL = "http://localhost/api/v1"


async def parse_data(response: aiohttp.ClientResponse) -> dict:
    if response.content_type == "application/json":
        response_json = await response.json()
        print(response_json)
        if response_json.get("data"):
            return response_json["data"]


async def run():
    client_session = aiohttp.ClientSession()
    async with client_session.post(API_URL + "/auth/login/session") as response:
        assert response.status == 200
        data = await parse_data(response)

    session_id = data["session_id"]
    webbrowser.open(f"{API_URL}/auth/authorization-url?session_id={session_id}", new=2)

    _wait_for_auth = input("인증이 완료되었으면 Enter키를 누르세요")

    async with client_session.get(
        API_URL + "/auth/login/session", params={"session_id": session_id}
    ) as response:
        assert response.status == 200
        data = await parse_data(response)

    token = data["access_token"]
    print(f"Session Token: {token}")
    await client_session.close()


asyncio.run(run())
