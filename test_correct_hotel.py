import asyncio
import httpx

async def test_correct_hotel():
    url = "http://localhost:8000/api/chat"
    
    # Start fresh session
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
    
    # Complete profile with correct hotel pattern
    profile_messages = [
        "yes", 
        "3 days", 
        "family of 4", 
        "flexible", 
        "comfortable", 
        "temples and food", 
        "staying in thamel"  # This matches the pattern
    ]
    
    for i, msg in enumerate(profile_messages):
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            response = data.get('message', '')
            print(f"Step {i+1}: {msg}")
            print(f"Response: {response[:300]}...")
            print("---")
            
            # Check if we're getting detailed LLM responses
            if len(response) > 200 and ("day" in response.lower() or "suggest" in response.lower() or "itinerary" in response.lower()):
                print("🎉 LLM IS WORKING!")
                print(f"Full response: {response}")
                return

if __name__ == "__main__":
    asyncio.run(test_correct_hotel())
