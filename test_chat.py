import asyncio
import httpx
import json

async def test_chat():
    url = "http://localhost:8000/api/chat"
    payload = {
        "session_id": None,
        "message": "Hello, can you help me plan a trip to Kathmandu?"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print("🔄 Testing chat endpoint...")
            r = await client.post(url, json=payload)
            print(f"Status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                print(f"✅ Response received:")
                print(f"Message: {data.get('message', 'No message')}")
                print(f"Reply: {data.get('reply', 'No reply')}")
                print(f"Session ID: {data.get('session_id', 'No session')}")
                return True
            else:
                print(f"❌ Error: {r.status_code}")
                print(f"Response: {r.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(test_chat())
