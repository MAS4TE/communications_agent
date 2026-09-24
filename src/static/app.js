// ── SLIDER DATA ──
const PREF_STEPS = [
  { label: 'Profit', color: '#eef1f0' },
  { label: 'Green',  color: '#39e07a' },
];
const EXPERTISE_STEPS = [
  { label: 'Beginner',     color: '#7ceaa3' },
  { label: 'Intermediate', color: '#39e07a' },
  { label: 'Expert',       color: '#1f8f52' },
];
const BORDER_STEPS = [
  { label: 'Community', color: '#7ceaa3' },
  { label: 'Country',   color: '#39e07a' },
  { label: 'All',       color: '#1f8f52' },
];
const RISK_STEPS = [
  { label: 'Low',     color: '#eef1f0' },
  { label: 'Medium',  color: '#39e07a' },
  { label: 'High',    color: '#ef4444' },
];

// ── LANGUAGE PICKER ──
const LANGUAGES = [
  { code: 'en', label: 'EN' },
  { code: 'nl', label: 'NL' },
  { code: 'fr', label: 'FR' },
  { code: 'de', label: 'DE' },
];
let currentLang = localStorage.getItem('mas4te_lang') || 'en';

function initLangPicker() {
  const container = document.getElementById('lang-picker');
  container.innerHTML = '';
  LANGUAGES.forEach(lang => {
    const btn = document.createElement('button');
    btn.className = 'lang-btn' + (lang.code === currentLang ? ' active' : '');
    btn.textContent = lang.label;
    btn.onclick = () => setLanguage(lang.code);
    container.appendChild(btn);
  });
}

function setLanguage(code) {
  currentLang = code;
  localStorage.setItem('mas4te_lang', code);
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent === code.toUpperCase());
  });
  // TODO: apply translations here in step 2, and pass currentLang to /chat in step 3
}

let prefValue      = 0;
let expertiseValue = 0;
let borderValue    = 2;
let batteryReserve = 20;
let batteryCapacityKwh = null;
let riskValue = 0;

// ── STEP SLIDER BUILDER ──
function buildSlider(dotsId, labelsId, fillId, rangeId, steps, getValue, setValue) {
  const dotsEl   = document.getElementById(dotsId);
  const labelsEl = document.getElementById(labelsId);
  const rangeEl  = document.getElementById(rangeId);
  if (!dotsEl || !labelsEl || !rangeEl) return;

  dotsEl.innerHTML = '';
  steps.forEach((_, i) => {
    const dot = document.createElement('div');
    dot.className = 'step-dot';
    dot.onclick = () => { setValue(i); refresh(); };
    dotsEl.appendChild(dot);
  });

  labelsEl.innerHTML = '';
  steps.forEach((s, i) => {
    const lbl = document.createElement('div');
    lbl.className = 'step-label';
    lbl.textContent = s.label;
    lbl.onclick = () => { setValue(i); refresh(); };
    labelsEl.appendChild(lbl);
  });

  rangeEl.oninput = () => { setValue(parseInt(rangeEl.value)); refresh(); };

  function refresh() {
    const v = getValue();
    const color = steps[v].color;
    const maxIdx = steps.length - 1;
    document.getElementById(fillId).style.width = maxIdx ? `${(v/maxIdx)*100}%` : '0%';
    document.getElementById(fillId).style.background = color;
    dotsEl.querySelectorAll('.step-dot').forEach((d, i) => {
      d.classList.toggle('active', i === v);
      d.style.background  = i === v ? color : '';
      d.style.borderColor = i === v ? color : '';
    });
    labelsEl.querySelectorAll('.step-label').forEach((l, i) => {
      l.classList.toggle('active', i === v);
      l.style.color = i === v ? color : '';
    });
    rangeEl.value = v;
    toggleRiskVisibility();
  }

  refresh();
}

// ── BATTERY RESERVE SLIDER ──
function initBatteryReserveSlider() {
  const rangeEl = document.getElementById('reserve-range');
  rangeEl.oninput = () => {
    batteryReserve = parseInt(rangeEl.value);
    refreshReserve();
  };
  refreshReserve();
}

