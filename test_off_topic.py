def _looks_like_off_topic(message: str) -> bool:
    m = message.strip().lower()
    return any(
        k in m
        for k in [
            "ai",
            "llm",
            "model",
            "ollama",
            "prompt",
            "token",
            "fine tune",
            "finetune",
            "api",
            "openai",
        ]
    )

# Test the problematic message
message = "I'm staying for 3 days with my family of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"
print(f"Message: {message}")
print(f"Off topic: {_looks_like_off_topic(message)}")

# Check which keyword is triggering
m = message.strip().lower()
for k in ["ai", "llm", "model", "ollama", "prompt", "token", "fine tune", "finetune", "api", "openai"]:
    if k in m:
        print(f"Found keyword: '{k}' in message")

# Test a clean message
clean_message = "I am staying for 3 days with my group of 4, we love spiritual places and good food. Can you suggest a detailed itinerary?"
print(f"\nClean message: {clean_message}")
print(f"Off topic: {_looks_like_off_topic(clean_message)}")
