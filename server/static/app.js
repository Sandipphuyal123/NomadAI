const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const btnRoute = document.getElementById('btnRoute');
const btnReset = document.getElementById('btnReset');
const btnCalendar = document.getElementById('btnCalendar');
const suggestionsEl = document.getElementById('suggestions');
const exportLinksEl = document.getElementById('exportLinks');
const placeSearch = document.getElementById('placeSearch');
const searchResults = document.getElementById('searchResults');

const screenLanding = document.getElementById('screenLanding');
const screenPlanner = document.getElementById('screenPlanner');
const wizardOverlay = document.getElementById('wizardOverlay');
const wizardBar = document.getElementById('wizardBar');
const btnStartPlanning = document.getElementById('btnStartPlanning');
const btnCreateTrip = document.getElementById('btnCreateTrip');

const screenResults = document.getElementById('screenResults');
const resultsCity = document.getElementById('resultsCity');
const resultsDesc = document.getElementById('resultsDesc');
const btnPersonalizedGuide = document.getElementById('btnPersonalizedGuide');
const btnEditChoices = document.getElementById('btnEditChoices');
const itineraryEl = document.getElementById('itinerary');
const hotelRecsEl = document.getElementById('hotelRecs');
const tripOverviewEl = document.getElementById('tripOverview');

const btnChatScroll = document.getElementById('btnChatScroll');
const btnItineraryScroll = document.getElementById('btnItineraryScroll');

const wizardStep1 = document.getElementById('wizardStep1');
const wizardStep2 = document.getElementById('wizardStep2');
const wizardStep3 = document.getElementById('wizardStep3');
const wizDestination = document.getElementById('wizDestination');
const wizDays = document.getElementById('wizDays');
const wizBack = document.getElementById('wizBack');
const wizNext = document.getElementById('wizNext');

const btnTheme = document.getElementById('btnTheme');

const SESSION_KEY = 'ktm_session_id_v1';

let sessionId = localStorage.getItem(SESSION_KEY) || '';
let currentState = null;

let placesIndex = {};

let plannerBooted = false;
let currentPlan = null;
let thinkingEl = null;

const THEME_KEY = 'nomadai_theme_v1';

function getPreferredTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  try {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

function applyTheme(theme) {
  const t = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  if (btnTheme) btnTheme.textContent = t === 'dark' ? 'Dark' : 'Light';
}

function setTheme(theme) {
  const t = theme === 'dark' ? 'dark' : 'light';
  localStorage.setItem(THEME_KEY, t);
  applyTheme(t);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
  setTheme(current === 'dark' ? 'light' : 'dark');
}

applyTheme(getPreferredTheme());

if (btnTheme) {
  btnTheme.addEventListener('click', () => {
    toggleTheme();
  });
}

function isChatNearBottom() {
  if (!chatLog) return true;
  const threshold = 120;
  const distance = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight;
  return distance <= threshold;
}

function updateChatScrollButton() {
  if (!btnChatScroll || !chatLog) return;
  const showBtn = !isChatNearBottom() && chatLog.scrollHeight > chatLog.clientHeight + 40;
  btnChatScroll.classList.toggle('isHidden', !showBtn);
}

function scrollChatToBottom() {
  if (!chatLog) return;
  chatLog.scrollTop = chatLog.scrollHeight;
  updateChatScrollButton();
}

function isItineraryNearBottom() {
  if (!itineraryEl) return true;
  const threshold = 120;
  const distance = itineraryEl.scrollHeight - itineraryEl.scrollTop - itineraryEl.clientHeight;
  return distance <= threshold;
}

function updateItineraryScrollButton() {
  if (!btnItineraryScroll || !itineraryEl) return;
  const showBtn = !isItineraryNearBottom() && itineraryEl.scrollHeight > itineraryEl.clientHeight + 40;
  btnItineraryScroll.classList.toggle('isHidden', !showBtn);
}

function scrollItineraryToBottom() {
  if (!itineraryEl) return;
  itineraryEl.scrollTop = itineraryEl.scrollHeight;
  updateItineraryScrollButton();
}

if (itineraryEl) {
  itineraryEl.addEventListener('scroll', () => {
    updateItineraryScrollButton();
  }, { passive: true });
}

if (btnItineraryScroll) {
  btnItineraryScroll.addEventListener('click', () => {
    scrollItineraryToBottom();
  });
}

if (chatLog) {
  chatLog.addEventListener('scroll', () => {
    updateChatScrollButton();
  }, { passive: true });
}

if (btnChatScroll) {
  btnChatScroll.addEventListener('click', () => {
    scrollChatToBottom();
  });
}

const wizardState = {
  step: 1,
  destination: 'Kathmandu, Nepal',
  days: 2,
  budget: 'flexible',
  group: 'solo'
};

const map = L.map('map', { zoomControl: true, scrollWheelZoom: false }).setView([27.7172, 85.3240], 13);
// OpenStreetMap tiles - free and open source
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  subdomains: ['a', 'b', 'c']
}).addTo(map);

const markerLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);

const mapPins = {};

// Ensure chat scrolling works even next to the map.
// Leaflet can capture wheel events; keep wheel scrolling inside the chat when cursor is over chat.
if (chatLog) {
  chatLog.addEventListener(
    'wheel',
    (e) => {
      // Only trap the wheel event when the chat can actually scroll in that direction.
      // This prevents the page from feeling "locked" when the chat is already at the top/bottom.
      const deltaY = e.deltaY || 0;
      const atTop = chatLog.scrollTop <= 0;
      const atBottom = chatLog.scrollTop + chatLog.clientHeight >= chatLog.scrollHeight - 1;
      const scrollingUp = deltaY < 0;
      const scrollingDown = deltaY > 0;
      const canScrollUp = !atTop;
      const canScrollDown = !atBottom;

      if ((scrollingUp && canScrollUp) || (scrollingDown && canScrollDown)) {
        e.stopPropagation();
      }
    },
    { passive: true }
  );
}