function refreshReserve() {
  const keep  = batteryReserve;
  const trade = 100 - keep;

  document.getElementById('reserve-keep-pct').textContent  = keep  + '%';
  document.getElementById('reserve-trade-pct').textContent = trade + '%';

  document.getElementById('reserve-keep-fill').style.width  = keep  + '%';
  document.getElementById('reserve-trade-fill').style.left  = keep  + '%';
  document.getElementById('reserve-trade-fill').style.width = trade + '%';
  document.getElementById('reserve-thumb').style.left       = keep  + '%';

  const keepFill  = document.getElementById('reserve-keep-fill');
  const tradeFill = document.getElementById('reserve-trade-fill');
  keepFill.style.borderRadius  = keep  === 100 ? '6px' : '6px 0 0 6px';
  tradeFill.style.borderRadius = trade === 100 ? '6px' : '0 6px 6px 0';
  tradeFill.style.display      = trade === 0 ? 'none' : 'block';
  keepFill.style.display       = keep  === 0 ? 'none' : 'block';

  if (batteryCapacityKwh) {
    const keepKwh  = ((keep  / 100) * batteryCapacityKwh).toFixed(1);
    const tradeKwh = ((trade / 100) * batteryCapacityKwh).toFixed(1);
    document.getElementById('reserve-keep-kwh').textContent  = keepKwh;
    document.getElementById('reserve-trade-kwh').textContent = tradeKwh;
  }
}

function toggleRiskVisibility() {
  const isGreen = prefValue === 1;
  document.getElementById('risk-range').disabled = isGreen;
  document.getElementById('risk-section').style.opacity = isGreen ? '0.45' : '1';
  document.getElementById('risk-section').style.pointerEvents = isGreen ? 'none' : 'auto';
  document.getElementById('risk-green-note').style.display = isGreen ? 'flex' : 'none';
}

function initSliders() {
  buildSlider('pref-dots','pref-labels','pref-fill','pref-range', PREF_STEPS, ()=>prefValue, v=>{prefValue=v;});
  buildSlider('expertise-dots','expertise-labels','expertise-fill','expertise-range', EXPERTISE_STEPS, ()=>expertiseValue, v=>{expertiseValue=v;});
  buildSlider('border-dots','border-labels','border-fill','border-range', BORDER_STEPS, ()=>borderValue, v=>{borderValue=v;});
  buildSlider('risk-dots','risk-labels','risk-fill','risk-range', RISK_STEPS, ()=>riskValue, v=>{riskValue=v;});
  initBatteryReserveSlider();
}

// ── TABS ──
function switchTab(tab) {
  document.getElementById('panel-prefs').style.display   = tab==='prefs'   ? 'flex' : 'none';
  document.getElementById('panel-profile').style.display = tab==='profile' ? 'flex' : 'none';
  document.getElementById('tab-prefs').classList.toggle('active',   tab==='prefs');
  document.getElementById('tab-profile').classList.toggle('active', tab==='profile');
}

// ── PROFILE ──
async function loadProfile() {
  try {
    const res = await fetch('/prosumer/profile');
    const d = await res.json();
    if (d.people != null) document.getElementById('profile-people').textContent = d.people;
    setBadge('profile-ev',       d.electric_car);
    setBadge('profile-heatpump', d.heat_pump);
    setBadge('profile-solar',    d.solar_panels);
    setBadge('profile-water',    d.electric_water_heating);
    setBadge('profile-battery',  d.home_battery);
    if (d.location) {
      const locEl = document.getElementById('profile-location');
      locEl.textContent = d.location;
      locEl.style.background = 'var(--surface-2)';
      locEl.style.color = 'var(--text)';
      locEl.style.border = '1px solid var(--border)';
    }

    if (d.home_battery) {
      document.getElementById('battery-reserve-section').style.display = 'block';
      if (d.battery_capacity_kwh != null) {
        batteryCapacityKwh = d.battery_capacity_kwh;
        document.getElementById('reserve-capacity-label').textContent = d.battery_capacity_kwh + ' kWh';
        document.getElementById('reserve-kwh-row').style.display = 'block';
        document.getElementById('profile-battery-capacity-row').style.display = 'flex';
        document.getElementById('profile-battery-capacity').textContent = d.battery_capacity_kwh + ' kWh';
      }
      refreshReserve();
    }

    // Solar chart only if the profile has panels; battery SoC group only
    // if it has a battery. Trade summary always shows.
    const hasBattery = !!d.home_battery;
    const hasSolar   = !!d.solar_panels;
    document.getElementById('battery-soc-group').style.display = hasBattery ? 'block' : 'none';
    document.getElementById('solar-card').style.display = hasSolar ? 'flex' : 'none';
  }
  catch(e) {
    document.getElementById('battery-reserve-section').style.display = 'block';
    refreshReserve();
    document.getElementById('battery-soc-group').style.display = 'none';
    document.getElementById('solar-card').style.display = 'none';
  }
}

