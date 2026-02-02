import asyncio
import httpx

async def debug_trip_state():
    """Debug what's happening with trip state during day saving"""
    url = "http://localhost:8000/api/chat"
    timeout = httpx.Timeout(60.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Setup session quickly
        r = await client.post(url, json={"session_id": None, "message": ""})
        session_id = r.json().get('session_id')
        
        # Quick profile
        for msg in ["yes", "2", "solo", "flexible", "comfortable", "history and temples", "thamel"]:
            await client.post(url, json={"session_id": session_id, "message": msg})
        
        # Plan Day 1
        for place in ["Boudhanath Stupa", "Pashupatinath Temple"]:
            await client.post(url, json={"session_id": session_id, "message": place})
        
        # Check state before saving Day 1
        r = await client.post(url, json={"session_id": session_id, "message": "debug_state"})
        data = r.json()
        trip_state = data.get('trip_state', {})
        
        print("🔍 TRIP STATE BEFORE SAVING DAY 1:")
        print(f"Profile: {trip_state.get('trip_profile', {})}")
        print(f"Trip: {trip_state.get('trip', {})}")
        print(f"UI Stage: {trip_state.get('ui_stage')}")
        
        # Save Day 1
        r = await client.post(url, json={"session_id": session_id, "message": "Yes"})
        data = r.json()
        response = data.get('message', '')
        print(f"\nDay 1 Save Response: {response}")
        
        # Check state after saving Day 1
        r = await client.post(url, json={"session_id": session_id, "message": "debug_state"})
        data = r.json()
        trip_state = data.get('trip_state', {})
        
        print("\n🔍 TRIP STATE AFTER SAVING DAY 1:")
        print(f"Profile: {trip_state.get('trip_profile', {})}")
        print(f"Trip: {trip_state.get('trip', {})}")
        print(f"UI Stage: {trip_state.get('ui_stage')}")
        
        # Plan Day 2
        for place in ["Swayambhunath (Monkey Temple)", "Garden of Dreams"]:
            await client.post(url, json={"session_id": session_id, "message": place})
        
        # Save Day 2
        r = await client.post(url, json={"session_id": session_id, "message": "Yes"})
        data = r.json()
        response = data.get('message', '')
        print(f"\n🎯 Day 2 Save Response: {response}")
        
        # Check state after saving Day 2
        r = await client.post(url, json={"session_id": session_id, "message": "debug_state"})
        data = r.json()
        trip_state = data.get('trip_state', {})
        
        print("\n🔍 TRIP STATE AFTER SAVING DAY 2:")
        print(f"Profile: {trip_state.get('trip_profile', {})}")
        print(f"Trip: {trip_state.get('trip', {})}")
        print(f"UI Stage: {trip_state.get('ui_stage')}")
        
        # Manual trip completion check
        profile = trip_state.get('trip_profile', {})
        stay_days = profile.get('time_days') if isinstance(profile, dict) else None
        trip = trip_state.get('trip', {})
        days = trip.get('days') if isinstance(trip, dict) else None
        
        print(f"\n🧪 MANUAL COMPLETION CHECK:")
        print(f"Stay Days: {stay_days}")
        print(f"Trip Days: {days}")
        
        if isinstance(days, list):
            confirmed = sum(1 for d in days if isinstance(d, dict) and d.get('confirmed') is True)
            print(f"Confirmed Days: {confirmed}")
            print(f"Trip Complete: {confirmed >= stay_days if stay_days else False}")

if __name__ == "__main__":
    asyncio.run(debug_trip_state())