// Only allow scroll-wheel zoom when the cursor is over the map.
const mapEl = document.getElementById('map');
if (mapEl) {
  mapEl.addEventListener('mouseenter', () => {
    try { map.scrollWheelZoom.enable(); } catch { }
  });
  mapEl.addEventListener('mouseleave', () => {
    try { map.scrollWheelZoom.disable(); } catch { }
  });
}

let isPersonalizedGuide = false;

let activeWizardStepEl = null;

function show(el) {
  if (!el) return;
  el.classList.remove('isHidden');
}

function hide(el) {
  if (!el) return;
  el.classList.add('isHidden');
}

function setWizardStep(step) {
  const prev = activeWizardStepEl;
  const next = step === 1 ? wizardStep1 : step === 2 ? wizardStep2 : wizardStep3;
  if (!next) return;

  wizardState.step = step;
  if (wizardBar) {
    const pct = step === 1 ? 33.33 : step === 2 ? 66.66 : 100;
    wizardBar.style.width = `${pct}%`;
  }
  if (wizBack) wizBack.disabled = step === 1;
  if (wizNext) wizNext.textContent = step === 3 ? 'Generate Plan ✓' : 'Continue →';

  if (wizardStep1) wizardStep1.classList.remove('isHidden');
  if (wizardStep2) wizardStep2.classList.remove('isHidden');
  if (wizardStep3) wizardStep3.classList.remove('isHidden');

  if (prev && prev !== next) {
    prev.classList.remove('isActive');
    prev.classList.add('isLeaving');
    setTimeout(() => {
      prev.classList.remove('isLeaving');
      prev.classList.add('isHidden');
    }, 260);
  }

  next.classList.remove('isHidden');
  requestAnimationFrame(() => {
    next.classList.add('isActive');
  });

  activeWizardStepEl = next;
  syncWizardChoiceUI();
  updateWizardNextState();
}

function openWizard() {
  if (wizDestination) wizDestination.value = wizardState.destination;
  if (wizDays) wizDays.value = String(wizardState.days || 2);
  if (!wizardOverlay) return;
  wizardOverlay.classList.remove('isHidden');
  requestAnimationFrame(() => {
    wizardOverlay.classList.add('isOpen');
  });
  activeWizardStepEl = null;
  setWizardStep(1);
}

function closeWizard() {
  if (!wizardOverlay) return;
  wizardOverlay.classList.remove('isOpen');
  setTimeout(() => {
    wizardOverlay.classList.add('isHidden');
  }, 240);
}

function syncWizardChoiceUI() {
  if (!wizardOverlay) return;
  const b = wizardState.budget;
  const g = wizardState.group;
  wizardOverlay.querySelectorAll('[data-budget]').forEach((btn) => {
    btn.classList.toggle('isActive', (btn.getAttribute('data-budget') || '') === b);
  });
  wizardOverlay.querySelectorAll('[data-group]').forEach((btn) => {
    btn.classList.toggle('isActive', (btn.getAttribute('data-group') || '') === g);
  });
}

function _validWizardDays() {
  const d = parseInt(String(wizardState.days || ''), 10);
  return Number.isFinite(d) && d >= 1 && d <= 14;
}

function updateWizardNextState() {
  if (!wizNext) return;
  let ok = true;
  if (wizardState.step === 1) {
    ok = _validWizardDays();
  } else if (wizardState.step === 2) {
    ok = ['budget', 'mid', 'luxury'].includes(String(wizardState.budget || ''));
  } else if (wizardState.step === 3) {
    ok = ['solo', 'couple', 'family', 'friends'].includes(String(wizardState.group || ''));
  }
  wizNext.disabled = !ok;
}

function mapsSearchUrl(name) {
  const q = encodeURIComponent(String(name || '').trim() || 'Kathmandu');
  return `https://www.google.com/maps/search/?api=1&query=${q}`;
}

function formatUsdRange(minUsd, maxUsd) {
  const a = Math.round(minUsd);
  const b = Math.round(maxUsd);
  return `$${a}–$${b}`;
}

function usdToNpr(usd) {
  // Approx; we avoid exact pricing guarantees.
  const rate = 132;
  return Math.round(usd * rate);
}

function hotelImageUrl(name) {
  const n = String(name || '').trim();
  if (!n) return '';
  return `/images/${encodeURIComponent(n)}.jpg`;
}

function hotelBudgetRangePerNight() {
  if (wizardState.budget === 'budget') return { min: 18, max: 45 };
  if (wizardState.budget === 'mid') return { min: 45, max: 90 };
  if (wizardState.budget === 'luxury') return { min: 90, max: 180 };
  return { min: 35, max: 95 };
}

function activityBudgetPerStop() {
  if (wizardState.budget === 'budget') return { min: 1, max: 8 };
  if (wizardState.budget === 'mid') return { min: 5, max: 18 };
  if (wizardState.budget === 'luxury') return { min: 10, max: 35 };
  return { min: 4, max: 20 };
}

function groupMultiplier() {
  const g = wizardState.group;
  if (g === 'solo') return 1;
  if (g === 'couple') return 2;
  if (g === 'family') return 3;
  if (g === 'friends') return 4;
  return 1;
}

function renderOverview() {
  if (!tripOverviewEl) return;
  if (!currentPlan) return;
  const days = currentPlan.stay_days || 0;
  const total = currentPlan.total_npr || { min: 0, max: 0 };
  const hotel = (currentPlan.hotel_options && currentPlan.hotel_options.price_npr) || { min: 0, max: 0 };
  const budgetLabel = wizardState.budget === 'budget' ? 'Budget Friendly' : wizardState.budget === 'mid' ? 'Moderate' : wizardState.budget === 'luxury' ? 'Luxury' : 'Flexible';
  const groupLabel = wizardState.group === 'solo' ? 'Solo' : wizardState.group === 'couple' ? 'Couple' : wizardState.group === 'family' ? 'Family' : wizardState.group === 'friends' ? 'Group/Friends' : 'Solo';

  tripOverviewEl.innerHTML = '';
  const rows = [
    { k: 'Budget', v: budgetLabel },
    { k: 'Traveler', v: groupLabel },
    { k: 'No of Days', v: String(days) },
    { k: 'Location', v: String(wizardState.destination || 'Kathmandu, Nepal') },
    { k: 'Hotel (per night)', v: `≈ NPR ${hotel.min || 0}–${hotel.max || hotel.min || 0}` },
    { k: 'Estimated Trip Range', v: `≈ NPR ${total.min || 0}–${total.max || total.min || 0}` }
  ];
  for (const r of rows) {
    const row = document.createElement('div');
    row.className = 'ovRow';
    const k = document.createElement('div');
    k.className = 'ovKey';
    k.textContent = r.k;
    const v = document.createElement('div');
    v.className = 'ovVal';
    v.textContent = r.v;
    row.appendChild(k);
    row.appendChild(v);
    tripOverviewEl.appendChild(row);
  }
}

