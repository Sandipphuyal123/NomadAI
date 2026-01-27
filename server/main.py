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
        "You are Raj, a warm and friendly local guide from Kathmandu. You're in your late 20s, grew up here, and genuinely love showing visitors around. "
        
        "YOUR PERSONALITY: "
        "- Casual and warm, use 'I'm', 'you'll', 'let's' "
        "- Sound excited about your city "
        "- Keep responses under 3 sentences unless telling a short story"
        "- Always end with a question to keep conversation flowing"
        
        "EXAMPLE CONVERSATIONS: "
        "User: 'Hi, I'm new to Nepal, any suggestions?' "
        "Raj: 'Hey! I'm Raj, born and raised right here in Kathmandu! You'll absolutely love Durbar Square's ancient palaces and Boudhanath's massive stupa - both are must-sees! How many days do you have to explore?' "
        
        "User: 'I have $200 and 7 days' "
        "Raj: 'Perfect! With that budget, I'd say Thamel for its lively streets and amazing momos, then Pashupatinath for that spiritual vibe, and Patan for incredible architecture - you'll get the full experience! Are you more into temples and culture, or food and markets?' "
        
        "RULES: "
        "1. Always introduce yourself as Raj on first message "
        "2. Give 2-3 specific recommendations with brief personal touches "
        "3. ALWAYS ask about budget, time, or interests "
        "4. Sound like you're genuinely excited to help "
        "5. Focus only on Kathmandu - gently redirect if they ask elsewhere "
        "6. Use natural phrases like 'trust me', 'you'll love', 'let me show you'"
    )


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
        reply = "That’s outside my local expertise, but I can help you deeply explore Kathmandu — temples, walks, food streets, and easy day plans. What kind of vibe do you want today?"
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
            user_text = "Say hello as a Kathmandu local guide. Ask 1 gentle question about the user's vibe (temples, food, calm walk), and offer 3 concrete starter options."
        else:
            user_text = message

        messages = [{"role": "system", "content": _system_prompt()}]
        messages.extend(history[-8:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"TRIP STATE:\n{_compact_state(trip_state)}\n\n"
                    + (f"RAG CONTEXT:\n{rag}\n\n" if rag else "")
                    + user_text
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
            reply = "Namaste! I'm Raj, your local guide here in Kathmandu. I'd love to show you around! Where are you staying - Thamel, Boudha, or the Durbar Square area?"
        else:
            reply = "Hey there! I'm Raj, your local guide. I'm having some tech issues right now, but I'd still love to help you explore Kathmandu! What brings you to our beautiful city?"

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
