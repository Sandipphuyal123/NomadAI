import asyncio
import httpx

async def test_llm_vs_fallback():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Setup session
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        
        # Quick profile setup
        for msg in ["yes", "3", "solo", "flexible", "comfortable", "history and temples", "staying near boudha"]:
            await client.post(url, json={"session_id": session_id, "message": msg})
        
        # TEST 1: Questions that should break pattern matching
        pattern_breaking_questions = [
            "what's the weather like in kathmandu tomorrow",
            "can you write a poem about swayambhunath",
            "if i visit in july vs december, what's different",
            "compare buddhist vs hindu temples in kathmandu",
            "what if i only have 2 hours instead of a full day"
        ]
        
        print("🧪 TEST 1: Pattern-Breaking Questions")
        print("=" * 50)
        
        for i, question in enumerate(pattern_breaking_questions, 1):
            print(f"\n{i}. '{question}'")
            try:
                r = await client.post(url, json={"session_id": session_id, "message": question})
                data = r.json()
                response = data.get('message', '')
                print(f"Response: {response[:200]}...")
                
                # Check if it's generic fallback
                if "well-loved stop" in response.lower() or len(response) < 50:
                    print("❌ FALLBACK DETECTED")
                elif len(response) > 100:
                    print("✅ LIKELY REAL LLM")
                else:
                    print("⚠️ UNCLEAR")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
        
        # TEST 2: Contextual memory tests
        print(f"\n🧪 TEST 2: Contextual Memory Tests")
        print("=" * 50)
        
        contextual_tests = [
            "remember i said i'm solo? suggest places for solo travelers",
            "given that i like history, what's the most historical site",
            "since i'm staying near boudha, what's walking distance",
            "you know i have 3 days, prioritize the top 3 must-sees"
        ]
        
        for i, question in enumerate(contextual_tests, 1):
            print(f"\n{i}. '{question}'")
            try:
                r = await client.post(url, json={"session_id": session_id, "message": question})
                data = r.json()
                response = data.get('message', '')
                print(f"Response: {response[:200]}...")
                
                # Check if it remembers context
                if any(word in response.lower() for word in ["solo", "boudha", "3 days", "history"]):
                    print("✅ CONTEXT REMEMBERED - REAL LLM")
                else:
                    print("❌ NO CONTEXT - POSSIBLE FALLBACK")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
        
        # TEST 3: Nonsense/Impossible questions
        print(f"\n🧪 TEST 3: Nonsense/Impossible Questions")
        print("=" * 50)
        
        nonsense_tests = [
            "can i visit everest base camp in kathmandu for lunch",
            "are there polar bears at the kathmandu zoo",
            "what's the subway schedule from thamel to boudha",
            "do i need a spaceship to visit swayambhunath"
        ]
        
        for i, question in enumerate(nonsense_tests, 1):
            print(f"\n{i}. '{question}'")
            try:
                r = await client.post(url, json={"session_id": session_id, "message": question})
                data = r.json()
                response = data.get('message', '')
                print(f"Response: {response[:200]}...")
                
                # Check if it intelligently handles nonsense
                if any(word in response.lower() for word in ["everest", "polar", "subway", "spaceship"]):
                    print("✅ INTELLIGENT RESPONSE - REAL LLM")
                else:
                    print("❌ GENERIC RESPONSE - POSSIBLE FALLBACK")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_vs_fallback())