async function fetchPlan() {
  const payload = {
    days: wizardState.days || 2,
    budget_tier: wizardState.budget || 'flexible',
    group: wizardState.group || 'solo',
    preferences: [],
    comfort: wizardState.budget === 'budget' ? 'budget' : wizardState.budget === 'mid' ? 'mid' : 'comfortable'
  };
  const res = await fetch('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to create plan');
  const data = await res.json();
  if (data.session_id) {
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);
  }
  if (data.plan) {
    currentPlan = data.plan;
  }

  // Enable trip dates button once a plan exists.
  if (btnCalendar) {
    btnCalendar.disabled = false;
    btnCalendar.removeAttribute('disabled');
    btnCalendar.style.cursor = 'pointer';
    btnCalendar.style.pointerEvents = 'auto';
    btnCalendar.style.opacity = '1';
  }
}

function getResultsHotelOptions() {
  const hotel = hotelBudgetRangePerNight();
  const options = wizardState.budget === 'luxury'
    ? ['Dwarika\'s Hotel', 'Hyatt Regency Kathmandu', 'Kathmandu Marriott Hotel']
    : wizardState.budget === 'mid'
      ? ['Aloft Kathmandu Thamel', 'Baber Mahal Vilas', 'Hotel Tibet International']
      : ['Kathmandu Guest House', 'Hotel Yala Peak', 'Thamel Boutique Hotel'];

  const meta = {
    "Dwarika's Hotel": { style: 'heritage luxury', bestFor: 'quiet, cultural atmosphere' },
    'Hyatt Regency Kathmandu': { style: 'resort-style', bestFor: 'space, calm, full amenities' },
    'Kathmandu Marriott Hotel': { style: 'international chain', bestFor: 'modern comfort and reliability' },
    'Aloft Kathmandu Thamel': { style: 'modern lifestyle', bestFor: 'being in the center of Thamel' },
    'Baber Mahal Vilas': { style: 'boutique heritage', bestFor: 'character and quieter evenings' },
    'Hotel Tibet International': { style: 'classic comfort', bestFor: 'Boudha access and calmer pace' },
    'Kathmandu Guest House': { style: 'classic budget', bestFor: 'walkable Thamel and value' },
    'Hotel Yala Peak': { style: 'simple budget', bestFor: 'solo travelers and basics done well' },
    'Thamel Boutique Hotel': { style: 'budget boutique', bestFor: 'Thamel convenience with comfort' },
  };

  return {
    price_min_usd: hotel.min,
    price_max_usd: hotel.max,
    options: options.slice(0, 2).map((name) => ({ name, ...(meta[name] || {}) }))
  };
}

function getResultsItinerary(days) {
  const d = Math.max(1, Math.min(14, parseInt(String(days || 2), 10) || 2));
  const picks = pickPlacesForDays(d);
  const out = [];
  for (let dayIndex = 1; dayIndex <= d; dayIndex++) {
    const p1 = picks[(dayIndex - 1) * 2];
    const p2 = picks[(dayIndex - 1) * 2 + 1];
    const visits = [];
    if (p1 && p1.id) visits.push(p1.id);
    if (p2 && p2.id) visits.push(p2.id);
    out.push({ dayIndex, visits });
  }
  return out;
}

async function bootPlannerAsPersonalizedGuide() {
  hide(screenLanding);
  hide(screenResults);
  show(screenPlanner);

  setTimeout(() => {
    try { map.invalidateSize(true); } catch { }
  }, 50);

  if (!plannerBooted) {
    plannerBooted = true;
    await loadPlaces();
  }

  isPersonalizedGuide = true;

  if (!currentPlan) {
    await fetchPlan();
  }
  await loadPlaces();

  const days = currentPlan?.stay_days || Math.max(1, Math.min(14, parseInt(String(wizardState.days || 2), 10) || 2));
  const guideInit = {
    destination: wizardState.destination || 'Kathmandu, Nepal',
    profile: {
      time_days: days,
      group_label: wizardState.group || 'solo',
      group_count: groupMultiplier(),
      comfort: wizardState.budget === 'budget' ? 'budget' : wizardState.budget === 'mid' ? 'mid' : 'comfortable',
      budget_tier: wizardState.budget || 'flexible'
    },
    hotel_options: (currentPlan && currentPlan.hotel_options) || getResultsHotelOptions(),
    itinerary: { days: (currentPlan && currentPlan.days) || getResultsItinerary(days) }
  };

  const data = await apiChat({ session_id: sessionId || null, message: '', guide_init: guideInit });
  applyServerResponse(data);
  addMsg('assistant', data.message || data.reply);
  await exportToGoogleMaps();
}