function setBadge(id, val) {
  if (val == null) return;
  const el = document.getElementById(id);
  el.dataset.value = val ? 'true' : 'false';
  el.textContent = val ? 'Yes' : 'No';
}

// ── CYCLE STEPPER ──
// PipelineStatus is shared between bidding and clearing and resets on
// each run, so we infer the overall phase from which step-name-shape
// (bidding vs clearing) the snapshot currently shows.
const CYCLE_PHASES = [
  { key: 'forecasting', label: 'Preparing bids',
    steps: ['retrieve_profile','retrieve_preferences','retrieve_market_info',
            'forecast_demand','forecast_solar','forecast_prices'] },
  { key: 'deciding',    label: 'Deciding bid',
    steps: ['reason_volume_range','battery_utility'] },
  { key: 'submitted',   label: 'Waiting on market decision',
    steps: ['make_orderbook','publish_bid'] },
  { key: 'cleared',     label: 'Market decision received',
    steps: ['retrieve_clearing_info','publish_battery_schedule'] },
];

let CURRENT_PHASE = -1;
let CYCLE_STATUS_TEXT = 'Waiting for market to open';

function computeCyclePhase(snapshot) {
  const steps = snapshot.steps || [];
  const isClearingShape = steps.includes('retrieve_clearing_info');

  if (steps.length === 0) {
    return { phase: -1, text: snapshot.message || 'Waiting for market to open' };
  }

  if (isClearingShape) {
    if (snapshot.status === 'done') {
      return { phase: 3, text: snapshot.message || 'Trade cleared — waiting for next market' };
    }
    return { phase: 3, text: snapshot.current ? `Clearing — ${snapshot.current}` : 'Clearing…' };
  }

  if (snapshot.status === 'done') {
    return { phase: 2, text: 'Bid submitted — waiting for clearing' };
  }
  if (snapshot.status === 'failed') {
    return { phase: -1, text: snapshot.message || 'Pipeline failed' };
  }

  const seen = Object.keys(snapshot.done || {});
  if (snapshot.current) seen.push(snapshot.current);
  let phase = 0;
  for (let i = 0; i < 3; i++) {
    if (CYCLE_PHASES[i].steps.some(s => seen.includes(s))) phase = i;
  }
  return { phase, text: snapshot.current ? `Running — ${snapshot.current}` : 'Working…' };
}

function renderCycleStepper() {
  const container = document.getElementById('cycle-steps');
  container.querySelectorAll('.cycle-step').forEach(el => el.remove());

  CYCLE_PHASES.forEach((phase, i) => {
    const step = document.createElement('div');
    step.className = 'cycle-step';

    const dot = document.createElement('div');
    dot.className = 'cycle-step-dot';
    if (i < CURRENT_PHASE) { dot.classList.add('done'); dot.textContent = '✓'; }
    else if (i === CURRENT_PHASE) { dot.classList.add('active'); dot.textContent = (i + 1); }
    else { dot.textContent = (i + 1); }

    const label = document.createElement('div');
    label.className = 'cycle-step-label';
    if (i < CURRENT_PHASE) label.classList.add('done');
    if (i === CURRENT_PHASE) label.classList.add('active');
    label.textContent = phase.label;

    step.appendChild(dot);
    step.appendChild(label);
    container.appendChild(step);
  });

  const pct = CURRENT_PHASE >= 0
    ? (CURRENT_PHASE / (CYCLE_PHASES.length - 1)) * 100
    : 0;
  document.getElementById('cycle-track-fill').style.width =
    `calc(${pct}% * (100% - 44px) / 100%)`;

  document.getElementById('cycle-status-text').textContent = CYCLE_STATUS_TEXT;
}

