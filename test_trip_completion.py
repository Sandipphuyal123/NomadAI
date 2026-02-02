import asyncio
import httpx

async def test_trip_completion():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start and complete a 3-day trip exactly like yours
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        
        # Quick setup
        setup = ["yes", "3", "solo", "flexible", "comfortable", "history and temples", "staying near boudha"]
        for msg in setup:
            await client.post(url, json={"session_id": session_id, "message": msg})
        
        # Complete 3 days
        days = [
            ["Boudhanath Stupa", "Pashupatinath Temple"],
            ["Swayambhunath (Monkey Temple)", "Garden of Dreams"], 
            ["Asan Bazaar"]
        ]
        
        for day, places in enumerate(days, 1):
            for place in places:
                await client.post(url, json={"session_id": session_id, "message": place})
            await client.post(url, json={"session_id": session_id, "message": "Yes"})  # Save day
        
        # Now test what happens with different messages
        test_messages = [
            "this is enough",
            "tell me more about these places",
            "what should i know before visiting",
            "give me some travel tips"
        ]
        
        for msg in test_messages:
            print(f"\n🔄 Testing: '{msg}'")
            try:
                r = await client.post(url, json={"session_id": session_id, "message": msg})
                data = r.json()
                response = data.get('message', '')
                print(f"Response: {response[:200]}...")
                
                if len(response) > 150:
                    print("✅ LLM RESPONSE")
                else:
                    print("⚠️ SHORT RESPONSE")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_trip_completion())