function renderHotelRecs() {
  if (!hotelRecsEl) return;
  hotelRecsEl.innerHTML = '';
  if (!currentPlan || !currentPlan.hotel_options) return;
  const hotel = currentPlan.hotel_options.price_npr || { min: 0, max: 0 };
  const options = (currentPlan.hotel_options.options || []).slice(0, 2);

  for (const opt of options) {
    const name = opt.name || 'Hotel';
    const card = document.createElement('div');
    card.className = 'recCard';

    const imgUrl = hotelImageUrl(name);
    const img = document.createElement('div');
    img.className = 'recThumb';
    if (imgUrl) {
      img.style.backgroundImage = `url('${imgUrl}')`;
    }

    const top = document.createElement('div');
    top.className = 'recTop';
    const left = document.createElement('div');
    const nm = document.createElement('div');
    nm.className = 'recName';
    nm.textContent = name;
    const sm = document.createElement('div');
    sm.className = 'recSmall';
    sm.textContent = 'Recommended based on your budget and pace.';
    left.appendChild(nm);
    left.appendChild(sm);

    const price = document.createElement('div');
    price.className = 'recPrice';
    price.textContent = `≈ NPR ${hotel.min || 0}–${hotel.max || hotel.min || 0}/night`;
    top.appendChild(left);
    top.appendChild(price);

    const sm2 = document.createElement('div');
    sm2.className = 'recSmall';
    sm2.textContent = `Estimated range — verify current prices on Google Maps.`;
    const link = document.createElement('a');
    link.className = 'stopLink';
    link.href = mapsSearchUrl(`${name}, Kathmandu`);
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.textContent = 'View on Google Maps →';

    card.appendChild(img);
    card.appendChild(top);
    card.appendChild(sm2);
    card.appendChild(link);
    hotelRecsEl.appendChild(card);
  }
}

function pickPlacesForDays(days) {
  const list = Object.values(placesIndex || {}).filter(p => p && p.name_en);
  // Keep deterministic-ish: sort by name
  list.sort((a, b) => String(a.name_en).localeCompare(String(b.name_en)));
  const need = days * 2;
  return list.slice(0, need);
}

async function fetchPlaceImages(placeIds) {
  if (!placeIds || placeIds.length === 0) return {};
  try {
    const res = await fetch(`/api/places/images?place_ids=${placeIds.join(',')}`);
    if (res.ok) {
      const data = await res.json();
      return data.images || {};
    }
  } catch (e) { console.warn('Place images fetch failed:', e); }
  return {};
}

async function renderItinerary() {
  if (!itineraryEl) return;
  itineraryEl.innerHTML = '';
  if (!currentPlan || !Array.isArray(currentPlan.days)) return;

  updateItineraryScrollButton();

  const daysArr = currentPlan.days.slice().sort((a, b) => (a.dayIndex || 0) - (b.dayIndex || 0));
  const allPlaceIds = [...new Set(daysArr.flatMap(d => (d.visits || []).slice(0, 2)))];
  const placeImages = await fetchPlaceImages(allPlaceIds);

  for (const day of daysArr) {
    const d = day.dayIndex || 0;
    const card = document.createElement('div');
    card.className = 'dayCard dayCardCollapsible';

    const header = document.createElement('div');
    header.className = 'dayHeader dayHeaderClickable';
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    header.setAttribute('aria-expanded', 'true');
    const title = document.createElement('div');
    title.className = 'dayTitle';
    title.textContent = `Day ${d}`;
    const chevron = document.createElement('span');
    chevron.className = 'dayChevron';
    chevron.textContent = '▼';
    header.appendChild(title);
    header.appendChild(chevron);
    card.appendChild(header);

    const stops = document.createElement('div');
    stops.className = 'dayStops dayStopsExpandable';

    const hotelStop = document.createElement('div');
    hotelStop.className = 'stop';
    hotelStop.innerHTML = `
      <div class="thumb thumbHotel">🏨</div>
      <div>
        <div class="stopTitle">Hotel / Stay</div>
        <div class="stopMeta">Start point for the day (we'll finalize it in the guide).</div>
      </div>
    `;
    stops.appendChild(hotelStop);

    const visitIds = (day.visits || []).slice(0, 2);
    for (const pid of visitIds) {
      const p = placesIndex[pid];
      if (!p) continue;
      const name = p.name_en;
      const imgUrl = placeImages[pid] || null;
      const thumbStyle = imgUrl ? `background-image: url('${imgUrl}'); background-size: cover;` : '';
      const story = (p.storyShort || p.story || '').toString().trim();
      const meta = story ? story.slice(0, 140) + (story.length > 140 ? '…' : '') : 'A great stop that fits your pace and interests.';
      const etiquette = Array.isArray(p.common_mistakes) && p.common_mistakes.length ? `Etiquette: ${p.common_mistakes[0]}.` : '';
      const price = (day.cost_npr || {});
      const priceTxt = `Day est: NPR ${price.min || 0}–${price.max || price.min || 0}`;

      const stop = document.createElement('div');
      stop.className = 'stop';
      stop.innerHTML = `
        <div class="thumb" style="${thumbStyle}"></div>
        <div>
          <div class="stopTitle">${name}</div>
          <div class="stopMeta">${priceTxt}</div>
          <div class="stopMeta">${meta}</div>
          <div class="stopMeta">${etiquette}</div>
        </div>
      `;
      const link = document.createElement('a');
      link.className = 'stopLink';
      link.href = mapsSearchUrl(`${name}, Kathmandu`);
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = 'Open in Google Maps →';
      stop.querySelector('div:last-child').appendChild(link);
      stops.appendChild(stop);
    }

    card.appendChild(stops);
    itineraryEl.appendChild(card);

    header.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isNowCollapsed = card.classList.toggle('dayCardCollapsed');
      header.setAttribute('aria-expanded', !isNowCollapsed);
    });
    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        header.click();
      }
    });
  }

  updateItineraryScrollButton();
}

async function showResults() {
  hide(screenLanding);
  hide(screenPlanner);
  show(screenResults);

  if (resultsCity) resultsCity.textContent = 'Kathmandu';
  if (resultsDesc) {
    const budgetLabel = wizardState.budget === 'budget' ? 'budget-friendly' : wizardState.budget === 'mid' ? 'moderate' : wizardState.budget === 'luxury' ? 'luxury' : 'flexible';
    resultsDesc.textContent = `A ${budgetLabel} itinerary tuned for your group and pace — up to 2 places per day.`;
  }

  renderHotelRecs();
  renderOverview();
  await renderItinerary();
}

