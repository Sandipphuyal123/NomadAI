const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const btnRoute = document.getElementById('btnRoute');
const btnReset = document.getElementById('btnReset');
const btnExport = document.getElementById('btnExport');
const suggestionsEl = document.getElementById('suggestions');
const exportLinksEl = document.getElementById('exportLinks');

const SESSION_KEY = 'ktm_session_id_v1';

let sessionId = localStorage.getItem(SESSION_KEY) || '';
let currentState = null;

let placesIndex = {};

const map = L.map('map', { zoomControl: true }).setView([27.7172, 85.3240], 13);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
}).addTo(map);

const markerLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);

const mapPins = {};

function pinIcon(color, label) {
  const bg = color === 'green' ? '#10b981' : '#3b82f6';
  const text = String(label || '').slice(0, 2).toUpperCase();
  const html = `
    <div style="
      width: 32px; height: 32px; border-radius: 999px;
      background: ${bg};
      border: 2px solid rgba(255,255,255,0.9);
      box-shadow: 0 6px 14px rgba(0,0,0,0.25);
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; color: white; font-size: 12px;
    ">${text}</div>
  `;
  return L.divIcon({
    className: '',
    html,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16]
  });
}

function executeCommands(commands) {
  if (!Array.isArray(commands)) return;
  for (const cmd of commands) {
    if (!cmd || typeof cmd !== 'object') continue;
    const keys = Object.keys(cmd);
    if (keys.length !== 1) continue;
    const k = keys[0];
    const payload = cmd[k];

    if (k === 'map.zoomTo' && payload) {
      const { lat, lng, zoom } = payload;
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        map.setView([lat, lng], Number.isFinite(zoom) ? zoom : map.getZoom(), { animate: true });
      }
      continue;
    }

    if (k === 'map.addPin' && payload) {
      const { id, lat, lng, color, label, type } = payload;
      if (!id || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      if (mapPins[id]) {
        markerLayer.removeLayer(mapPins[id]);
        delete mapPins[id];
      }
      const shortLabel = type === 'hotel' ? 'H' : 'V';
      const marker = L.marker([lat, lng], { icon: pinIcon(color, shortLabel) }).addTo(markerLayer);
      if (label) marker.bindPopup(String(label));
      mapPins[id] = marker;
      continue;
    }

    if (k === 'map.removePin') {
      const id = payload;
      if (id && mapPins[id]) {
        markerLayer.removeLayer(mapPins[id]);
        delete mapPins[id];
      }
      continue;
    }

    if (k === 'session.storeProfile' && payload) {
      sessionStorage.setItem('userProfile', JSON.stringify(payload));
      continue;
    }

    if (k === 'session.storePlaces' && payload) {
      if (payload && typeof payload === 'object') {
        sessionStorage.setItem('places', JSON.stringify(payload));
        placesIndex = payload;
      }
      continue;
    }

    if (k === 'session.addPlaceToDay' && payload) {
      const tripRaw = sessionStorage.getItem('trip');
      const trip = tripRaw ? JSON.parse(tripRaw) : { days: [], notes: '' };
      const { dayIndex, placeId } = payload;
      if (!Number.isFinite(dayIndex) || !placeId) {
        sessionStorage.setItem('trip', JSON.stringify(trip));
        continue;
      }
      let day = trip.days.find(d => d.dayIndex === dayIndex);
      if (!day) {
        day = { dayIndex, hotelPlaceId: null, visits: [], confirmed: false };
        trip.days.push(day);
      }
      if (!Array.isArray(day.visits)) day.visits = [];
      if (!day.visits.includes(placeId)) day.visits.push(placeId);
      sessionStorage.setItem('trip', JSON.stringify(trip));
      continue;
    }

    if (k === 'session.storeHotel' && payload) {
      const tripRaw = sessionStorage.getItem('trip');
      const trip = tripRaw ? JSON.parse(tripRaw) : { days: [], notes: '' };
      const { dayIndex, placeId, name_en, lat, lng } = payload;
      if (!Number.isFinite(dayIndex) || !placeId) {
        sessionStorage.setItem('trip', JSON.stringify(trip));
        continue;
      }
      let day = trip.days.find(d => d.dayIndex === dayIndex);
      if (!day) {
        day = { dayIndex, hotelPlaceId: null, visits: [], confirmed: false };
        trip.days.push(day);
      }
      day.hotelPlaceId = placeId;

      const placesRaw = sessionStorage.getItem('places');
      const places = placesRaw ? JSON.parse(placesRaw) : {};
      places[placeId] = { id: placeId, name_en, lat, lng };
      sessionStorage.setItem('places', JSON.stringify(places));
      placesIndex = places;

      sessionStorage.setItem('trip', JSON.stringify(trip));
      continue;
    }

    if (k === 'session.confirmDay') {
      const dayIndex = payload;
      const tripRaw = sessionStorage.getItem('trip');
      const trip = tripRaw ? JSON.parse(tripRaw) : { days: [] };
      const day = trip.days.find(d => d.dayIndex === dayIndex);
      if (day) day.confirmed = true;
      sessionStorage.setItem('trip', JSON.stringify(trip));
      continue;
    }

    if (k === 'ui.enableButton' && payload) {
      const name = payload;
      if (name === 'buildRoute') btnRoute.disabled = false;
      if (name === 'export') btnExport.disabled = false;
      continue;
    }

    if (k === 'ui.resetSession') {
      resetSession();
      continue;
    }

    if (k === 'ui.showReview' && payload) {
      const review = payload.review || payload['short review'] || '';
      if (review) addMsg('assistant', String(review));
      continue;
    }

    if (k === 'ui.showImages' && payload) {
      const urls = payload.urls || payload[1] || [];
      if (Array.isArray(urls) && urls.length > 0) {
        const el = document.createElement('div');
        el.className = 'msg assistant';
        for (const u of urls.slice(0, 3)) {
          const img = document.createElement('img');
          img.src = String(u);
          img.style.maxWidth = '100%';
          img.style.borderRadius = '12px';
          img.style.marginTop = '8px';
          el.appendChild(img);
        }
        chatLog.appendChild(el);
        chatLog.scrollTop = chatLog.scrollHeight;
      }
      continue;
    }
  }
}

