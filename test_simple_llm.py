import asyncio
import httpx

async def test_simple_llm():
    url = "http://localhost:8000/api/chat"
    
    # Use a longer timeout
    timeout = httpx.Timeout(30.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start fresh session
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
        print("Session started")
        
        # Complete profile quickly
        profile_messages = ["yes", "3 days", "family of 4", "flexible", "comfortable", "temples", "staying in thamel"]
        
        for msg in profile_messages:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            if "Perfect" in data.get('message', ''):
                print("✅ Hotel detected! Now testing LLM...")
                break
        
        # Test with a simple request that should trigger LLM
        try:
            r = await client.post(url, json={"session_id": session_id, "message": "what do you suggest for spiritual places?"})
            data = r.json()
            response = data.get('message', '')
            print(f"LLM Response: {response[:300]}...")
            
            if len(response) > 100:
                print("🎉 LLM IS WORKING!")
                return True
            else:
                print("❌ Still short response")
                return False
                
        except Exception as e:
            print(f"Error: {e}")
            return False

if __name__ == "__main__":
    result = asyncio.run(test_simple_llm())
    print(f"Final result: {result}")