async function bootPlannerWithWizardState() {
  hide(screenLanding);
  hide(screenResults);
  show(screenPlanner);

  // Leaflet needs a size recalculation when a hidden container becomes visible.
  setTimeout(() => {
    try { map.invalidateSize(true); } catch { }
  }, 50);

  if (plannerBooted) return;
  plannerBooted = true;

  await loadPlaces();

  const days = Math.max(1, Math.min(14, parseInt(String(wizardState.days || 2), 10) || 2));
  const budgetText = wizardState.budget === 'budget' ? 'budget-friendly' : wizardState.budget === 'mid' ? 'moderate' : wizardState.budget === 'luxury' ? 'comfortable' : 'flexible';
  const groupText = wizardState.group || 'solo';

  const firstMsg =
    `Yes — I'd like a personalized plan for ${wizardState.destination || 'Kathmandu'}. ` +
    `I'm staying ${days} days. I'm traveling ${groupText}. ` +
    `My budget is ${budgetText}. ` +
    `Please keep it Kathmandu-only and help me plan day by day.`;

  // Start/continue a session and seed the context.
  const data = await apiChat({ session_id: sessionId || null, message: firstMsg });
  applyServerResponse(data);
  addMsg('assistant', data.message || data.reply);
}

function pinIcon(color, label, photoUrl = null) {
  const bg = color === 'green' ? '#10b981' : '#3b82f6';
  const text = String(label || '').slice(0, 2).toUpperCase();
  
  let html;
  if (photoUrl) {
    html = `
      <div style="
        width: 40px; height: 40px; border-radius: 999px;
        background-image: url('${photoUrl}');
        background-size: cover;
        background-position: center;
        border: 3px solid rgba(255,255,255,0.95);
        box-shadow: 0 6px 14px rgba(0,0,0,0.3);
        display: flex; align-items: center; justify-content: center;
        overflow: hidden;
      ">
        <div style="
          width: 100%; height: 100%;
          background: linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.3) 100%);
          display: flex; align-items: flex-end; justify-content: center;
          padding-bottom: 4px;
          font-weight: 700; color: white; font-size: 10px;
          text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        ">${text}</div>
      </div>
    `;
  } else {
    html = `
      <div style="
        width: 32px; height: 32px; border-radius: 999px;
        background: ${bg};
        border: 2px solid rgba(255,255,255,0.9);
        box-shadow: 0 6px 14px rgba(0,0,0,0.25);
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; color: white; font-size: 12px;
      ">${text}</div>
    `;
  }
  
  return L.divIcon({
    className: '',
    html,
    iconSize: photoUrl ? [40, 40] : [32, 32],
    iconAnchor: photoUrl ? [20, 20] : [16, 16],
    popupAnchor: [0, photoUrl ? -20 : -16]
  });
}

function _placeLatLng(place) {
  if (!place || typeof place !== 'object') return null;
  if (Number.isFinite(place.lat) && Number.isFinite(place.lng)) return [place.lat, place.lng];
  if (Array.isArray(place.coordinates) && place.coordinates.length === 2) {
    const lat = place.coordinates[0];
    const lng = place.coordinates[1];
    if (Number.isFinite(lat) && Number.isFinite(lng)) return [lat, lng];
  }
  return null;
}

function syncPinsFromTripState(tripState) {
  if (!tripState || typeof tripState !== 'object') return;

  const desired = new Set();

  const trip = tripState.trip;
  const days = trip && typeof trip === 'object' ? trip.days : null;
  if (Array.isArray(days)) {
    for (const d of days) {
      if (!d || typeof d !== 'object') continue;
      const visits = d.visits;
      if (!Array.isArray(visits)) continue;
      for (const pid of visits) {
        if (typeof pid !== 'string' || !pid) continue;
        desired.add(pid);
      }
    }
  }

  const hotel = tripState.hotel;
  if (hotel && typeof hotel === 'object' && hotel.coordinates && Array.isArray(hotel.coordinates) && hotel.coordinates.length === 2) {
    desired.add('hotel');
  }

  for (const id of Object.keys(mapPins)) {
    if (!desired.has(id)) {
      markerLayer.removeLayer(mapPins[id]);
      delete mapPins[id];
    }
  }

  for (const id of desired) {
    if (mapPins[id]) continue;

    if (id === 'hotel') {
      if (!(hotel && typeof hotel === 'object')) continue;
      const coords = hotel.coordinates;
      const lat = coords[0];
      const lng = coords[1];
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      executeCommands([
        { 'map.addPin': { id: 'hotel', lat, lng, type: 'hotel', label: hotel.name || 'Hotel' } }
      ]);
      continue;
    }

    const place = (placesIndex && placesIndex[id]) ? placesIndex[id] : null;
    const ll = _placeLatLng(place);
    if (!ll) continue;
    
    // Fetch place details with photos asynchronously
    fetchPlaceDetailsWithPhoto(id, place, ll[0], ll[1]);
  }
}

async function fetchPlaceDetailsWithPhoto(placeId, place, lat, lng) {
  try {
    const response = await fetch(`/api/place/details?place_id=${encodeURIComponent(placeId)}`);
    if (response.ok) {
      const data = await response.json();
      const photoUrl = (data.images && data.images.length > 0) ? data.images[0] : 
                       (data.foursquare && data.foursquare.photos && data.foursquare.photos.length > 0) ? data.foursquare.photos[0] : null;
      
      executeCommands([
        { 'map.addPin': { 
          id: placeId, 
          lat, 
          lng, 
          type: 'visit', 
          label: place && place.name_en ? place.name_en : placeId,
          photoUrl: photoUrl
        } }
      ]);
    } else {
      // Fallback without photo
      executeCommands([
        { 'map.addPin': { id: placeId, lat, lng, type: 'visit', label: place && place.name_en ? place.name_en : placeId } }
      ]);
    }
  } catch (error) {
    // Fallback without photo on error
    executeCommands([
      { 'map.addPin': { id: placeId, lat, lng, type: 'visit', label: place && place.name_en ? place.name_en : placeId } }
    ]);
  }
}