async function pollCycleStatus() {
  try {
    const res = await fetch('/pipeline/status');
    const snapshot = await res.json();
    const result = computeCyclePhase(snapshot);
    CURRENT_PHASE = result.phase;
    CYCLE_STATUS_TEXT = result.text;
  } catch (e) {
    CYCLE_STATUS_TEXT = 'Status unavailable';
  }
  renderCycleStepper();
}

function startCycleStatusPolling() {
  pollCycleStatus();
  setInterval(pollCycleStatus, 5000);
}

// ── SOLAR/DEMAND 7-DAY CHART ──
let CHART_DAYS = [];
let DEMAND_KWH = [];
let SOLAR_KWH  = [];

async function fetchEnergyWeek() {
  try {
    const res = await fetch('/prosumer/energy-week');
    const d = await res.json();

    CHART_DAYS = d.days || [];
    DEMAND_KWH = d.demand_kwh || [];
    SOLAR_KWH  = d.solar_kwh || [];

    const rangeEl = document.getElementById('solar-date-range');
    if (d.period_start && d.period_end) {
      rangeEl.textContent = `${d.period_start} to ${d.period_end}`;
    } else {
      rangeEl.textContent = 'previous 7 days';
    }
  } catch (e) {
    CHART_DAYS = []; DEMAND_KWH = []; SOLAR_KWH = [];
  }
  renderSolarChart();
}

function startEnergyWeekPolling() {
  fetchEnergyWeek();
  setInterval(fetchEnergyWeek, 15000);
}

function renderSolarChart() {
  const svg = document.getElementById('solar-chart-svg');
  if (CHART_DAYS.length === 0) { svg.innerHTML = ''; return; }
  const W = 560, H = 120, padTop = 10, padBottom = 24, padSide = 8, padLeft = 44;
  const chartH = H - padTop - padBottom;
  const maxVal = Math.max(...DEMAND_KWH, ...SOLAR_KWH) * 1.1;
  const groupW = (W - padLeft - padSide) / CHART_DAYS.length;
  const barW = groupW * 0.32;

  let svgContent = '';

  // Y-axis gridlines and labels
  const ticks = [0, maxVal / 2, maxVal];
  ticks.forEach(t => {
    const y = padTop + chartH - (t / maxVal) * chartH;
    svgContent += `<line x1="${padLeft}" y1="${y}" x2="${W - padSide}" y2="${y}" stroke="#262e29" stroke-width="1"/>`;
    svgContent += `<text x="2" y="${y - 3}" font-size="9" fill="#5b6560" font-family="DM Sans, sans-serif">${t.toFixed(1)} kWh</text>`;
  });

  // Bars and day labels
  CHART_DAYS.forEach((day, i) => {
    const groupX = padLeft + i * groupW + groupW / 2;
    const demandH = (DEMAND_KWH[i] / maxVal) * chartH;
    const solarH  = (SOLAR_KWH[i]  / maxVal) * chartH;

    svgContent += `<rect x="${groupX - barW - 3}" y="${padTop + chartH - demandH}" width="${barW}" height="${demandH}" fill="#eef1f0" rx="2"/>`;
    svgContent += `<rect x="${groupX + 3}" y="${padTop + chartH - solarH}" width="${barW}" height="${solarH}" fill="#39e07a" rx="2"/>`;
    svgContent += `<text x="${groupX}" y="${H - 6}" text-anchor="middle" font-size="11" fill="#5b6560" font-family="DM Sans, sans-serif">${day}</text>`;
  });

  svg.innerHTML = svgContent;
}
// ── TRADE SUMMARY ──
let lastTradeSummaryJSON = null;

