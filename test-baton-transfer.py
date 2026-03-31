import asyncio
from httpx import AsyncClient

async def main():
    async with AsyncClient(base_url="https://ihouse-core-production-ee42.up.railway.app") as client:
        # Assuming permissions_router handles the baton transfer
        res = await client.delete(
            "/staff/assignments/bd2e5bec-6e5b-4483-9390-ca84b46f8d9a/KPG-500",
            headers={"Authorization": "Bearer DEV-TOKEN"} # wait, I don't have a staging token
        )
        print(res.status_code, res.text)

asyncio.run(main())