function bindWizardChoices() {
  if (!wizardOverlay) return;

  // Budget choices
  wizardOverlay.querySelectorAll('[data-budget]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const v = btn.getAttribute('data-budget') || 'flexible';
      wizardState.budget = v;
      wizardOverlay.querySelectorAll('[data-budget]').forEach((b) => b.classList.toggle('isActive', b === btn));
      updateWizardNextState();
    });
  });

  // Group choices
  wizardOverlay.querySelectorAll('[data-group]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const v = btn.getAttribute('data-group') || 'solo';
      wizardState.group = v;
      wizardOverlay.querySelectorAll('[data-group]').forEach((b) => b.classList.toggle('isActive', b === btn));
      updateWizardNextState();
    });
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
      const { id, lat, lng, label, type, photoUrl } = payload;
      if (!id || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      if (mapPins[id]) {
        markerLayer.removeLayer(mapPins[id]);
        delete mapPins[id];
      }
      const pinColor = type === 'hotel' ? 'green' : 'blue';
      const shortLabel = type === 'hotel' ? 'H' : 'V';
      
      // Create popup content with photo if available
      let popupContent = String(label || '');
      if (photoUrl) {
        popupContent = `
          <div style="text-align: center;">
            <img src="${photoUrl}" style="width: 200px; height: 150px; object-fit: cover; border-radius: 8px; margin-bottom: 8px;" />
            <div style="font-weight: 600; margin-top: 4px;">${label || ''}</div>
          </div>
        `;
      }
      
      const marker = L.marker([lat, lng], { icon: pinIcon(pinColor, shortLabel, photoUrl) }).addTo(markerLayer);
      marker.bindPopup(popupContent, { maxWidth: 250 });
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
      if (name === 'buildRoute' && btnRoute) {
        btnRoute.disabled = false;
        btnRoute.removeAttribute('disabled');
        btnRoute.style.cursor = 'pointer';
        btnRoute.style.pointerEvents = 'auto';
        btnRoute.style.opacity = '1';
      }
      // We no longer use a separate 'export' button; trip dates are enabled after planning.
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
        const wasNearBottom = isChatNearBottom();
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
        if (wasNearBottom) scrollChatToBottom();
        else updateChatScrollButton();
      }
      continue;
    }
  }
}

function addMsg(role, text) {
  if (!chatLog) return;
  const wasNearBottom = isChatNearBottom();
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.textContent = text;
  chatLog.appendChild(el);
  if (wasNearBottom) scrollChatToBottom();
  else updateChatScrollButton();
}

function showThinking() {
  if (!chatLog || thinkingEl) return;
  const wasNearBottom = isChatNearBottom();
  const el = document.createElement('div');
  el.className = 'msg assistant loading';
  el.textContent = 'NomadAI is thinking…';
  chatLog.appendChild(el);
  if (wasNearBottom) scrollChatToBottom();
  else updateChatScrollButton();
  thinkingEl = el;
}

