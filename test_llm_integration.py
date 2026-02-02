import asyncio
import json
from pathlib import Path

# Import the actual functions from the app
import sys
sys.path.append(str(Path(__file__).parent / "server"))

from main import _maybe_llm_reply, _default_trip_state

async def test_llm_integration():
    print("🔄 Testing _maybe_llm_reply function...")
    
    # Create a test trip state
    trip_state = _default_trip_state()
    user_message = "I'm staying for 3 days with my family of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"
    fallback = "Let's stick to Kathmandu plans. What would you like to see?"
    
    try:
        print(f"User message: {user_message}")
        print(f"Fallback: {fallback}")
        
        # Test the actual function
        reply = await _maybe_llm_reply(trip_state, user_message, fallback)
        
        print(f"Reply: {reply}")
        
        if reply == fallback:
            print("❌ LLM failed - using fallback")
        else:
            print("✅ LLM working properly")
            
    except Exception as e:
        print(f"❌ Exception in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_integration())
