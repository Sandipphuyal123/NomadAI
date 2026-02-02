import asyncio
import httpx

async def test_full_conversation_flow():
    url = "http://localhost:8000/api/chat"
    
    # Step 1: Start with empty message to get intro
    print("🔄 Step 1: Getting intro...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
        print(f"Intro: {data.get('message', '')[:100]}...")
        
    # Step 2: Say "yes" to give planning permission
    print("\n🔄 Step 2: Giving planning permission...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "yes"})
        data = r.json()
        print(f"Response: {data.get('message', '')}")
        
    # Step 3: Answer profile questions
    print("\n🔄 Step 3: Providing profile info...")
    
    # Answer days
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "3 days"})
        data = r.json()
        print(f"Days response: {data.get('message', '')}")
        
    # Answer group size
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "family of 4"})
        data = r.json()
        print(f"Group response: {data.get('message', '')}")
        
    # Answer budget
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "flexible budget"})
        data = r.json()
        print(f"Budget response: {data.get('message', '')}")
        
    # Answer comfort
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "comfortable"})
        data = r.json()
        print(f"Comfort response: {data.get('message', '')}")
        
    # Answer preferences
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "spiritual places and good food"})
        data = r.json()
        print(f"Preferences response: {data.get('message', '')[:200]}...")
        
        # Check if it's using LLM
        if len(data.get('message', '')) > 150:
            print("✅ LLM is working!")
        else:
            print("❌ Still using fallback")

if __name__ == "__main__":
    asyncio.run(test_full_conversation_flow())
