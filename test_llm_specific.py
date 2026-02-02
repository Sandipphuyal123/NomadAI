import asyncio
import httpx

async def test_llm_specific():
    url = "http://localhost:8000/api/chat"
    
    # Test with a message that would require LLM processing
    payload = {
        "session_id": None,
        "message": "I'm staying for 3 days with my family of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print("🔄 Testing complex LLM request...")
            r = await client.post(url, json=payload)
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                message = data.get('message', '')
                print(f"Response: {message}")
                
                # Check if response seems like LLM-generated
                if len(message) > 100 and ('itinerary' in message.lower() or 'day' in message.lower()):
                    print("✅ Likely using LLM (detailed response)")
                else:
                    print("⚠️ Might be using fallback (short/generic response)")
                    
                return True
            else:
                print(f"❌ Error: {r.status_code}")
                print(f"Response: {r.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(test_llm_specific())
