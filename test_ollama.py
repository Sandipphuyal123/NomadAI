import asyncio
import httpx
import os

async def test_ollama():
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    
    payload = {"model": model, "prompt": "Hello, how are you?", "stream": False}
    
    timeout = httpx.Timeout(60.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(f"{url}/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()
            text = str(data.get("response", "")).strip()
            print(f"✅ Ollama Response: {text}")
            return True
        except Exception as e:
            print(f"❌ Ollama Error: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(test_ollama())
