import re

def _parse_time_days(message: str) -> Optional[int]:
    m = message.strip().lower()
    mm = re.search(r"\b(\d{1,2})\s*(day|days|week|weeks)\b", m)
    if not mm:
        return None
    n = int(mm.group(1))
    unit = mm.group(2)
    if unit.startswith("week"):
        n *= 7
    if n <= 0:
        return None
    return n

# Test the parsing
test_messages = ["2", "2 days", "two days", "I'm staying 2 days", "2d", "for 2 days"]

print("🧪 TESTING TIME DAYS PARSING:")
print("=" * 40)

for msg in test_messages:
    result = _parse_time_days(msg)
    print(f"Message: '{msg}' -> Parsed: {result}")
