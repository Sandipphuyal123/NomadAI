import asyncio
import httpx

async def test_day_planning():
    url = "http://localhost:8000/api/chat"
    
    # Start fresh session and complete profile
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
    
    # Quick profile setup
    profile_messages = ["yes", "3 days", "family of 4", "flexible", "comfortable", "temples and food", "staying in thamel"]
    
    for msg in profile_messages:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            if "Perfect" in data.get('message', ''):
                print("✅ Hotel detected!")
                break
    
    # Now let's plan Day 1 with LLM suggestions
    planning_messages = [
        "What do you recommend for spiritual places?",
        "Suggest some temples for day 1",
        "I'd like to visit Pashupatinath and Boudhanath"
    ]
    
    for i, msg in enumerate(planning_messages):
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            response = data.get('message', '')
            print(f"\nPlanning Step {i+1}: {msg}")
            print(f"Response: {response[:400]}...")
            
            # Check if we're getting detailed LLM responses
            if len(response) > 150 and any(word in response.lower() for word in ["suggest", "recommend", "perfect", "excellent", "great"]):
                print("🎉 LLM IS WORKING!")
                print(f"Full response: {response}")
                return

if __name__ == "__main__":
    asyncio.run(test_day_planning())
