"""
Simple test script for AI Community Companions.
Run this after starting the API server.
"""

import asyncio
import httpx

BASE_URL = "http://localhost:8000"


async def main():
    print("=" * 50)
    print("AI Community Companions - Test Script")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Health check
        print("\n[1] Health Check...")
        try:
            r = await client.get(f"{BASE_URL}/health")
            print(f"    Status: {r.json()['status']}")
        except httpx.ConnectError:
            print("    ERROR: Cannot connect to API. Is it running?")
            print("    Run: python -m mind.api.main")
            return

        # 2. Detailed health
        print("\n[2] Checking Components...")
        r = await client.get(f"{BASE_URL}/health/detailed")
        components = r.json().get("components", {})
        for name, status in components.items():
            icon = "✓" if status == "healthy" else "✗"
            print(f"    {icon} {name}: {status}")

        # 3. Initialize platform
        print("\n[3] Initializing Platform (2 communities)...")
        r = await client.post(f"{BASE_URL}/platform/initialize?num_communities=2")

        if r.status_code != 200:
            print(f"    ERROR: Status {r.status_code}")
            print(f"    Response: {r.text[:500]}")
            return

        data = r.json()

        if "error" in str(data).lower():
            print(f"    ERROR: {data}")
            return

        print(f"    Created {data['communities_created']} communities")
        for comm in data["communities"]:
            print(f"    - {comm['name']}: {comm['bots']} bots")

        # 4. Get platform stats
        print("\n[4] Platform Stats...")
        r = await client.get(f"{BASE_URL}/platform/stats")
        stats = r.json()
        print(f"    Total communities: {stats['total_communities']}")
        print(f"    Active bots: {stats['active_bots']}")

        # 5. Get bots from first community
        community_id = data["communities"][0]["id"]
        print(f"\n[5] Fetching Bots from '{data['communities'][0]['name']}'...")
        r = await client.get(f"{BASE_URL}/communities/{community_id}/bots?limit=3")
        bots = r.json()

        for bot in bots:
            print(f"\n    Bot: {bot['display_name']} ({bot['handle']})")
            print(f"    Bio: {bot['bio'][:60]}...")
            print(f"    Mood: {bot['mood']} | Energy: {bot['energy']}")
            print(f"    Interests: {', '.join(bot['interests'][:3])}")

        # 6. Chat with a bot
        if bots:
            bot = bots[0]
            print(f"\n[6] Chatting with {bot['display_name']}...")
            print(f"    You: Hey! What's something you've been excited about lately?")

            try:
                r = await client.post(
                    f"{BASE_URL}/bots/{bot['id']}/message",
                    json={
                        "bot_id": str(bot["id"]),
                        "conversation_id": "test-conversation-1",
                        "content": "Hey! What's something you've been excited about lately?",
                        "is_direct_message": True,
                    },
                )
                response = r.json()

                print(f"\n    {bot['display_name']}: {response['text']}")
                print(f"\n    [Response delay: {response['response_delay_ms']}ms]")
                print(f"    [Typing time: {response['typing_delay_ms']}ms]")
                print(f"    [New mood: {response['emotional_state']['mood']}]")

            except Exception as e:
                print(f"    Error chatting: {e}")

        print("\n" + "=" * 50)
        print("Test Complete!")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