async function checkTradeSummary() {
  try {
    const res = await fetch('/prosumer/last-trade-summary');
    const d = await res.json();
    const json = JSON.stringify(d);

    const roleWord = d.traded ? (d.role === 'seller' ? 'sold' : 'bought') : 'no trade last week';
    document.getElementById('trade-summary-role').textContent =
      d.traded ? `Trading — ${roleWord}` : 'Trading — no trade last week';

    document.getElementById('trade-stat-volume').textContent =
      d.traded ? `${d.volume_kwh} kWh` : '0 kWh';
    document.getElementById('trade-stat-total').textContent =
      (d.traded && d.clearing_price_per_kwh != null)
        ? `€${(d.volume_kwh * d.clearing_price_per_kwh).toFixed(2)}`
        : '€0.00';

    document.getElementById('battery-kept-sub').textContent =
      (d.traded && d.battery_kept_pct != null) ? `Battery kept: ${d.battery_kept_pct}%` : '';

    const cum = d.cumulative || { volume_kwh: 0, total_eur: 0 };
    document.getElementById('trade-stat-cum-volume').textContent = `${cum.volume_kwh.toFixed(1)} kWh`;
    document.getElementById('trade-stat-cum-total').textContent = `€${cum.total_eur.toFixed(2)}`;

    if (lastTradeSummaryJSON !== null && json !== lastTradeSummaryJSON) {
      fetchEnergyWeek();
    }
    lastTradeSummaryJSON = json;
  } catch (e) { /* leave things as they were */ }
}

function startTradeSummaryPolling() {
  checkTradeSummary();
  setInterval(checkTradeSummary, 20000);
}

// ── SAVE ──
async function savePreferences() {
  const note = document.getElementById('save-note');
  try {
    const res = await fetch('/prosumer/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trading_preference:   PREF_STEPS[prefValue].label,
        battery_tradeable_pct: 100 - batteryReserve,
        expertise:            EXPERTISE_STEPS[expertiseValue].label,
        trading_scope:        BORDER_STEPS[borderValue].label,
        risk_tolerance:       RISK_STEPS[riskValue].label,
      })
    });
    if (!res.ok) throw new Error();
    note.textContent = '✓ Preferences saved!';
    note.style.color = 'var(--primary)';
  } catch(e) {
    note.textContent = '✗ Failed to save, try again';
    note.style.color = 'var(--danger)';
  }
  note.classList.add('show');
  setTimeout(() => note.classList.remove('show'), 2200);
}

// ── INIT ──
window.onload = function() {
  initSliders();
  initLangPicker();
  startEnergyWeekPolling();
  loadProfile();
  startTradeSummaryPolling();
  startCycleStatusPolling();
  document.getElementById('chat-box').innerHTML = `
    <div class="message assistant-message">
      Hello! I'm your MAS4TE Assistant. You can ask me about your energy consumption or actions on the market.
    </div>`;
};

// ── CHAT ──
async function sendMessage() {
  const input = document.getElementById('user-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  const chatBox = document.getElementById('chat-box');
  chatBox.innerHTML += `<div class="message user-message">${escapeHTML(msg)}</div>`;
  chatBox.innerHTML += `<div id="typing-indicator" class="message assistant-message">Thinking…</div>`;
  chatBox.scrollTop = chatBox.scrollHeight;
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        preferences: {
          trading_preference:    PREF_STEPS[prefValue].label,
          battery_tradeable_pct: 100 - batteryReserve,
          expertise:             EXPERTISE_STEPS[expertiseValue].label,
          trading_scope:         BORDER_STEPS[borderValue].label,
          risk_tolerance:        RISK_STEPS[riskValue].label,
        }
      })
    });
    const data = await res.json();
    document.getElementById('typing-indicator').remove();
    chatBox.innerHTML += `<div class="message assistant-message">${escapeHTML(data.response)}</div>`;
  } catch(e) {
    document.getElementById('typing-indicator').remove();
    chatBox.innerHTML += `<div class="message assistant-message">Sorry, there was an error. Please try again.</div>`;
  }
  chatBox.scrollTop = chatBox.scrollHeight;
}

function escapeHTML(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}