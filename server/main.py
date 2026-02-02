from __future__ import annotations

import json
import math
import os
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

KATHMANDU_CENTER: Tuple[float, float] = (27.7172, 85.3240)

OTHER_CITIES = {
    "pokhara",
    "chitwan",
    "lumbini",
    "butwal",
    "biratnagar",
    "bharatpur",
    "hetauda",
    "dharan",
    "janakpur",
    "nepalgunj",
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, v in a.items():
        dot += v * b.get(k, 0)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot / (na * nb))


class SimpleRAG:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs
        self._doc_vecs: List[Counter[str]] = []
        for d in docs:
            text = f"{d.get('title','')} {d.get('place','')} {d.get('text','')}"
            self._doc_vecs.append(Counter(_tokenize(text)))

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        q = Counter(_tokenize(query))
        scored = []
        for doc, vec in zip(self._docs, self._doc_vecs):
            scored.append((_cosine_similarity(q, vec), doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = [d for s, d in scored if s > 0.0][:top_k]
        return out


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


POIS = _load_json(DATA_DIR / "pois.json")
STORIES = _load_json(DATA_DIR / "stories.json")
RAG = SimpleRAG(STORIES)


def _place_id(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    return s or "place"


def _story_for_place(name: str) -> Optional[Dict[str, Any]]:
    for s in STORIES:
        if str(s.get("place", "")).strip().lower() == str(name).strip().lower():
            return s
    return None


def _short_story_text(text: str, max_len: int = 240) -> str:
    t = " ".join(str(text).split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _cost_range_for_category(cat: str) -> str:
    c = str(cat or "").lower()
    if c in {"temple", "stupa", "heritage", "monastery"}:
        return "Low to medium (entry fees vary). Estimated range — not fixed."
    if c in {"park"}:
        return "Low. Estimated range — not fixed."
    if c in {"market", "neighborhood"}:
        return "Flexible (depends on spending). Estimated range — not fixed."
    return "Flexible. Estimated range — not fixed."


PLACES: Dict[str, Dict[str, Any]] = {}
for p in POIS:
    name = str(p.get("name", "")).strip()
    coords = p.get("coordinates")
    if not name or not (isinstance(coords, list) and len(coords) == 2):
        continue
    pid = _place_id(name)
    story = _story_for_place(name) or {}
    story_text = _short_story_text(story.get("text", ""))
    PLACES[pid] = {
        "id": pid,
        "name_en": name,
        "lat": float(coords[0]),
        "lng": float(coords[1]),
        "category": str(p.get("category", "")),
        "storyShort": story_text,
        "costRange": _cost_range_for_category(str(p.get("category", ""))),
        "images": [],
        "review": "A well-loved stop for first-time visitors — easy to reach, and memorable without feeling rushed.",
    }


def _default_trip_state() -> Dict[str, Any]:
    return {
        "city": "Kathmandu",
        "hotel": None,
        "selected_places": [],
        "routes": [],
        "stage": "exploring",
        "map_view": {"center": list(KATHMANDU_CENTER), "zoom": 13},
        "ui_stage": "intro",
        "planning_permission": None,
        "trip": {"days": [], "current_day": 1, "notes": ""},
        "trip_profile": {
            "time_days": None,
            "group": None,
            "budget": None,
            "budget_unknown": None,
            "comfort": None,
            "preferences": [],
        },
        "asked_profile_fields": [],
    }


def _looks_like_yes(message: str) -> bool:
    m = message.strip().lower()
    return m in {"yes", "y", "yeah", "yep", "ok", "okay", "sure", "please", "yes please"} or "yes" in m


def _looks_like_no(message: str) -> bool:
    m = message.strip().lower()
    return m in {"no", "n", "nope", "not now"} or ("no" in m and "not" in m)


def _is_trip_complete(trip_state: Dict[str, Any]) -> bool:
    profile = trip_state.get("trip_profile") if isinstance(trip_state, dict) else None
    stay_days = None
    if isinstance(profile, dict) and isinstance(profile.get("time_days"), int):
        stay_days = int(profile.get("time_days") or 0)
    if not stay_days or stay_days <= 0:
        return False
    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    days = trip.get("days") if isinstance(trip, dict) else None
    if not isinstance(days, list) or not days:
        return False
    confirmed = 0
    for d in days:
        if isinstance(d, dict) and d.get("confirmed") is True:
            confirmed += 1
    return confirmed >= stay_days


def _has_buildable_trip(trip_state: Dict[str, Any]) -> bool:
    """True if user has hotel and at least one confirmed day (can build route)."""
    if not isinstance(trip_state, dict) or not trip_state.get("hotel"):
        return False
    trip = trip_state.get("trip")
    if not isinstance(trip, dict):
        return False
    days = trip.get("days")
    if not isinstance(days, list):
        return False
    for d in days:
        if isinstance(d, dict) and d.get("confirmed") is True:
            return True
    return False


def _candidate_pois(trip_state: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    planned_ids: set[str] = set()
    try:
        trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
        days = trip.get("days") if isinstance(trip, dict) else None
        if isinstance(days, list):
            for d in days:
                if not isinstance(d, dict):
                    continue
                visits = d.get("visits")
                if isinstance(visits, list):
                    for pid in visits:
                        if isinstance(pid, str):
                            planned_ids.add(pid)
    except Exception:
        planned_ids = set()

    out: List[Dict[str, Any]] = []
    for p in POIS:
        pid = _place_id(str(p.get("name", "")))
        if pid in planned_ids:
            continue
        place = PLACES.get(pid)
        if not place:
            continue
        out.append(place)
        if len(out) >= limit:
            break
    return out


def _day_preview_text(trip_state: Dict[str, Any], day_index: int) -> Optional[str]:
    if not trip_state.get("hotel"):
        return None
    d = _find_day(trip_state, day_index)
    visits = d.get("visits")
    if not isinstance(visits, list) or not (1 <= len(visits) <= 2):
        return None
    names = []
    for pid in visits[:2]:
        p = PLACES.get(str(pid))
        if p:
            names.append(str(p.get("name_en") or pid))
    if not names:
        return None

    cost_ranges = []
    for pid in visits[:2]:
        p = PLACES.get(str(pid))
        if p and p.get("costRange"):
            cost_ranges.append(str(p.get("costRange")))
    cost_text = cost_ranges[0] if cost_ranges else "Flexible. Estimated range — not fixed."

    route = "Hotel → " + " → ".join(names)
    if len(names) == 1:
        times = "Suggested timing: 9:00–12:00, then a relaxed lunch break."
    else:
        times = "Suggested timing: 9:00–12:00 for the first stop, 13:30–16:30 for the second (less rushing in traffic)."

    return (
        f"Day {day_index}: {route}\n"
        f"{times}\n"
        f"Estimated cost range: {cost_text}"
    )


def _default_session() -> Dict[str, Any]:
    return {
        "trip_state": _default_trip_state(),
        "history": [],
    }


SESSIONS: Dict[str, Dict[str, Any]] = {}


def _compact_state(trip_state: Dict[str, Any]) -> str:
    return json.dumps(trip_state, ensure_ascii=False, separators=(",", ":"))


def _is_outside_kathmandu(message: str) -> bool:
    tokens = set(_tokenize(message))
    return any(c in tokens for c in OTHER_CITIES)


def _looks_like_place_name(message: str) -> Optional[str]:
    m = message.strip()
    if not m:
        return None
    if m.lower().startswith("tell me about "):
        return m[13:].strip()
    return m


def _looks_like_save_day(message: str) -> bool:
    m = message.strip().lower()
    return any(k in m for k in ["save day", "confirm day", "save this day", "save it", "confirm it"])


async def _ollama_generate(prompt: str) -> str:
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

    payload = {"model": model, "prompt": prompt, "stream": False}

    timeout = httpx.Timeout(60.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{url}/api/generate", json=payload)
        r.raise_for_status()
        data = r.json()
        text = str(data.get("response", "")).strip()
        return text


async def _ollama_chat(messages: List[Dict[str, str]]) -> str:
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

    payload = {"model": model, "messages": messages, "stream": False}

    timeout = httpx.Timeout(60.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{url}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        msg = data.get("message") or {}
        text = str(msg.get("content", "")).strip()
        return text


def _context_for_llm(trip_state: Dict[str, Any]) -> str:
    """Build context so the LLM remembers trip state and does not repeat suggestions."""
    parts = []
    profile = trip_state.get("trip_profile") if isinstance(trip_state, dict) else None
    if isinstance(profile, dict):
        td = profile.get("time_days")
        if isinstance(td, int) and td > 0:
            parts.append(f"User is staying {td} days. Plan only up to {td} days.")
        if profile.get("group") and isinstance(profile["group"], dict) and profile["group"].get("count"):
            parts.append(f"Group size: {profile['group'].get('count')}.")
        if profile.get("comfort"):
            parts.append(f"Comfort: {profile.get('comfort')}.")
        if isinstance(profile.get("preferences"), list) and profile["preferences"]:
            parts.append(f"Preferences: {', '.join(str(p) for p in profile['preferences'][:5])}.")
    hotel = trip_state.get("hotel") if isinstance(trip_state, dict) else None
    if isinstance(hotel, dict) and hotel.get("name"):
        parts.append(f"Hotel/stay: {hotel.get('name')}.")
    planned_names: List[str] = []
    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    days = trip.get("days") if isinstance(trip, dict) else None
    if isinstance(days, list):
        for d in days:
            if not isinstance(d, dict):
                continue
            for pid in d.get("visits") or []:
                if isinstance(pid, str):
                    place = PLACES.get(pid)
                    if place and place.get("name_en"):
                        planned_names.append(str(place["name_en"]))
    if planned_names:
        parts.append("Already chosen (do not suggest again): " + ", ".join(planned_names) + ".")
    return " ".join(parts)


async def _maybe_llm_reply(
    trip_state: Dict[str, Any], user_message: str, fallback: str, suggestion_names: Optional[List[str]] = None
) -> str:
    """Try short LLM reply with context; return fallback if Ollama fails."""
    try:
        context = _context_for_llm(trip_state)
        system = (
            "You are NomadAI, a Kathmandu travel guide. Be warm and brief. "
            "Keep every reply to 2-4 sentences. Never suggest a place the user has already chosen. "
            "If user said how many days they stay, only plan up to that many days.\n\nCurrent context: "
            + context
        )
        if suggestion_names:
            system += "\n\nSuggest only from this list: " + ", ".join(suggestion_names[:5]) + "."
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message or "What next?"},
        ]
        reply = await _ollama_chat(messages)
        if reply and len(reply.strip()) > 5:
            return reply.strip()[:500]
    except Exception:
        pass
    return fallback


def _system_prompt() -> str:
    return (
        "\n".join(
            [
                "🔒 SYSTEM PROMPT — “Aarav, Kathmandu Local Guide”",
                "You are Aarav, a calm, observant, and experienced local guide from Kathmandu.",
                "",
                "Your role:",
                "- Act like a real human guide, not an AI.",
                "- Speak naturally, warmly, and confidently.",
                "- Share lived-in knowledge, small observations, and reasons for suggestions.",
                "- Focus ONLY on Kathmandu.",
                "- Do not talk about other parts of Nepal.",
                "",
                "Behavior rules:",
                "- Never rush the user.",
                "- Never interrogate the user with back-to-back questions.",
                "- Always provide value before asking questions.",
                "- Explain WHY you ask for information.",
                "- Avoid sounding promotional or sales-driven.",
                "",
                "Conversation structure:",
                "- Start with inspiration and storytelling.",
                "- Ask for permission before planning.",
                "- Collect key info gradually: time, group size, comfort, budget (rough), preferences.",
                "- When information is missing, keep suggestions flexible.",
                "- Use soft transitions, not hard commands.",
                "",
                "Content rules:",
                "- Use short, meaningful stories instead of facts.",
                "- Avoid Wikipedia-style explanations.",
                "- Avoid exact prices — always give ranges and disclaimers.",
                "- Mention local realities (traffic, walking pace, crowds) when relevant.",
                "- Be honest about trade-offs (crowded vs calm, central vs quiet).",
                "",
                "Tone & language:",
                "- Calm, friendly, grounded.",
                "- Occasionally reflective (“many travelers tell me…”).",
                "- Never robotic, never overly enthusiastic.",
                "- Avoid emojis unless very light and human.",
                "",
                "Planning rules:",
                "- Suggest no more than 2–3 places at a time.",
                "- Justify every recommendation briefly.",
                "- Keep itineraries flexible and swappable.",
                "- Always remind that plans are estimates, not fixed commitments.",
                "",
                "Restrictions:",
                "- Do not book anything.",
                "- Do not mention APIs, models, or being an AI.",
                "- Do not ask questions unrelated to Kathmandu travel.",
                "- Do not hallucinate statistics or exact numbers.",
                "",
                "If the user goes off-topic or gives unclear input:",
                "- Gently guide them back without breaking immersion.",
            ]
        )
    )


FALLBACK_LINES: Dict[str, str] = {
    "vague": "No problem — we can keep it flexible. What would you like to do next?",
    "too_broad": "I'll suggest a few standout places. Which sounds good?",
    "skips_info": "We can come back to that. What matters most to you right now?",
    "changes_mind": "Sure, we can change the plan. What would you prefer?",
    "exact_prices": "Prices vary by season; I'll give rough ranges. What's your comfort level?",
    "off_topic": "Let's stick to Kathmandu plans. What would you like to see?",
    "silent": "Take your time. When you're ready, just say what you'd like.",
    "immediate_plan": "A couple of details will help — how many days, and where are you staying?",
}


def _fallback(key: str) -> str:
    return FALLBACK_LINES.get(key, FALLBACK_LINES["vague"])


def _rag_text_for_query(query: str, top_k: int = 3) -> str:
    docs = RAG.retrieve(query, top_k=top_k)
    if not docs:
        return ""
    parts = []
    for d in docs:
        title = d.get("title") or d.get("place") or "Context"
        text = d.get("text", "")
        parts.append(f"[{title}]\n{text}")
    return "\n\n".join(parts).strip()


def _find_poi_by_name(name: str) -> Optional[Dict[str, Any]]:
    for p in POIS:
        if str(p.get("name", "")).lower() == name.lower():
            return p
    return None


def _maybe_extract_stay_area(message: str) -> Optional[str]:
    m = message.strip().lower()
    patterns = [
        r"^i\s*['’]?m\s+staying\s+(?:in|near)\s+(.+)$",
        r"^i\s+am\s+staying\s+(?:in|near)\s+(.+)$",
        r"^staying\s+(?:in|near)\s+(.+)$",
        r"^my\s+hotel\s+is\s+(?:in|near)\s+(.+)$",
    ]
    for pat in patterns:
        mm = re.match(pat, m)
        if mm:
            area = mm.group(1).strip()
            area = re.sub(r"[\.!\?]+$", "", area).strip()
            return area if area else None
    return None


def _looks_like_build_route(message: str) -> bool:
    m = message.strip().lower()
    return any(
        k in m
        for k in [
            "build route",
            "create route",
            "make a route",
            "plan my route",
            "route for me",
        ]
    )


def _looks_like_too_broad(message: str) -> bool:
    m = message.strip().lower()
    return any(
        k in m
        for k in [
            "tell me everything",
            "everything",
            "all places",
            "all the places",
            "everything to do",
        ]
    )


def _looks_like_exact_prices(message: str) -> bool:
    m = message.strip().lower()
    return any(
        k in m
        for k in [
            "exact price",
            "exactly how much",
            "exact cost",
            "exactly",
            "fixed price",
        ]
    ) and any(k in m for k in ["price", "cost", "fee", "budget", "rupees", "rs", "usd", "$", "dollar"])


def _looks_like_off_topic(message: str) -> bool:
    m = message.strip().lower()
    # Use word boundaries to avoid false positives like "family" containing "ai"
    import re
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


def _looks_like_vague_or_confused(message: str) -> bool:
    m = message.strip().lower()
    return m in {"help", "hi", "hello", "hey"} or any(
        k in m
        for k in [
            "not sure",
            "i don't know",
            "dont know",
            "confused",
            "whatever",
            "anything is fine",
        ]
    )


def _looks_like_change_of_mind(message: str) -> bool:
    m = message.strip().lower()
    return any(k in m for k in ["never mind", "nevermind", "actually", "change of plan", "instead"])


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


def _parse_group(message: str) -> Optional[Dict[str, Any]]:
    m = message.strip().lower()

    if any(k in m for k in ["solo", "alone", "by myself", "just me"]):
        return {"label": "one", "count": 1}

    if any(k in m for k in ["couple", "duo", "two of us", "we two"]):
        return {"label": "duo", "count": 2}

    mm = re.search(r"\bwe\s+are\s+(\d{1,2})\b", m)
    if not mm:
        mm = re.search(r"\b(\d{1,2})\s*(people|persons|friends|travelers|travellers)\b", m)
    if mm:
        n = int(mm.group(1))
        if n <= 0:
            return None
        label = "many" if n >= 3 else ("duo" if n == 2 else "one")
        return {"label": label, "count": n}

    return None


def _parse_budget(message: str) -> Tuple[Optional[float], Optional[bool]]:
    m = message.strip().lower()

    if any(k in m for k in ["don't know", "dont know", "not sure", "no idea", "haven't decided"]):
        return None, True

    mm = re.search(r"\$\s*(\d+(?:\.\d+)?)", m)
    if not mm:
        mm = re.search(r"\b(\d+(?:\.\d+)?)\s*(usd|dollars|dollar)\b", m)
    if mm:
        return float(mm.group(1)), False

    return None, None


def _parse_comfort(message: str) -> Optional[str]:
    m = message.strip().lower()
    if any(k in m for k in ["budget", "cheap", "backpacker", "hostel", "basic"]):
        return "budget"
    if any(k in m for k in ["mid", "mid-range", "midrange", "comfortable", "standard", "3 star", "3-star"]):
        return "mid"
    if any(k in m for k in ["luxury", "premium", "5 star", "5-star", "high-end"]):
        return "comfortable"
    return None


def _parse_preferences(message: str) -> List[str]:
    m = message.strip().lower()
    prefs: List[str] = []
    mapping = [
        ("history", ["history", "historical", "heritage", "old city", "durbar"]),
        ("spiritual", ["spiritual", "religious", "temple", "stupa", "monastery", "hindu", "buddhist"]),
        ("architecture", ["architecture", "unique building", "tower", "dharahara", "design"]),
        ("food", ["food", "momo", "cafes", "coffee", "street food"]),
        ("markets", ["market", "shopping", "bazaar", "souvenir"]),
        ("walking", ["walk", "walking", "stroll", "on foot"]),
        ("calm", ["quiet", "calm", "slow", "peaceful", "courtyard"]),
        ("viewpoints", ["view", "viewpoint", "sunrise", "sunset", "hill", "hike"]),
    ]
    for label, keys in mapping:
        if any(k in m for k in keys):
            prefs.append(label)
    return sorted(set(prefs))


def _update_trip_profile_from_message(trip_state: Dict[str, Any], message: str) -> None:
    if not message:
        return

    profile = trip_state.get("trip_profile")
    if not isinstance(profile, dict):
        profile = {}
        trip_state["trip_profile"] = profile

    td = _parse_time_days(message)
    if td is not None and not profile.get("time_days"):
        profile["time_days"] = td

    group = _parse_group(message)
    if group is not None and not profile.get("group"):
        profile["group"] = group

    budget_value, budget_unknown = _parse_budget(message)
    if budget_value is not None and profile.get("budget") is None:
        profile["budget"] = budget_value
        profile["budget_unknown"] = False
    if budget_unknown is True and profile.get("budget_unknown") is None and profile.get("budget") is None:
        profile["budget_unknown"] = True

    comfort = _parse_comfort(message)
    if comfort is not None and not profile.get("comfort"):
        profile["comfort"] = comfort

    prefs = _parse_preferences(message)
    if prefs:
        existing = profile.get("preferences")
        if not isinstance(existing, list):
            existing = []
        profile["preferences"] = sorted(set([str(x) for x in existing] + prefs))


def _next_profile_field(trip_state: Dict[str, Any]) -> Optional[str]:
    profile = trip_state.get("trip_profile")
    if not isinstance(profile, dict):
        return "time_days"

    asked = trip_state.get("asked_profile_fields")
    if not isinstance(asked, list):
        asked = []
        trip_state["asked_profile_fields"] = asked

    order = ["time_days", "group", "budget", "comfort", "preferences"]
    missing = []
    if not profile.get("time_days"):
        missing.append("time_days")
    if not profile.get("group"):
        missing.append("group")
    if profile.get("budget") is None and profile.get("budget_unknown") is None:
        missing.append("budget")
    if not profile.get("comfort"):
        missing.append("comfort")
    if not profile.get("preferences"):
        missing.append("preferences")

    for f in order:
        if f in missing and f not in asked:
            return f

    return None


def _profile_question_for(field: str) -> str:
    if field == "time_days":
        return "How many days will you be in Kathmandu?"
    if field == "group":
        return "Solo, duo, or group? How many people?"
    if field == "budget":
        return "Rough budget in mind, or keep it flexible?"
    if field == "comfort":
        return "Budget, mid-range, or more comfortable? I ask so I don’t suggest days that feel too rushed or too expensive for your style."
    if field == "preferences":
        return "What do you enjoy most — history, temples, food, or quieter spots?"
    return "Anything else I should know to shape your plan?"


def _ensure_session(session_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    if session_id and session_id in SESSIONS:
        return session_id, SESSIONS[session_id]

    import uuid

    sid = session_id or str(uuid.uuid4())
    SESSIONS[sid] = _default_session()
    return sid, SESSIONS[sid]


def _upsert_selected_place(trip_state: Dict[str, Any], name: str, coordinates: List[float]) -> None:
    existing = trip_state.get("selected_places", [])
    for p in existing:
        if str(p.get("name", "")).lower() == name.lower():
            p["coordinates"] = coordinates
            return
    existing.append({"name": name, "coordinates": coordinates})
    trip_state["selected_places"] = existing


def _set_hotel(trip_state: Dict[str, Any], name: str, coordinates: List[float]) -> None:
    trip_state["hotel"] = {"name": name, "coordinates": coordinates}


def _build_routes(trip_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    hotel = trip_state.get("hotel")
    places = trip_state.get("selected_places", [])
    if not hotel or not places:
        return []

    points: List[Tuple[str, List[float]]] = [("Hotel", hotel["coordinates"])]
    for p in places:
        points.append((p["name"], p["coordinates"]))

    routes = []
    for i in range(len(points) - 1):
        routes.append({"from": points[i][0], "to": points[i + 1][0], "polyline": [points[i][1], points[i + 1][1]]})
    return routes


async def _build_routes_for_confirmed_days(trip_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    hotel = trip_state.get("hotel") if isinstance(trip_state, dict) else None
    if not isinstance(hotel, dict):
        return []
    hc = hotel.get("coordinates")
    if not (isinstance(hc, list) and len(hc) == 2):
        return []

    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    days = trip.get("days") if isinstance(trip, dict) else None
    if not isinstance(days, list):
        return []

    routes: List[Dict[str, Any]] = []
    for d in days:
        if not isinstance(d, dict) or d.get("confirmed") is not True:
            continue
        day_index = d.get("dayIndex")
        if not isinstance(day_index, int):
            continue
        visits = d.get("visits")
        if not isinstance(visits, list) or len(visits) == 0:
            continue

        coords: List[List[float]] = [hc]
        names: List[str] = ["Hotel"]
        for pid in visits[:2]:
            place = PLACES.get(str(pid))
            if not place:
                continue
            coords.append([float(place["lat"]), float(place["lng"])])
            names.append(str(place.get("name_en") or pid))

        if len(coords) < 2:
            continue

        for i in range(len(coords) - 1):
            polyline = None
            try:
                polyline = await _osrm_leg_polyline(coords[i], coords[i + 1])
            except Exception:
                polyline = None
            if not polyline:
                polyline = [coords[i], coords[i + 1]]
            routes.append({"day": day_index, "from": names[i], "to": names[i + 1], "polyline": polyline})

    return routes


async def _osrm_leg_polyline(a: List[float], b: List[float]) -> Optional[List[List[float]]]:
    osrm_url = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
    lonlat = f"{a[1]},{a[0]};{b[1]},{b[0]}"
    url = f"{osrm_url}/route/v1/driving/{lonlat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        routes = data.get("routes") or []
        if not routes:
            return None
        geom = (routes[0].get("geometry") or {}).get("coordinates")
        if not isinstance(geom, list) or len(geom) < 2:
            return None
        return [[c[1], c[0]] for c in geom if isinstance(c, list) and len(c) == 2]


async def _build_routes_osrm(trip_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    hotel = trip_state.get("hotel")
    places = trip_state.get("selected_places", [])
    if not hotel or not places:
        return []

    points: List[Tuple[str, List[float]]] = [("Hotel", hotel["coordinates"])]
    for p in places:
        points.append((p["name"], p["coordinates"]))

    routes = []
    for i in range(len(points) - 1):
        a_name, a = points[i]
        b_name, b = points[i + 1]

        polyline = None
        try:
            polyline = await _osrm_leg_polyline(a, b)
        except Exception:
            polyline = None

        if not polyline:
            polyline = [a, b]

        routes.append({"from": a_name, "to": b_name, "polyline": polyline})

    return routes


def _suggestions_for_state(trip_state: Dict[str, Any]) -> List[str]:
    suggestions: List[str] = []

    planned_ids: set[str] = set()
    try:
        for p in trip_state.get("selected_places", []) or []:
            n = str(p.get("name", ""))
            if n:
                planned_ids.add(_place_id(n))
    except Exception:
        planned_ids = set()

    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    days = trip.get("days") if isinstance(trip, dict) else None
    if isinstance(days, list):
        for d in days:
            if not isinstance(d, dict):
                continue
            visits = d.get("visits")
            if isinstance(visits, list):
                for pid in visits:
                    if isinstance(pid, str):
                        planned_ids.add(pid)

    if not trip_state.get("hotel"):
        suggestions.append("I'm staying in Thamel")
        suggestions.append("I'm staying near Boudha")
        suggestions.append("I'm staying near Durbar Square")

    if not trip_state.get("selected_places"):
        for p in POIS:
            pid = _place_id(str(p.get("name", "")))
            if pid in planned_ids:
                continue
            suggestions.append(f"Tell me about {p['name']}")
            if len(suggestions) >= 5:
                break
    else:
        suggestions.append("Build a simple route for me")
        suggestions.append("Add a calm place for a break")
        suggestions.append("I prefer temples and history")

    return suggestions[:6]


def _map_actions_from_state(trip_state: Dict[str, Any]) -> Dict[str, Any]:
    view = trip_state.get("map_view") if isinstance(trip_state, dict) else None
    center = list(KATHMANDU_CENTER)
    zoom = 13
    if isinstance(view, dict):
        c = view.get("center")
        z = view.get("zoom")
        if isinstance(c, list) and len(c) == 2:
            center = c
        if isinstance(z, int):
            zoom = z

    actions: Dict[str, Any] = {"center": center, "zoom": zoom, "markers": [], "routes": []}

    if trip_state.get("hotel"):
        actions["markers"].append({"type": "hotel", **trip_state["hotel"]})

    for p in trip_state.get("selected_places", []):
        actions["markers"].append({"type": "place", "name": p["name"], "coordinates": p["coordinates"]})

    for r in trip_state.get("routes", []):
        actions["routes"].append(r)

    return actions


def _set_map_view(trip_state: Dict[str, Any], center: List[float], zoom: int = 15) -> None:
    if not isinstance(trip_state, dict):
        return
    if not (isinstance(center, list) and len(center) == 2):
        return
    trip_state["map_view"] = {"center": center, "zoom": zoom}


def _find_poi_mention(message: str) -> Optional[Dict[str, Any]]:
    m = message.strip().lower()
    if not m:
        return None

    best = None
    best_len = 0
    for p in POIS:
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        n = name.lower()
        if n in m and len(n) > best_len:
            best = p
            best_len = len(n)
    return best


def _looks_like_affirmation(message: str) -> bool:
    m = message.strip().lower()
    return any(
        k in m
        for k in [
            "i like",
            "sounds good",
            "let's go",
            "lets go",
            "i want to go",
            "add it",
            "include",
            "yes",
            "okay",
            "ok",
        ]
    )


def _split_into_days(items: List[Any], days: int) -> List[List[Any]]:
    if days <= 1:
        return [items]
    out = [[] for _ in range(days)]
    for i, it in enumerate(items):
        out[i % days].append(it)
    return out


def _google_maps_dir_link(points: List[List[float]]) -> Optional[str]:
    if not points or len(points) < 2:
        return None
    origin = f"{points[0][0]},{points[0][1]}"
    destination = f"{points[-1][0]},{points[-1][1]}"
    waypoints = "|".join(f"{p[0]},{p[1]}" for p in points[1:-1])

    params = {"api": "1", "origin": origin, "destination": destination}
    if waypoints:
        params["waypoints"] = waypoints
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params, safe=",|")


def _ensure_trip_days(trip_state: Dict[str, Any], stay_days: int) -> None:
    if not isinstance(trip_state, dict):
        return
    trip = trip_state.get("trip")
    if not isinstance(trip, dict):
        trip = {"days": [], "current_day": 1, "notes": ""}
        trip_state["trip"] = trip
    days = trip.get("days")
    if not isinstance(days, list):
        days = []
        trip["days"] = days
    if stay_days <= 0:
        return
    if len(days) >= stay_days:
        return
    for i in range(len(days) + 1, stay_days + 1):
        days.append({"dayIndex": i, "hotelPlaceId": None, "visits": [], "confirmed": False})


def _current_day_index(trip_state: Dict[str, Any]) -> int:
    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    if isinstance(trip, dict):
        cd = trip.get("current_day")
        if isinstance(cd, int) and cd >= 1:
            return cd
    return 1


def _find_day(trip_state: Dict[str, Any], day_index: int) -> Dict[str, Any]:
    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    if not isinstance(trip, dict):
        trip = {"days": [], "current_day": 1, "notes": ""}
        trip_state["trip"] = trip
    days = trip.get("days")
    if not isinstance(days, list):
        days = []
        trip["days"] = days
    for d in days:
        if isinstance(d, dict) and d.get("dayIndex") == day_index:
            return d
    d = {"dayIndex": day_index, "hotelPlaceId": None, "visits": [], "confirmed": False}
    days.append(d)
    return d


def _add_visit_to_day(trip_state: Dict[str, Any], day_index: int, place_id: str) -> Tuple[bool, str]:
    d = _find_day(trip_state, day_index)
    visits = d.get("visits")
    if not isinstance(visits, list):
        visits = []
        d["visits"] = visits
    if place_id in visits:
        return False, "already_added"
    if len(visits) >= 2:
        return False, "day_full"
    visits.append(place_id)
    return True, "added"


def _confirm_day(trip_state: Dict[str, Any], day_index: int) -> None:
    d = _find_day(trip_state, day_index)
    d["confirmed"] = True
    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    if isinstance(trip, dict):
        trip["current_day"] = max(day_index + 1, int(trip.get("current_day") or 1))


def _export_user_profile(trip_state: Dict[str, Any]) -> Dict[str, Any]:
    profile = trip_state.get("trip_profile") if isinstance(trip_state, dict) else None
    out = {
        "stay_days": None,
        "group_size": None,
        "budget_range": None,
        "comfort_level": None,
        "preferences": [],
    }
    if not isinstance(profile, dict):
        return out

    td = profile.get("time_days")
    if isinstance(td, int):
        out["stay_days"] = td

    group = profile.get("group")
    if isinstance(group, dict):
        c = group.get("count")
        if isinstance(c, int):
            out["group_size"] = c

    budget = profile.get("budget")
    if isinstance(budget, (int, float)):
        out["budget_range"] = "flexible"
    if profile.get("budget_unknown") is True:
        out["budget_range"] = "flexible"

    comfort = profile.get("comfort")
    if isinstance(comfort, str):
        if comfort == "budget":
            out["comfort_level"] = "low"
        elif comfort == "mid":
            out["comfort_level"] = "medium"
        else:
            out["comfort_level"] = "high"

    prefs = profile.get("preferences")
    if isinstance(prefs, list):
        allowed = {"history", "spiritual", "food", "walking", "markets"}
        out["preferences"] = [p for p in prefs if isinstance(p, str) and p in allowed]
    return out


def export_plan(request: Request) -> JSONResponse:
    session_id_value = request.query_params.get("session_id")
    if not isinstance(session_id_value, str) or not session_id_value or session_id_value not in SESSIONS:
        return JSONResponse({"ok": False, "error": "missing_session"}, status_code=400)

    session = SESSIONS[session_id_value]
    trip_state = session.get("trip_state") or {}
    profile = trip_state.get("trip_profile") if isinstance(trip_state, dict) else {}

    trip = trip_state.get("trip") if isinstance(trip_state, dict) else None
    days_list = trip.get("days") if isinstance(trip, dict) else None
    if not isinstance(days_list, list):
        days_list = []

    hotel = trip_state.get("hotel") if isinstance(trip_state, dict) else None
    hotel_coords = None
    if isinstance(hotel, dict):
        hc = hotel.get("coordinates")
        if isinstance(hc, list) and len(hc) == 2:
            hotel_coords = hc

    links: List[Dict[str, Any]] = []
    for d in days_list:
        if not isinstance(d, dict):
            continue
        if d.get("confirmed") is not True:
            continue
        day_index = d.get("dayIndex")
        if not isinstance(day_index, int):
            continue
        visits = d.get("visits")
        if not isinstance(visits, list) or len(visits) == 0:
            continue

        coords: List[List[float]] = []
        if hotel_coords:
            coords.append(hotel_coords)

        for pid in visits[:2]:
            place = PLACES.get(str(pid))
            if not place:
                continue
            coords.append([float(place["lat"]), float(place["lng"])])

        if len(coords) < 2:
            continue
        url = _google_maps_dir_link(coords)
        if not url:
            continue
        links.append({"day": day_index, "url": url})

    return JSONResponse({"ok": True, "days": len(days_list), "links": links})


def index(request: Request) -> Response:
    return FileResponse(str(STATIC_DIR / "index.html"))


def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def pois(request: Request) -> JSONResponse:
    return JSONResponse(POIS)


def places(request: Request) -> JSONResponse:
    return JSONResponse({"places": list(PLACES.values())})


async def chat(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    session_id_value = payload.get("session_id")
    if not isinstance(session_id_value, str) or not session_id_value:
        session_id_value = None

    message_value = payload.get("message", "")
    message = message_value.strip() if isinstance(message_value, str) else ""

    map_event = payload.get("map_event")
    if map_event is not None and not isinstance(map_event, dict):
        map_event = None

    session_id, session = _ensure_session(session_id_value)
    trip_state = session["trip_state"]
    history: List[Dict[str, str]] = session["history"]

    commands: List[Dict[str, Any]] = []

    commands.append({"session.storePlaces": PLACES})

    if message and trip_state.get("planning_permission") is True:
        _update_trip_profile_from_message(trip_state, message)

    commands.append({"session.storeProfile": _export_user_profile(trip_state)})

    profile = trip_state.get("trip_profile") if isinstance(trip_state, dict) else None
    if isinstance(profile, dict):
        td = profile.get("time_days")
        if isinstance(td, int) and td > 0:
            _ensure_trip_days(trip_state, min(td, 14))

    if not message and not map_event:
        intro = []
        for pid in [
            _place_id("Swayambhunath (Monkey Temple)"),
            _place_id("Boudhanath Stupa"),
            _place_id("Garden of Dreams"),
        ]:
            p = PLACES.get(pid)
            if not p:
                continue
            intro.append(f"{p['name_en']}: {str(p.get('storyShort') or '').strip()}")
        reply = (
            "Namaste — I’m NomadAI, your Kathmandu-only travel companion.\n\n"
            + "\n".join(intro[:3])
            + "\n\nWould you like a personalized plan for Kathmandu?"
        )
        trip_state["ui_stage"] = "intro"
        if trip_state.get("planning_permission") is None:
            trip_state["planning_permission"] = None
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": ["Yes", "No"],
            }
        )

    if message and trip_state.get("planning_permission") is None:
        if _looks_like_yes(message):
            trip_state["planning_permission"] = True
            trip_state["ui_stage"] = "collect_profile"
        elif _looks_like_no(message):
            trip_state["planning_permission"] = False
            trip_state["ui_stage"] = "inspiration"

    if trip_state.get("planning_permission") is False:
        if message and _looks_like_yes(message):
            trip_state["planning_permission"] = True
            trip_state["ui_stage"] = "collect_profile"
        else:
            picks = _candidate_pois(trip_state, limit=3)
            lines = []
            for p in picks:
                lines.append(f"{p['name_en']}: {str(p.get('storyShort') or '').strip()}")
            reply = "Here are a few Kathmandu ideas you can enjoy without over-planning:\n\n" + "\n".join(lines)
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [p["name_en"] for p in picks],
                }
            )

    if trip_state.get("planning_permission") is True and trip_state.get("ui_stage") == "day_confirm" and message:
        day_index = _current_day_index(trip_state)
        d = _find_day(trip_state, day_index)
        if _looks_like_yes(message):
            if trip_state.get("hotel") and isinstance(d.get("visits"), list) and 1 <= len(d.get("visits")) <= 2:
                _confirm_day(trip_state, day_index)
                commands.append({"session.confirmDay": day_index})
                if _is_trip_complete(trip_state):
                    commands.append({"ui.enableButton": "buildRoute"})
                    reply = _final_trip_summary(trip_state)
                    trip_state["ui_stage"] = "done"
                    return JSONResponse(
                        {
                            "session_id": session_id,
                            "message": reply,
                            "reply": reply,
                            "commands": commands,
                            "trip_state": trip_state,
                            "map_actions": _map_actions_from_state(trip_state),
                            "suggestions": [],
                        }
                    )

                next_day = _current_day_index(trip_state)
                stay_days = None
                if isinstance(trip_state.get("trip_profile"), dict):
                    stay_days = trip_state["trip_profile"].get("time_days")
                if isinstance(stay_days, int) and next_day > stay_days:
                    commands.append({"ui.enableButton": "buildRoute"})
                    reply = f"All your {stay_days} days are planned. You can build routes now."
                    trip_state["ui_stage"] = "done"
                    return JSONResponse(
                        {
                            "session_id": session_id,
                            "message": reply,
                            "reply": reply,
                            "commands": commands,
                            "trip_state": trip_state,
                            "map_actions": _map_actions_from_state(trip_state),
                            "suggestions": [],
                        }
                    )

                trip_state["ui_stage"] = "day_suggest"
                picks = _candidate_pois(trip_state, limit=3)
                reply = f"Day {day_index} saved. For Day {next_day}, pick up to 2 places. Which first?"
                return JSONResponse(
                    {
                        "session_id": session_id,
                        "message": reply,
                        "reply": reply,
                        "commands": commands,
                        "trip_state": trip_state,
                        "map_actions": _map_actions_from_state(trip_state),
                        "suggestions": [p["name_en"] for p in picks],
                    }
                )
        if _looks_like_no(message):
            visits = d.get("visits")
            if isinstance(visits, list):
                for pid in visits:
                    if isinstance(pid, str):
                        commands.append({"map.removePin": pid})
                d["visits"] = []
            reply = f"No problem. For Day {day_index}, pick up to 2 visiting places (it keeps the map clear and the pace comfortable). Which place should we start with?"
            trip_state["ui_stage"] = "day_suggest"
            picks = _candidate_pois(trip_state, limit=3)
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [p["name_en"] for p in picks],
                }
            )

    stay_area = _maybe_extract_stay_area(message) if message else None
    if trip_state.get("planning_permission") is True and stay_area:
        poi = _find_poi_by_name(stay_area)
        if not poi and stay_area.lower() in {"boudha", "bouddha", "boudhanath"}:
            poi = _find_poi_by_name("Boudhanath Stupa")
        if not poi and stay_area.lower() in {"durbar", "durbar square", "kathmandu durbar"}:
            poi = _find_poi_by_name("Kathmandu Durbar Square")
        if poi:
            coords = list(poi.get("coordinates") or list(KATHMANDU_CENTER))
            _set_hotel(trip_state, stay_area.title(), coords)
            _set_map_view(trip_state, coords, zoom=14)
            day_index = _current_day_index(trip_state)
            d = _find_day(trip_state, day_index)
            d["hotelPlaceId"] = "hotel"
            commands.append({"map.addPin": {"id": "hotel", "lat": float(coords[0]), "lng": float(coords[1]), "type": "hotel", "color": "green", "label": stay_area.title()}})
            commands.append({"map.zoomTo": {"lat": float(coords[0]), "lng": float(coords[1]), "zoom": 14}})
            commands.append({"session.storeHotel": {"dayIndex": day_index, "placeId": "hotel", "name_en": stay_area.title(), "lat": float(coords[0]), "lng": float(coords[1])}})
            trip_state["ui_stage"] = "day_suggest"

            reply = "Perfect — I’ll treat that as your stay point (it becomes the start of each day’s route). Now, for Day 1, which place would you like to add first?"
            picks = _candidate_pois(trip_state, limit=3)
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [p["name_en"] for p in picks],
                }
            )

    if _has_buildable_trip(trip_state):
        commands.append({"ui.enableButton": "buildRoute"})
    if _is_trip_complete(trip_state) and trip_state.get("routes"):
        commands.append({"ui.enableButton": "export"})

    next_field = _next_profile_field(trip_state) if trip_state.get("planning_permission") is True else None
    next_question = _profile_question_for(next_field) if next_field else None

    if next_field and next_question:
        asked = trip_state.get("asked_profile_fields")
        if not isinstance(asked, list):
            asked = []
            trip_state["asked_profile_fields"] = asked
        if next_field not in asked:
            asked.append(next_field)

    if message and _looks_like_off_topic(message):
        reply = _fallback("off_topic")
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": [],
            }
        )

    if message and _looks_like_too_broad(message):
        reply = _fallback("too_broad")
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": [],
            }
        )

    if message and _looks_like_exact_prices(message):
        reply = _fallback("exact_prices")
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": [],
            }
        )

    if message and _looks_like_change_of_mind(message):
        reply = _fallback("changes_mind")
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": [],
            }
        )

    if map_event:
        et = str(map_event.get("type", ""))

        if et == "select_place":
            name = str(map_event.get("name", "")).strip()
            coords = map_event.get("coordinates")
            if not name and isinstance(coords, list) and len(coords) == 2:
                name = "Selected place"
            if not (isinstance(coords, list) and len(coords) == 2):
                coords = None

            poi = _find_poi_by_name(name) if name else None
            if poi and not coords:
                coords = poi.get("coordinates")
            if not coords:
                coords = [KATHMANDU_CENTER[0], KATHMANDU_CENTER[1]]

            _upsert_selected_place(trip_state, name, coords)
            _set_map_view(trip_state, coords, zoom=15)
            trip_state["stage"] = "exploring"

            pid = _place_id(name)
            day_index = _current_day_index(trip_state)
            ok, reason = _add_visit_to_day(trip_state, day_index, pid)
            if not ok and reason == "day_full":
                reply = "For map clarity and comfort, I keep it to 2 visiting places per day. If you want, we can move this one to the next day."
                picks = _candidate_pois(trip_state, limit=3)
                return JSONResponse(
                    {
                        "session_id": session_id,
                        "message": reply,
                        "reply": reply,
                        "commands": commands,
                        "trip_state": trip_state,
                        "map_actions": _map_actions_from_state(trip_state),
                        "suggestions": [p["name_en"] for p in picks],
                    }
                )
            place = PLACES.get(pid)
            if place:
                commands.append({"map.addPin": {"id": pid, "lat": place["lat"], "lng": place["lng"], "type": "visit", "color": "blue", "label": place["name_en"]}})
                commands.append({"map.zoomTo": {"lat": place["lat"], "lng": place["lng"], "zoom": 15}})
                commands.append({"ui.showImages": {"placeId": pid, "urls": place.get("images") or []}})
                commands.append({"ui.showReview": {"placeId": pid, "review": str(place.get("review") or "")}})
                commands.append({"session.addPlaceToDay": {"dayIndex": day_index, "placeId": pid}})

            d = _find_day(trip_state, day_index)
            visits = d.get("visits") if isinstance(d, dict) else None
            if isinstance(visits, list) and len(visits) >= 2:
                preview = _day_preview_text(trip_state, day_index) or ""
                trip_state["ui_stage"] = "day_confirm"
                reply = preview + "\n\nSave this as Day " + str(day_index) + "?"
                return JSONResponse(
                    {
                        "session_id": session_id,
                        "message": reply,
                        "reply": reply,
                        "commands": commands,
                        "trip_state": trip_state,
                        "map_actions": _map_actions_from_state(trip_state),
                        "suggestions": ["Yes", "No"],
                    }
                )

            trip_state["ui_stage"] = "day_suggest"
            picks = _candidate_pois(trip_state, limit=3)
            short_story = str(place.get("storyShort") or "").strip() if isinstance(place, dict) else ""
            reply = (
                (f"{place.get('name_en')}: {short_story}\n\n" if short_story and isinstance(place, dict) else "")
                + f"I recommend max 2 visiting places per day (map clarity and comfort). Which second place should we add for Day {day_index}?"
            )
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [p["name_en"] for p in picks],
                }
            )

        if et == "set_hotel":
            name = str(map_event.get("name", "")) or "Stay"
            coords = map_event.get("coordinates")
            if not (isinstance(coords, list) and len(coords) == 2):
                coords = [KATHMANDU_CENTER[0], KATHMANDU_CENTER[1]]
            _set_hotel(trip_state, name, coords)
            _set_map_view(trip_state, coords, zoom=14)
            trip_state["stage"] = "exploring"

            day_index = _current_day_index(trip_state)
            d = _find_day(trip_state, day_index)
            d["hotelPlaceId"] = "hotel"

            commands.append({"map.addPin": {"id": "hotel", "lat": float(coords[0]), "lng": float(coords[1]), "type": "hotel", "color": "green", "label": str(name)}})
            commands.append({"map.zoomTo": {"lat": float(coords[0]), "lng": float(coords[1]), "zoom": 14}})
            commands.append({"session.storeHotel": {"dayIndex": day_index, "placeId": "hotel", "name_en": str(name), "lat": float(coords[0]), "lng": float(coords[1])}})

            trip_state["ui_stage"] = "day_suggest"
            picks = _candidate_pois(trip_state, limit=3)
            reply = "Perfect — I’ll treat that as your stay point (green pin). For Day 1, which place would you like to add first?"
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [p["name_en"] for p in picks],
                }
            )

        if et == "create_route":
            trip_state["routes"] = await _build_routes_for_confirmed_days(trip_state)
            trip_state["stage"] = "planning" if trip_state.get("routes") else trip_state.get("stage", "exploring")

            if not _is_trip_complete(trip_state):
                reply = "Finish confirming your days first, then I can build clean routes for each day."
            elif not trip_state.get("routes"):
                reply = "I couldn’t build the route yet — please make sure each confirmed day has 1–2 visiting stops."
            else:
                commands.append({"ui.enableButton": "export"})
                reply = "Done — your day-by-day routes are ready. You can now export each day to Google Maps."

            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [],
                }
            )

    if message and _is_outside_kathmandu(message):
        reply = _fallback("off_topic")
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": [],
            }
        )

    if trip_state.get("planning_permission") is True:
        day_index = _current_day_index(trip_state)
        stay_days = None
        if isinstance(trip_state.get("trip_profile"), dict):
            stay_days = trip_state["trip_profile"].get("time_days")
        if isinstance(stay_days, int) and day_index > stay_days and _has_buildable_trip(trip_state):
            commands.append({"ui.enableButton": "buildRoute"})
            reply = f"All your {stay_days} days are planned. You can build routes now."
            trip_state["ui_stage"] = "done"
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [],
                }
            )

        d = _find_day(trip_state, day_index)
        visits = d.get("visits") if isinstance(d, dict) else None
        if message and trip_state.get("ui_stage") == "day_suggest" and _looks_like_save_day(message):
            if isinstance(visits, list) and 1 <= len(visits) <= 2:
                preview = _day_preview_text(trip_state, day_index) or ""
                trip_state["ui_stage"] = "day_confirm"
                reply = preview + "\n\nSave this as Day " + str(day_index) + "?"
                return JSONResponse(
                    {
                        "session_id": session_id,
                        "message": reply,
                        "reply": reply,
                        "commands": commands,
                        "trip_state": trip_state,
                        "map_actions": _map_actions_from_state(trip_state),
                        "suggestions": ["Yes", "No"],
                    }
                )

        if next_field and next_question:
            trip_state["ui_stage"] = "collect_profile"
            reply = next_question
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [],
                }
            )

        if not trip_state.get("hotel"):
            trip_state["ui_stage"] = "collect_hotel"
            reply = "Where are you staying in Kathmandu? (Area is fine — it's your starting point each day.)"
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": ["I'm staying in Thamel", "I'm staying near Boudha", "I'm staying near Durbar Square"],
                }
            )

        if d.get("confirmed") is True:
            reply = f"Day {day_index} is already confirmed."
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [],
                }
            )

        picks = _candidate_pois(trip_state, limit=3)
        place_guess = _looks_like_place_name(message) if message else None
        poi = _find_poi_by_name(place_guess) if place_guess else None
        if not poi and place_guess:
            poi = _find_poi_mention(place_guess)
        if poi and trip_state.get("ui_stage") in {"day_suggest", "collect_hotel", "collect_profile", "intro"}:
            name = str(poi.get("name", "Selected place"))
            coords = poi.get("coordinates")
            if not (isinstance(coords, list) and len(coords) == 2):
                coords = [KATHMANDU_CENTER[0], KATHMANDU_CENTER[1]]
            pid = _place_id(name)
            ok, reason = _add_visit_to_day(trip_state, day_index, pid)
            if not ok and reason == "day_full":
                reply = "For map clarity and comfort, I keep it to 2 visiting places per day. If you want, we can move this one to the next day."
                return JSONResponse(
                    {
                        "session_id": session_id,
                        "message": reply,
                        "reply": reply,
                        "commands": commands,
                        "trip_state": trip_state,
                        "map_actions": _map_actions_from_state(trip_state),
                        "suggestions": [p["name_en"] for p in picks],
                    }
                )

            _upsert_selected_place(trip_state, name, coords)
            _set_map_view(trip_state, coords, zoom=15)
            place = PLACES.get(pid)
            if place:
                commands.append({"map.addPin": {"id": pid, "lat": place["lat"], "lng": place["lng"], "type": "visit", "color": "blue", "label": place["name_en"]}})
                commands.append({"map.zoomTo": {"lat": place["lat"], "lng": place["lng"], "zoom": 15}})
                commands.append({"ui.showImages": {"placeId": pid, "urls": place.get("images") or []}})
                commands.append({"ui.showReview": {"placeId": pid, "review": str(place.get("review") or "")}})
                commands.append({"session.addPlaceToDay": {"dayIndex": day_index, "placeId": pid}})

            d = _find_day(trip_state, day_index)
            visits = d.get("visits") if isinstance(d, dict) else None
            if isinstance(visits, list) and len(visits) >= 2:
                preview = _day_preview_text(trip_state, day_index) or ""
                trip_state["ui_stage"] = "day_confirm"
                reply = preview + "\n\nSave this as Day " + str(day_index) + "?"
                return JSONResponse(
                    {
                        "session_id": session_id,
                        "message": reply,
                        "reply": reply,
                        "commands": commands,
                        "trip_state": trip_state,
                        "map_actions": _map_actions_from_state(trip_state),
                        "suggestions": ["Yes", "No"],
                    }
                )

            trip_state["ui_stage"] = "day_suggest"
            remaining = _candidate_pois(trip_state, limit=3)
            reply = f"Added {name}. I recommend max 2 visiting places per day (map clarity and comfort). Which second place should we add for Day {day_index}?"
            return JSONResponse(
                {
                    "session_id": session_id,
                    "message": reply,
                    "reply": reply,
                    "commands": commands,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": [p["name_en"] for p in remaining] + [f"Save Day {day_index}"],
                }
            )

        trip_state["ui_stage"] = "day_suggest"
        lines = []
        for p in picks:
            lines.append(f"{p['name_en']}: {str(p.get('storyShort') or '').strip()}")
        short_reply = (
            f"For Day {day_index}, pick up to 2 places: " + ", ".join(p["name_en"] for p in picks) + ". Which first?"
        )
        reply = await _maybe_llm_reply(
            trip_state, message, short_reply, suggestion_names=[p["name_en"] for p in picks]
        )
        return JSONResponse(
            {
                "session_id": session_id,
                "message": reply,
                "reply": reply,
                "commands": commands,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": [p["name_en"] for p in picks],
            }
        )

    reply = await _maybe_llm_reply(trip_state, message, _fallback("vague"))
    return JSONResponse(
        {
            "session_id": session_id,
            "message": reply,
            "reply": reply,
            "commands": commands,
            "trip_state": trip_state,
            "map_actions": _map_actions_from_state(trip_state),
            "suggestions": [],
        }
    )


routes = [
    Route("/", endpoint=index, methods=["GET"]),
    Route("/api/health", endpoint=health, methods=["GET"]),
    Route("/api/pois", endpoint=pois, methods=["GET"]),
    Route("/api/places", endpoint=places, methods=["GET"]),
    Route("/api/chat", endpoint=chat, methods=["POST"]),
    Route("/api/export", endpoint=export_plan, methods=["GET"]),
    Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
]


app = Starlette(routes=routes)
