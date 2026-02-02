import asyncio
import httpx

async def test_better_questions():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Setup session like yours
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        
        # Quick profile
        for msg in ["yes", "3", "solo", "flexible", "comfortable", "history and temples", "staying near boudha"]:
            await client.post(url, json={"session_id": session_id, "message": msg})
        
        # Instead of just place names, ask informational questions
        better_questions = [
            "tell me more about boudhanath stupa",
            "what's special about pashupatinath temple", 
            "why should i visit swayambhunath",
            "what's the best time to visit these places",
            "give me some tips for visiting temples in kathmandu"
        ]
        
        for i, question in enumerate(better_questions):
            print(f"\n--- Question {i+1}: '{question}' ---")
            try:
                r = await client.post(url, json={"session_id": session_id, "message": question})
                data = r.json()
                response = data.get('message', '')
                print(f"Response: {response[:300]}...")
                
                if len(response) > 100 and "well-loved stop" not in response:
                    print("✅ GOOD LLM RESPONSE")
                else:
                    print("⚠️ GENERIC RESPONSE")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_better_questions())
