"""Create GitHub repository for the project."""
import asyncio
import aiohttp
import sys
sys.path.insert(0, ".")

from mind.config.settings import settings

async def create_repo():
    token = settings.GITHUB_TOKEN
    if not token:
        print("No GitHub token configured")
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    repo_data = {
        "name": "hive",
        "description": "Autonomous AI social simulation where bots have genuine minds, learn, evolve, and write code to improve themselves",
        "private": False,
        "auto_init": False
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=repo_data
        ) as response:
            if response.status == 201:
                data = await response.json()
                print(f"Repository created: {data['html_url']}")
                print(f"Clone URL: {data['clone_url']}")
                return data
            else:
                error = await response.json()
                print(f"Failed to create repo: {error.get('message', 'Unknown error')}")
                if "already exists" in str(error):
                    print("Repository already exists, that's fine!")
                    return {"clone_url": f"https://github.com/VaibhavJeet/hive.git"}
                return None

if __name__ == "__main__":
    asyncio.run(create_repo())
