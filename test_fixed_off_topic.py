import re

def _looks_like_off_topic_fixed(message: str) -> bool:
    m = message.strip().lower()
    # Use word boundaries to avoid false positives like "family" containing "ai"
    patterns = [
        r'\bai\b',
        r'\bllm\b',
        r'\bmodel\b',
        r'\bollama\b',
        r'\bprompt\b',
        r'\btoken\b',
        r'\bfine\s*tune\b',
        r'\bapi\b',
        r'\bopenai\b',
    ]
    return any(re.search(pattern, m) for pattern in patterns)

# Test the problematic message
message = "I'm staying for 3 days with my family of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"
print(f"Message: {message}")
print(f"Off topic (fixed): {_looks_like_off_topic_fixed(message)}")

# Test with actual AI terms
ai_message = "What AI model are you using?"
print(f"\nAI message: {ai_message}")
print(f"Off topic (fixed): {_looks_like_off_topic_fixed(ai_message)}")

# Test a clean message
clean_message = "I am staying for 3 days with my group of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"
print(f"\nClean message: {clean_message}")
print(f"Off topic (fixed): {_looks_like_off_topic_fixed(clean_message)}")
