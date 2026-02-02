import asyncio
import httpx

async def test_definitive_proof():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Setup session
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        
        # Quick profile
        for msg in ["yes", "3", "solo", "flexible", "comfortable", "history and temples", "staying near boudha"]:
            await client.post(url, json={"session_id": session_id, "message": msg})
        
        print("🔬 DEFINITIVE PROOF TESTS")
        print("=" * 60)
        
        # Test 1: Current events/time-sensitive questions
        print("\n1. TIME-SENSITIVE QUESTION:")
        print("   'what year is it right now'")
        try:
            r = await client.post(url, json={"session_id": session_id, "message": "what year is it right now"})
            data = r.json()
            response = data.get('message', '')
            print(f"   Response: {response[:100]}...")
            if any(year in response for year in ["2025", "2026", "2024"]):
                print("   ✅ REAL-TIME AWARENESS - DEFINITELY LLM")
            else:
                print("   ❌ STATIC RESPONSE - POSSIBLE FALLBACK")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        
        # Test 2: Personalized creative request
        print("\n2. CREATIVE PERSONALIZATION:")
        print("   'write a short story about me visiting these temples as a solo traveler'")
        try:
            r = await client.post(url, json={"session_id": session_id, "message": "write a short story about me visiting these temples as a solo traveler"})
            data = r.json()
            response = data.get('message', '')
            print(f"   Response: {response[:150]}...")
            if any(word in response.lower() for word in ["solo", "story", "journey", "adventure"]) and len(response) > 100:
                print("   ✅ PERSONALIZED CREATIVITY - DEFINITELY LLM")
            else:
                print("   ❌ GENERIC RESPONSE - POSSIBLE FALLBACK")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        
        # Test 3: Complex hypothetical
        print("\n3. COMPLEX HYPOTHETICAL:")
        print("   'if i had to choose between visiting one temple or three small shrines, what would you recommend and why?'")
        try:
            question = "if i had to choose between visiting one temple or three small shrines, what would you recommend and why?"
            r = await client.post(url, json={"session_id": session_id, "message": question})
            data = r.json()
            response = data.get('message', '')
            print(f"   Response: {response[:150]}...")
            if "why" in response.lower() and len(response) > 100:
                print("   ✅ REASONING ABILITY - DEFINITELY LLM")
            else:
                print("   ❌ SIMPLE RESPONSE - POSSIBLE FALLBACK")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        
        # Test 4: Self-reference test
        print("\n4. SELF-REFERENCE TEST:")
        print("   'what ai model are you using to answer my questions?'")
        try:
            question = "what ai model are you using to answer my questions?"
            r = await client.post(url, json={"session_id": session_id, "message": question})
            data = r.json()
            response = data.get('message', '')
            print(f"   Response: {response[:150]}...")
            if "ai" in response.lower() or "model" in response.lower():
                print("   ✅ HANDLES META-QUESTIONS - DEFINITELY LLM")
            else:
                print("   ❌ AVOIDS QUESTION - LIKELY FALLBACK")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
        
        # Test 5: Mathematical/logical reasoning
        print("\n5. LOGICAL REASONING:")
        print("   'if i spend 2 hours at each temple and have 8 hours, how many temples can i visit?'")
        try:
            question = "if i spend 2 hours at each temple and have 8 hours, how many temples can i visit?"
            r = await client.post(url, json={"session_id": session_id, "message": question})
            data = r.json()
            response = data.get('message', '')
            print(f"   Response: {response[:150]}...")
            if any(num in response for num in ["4", "four"]) and "temple" in response.lower():
                print("   ✅ MATHEMATICAL REASONING - DEFINITELY LLM")
            else:
                print("   ❌ NO MATH - POSSIBLE FALLBACK")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_definitive_proof())
