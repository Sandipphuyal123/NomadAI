import asyncio
import httpx
import json

async def debug_real_chat():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start a session and complete profile
        r = await client.post(url, json={"session_id": None, "message": ""})
        data = r.json()
        session_id = data.get('session_id')
        print("✅ Session started")
        
        # Quick profile
        profile = ["yes", "3 days", "solo", "flexible", "comfortable", "history and temples", "staying near boudha"]
        
        for msg in profile:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            print(f"Profile: {msg} -> {data.get('message', '')[:50]}...")
            if "Perfect" in data.get('message', ''):
                print("✅ Hotel set, testing LLM...")
                break
        
        # Test with a message that should trigger LLM
        print("\n🔄 Testing LLM with: 'tell me more about swayambhunath'")
        try:
            r = await client.post(url, json={"session_id": session_id, "message": "tell me more about swayambhunath"})
            data = r.json()
            response = data.get('message', '')
            print(f"Response: {response}")
            
            # Check if it's the generic fallback
            if "well-loved stop" in response.lower():
                print("❌ USING FALLBACK - LLM NOT WORKING")
                return False
            elif len(response) > 100:
                print("✅ LLM WORKING")
                return True
            else:
                print("⚠️ UNCLEAR")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            return False

if __name__ == "__main__":
    result = asyncio.run(debug_real_chat())
    print(f"\nFinal result: LLM Working = {result}")
