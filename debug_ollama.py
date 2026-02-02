import asyncio
import httpx
import os

async def debug_ollama():
    # Test the exact same way the app does
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    
    print(f"Model: {model}")
    print(f"URL: {url}")
    
    # Test generate endpoint
    payload = {"model": model, "prompt": "Hello", "stream": False}
    
    timeout = httpx.Timeout(60.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            print("🔄 Testing /api/generate...")
            r = await client.post(f"{url}/api/generate", json=payload)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                text = str(data.get("response", "")).strip()
                print(f"✅ Generate Response: {text}")
            else:
                print(f"❌ Generate Error: {r.text}")
        except Exception as e:
            print(f"❌ Generate Exception: {e}")
            
        # Test chat endpoint
        messages = [{"role": "system", "content": "You are a helpful assistant."}, 
                   {"role": "user", "content": "Hello"}]
        chat_payload = {"model": model, "messages": messages, "stream": False}
        
        try:
            print("🔄 Testing /api/chat...")
            r = await client.post(f"{url}/api/chat", json=chat_payload)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                msg = data.get("message") or {}
                text = str(msg.get("content", "")).strip()
                print(f"✅ Chat Response: {text}")
            else:
                print(f"❌ Chat Error: {r.text}")
        except Exception as e:
            print(f"❌ Chat Exception: {e}")

if __name__ == "__main__":
    asyncio.run(debug_ollama())
