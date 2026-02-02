import asyncio
import httpx

async def test_manual_flow():
    """Test the flow exactly as a user would interact with it"""
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start fresh session
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        print("✅ Fresh session started")
        
        # Complete profile exactly as user would
        user_flow = [
            "yes",           # Give planning permission
            "2",            # 2 days
            "solo",         # Solo travel
            "flexible",     # Flexible budget
            "comfortable",  # Comfort level
            "history and temples",  # Preferences
            "thamel"        # Hotel area
        ]
        
        for i, msg in enumerate(user_flow):
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            response = data.get('message', '')
            print(f"\nStep {i+1}: '{msg}'")
            print(f"Response: {response[:100]}...")
            
            # Check for hotel confirmation
            if "Good choice" in response:
                print("🏨 ✅ Improved hotel explanation detected!")
        
        # Plan days exactly as user would
        print(f"\n🧪 DAY PLANNING:")
        print("=" * 30)
        
        # Day 1
        day1_places = ["Boudhanath Stupa", "Pashupatinath Temple"]
        for place in day1_places:
            r = await client.post(url, json={"session_id": session_id, "message": place})
            data = r.json()
            print(f"Added {place}: {data.get('message', '')[:60]}...")
        
        # Save Day 1
        r = await client.post(url, json={"session_id": session_id, "message": "Yes"})
        data = r.json()
        response = data.get('message', '')
        print(f"Day 1 save: {response[:100]}...")
        
        # Day 2
        day2_places = ["Swayambhunath (Monkey Temple)", "Garden of Dreams"]
        for place in day2_places:
            r = await client.post(url, json={"session_id": session_id, "message": place})
            data = r.json()
            print(f"Added {place}: {data.get('message', '')[:60]}...")
        
        # Save Day 2 - THIS IS WHERE THE BUG SHOULD APPEAR
        r = await client.post(url, json={"session_id": session_id, "message": "Yes"})
        data = r.json()
        response = data.get('message', '')
        print(f"\n🎯 CRITICAL TEST - Day 2 save:")
        print(f"Response: {response[:200]}...")
        
        # Check results
        if "day 3" in response.lower():
            print("❌ DAY 3 BUG STILL EXISTS")
        elif "budget" in response.lower() or "npr" in response.lower() or "export" in response.lower():
            print("✅ DAY 3 BUG FIXED - Trip completed properly!")
            if "budget" in response.lower():
                print("✅ BUDGET INFORMATION INCLUDED!")
        else:
            print("⚠️ UNCLEAR RESULT - Need investigation")

if __name__ == "__main__":
    asyncio.run(test_manual_flow())
