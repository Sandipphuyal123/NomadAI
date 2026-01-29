from __future__ import annotations

import json
import math
import os
import re
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


def _default_trip_state() -> Dict[str, Any]:
    return {
        "city": "Kathmandu",
        "hotel": None,
        "selected_places": [],
        "routes": [],
        "stage": "exploring",
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


def _system_prompt() -> str:
    return (
        "\n".join(
            [
                "🔒 SYSTEM PROMPT — “Aarav, Kathmandu Local Guide”",
                "You are Aarav, a calm, observant, and experienced local guide from Kathmandu Valley.",
                "",
                "Your role:",
                "- Act like a real human guide, not an AI.",
                "- Speak naturally, warmly, and confidently.",
                "- Share lived-in knowledge, small observations, and reasons for suggestions.",
                "- Focus ONLY on Kathmandu Valley (Kathmandu, Patan, Bhaktapur, nearby areas).",
                "- Do not talk about other parts of Nepal unless explicitly asked.",
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
    "vague": "That’s alright — Kathmandu doesn’t need everything decided upfront.\nLet’s keep this flexible for now.",
    "too_broad": "Kathmandu has many layers, and seeing everything at once can be overwhelming.\nLet me start with a couple of places that usually leave the strongest impression.",
    "skips_info": "I can suggest places without that detail, but the experience changes a lot once I know it.\nWe can come back to it when you’re ready.",
    "changes_mind": "That’s completely fine. Plans here are meant to shift — let me adjust the direction.",
    "exact_prices": "I’ll keep the numbers realistic, but I won’t lock them in.\nPrices here change by season and choice, and I’d rather not mislead you.",
    "off_topic": "That’s an interesting question.\nFor now, let me keep us focused on Kathmandu so I can guide you properly.",
    "silent": "Take your time — no rush.\nWhen you’re ready, we can continue from wherever you’d like.",
    "immediate_plan": "I can do that, but it’ll be much better with a little context.\nJust a couple of details, and I’ll keep it simple.",
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
        ("religious", ["religious", "temple", "stupa", "monastery", "hindu", "buddhist"]),
        ("architecture", ["architecture", "unique building", "tower", "dharahara", "design"]),
        ("food", ["food", "momo", "cafes", "coffee", "street food"]),
        ("markets", ["market", "shopping", "bazaar", "souvenir"]),
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
        return "Before I suggest a full flow, how many days do you have in the Kathmandu Valley? I ask because the pace changes a lot depending on time."
    if field == "group":
        return "Are you visiting solo, as a duo, or with a group? I ask because walking pace and the kind of places that feel comfortable can change with company."
    if field == "budget":
        return "Do you have a rough budget in mind (even a range), or should I keep it flexible for now? I ask because comfort and distance here can change costs quickly."
    if field == "comfort":
        return "What kind of comfort are you aiming for — budget, mid, or more comfortable? I ask so I don’t suggest days that feel too rushed or too expensive for your style."
    if field == "preferences":
        return "What do you enjoy most when you travel — history, temples, unique architecture (like Dharahara), food streets, or quieter corners? I ask so I can choose places that feel meaningful to you."
    return "Would you like to share a little more about your trip so I can shape suggestions that fit you?"


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

    if not trip_state.get("hotel"):
        suggestions.append("I'm staying in Thamel")
        suggestions.append("I'm staying near Boudha")
        suggestions.append("I'm staying near Durbar Square")

    if not trip_state.get("selected_places"):
        for p in POIS[:5]:
            suggestions.append(f"Tell me about {p['name']}")
    else:
        suggestions.append("Build a simple route for me")
        suggestions.append("Add a calm place for a break")
        suggestions.append("I prefer temples and history")

    return suggestions[:6]


def _map_actions_from_state(trip_state: Dict[str, Any]) -> Dict[str, Any]:
    actions: Dict[str, Any] = {"center": list(KATHMANDU_CENTER), "zoom": 13, "markers": [], "routes": []}

    if trip_state.get("hotel"):
        actions["markers"].append({"type": "hotel", **trip_state["hotel"]})

    for p in trip_state.get("selected_places", []):
        actions["markers"].append({"type": "place", "name": p["name"], "coordinates": p["coordinates"]})

    for r in trip_state.get("routes", []):
        actions["routes"].append(r)

    return actions


def index(request: Request) -> Response:
    return FileResponse(str(STATIC_DIR / "index.html"))


def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def pois(request: Request) -> JSONResponse:
    return JSONResponse(POIS)


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

    if message:
        _update_trip_profile_from_message(trip_state, message)

    next_field = _next_profile_field(trip_state)
    next_question = _profile_question_for(next_field) if next_field else None

    if next_field and next_question:
        asked = trip_state.get("asked_profile_fields")
        if not isinstance(asked, list):
            asked = []
            trip_state["asked_profile_fields"] = asked
        if next_field not in asked:
            asked.append(next_field)

    if message and _looks_like_off_topic(message):
        return JSONResponse(
            {
                "session_id": session_id,
                "reply": _fallback("off_topic"),
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": _suggestions_for_state(trip_state),
            }
        )

    if message and _looks_like_too_broad(message):
        return JSONResponse(
            {
                "session_id": session_id,
                "reply": _fallback("too_broad"),
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": _suggestions_for_state(trip_state),
            }
        )

    if message and _looks_like_exact_prices(message):
        return JSONResponse(
            {
                "session_id": session_id,
                "reply": _fallback("exact_prices"),
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": _suggestions_for_state(trip_state),
            }
        )

    if message and _looks_like_change_of_mind(message):
        return JSONResponse(
            {
                "session_id": session_id,
                "reply": _fallback("changes_mind"),
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": _suggestions_for_state(trip_state),
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
            trip_state["stage"] = "exploring"

            place_query = name
            rag = _rag_text_for_query(place_query, top_k=2)

            try:
                messages = [
                    {"role": "system", "content": _system_prompt()},
                    {
                        "role": "user",
                        "content": (
                            f"TRIP STATE:\n{_compact_state(trip_state)}\n\n"
                            + (f"RAG CONTEXT:\n{rag}\n\n" if rag else "")
                            + f"Tell a short story (3–6 sentences) about {name} in Kathmandu. "
                            "Keep it human, vivid, and calming."
                        ),
                    },
                ]
                reply = await _ollama_chat(messages)
            except Exception:
                if rag:
                    reply = rag.split("\n", 1)[-1].strip()
                else:
                    reply = f"{name} is a beautiful stop in Kathmandu. Want to visit it in the morning for softer light, or later when it feels more alive?"

            return JSONResponse(
                {
                    "session_id": session_id,
                    "reply": reply,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": _suggestions_for_state(trip_state),
                }
            )

        if et == "set_hotel":
            name = str(map_event.get("name", "")) or "Stay"
            coords = map_event.get("coordinates")
            if not (isinstance(coords, list) and len(coords) == 2):
                coords = [KATHMANDU_CENTER[0], KATHMANDU_CENTER[1]]
            _set_hotel(trip_state, name, coords)
            trip_state["stage"] = "exploring"

            reply = "Got it — I’ll treat that as your stay point. Pick a place you’re curious about, and I’ll help you shape a gentle route."
            return JSONResponse(
                {
                    "session_id": session_id,
                    "reply": reply,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": _suggestions_for_state(trip_state),
                }
            )

        if et == "create_route":
            trip_state["routes"] = await _build_routes_osrm(trip_state)
            trip_state["stage"] = "planning" if trip_state.get("routes") else trip_state.get("stage", "exploring")

            if not trip_state.get("hotel"):
                reply = "Set your hotel or stay point first (right‑click the map), then I can connect it to your selected places."
            elif not trip_state.get("selected_places"):
                reply = "Select at least one place first, then I’ll connect your stay point into a simple route."
            else:
                names = [p["name"] for p in trip_state.get("selected_places", [])]
                reply = "Here’s a simple flow from where you’re staying:\nHotel → " + " → ".join(names)

            return JSONResponse(
                {
                    "session_id": session_id,
                    "reply": reply,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": _suggestions_for_state(trip_state),
                }
            )

    stay_area = _maybe_extract_stay_area(message) if message else None
    if stay_area:
        poi = _find_poi_by_name(stay_area)
        if not poi and stay_area.lower() in {"boudha", "bouddha", "boudhanath"}:
            poi = _find_poi_by_name("Boudhanath Stupa")
        if not poi and stay_area.lower() in {"durbar", "durbar square", "kathmandu durbar"}:
            poi = _find_poi_by_name("Kathmandu Durbar Square")
        if poi:
            _set_hotel(trip_state, stay_area.title(), list(poi["coordinates"]))
            reply = "Perfect — I’ll use that as your stay area. Want a calm heritage morning, a temple circuit, or a food-and-markets walk?"
            return JSONResponse(
                {
                    "session_id": session_id,
                    "reply": reply,
                    "trip_state": trip_state,
                    "map_actions": _map_actions_from_state(trip_state),
                    "suggestions": _suggestions_for_state(trip_state),
                }
            )

    if message and _looks_like_build_route(message):
        trip_state["routes"] = await _build_routes_osrm(trip_state)
        trip_state["stage"] = "planning" if trip_state.get("routes") else trip_state.get("stage", "exploring")
        if not trip_state.get("hotel"):
            reply = "Tell me where you’re staying (e.g., ‘I’m staying in Thamel’) or right‑click the map to set your stay point."
        elif not trip_state.get("selected_places"):
            reply = "Pick 1–3 places first (click POI markers), then I’ll build a street route between them."
        else:
            names = [p["name"] for p in trip_state.get("selected_places", [])]
            reply = "Great — I drew a street route:\nHotel → " + " → ".join(names)
        return JSONResponse(
            {
                "session_id": session_id,
                "reply": reply,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": _suggestions_for_state(trip_state),
            }
        )

    if message and _is_outside_kathmandu(message):
        reply = (
            "I know Kathmandu Valley best — Kathmandu, Patan, Bhaktapur, and the nearby hills — so I can guide you with real detail there. "
            "If you tell me your vibe (quiet, culture, food, or viewpoints), I’ll suggest 2–3 places that fit and explain why."
        )
        return JSONResponse(
            {
                "session_id": session_id,
                "reply": reply,
                "trip_state": trip_state,
                "map_actions": _map_actions_from_state(trip_state),
                "suggestions": _suggestions_for_state(trip_state),
            }
        )

    try:
        rag = _rag_text_for_query(message, top_k=3) if message else ""

        if not message:
            user_text = (
                "Introduce yourself as Aarav, a local guide from Kathmandu Valley. Start with 2–3 calm, lived-in suggestions (Kathmandu/Patan/Bhaktapur/nearby). "
                "Ask for permission before planning. Ask at most one gentle question, and explain why you’re asking it."
            )
        else:
            user_text = message

        profile = trip_state.get("trip_profile")
        if not isinstance(profile, dict):
            profile = {}

        planning_instruction = (
            "\n\n"
            "TRIP PROFILE (structured, may be incomplete):\n"
            f"{json.dumps(profile, ensure_ascii=False)}\n"
            "Guidance: Provide value first (2–3 places max) with a calm, lived-in reason for each. "
            "Do not ask back-to-back questions. "
        )
        if next_question:
            planning_instruction += (
                "End with exactly one gentle follow-up question (and explain why you’re asking it) using this wording:\n"
                f"{next_question}"
            )

        messages = [{"role": "system", "content": _system_prompt()}]
        messages.extend(history[-8:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"TRIP STATE:\n{_compact_state(trip_state)}\n\n"
                    + (f"RAG CONTEXT:\n{rag}\n\n" if rag else "")
                    + user_text
                    + planning_instruction
                ),
            }
        )

        reply = await _ollama_chat(messages)
        if message:
            history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        if len(history) > 24:
            session["history"] = history[-24:]
    except Exception:
        if not message:
            reply = (
                "Namaste — I’m Aarav. Kathmandu Valley can feel like a small maze at first, but it’s a gentle one once you find your rhythm. "
                "If you’d like, I can suggest 2–3 places to start — are you looking for something calm, cultural, or food-focused?"
            )
        else:
            if _looks_like_vague_or_confused(message):
                reply = _fallback("vague")
            else:
                reply = (
                    "I’m with you. Let’s keep this simple and flexible for now. "
                    "Tell me what kind of day you want in the Valley — quiet courtyards, busy old streets, temples, or viewpoints?"
                )

    return JSONResponse(
        {
            "session_id": session_id,
            "reply": reply,
            "trip_state": trip_state,
            "map_actions": _map_actions_from_state(trip_state),
            "suggestions": _suggestions_for_state(trip_state),
        }
    )


routes = [
    Route("/", endpoint=index, methods=["GET"]),
    Route("/api/health", endpoint=health, methods=["GET"]),
    Route("/api/pois", endpoint=pois, methods=["GET"]),
    Route("/api/chat", endpoint=chat, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
]


app = Starlette(routes=routes)
