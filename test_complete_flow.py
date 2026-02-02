import asyncio
import httpx

async def test_complete_conversation_flow():
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
        
    # Step 3: Answer all profile questions
    print("\n🔄 Step 3: Providing complete profile info...")
    
    questions_and_answers = [
        ("3 days", "How many days will you be in Kathmandu?"),
        ("family of 4", "Solo, duo, or group? How many people?"),
        ("flexible budget", "Rough budget in mind, or keep it flexible?"),
        ("comfortable", "Budget, mid-range, or more comfortable?"),
        ("spiritual places and food", "What do you enjoy most — history, temples, food, or quieter spots?"),
        ("staying in thamel", "Where are you staying in Kathmandu?")
    ]
    
    for answer, expected_question in questions_and_answers:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"session_id": session_id, "message": answer})
            data = r.json()
            response = data.get('message', '')
            print(f"Q: {expected_question[:50]}...")
            print(f"A: {answer}")
            print(f"Response: {response[:100]}...")
            
            # Check if we're getting LLM responses
            if len(response) > 150 and "day" in response.lower():
                print("✅ LLM is working!")
                return
            print()

if __name__ == "__main__":
    asyncio.run(test_complete_conversation_flow())
