import asyncio
import httpx

async def test_conversation_flow():
    url = "http://localhost:8000/api/chat"
    
    # Step 1: Start with empty message to get intro
    print("🔄 Step 1: Getting intro...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
        print(f"Intro: {data.get('message', '')[:100]}...")
        print(f"Session ID: {session_id}")
        
    # Step 2: Say "yes" to give planning permission
    print("\n🔄 Step 2: Giving planning permission...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "yes"})
        data = r.json()
        print(f"Response: {data.get('message', '')[:100]}...")
        
    # Step 3: Now send the complex message
    print("\n🔄 Step 3: Sending complex travel request...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": session_id, "message": "I'm staying for 3 days with my family of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"})
        data = r.json()
        print(f"Response: {data.get('message', '')[:200]}...")
        
        # Check if it's using LLM
        if len(data.get('message', '')) > 150:
            print("✅ LLM is working!")
        else:
            print("❌ Still using fallback")

if __name__ == "__main__":
    asyncio.run(test_conversation_flow())
