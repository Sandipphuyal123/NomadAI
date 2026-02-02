import re

def _maybe_extract_stay_area(message: str):
    m = message.strip().lower()
    patterns = [
        r"^i\s*['']?m\s+staying\s+(?:in|near)\s+(.+)$",
        r"^i\s+am\s+staying\s+(?:in|near)\s+(.+)$",
        r"^staying\s+(?:in|near)\s+(.+)$",
        r"^my\s+hotel\s+is\s+(?:in|near)\s+(.+)$",
        # More flexible patterns
        r"^(?:in|near)\s+(.+)$",
        r"^(.+)\s+area$",
        r"^(thamel|boudha|durbar|durbar square|kathmandu durbar)$",
    ]
    for pat in patterns:
        mm = re.match(pat, m)
        if mm:
            area = mm.group(1).strip()
            area = re.sub(r"[\.!\?]+$", "", area).strip()
            return area if area else None
    return None

# Test the patterns
test_messages = [
    "thamel",
    "near boudha", 
    "near durbar square",
    "staying in thamel",
    "I'm staying near boudha",
    "thamel area",
    "in durbar square"
]

print("🧪 TESTING HOTEL DETECTION PATTERNS:")
print("=" * 40)

for msg in test_messages:
    result = _maybe_extract_stay_area(msg)
    print(f"Message: '{msg}' -> Detected: '{result}'")
