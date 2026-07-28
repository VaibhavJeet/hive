"""Test GitHub integration."""
import asyncio
import os
import sys
sys.path.insert(0, ".")

from mind.config.settings import settings

async def test_github():
    import aiohttp

    token = settings.GITHUB_TOKEN
    if not token:
        print("No GitHub token configured in .env")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.github.com/user", headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                print(f"GitHub connected successfully!")
                print(f"Username: {data['login']}")
                print(f"Name: {data.get('name', 'N/A')}")
                print(f"Public repos: {data['public_repos']}")
                scopes = response.headers.get("X-OAuth-Scopes", "")
                print(f"Token scopes: {scopes}")
                return True
            else:
                error = await response.json()
                print(f"Authentication failed: {error.get('message', 'Unknown error')}")
                return False

if __name__ == "__main__":
    asyncio.run(test_github())
