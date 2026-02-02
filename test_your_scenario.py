import asyncio
import httpx

async def test_your_exact_scenario():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start session
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
        
        # Replicate your exact conversation
        messages = [
            "Yes",
            "3", 
            "solo",
            "flexible",
            "more comfortable",  # Note: typo like in your conversation
            "history and temples",
            "hello",  # Your first hotel response
            "I'm staying near Boudha",
            "Boudhanath Stupa",
            "Pashupatinath Temple", 
            "Yes",  # Save Day 1
            "Swayambhunath (Monkey Temple)",
            "Garden of Dreams",
            "Yes",  # Save Day 2  
            "Asan Bazaar",
            "Save Day 3",
            "Yes",  # Save Day 3
            "this is enough"  # Your final message
        ]
        
        for i, msg in enumerate(messages):
            print(f"\n--- Message {i+1}: '{msg}' ---")
            try:
                r = await client.post(url, json={"session_id": session_id, "message": msg})
                data = r.json()
                response = data.get('message', '')
                print(f"Response: {response[:100]}...")
                
                # Check if responses are generic fallbacks
                if "well-loved stop" in response.lower():
                    print("⚠️ GENERIC FALLBACK RESPONSE")
                elif len(response) > 150:
                    print("✅ DETAILED LLM RESPONSE")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_your_exact_scenario())