function hideThinking() {
  if (thinkingEl && thinkingEl.parentNode) {
    thinkingEl.parentNode.removeChild(thinkingEl);
  }
  thinkingEl = null;
  updateChatScrollButton();
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
    return { ok: false };
  }
  const res = await fetch(`/api/export?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) {
    renderExportLinks({ ok: false });
    return { ok: false };
  }
  const data = await res.json();
  renderExportLinks(data);
  return data;
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

  const fitPoints = [];

  if (Array.isArray(mapActions.center) && mapActions.center.length === 2) {
    const z = Number.isFinite(mapActions.zoom) ? mapActions.zoom : map.getZoom();
    map.setView(mapActions.center, z, { animate: true });
  }

  if (Array.isArray(mapActions.routes)) {
    for (const r of mapActions.routes) {
      const pl = r.polyline;
      if (!Array.isArray(pl) || pl.length < 2) continue;
      L.polyline(pl, { color: '#ffd28a', weight: 4, opacity: 0.85 }).addTo(routeLayer);
      for (const pt of pl) {
        if (Array.isArray(pt) && pt.length === 2) fitPoints.push(pt);
      }
    }
  }

  if (fitPoints.length >= 2) {
    const bounds = L.latLngBounds(fitPoints.map(p => L.latLng(p[0], p[1])));
    try {
      map.fitBounds(bounds, { padding: [40, 40] });
    } catch {}
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
  syncPinsFromTripState(currentState);
}

async function sendUserMessage(text) {
  const msg = (text || '').trim();
  if (!msg) return;
  addMsg('user', msg);
  showThinking();
  try {
    const data = await apiChat({ session_id: sessionId || null, message: msg });
    applyServerResponse(data);
    addMsg('assistant', data.message || data.reply);
  } catch (error) {
    console.error('sendUserMessage error:', error);
    addMsg('assistant', 'Sorry — something went wrong while responding. Please try again.');
  } finally {
    hideThinking();
  }
}

async function selectPlace(place) {
  showThinking();
  try {
    const data = await apiChat({
      session_id: sessionId || null,
      message: '',
      map_event: { type: 'select_place', name: place.name, coordinates: place.coordinates }
    });
    addMsg('assistant', data.message || data.reply);
    applyServerResponse(data);
  } catch (error) {
    console.error('selectPlace error:', error);
    addMsg('assistant', 'Sorry — I could not add that place. Please try again.');
  } finally {
    hideThinking();
  }
}

async function setHotel(latlng) {
  showThinking();
  try {
    const data = await apiChat({
      session_id: sessionId || null,
      message: '',
      map_event: { type: 'set_hotel', name: 'Stay', coordinates: [latlng.lat, latlng.lng] }
    });
    addMsg('assistant', data.message || data.reply);
    applyServerResponse(data);
  } catch (error) {
    console.error('setHotel error:', error);
    addMsg('assistant', 'Sorry — I could not set that stay point. Please try again.');
  } finally {
    hideThinking();
  }
}

async function buildAndOpenRoutes() {
  if (btnRoute && btnRoute.disabled) return;
  showThinking();
  try {
    const data = await apiChat({
      session_id: sessionId || null,
      message: '',
      map_event: { type: 'create_route' }
    });
    addMsg('assistant', data.message || data.reply);
    applyServerResponse(data);
    const exportData = await exportToGoogleMaps();
    const links = exportData && Array.isArray(exportData.links) ? exportData.links : [];
    if (links.length > 0) {
      addMsg('assistant', 'Routes are ready. Use the Export section below to open each day in Google Maps.');
    }
  } catch (error) {
    console.error('buildAndOpenRoutes error:', error);
    addMsg('assistant', 'Sorry — I could not build or open the routes. Please confirm your days and try again.');
  } finally {
    hideThinking();
  }
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
  if (btnCalendar) btnCalendar.disabled = true;
  renderExportLinks({ ok: false });
  renderMapActions(null);
  renderSuggestions(null);
  // After reset, stay on planner screen and re-seed via wizard choices.
  plannerBooted = false;
  await bootPlannerWithWizardState();
}

function formatDateForGoogleCalendar(date) {
  // Format: YYYYMMDDTHHmmssZ (UTC)
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  const hours = String(date.getUTCHours()).padStart(2, '0');
  const minutes = String(date.getUTCMinutes()).padStart(2, '0');
  const seconds = String(date.getUTCSeconds()).padStart(2, '0');
  return `${year}${month}${day}T${hours}${minutes}${seconds}Z`;
}

function createGoogleCalendarLink(title, description, startDate, endDate, location) {
  const baseUrl = 'https://calendar.google.com/calendar/render';
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: title,
    dates: `${formatDateForGoogleCalendar(startDate)}/${formatDateForGoogleCalendar(endDate)}`,
    details: description,
    location: location || 'Kathmandu, Nepal',
    sf: 'true',
    output: 'xml'
  });
  return `${baseUrl}?${params.toString()}`;
}

async function showTripDates() {
  if (!currentPlan || !Array.isArray(currentPlan.days)) {
    addMsg('assistant', 'I need a saved plan first. Please finish planning, then try again.');
    return;
  }
  
  // Create a better date picker UI
  const input = window.prompt('When does your Kathmandu stay start? (YYYY-MM-DD)\n\nExample: 2026-03-15');
  if (!input) return;
  
  const start = new Date(input + 'T09:00:00'); // Default to 9 AM
  if (Number.isNaN(start.getTime())) {
    addMsg('assistant', 'That date did not look valid. Please use format YYYY-MM-DD.');
    return;
  }
  
  const calendarLinks = [];
  const lines = [];
  const daysArr = currentPlan.days.slice().sort((a, b) => (a.dayIndex || 0) - (b.dayIndex || 0));
  
  for (const day of daysArr) {
    const idx = day.dayIndex || 1;
    const dayDate = new Date(start.getTime());
    dayDate.setDate(dayDate.getDate() + (idx - 1));
    
    const y = dayDate.getFullYear();
    const m = String(dayDate.getMonth() + 1).padStart(2, '0');
    const dd = String(dayDate.getDate()).padStart(2, '0');
    const dateStr = `${y}-${m}-${dd}`;
    
    const visitIds = (day.visits || []).slice(0, 2);
    const names = [];
    const locations = [];
    
    // Add hotel as starting point
    names.push('Hotel / Stay');
    
    // Add visit places
    for (const pid of visitIds) {
      const p = placesIndex[pid];
      if (p && p.name_en) {
        names.push(p.name_en);
        locations.push(p.name_en);
      }
    }
    
    const dayTitle = `Day ${idx}: ${names.slice(1).join(' → ')}`;
    const dayDescription = `Kathmandu Trip - Day ${idx}\n\nPlaces to visit:\n${names.map((n, i) => `${i + 1}. ${n}`).join('\n')}\n\n${currentPlan.days[idx - 1]?.cost_npr ? `Estimated cost: NPR ${currentPlan.days[idx - 1].cost_npr.min || 0}-${currentPlan.days[idx - 1].cost_npr.max || 0}` : ''}`;
    
    // Create start and end times for the day (9 AM to 6 PM)
    const dayStart = new Date(dayDate);
    dayStart.setHours(9, 0, 0, 0);
    const dayEnd = new Date(dayDate);
    dayEnd.setHours(18, 0, 0, 0);
    
    const calendarLink = createGoogleCalendarLink(
      dayTitle,
      dayDescription,
      dayStart,
      dayEnd,
      locations.join(', ') || 'Kathmandu, Nepal'
    );
    
    calendarLinks.push({
      day: idx,
      date: dateStr,
      title: dayTitle,
      link: calendarLink,
      places: names
    });
    
    lines.push(`Day ${idx} (${dateStr}): ${names.join(' → ')}`);
  }
  
  // Display calendar summary
  addMsg('assistant', `📅 Trip Calendar for Kathmandu:\n\n${lines.join('\n')}\n\nClick the links below to add each day to your Google Calendar:`);
  
  // Create clickable calendar links
  const calendarDiv = document.createElement('div');
  calendarDiv.className = 'msg assistant';
  calendarDiv.style.cssText = 'margin-top: 12px; padding: 12px; background: #f8f9fa; border-radius: 8px;';
  
  for (const item of calendarLinks) {
    const linkEl = document.createElement('a');
    linkEl.href = item.link;
    linkEl.target = '_blank';
    linkEl.rel = 'noreferrer';
    linkEl.className = 'exportLink';
    linkEl.style.cssText = 'display: block; margin-bottom: 8px; padding: 8px; background: white; border-radius: 4px; text-decoration: none; color: #6366f1; font-weight: 500;';
    linkEl.textContent = `📅 Add Day ${item.day} (${item.date}) to Google Calendar`;
    linkEl.addEventListener('click', (e) => {
      e.preventDefault();
      window.open(item.link, '_blank', 'noreferrer');
    });
    calendarDiv.appendChild(linkEl);
  }
  
  chatLog.appendChild(calendarDiv);
  if (isChatNearBottom()) scrollChatToBottom();
  else updateChatScrollButton();
  
  // Also create a combined calendar link for the entire trip
  if (calendarLinks.length > 0) {
    const firstDay = new Date(start);
    firstDay.setHours(9, 0, 0, 0);
    const lastDay = new Date(start);
    lastDay.setDate(lastDay.getDate() + (daysArr.length - 1));
    lastDay.setHours(18, 0, 0, 0);
    
    const allDaysLink = createGoogleCalendarLink(
      `Kathmandu Trip - ${daysArr.length} Days`,
      `Complete itinerary for ${daysArr.length} days in Kathmandu.\n\n${lines.join('\n')}`,
      firstDay,
      lastDay,
      'Kathmandu, Nepal'
    );

    const allDaysLinkEl = document.createElement('a');
    allDaysLinkEl.href = allDaysLink;
    allDaysLinkEl.target = '_blank';
    allDaysLinkEl.rel = 'noreferrer';
    allDaysLinkEl.className = 'exportLink';
    allDaysLinkEl.style.cssText = 'display: block; margin-top: 8px; padding: 10px; background: #6366f1; color: white; border-radius: 4px; text-decoration: none; font-weight: 600; text-align: center;';
    allDaysLinkEl.textContent = '📅 Add Entire Trip to Google Calendar';
    allDaysLinkEl.addEventListener('click', (e) => {
      e.preventDefault();
      window.open(allDaysLink, '_blank', 'noreferrer');
    });
    calendarDiv.appendChild(allDaysLinkEl);
  }
}

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = (chatInput.value || '').trim();
  if (!text) return;
  chatInput.value = '';

  await sendUserMessage(text);
});

if (btnRoute) btnRoute.addEventListener('click', buildAndOpenRoutes);
if (btnReset) btnReset.addEventListener('click', resetSession);
if (btnCalendar) btnCalendar.addEventListener('click', showTripDates);

map.on('contextmenu', async (e) => {
  try {
    if (e && e.originalEvent && typeof e.originalEvent.preventDefault === 'function') {
      e.originalEvent.preventDefault();
    }
  } catch {}
  addMsg('assistant', 'Setting your stay point here. (Tip: right-click anywhere to change it.)');
  if (e && e.latlng) {
    await setHotel(e.latlng);
  }
});

bindWizardChoices();

if (btnStartPlanning) btnStartPlanning.addEventListener('click', openWizard);
if (btnCreateTrip) btnCreateTrip.addEventListener('click', openWizard);

if (wizBack) {
  wizBack.addEventListener('click', () => {
    setWizardStep(Math.max(1, wizardState.step - 1));
  });
}

if (wizNext) {
  wizNext.addEventListener('click', async () => {
    if (wizardState.step === 1) {
      wizardState.destination = (wizDestination && wizDestination.value) ? wizDestination.value : 'Kathmandu, Nepal';
      wizardState.days = (wizDays && wizDays.value) ? parseInt(String(wizDays.value), 10) : 2;
      setWizardStep(2);
      return;
    }
    if (wizardState.step === 2) {
      setWizardStep(3);
      return;
    }

    if (wizNext) {
      wizNext.disabled = true;
      wizNext.textContent = 'Generating…';
    }
    if (wizBack) wizBack.disabled = true;

    closeWizard();
    await fetchPlan();
    await loadPlaces();
    await showResults();

    if (wizNext) {
      wizNext.textContent = 'Generate Plan ✓';
    }
  });
}

if (wizDays) {
  wizDays.addEventListener('input', () => {
    wizardState.days = parseInt(String(wizDays.value || '2'), 10) || 2;
    updateWizardNextState();
  });
}

// Initial screen
show(screenLanding);
hide(screenPlanner);
hide(screenResults);

if (btnPersonalizedGuide) {
  btnPersonalizedGuide.addEventListener('click', async () => {
    await bootPlannerAsPersonalizedGuide();
  });
}

if (btnEditChoices) {
  btnEditChoices.addEventListener('click', () => {
    openWizard();
  });
}

// Place search functionality
let searchTimeout = null;
if (placeSearch) {
  placeSearch.addEventListener('input', async (e) => {
    const query = e.target.value.trim();
    
    clearTimeout(searchTimeout);
    
    if (query.length < 2) {
      searchResults.style.display = 'none';
      return;
    }
    
    searchTimeout = setTimeout(async () => {
      try {
        const center = map.getCenter();
        const response = await fetch(`/api/places/search?q=${encodeURIComponent(query)}&lat=${center.lat}&lng=${center.lng}`);
        if (response.ok) {
          const data = await response.json();
          displaySearchResults(data.results || []);
        }
      } catch (error) {
        console.error('Search error:', error);
      }
    }, 300);
  });
  
  // Hide search results when clicking outside
  document.addEventListener('click', (e) => {
    if (!placeSearch.contains(e.target) && !searchResults.contains(e.target)) {
      searchResults.style.display = 'none';
    }
  });
}

function displaySearchResults(results) {
  if (!searchResults) return;
  
  searchResults.innerHTML = '';
  
  if (results.length === 0) {
    searchResults.innerHTML = '<div style="padding: 12px; color: #666; text-align: center;">No places found</div>';
    searchResults.style.display = 'block';
    return;
  }
  
  for (const place of results.slice(0, 5)) {
    const item = document.createElement('div');
    item.style.cssText = 'padding: 12px; cursor: pointer; border-bottom: 1px solid rgba(0,0,0,0.05); transition: background 0.2s;';
    
    item.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 4px;">${place.name || 'Unknown'}</div>
      <div style="font-size: 12px; color: #666;">${place.address || ''}</div>
      ${place.rating ? `<div style="font-size: 11px; color: #888; margin-top: 4px;">⭐ ${place.rating.toFixed(1)}</div>` : ''}
    `;
    
    item.addEventListener('mouseenter', () => {
      item.style.background = '#f5f5f5';
    });
    
    item.addEventListener('mouseleave', () => {
      item.style.background = 'white';
    });
    
    item.addEventListener('click', async () => {
      if (place.lat && place.lng) {
        map.setView([place.lat, place.lng], 15, { animate: true });
        await selectPlace({
          name: place.name || 'Place',
          coordinates: [place.lat, place.lng]
        });
      }
      placeSearch.value = '';
      searchResults.style.display = 'none';
    });
    
    searchResults.appendChild(item);
  }
  
  searchResults.style.display = 'block';
}
