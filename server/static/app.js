const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const btnRoute = document.getElementById('btnRoute');
const btnReset = document.getElementById('btnReset');
const suggestionsEl = document.getElementById('suggestions');

const SESSION_KEY = 'ktm_session_id_v1';

let sessionId = localStorage.getItem(SESSION_KEY) || '';
let currentState = null;

const map = L.map('map', { zoomControl: true }).setView([27.7172, 85.3240], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const markerLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);

function addMsg(role, text) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function apiChat(payload) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t);
  }
  return await res.json();
}

function renderMapActions(mapActions) {
  markerLayer.clearLayers();
  routeLayer.clearLayers();

  if (!mapActions) return;

  if (Array.isArray(mapActions.markers)) {
    for (const m of mapActions.markers) {
      const coords = m.coordinates;
      if (!Array.isArray(coords) || coords.length !== 2) continue;

      const isHotel = m.type === 'hotel';
      const color = isHotel ? '#76c7ff' : '#9cffc9';

      const marker = L.circleMarker(coords, {
        radius: isHotel ? 9 : 7,
        color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.25
      }).addTo(markerLayer);

      const label = isHotel ? `Stay: ${m.name}` : m.name;
      marker.bindPopup(label);
    }
  }

  if (Array.isArray(mapActions.routes)) {
    for (const r of mapActions.routes) {
      const pl = r.polyline;
      if (!Array.isArray(pl) || pl.length < 2) continue;
      L.polyline(pl, { color: '#ffd28a', weight: 4, opacity: 0.85 }).addTo(routeLayer);
    }
  }
}

function renderSuggestions(suggestions) {
  if (!suggestionsEl) return;
  suggestionsEl.innerHTML = '';
  if (!Array.isArray(suggestions) || suggestions.length === 0) return;

  for (const s of suggestions) {
    const text = String(s);
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip';
    chip.textContent = text;
    chip.addEventListener('click', () => {
      sendUserMessage(text);
    });
    suggestionsEl.appendChild(chip);
  }
}

function applyServerResponse(data) {
  sessionId = data.session_id;
  localStorage.setItem(SESSION_KEY, sessionId);
  currentState = data.trip_state;
  renderMapActions(data.map_actions);
  renderSuggestions(data.suggestions);
}

async function sendUserMessage(text) {
  const msg = (text || '').trim();
  if (!msg) return;
  addMsg('user', msg);

  const data = await apiChat({ session_id: sessionId || null, message: msg });
  applyServerResponse(data);
  addMsg('assistant', data.reply);
}

async function selectPlace(place) {
  const data = await apiChat({
    session_id: sessionId || null,
    message: '',
    map_event: { type: 'select_place', name: place.name, coordinates: place.coordinates }
  });
  addMsg('assistant', data.reply);
  applyServerResponse(data);
}

async function setHotel(latlng) {
  const data = await apiChat({
    session_id: sessionId || null,
    message: '',
    map_event: { type: 'set_hotel', name: 'Stay', coordinates: [latlng.lat, latlng.lng] }
  });
  addMsg('assistant', data.reply);
  applyServerResponse(data);
}

async function buildRoute() {
  const data = await apiChat({
    session_id: sessionId || null,
    message: '',
    map_event: { type: 'create_route' }
  });
  addMsg('assistant', data.reply);
  applyServerResponse(data);
}

async function resetSession() {
  localStorage.removeItem(SESSION_KEY);
  sessionId = '';
  currentState = null;
  chatLog.innerHTML = '';
  renderMapActions(null);
  renderSuggestions(null);
  await bootHello();
}

async function bootHello() {
  const data = await apiChat({ session_id: sessionId || null, message: '' });
  addMsg('assistant', data.reply);
  applyServerResponse(data);
}

async function loadPois() {
  const res = await fetch('/api/pois');
  const pois = await res.json();
  for (const p of pois) {
    const coords = p.coordinates;
    const marker = L.marker(coords).addTo(map);
    marker.bindPopup(p.name);
    marker.on('click', () => selectPlace(p));
  }
}

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = (chatInput.value || '').trim();
  if (!text) return;
  chatInput.value = '';

  await sendUserMessage(text);
});

btnRoute.addEventListener('click', buildRoute);
btnReset.addEventListener('click', resetSession);

map.on('contextmenu', async (e) => {
  await setHotel(e.latlng);
});

loadPois();
bootHello();