function addMsg(role, text) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderExportLinks(payload) {
  if (!exportLinksEl) return;
  exportLinksEl.innerHTML = '';

  if (!payload || payload.ok !== true) {
    const el = document.createElement('div');
    el.className = 'exportEmpty';
    el.textContent = 'Add a hotel (right-click) and a few places first, then export.';
    exportLinksEl.appendChild(el);
    return;
  }

  const links = payload.links || [];
  if (!Array.isArray(links) || links.length === 0) {
    const el = document.createElement('div');
    el.className = 'exportEmpty';
    el.textContent = 'Not enough stops yet to build a day route. Add more places.';
    exportLinksEl.appendChild(el);
    return;
  }

  for (const item of links) {
    const row = document.createElement('a');
    row.className = 'exportLink';
    row.target = '_blank';
    row.rel = 'noreferrer';
    row.href = item.url;
    row.textContent = `Open Day ${item.day} in Google Maps`;
    exportLinksEl.appendChild(row);
  }
}

async function exportToGoogleMaps() {
  if (!sessionId) {
    renderExportLinks({ ok: false });
    return;
  }
  const res = await fetch(`/api/export?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) {
    renderExportLinks({ ok: false });
    return;
  }
  const data = await res.json();
  renderExportLinks(data);
}

async function loadPlaces() {
  try {
    const res = await fetch('/api/places');
    if (!res.ok) return;
    const data = await res.json();
    const places = {};
    const list = (data && data.places) || [];
    if (Array.isArray(list)) {
      for (const p of list) {
        if (!p || typeof p !== 'object') continue;
        if (!p.id) continue;
        places[p.id] = p;
      }
    }
    sessionStorage.setItem('places', JSON.stringify(places));
    placesIndex = places;
  } catch {
  }
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
  routeLayer.clearLayers();

  if (!mapActions) return;

  if (Array.isArray(mapActions.center) && mapActions.center.length === 2) {
    const z = Number.isFinite(mapActions.zoom) ? mapActions.zoom : map.getZoom();
    map.setView(mapActions.center, z, { animate: true });
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
  executeCommands(data.commands);
}

async function sendUserMessage(text) {
  const msg = (text || '').trim();
  if (!msg) return;
  addMsg('user', msg);

  const data = await apiChat({ session_id: sessionId || null, message: msg });
  applyServerResponse(data);
  addMsg('assistant', data.message || data.reply);
}

async function selectPlace(place) {
  const data = await apiChat({
    session_id: sessionId || null,
    message: '',
    map_event: { type: 'select_place', name: place.name, coordinates: place.coordinates }
  });
  addMsg('assistant', data.message || data.reply);
  applyServerResponse(data);
}

async function setHotel(latlng) {
  const data = await apiChat({
    session_id: sessionId || null,
    message: '',
    map_event: { type: 'set_hotel', name: 'Stay', coordinates: [latlng.lat, latlng.lng] }
  });
  addMsg('assistant', data.message || data.reply);
  applyServerResponse(data);
}

async function buildRoute() {
  const data = await apiChat({
    session_id: sessionId || null,
    message: '',
    map_event: { type: 'create_route' }
  });
  addMsg('assistant', data.message || data.reply);
  applyServerResponse(data);
}

async function resetSession() {
  localStorage.removeItem(SESSION_KEY);
  sessionStorage.clear();
  sessionId = '';
  currentState = null;
  chatLog.innerHTML = '';
  for (const k of Object.keys(mapPins)) {
    if (mapPins[k]) markerLayer.removeLayer(mapPins[k]);
    delete mapPins[k];
  }
  routeLayer.clearLayers();
  map.setView([27.7172, 85.3240], 13, { animate: true });
  if (btnRoute) btnRoute.disabled = true;
  if (btnExport) btnExport.disabled = true;
  renderExportLinks({ ok: false });
  renderMapActions(null);
  renderSuggestions(null);
  await bootHello();
}

async function bootHello() {
  await loadPlaces();
  const data = await apiChat({ session_id: sessionId || null, message: '' });
  addMsg('assistant', data.message || data.reply);
  applyServerResponse(data);
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
if (btnExport) btnExport.addEventListener('click', exportToGoogleMaps);

map.on('contextmenu', async (e) => {
  await setHotel(e.latlng);
});

bootHello();
