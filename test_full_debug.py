import asyncio
import httpx

async def test_full_debug():
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start session
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        print("✅ Session started")
        
        # Complete profile step by step
        profile_steps = [
            ("yes", "Give planning permission"),
            ("2", "Set days"),
            ("solo", "Set group"),  
            ("flexible", "Set budget"),
            ("comfortable", "Set comfort"),
            ("history and temples", "Set preferences")
        ]
        
        for msg, desc in profile_steps:
            r = await client.post(url, json={"session_id": session_id, "message": msg})
            data = r.json()
            response = data.get('message', '')
            print(f"\n{desc}: '{msg}'")
            print(f"Response: {response[:80]}...")
            
            # Check if we have hotel
            trip_state = data.get('trip_state', {})
            hotel = trip_state.get('hotel')
            if hotel:
                print(f"🏨 Hotel already set: {hotel}")
        
        # Now test area selection
        print(f"\n🧪 TESTING AREA SELECTION:")
        print("=" * 40)
        
        test_areas = ["thamel", "near boudha", "near durbar square"]
        
        for area in test_areas:
            print(f"\nTesting: '{area}'")
            
            r = await client.post(url, json={"session_id": session_id, "message": area})
            data = r.json()
            response = data.get('message', '')
            trip_state = data.get('trip_state', {})
            hotel = trip_state.get('hotel')
            
            print(f"Response: {response[:100]}...")
            print(f"Hotel in state: {hotel}")
            
            if hotel:
                print("✅ HOTEL DETECTED AND SET!")
                # Check if it has the improved explanation
                if any(word in response.lower() for word in ["lively", "quiet", "historic", "perfect choice", "good choice"]):
                    print("✅ IMPROVED EXPLANATION")
                else:
                    print("⚠️ Standard explanation")
                break
            else:
                print("❌ Hotel not set")
        
        # If hotel is set, test the day planning and budget
        if hotel:
            print(f"\n🧪 TESTING DAY PLANNING AND BUDGET:")
            print("=" * 45)
            
            # Add some places to complete days
            places_day1 = ["Boudhanath Stupa", "Pashupatinath Temple"]
            
            for place in places_day1:
                r = await client.post(url, json={"session_id": session_id, "message": place})
                data = r.json()
                print(f"Added {place}: {data.get('message', '')[:50]}...")
            
            # Save day 1
            r = await client.post(url, json={"session_id": session_id, "message": "Yes"})
            data = r.json()
            print(f"Saved Day 1: {data.get('message', '')[:50]}...")
            
            # Add day 2
            places_day2 = ["Swayambhunath (Monkey Temple)", "Garden of Dreams"]
            for place in places_day2:
                r = await client.post(url, json={"session_id": session_id, "message": place})
                data = r.json()
                print(f"Added {place}: {data.get('message', '')[:50]}...")
            
            # Save day 2 and check for budget
            r = await client.post(url, json={"session_id": session_id, "message": "Yes"})
            data = r.json()
            response = data.get('message', '')
            print(f"Saved Day 2: {response[:200]}...")
            
            if "budget" in response.lower() or "npr" in response.lower():
                print("✅ BUDGET INFORMATION INCLUDED")
            else:
                print("❌ NO BUDGET INFORMATION")

if __name__ == "__main__":
    asyncio.run(test_full_debug())
