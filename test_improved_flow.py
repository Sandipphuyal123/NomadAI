import asyncio
import httpx

async def test_improved_flow():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start session
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        print("✅ Session started")
        
        # Test the improved guided area selection
        print("\n🧪 TESTING IMPROVED AREA SELECTION:")
        print("=" * 50)
        
        # Complete profile
        profile = ["yes", "2", "solo", "flexible", "comfortable", "history and temples"]
        
        for msg in profile:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            response = data.get('message', '')
            print(f"Q: {msg}")
            print(f"A: {response[:100]}...")
            print()
        
        # Test area suggestions
        print("🧪 TESTING AREA SUGGESTIONS:")
        r = await client.post(url, json={"session_id": session_id, "message": ""})
        data = r.json()
        suggestions = data.get('suggestions', [])
        print(f"Area suggestions: {suggestions}")
        
        # Test area selection with improved explanations
        print("\n🧪 TESTING IMPROVED AREA EXPLANATIONS:")
        test_areas = ["thamel", "near boudha", "near durbar square"]
        
        for area in test_areas:
            # Reset session for each test
            r = await client.post(url, json={"session_id": None, "message": ""})
            session_id = r.json().get('session_id')
            
            # Quick setup
            for msg in ["yes", "2", "solo", "flexible", "comfortable", "history and temples"]:
                await client.post(url, json={"session_id": session_id, "message": msg})
            
            # Test area selection
            r = await client.post(url, json={"session_id": session_id, "message": area})
            data = r.json()
            response = data.get('message', '')
            print(f"\nArea: {area}")
            print(f"Response: {response[:200]}...")
            
            # Check for improved explanations
            if any(word in response.lower() for word in ["lively", "quiet", "historic", "perfect choice", "good choice", "great pick"]):
                print("✅ IMPROVED EXPLANATION DETECTED")
            else:
                print("⚠️ STANDARD RESPONSE")
        
        # Test Day 3 bug fix
        print("\n🧪 TESTING DAY 3 BUG FIX:")
        print("=" * 30)
        
        # Reset and complete 2-day trip
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        
        # Quick setup for 2 days
        for msg in ["yes", "2", "solo", "flexible", "comfortable", "history and temples", "near boudha"]:
            await client.post(url, json={"session_id": session_id, "message": msg})
        
        # Complete Day 1
        for place in ["Boudhanath Stupa", "Pashupatinath Temple"]:
            await client.post(url, json={"session_id": session_id, "message": place})
        await client.post(url, json={"session_id": session_id, "message": "Yes"})
        
        # Complete Day 2  
        for place in ["Swayambhunath (Monkey Temple)", "Garden of Dreams"]:
            await client.post(url, json={"session_id": session_id, "message": place})
        await client.post(url, json={"session_id": session_id, "message": "Yes"})
        
        # Check if it tries to suggest Day 3 (it shouldn't)
        r = await client.post(url, json={"session_id": session_id, "message": "what's next"})
        data = r.json()
        response = data.get('message', '')
        print(f"After completing 2 days: {response[:200]}...")
        
        if "day 3" in response.lower():
            print("❌ DAY 3 BUG STILL EXISTS")
        elif "budget" in response.lower() or "export" in response.lower():
            print("✅ DAY 3 BUG FIXED - Trip completed properly")
        else:
            print("⚠️ UNCLEAR RESULT")
        
        # Test budget estimation
        print("\n🧪 TESTING BUDGET ESTIMATION:")
        print("=" * 35)
        
        if "budget" in response.lower() or "npr" in response.lower():
            print("✅ BUDGET INFORMATION INCLUDED")
            print(f"Budget preview: {response[:300]}...")
        else:
            print("❌ NO BUDGET INFORMATION")

if __name__ == "__main__":
    asyncio.run(test_improved_flow())
