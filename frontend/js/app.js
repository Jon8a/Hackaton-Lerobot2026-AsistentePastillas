// Punto de entrada: cabecera, pestañas, atajos de teclado y sondeo del robot.
import { api } from './api.js';
import { store, subscribe, emit, refresh, currentMoment, residentById } from './store.js';
import { esc, toast, onAction, onChange, installDelegation } from './ui.js';
import { voiceEnabled, toggleVoice } from './voice.js';
import { renderPanel } from './views/panel.js';
import { renderHistory } from './views/history.js';
import { renderSettings } from './views/settings.js';
import {
  modal, renderModal, openServe, startServe, stopRobot, closeModal, isRunning, attachToJob, toggleLog,
} from './views/serve.js';

const VIEWS = {
  panel: { label: 'Residentes', render: renderPanel },
  history: { label: 'Historial', render: renderHistory },
  settings: { label: 'Ajustes', render: renderSettings },
};

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------------ render
function renderMoments() {
  const s = store.state;
  const cur = currentMoment();
  $('moments').innerHTML = s.moments.map((m) => `
    <button class="moment-chip ${m.id === cur ? 'on' : ''}" data-action="moment" data-moment="${m.id}"
            title="${m.id === s.current_moment ? 'Toma de ahora' : 'Ver esta toma'}">
      ${m.icon} ${esc(m.label)} ${m.id === s.current_moment ? '<span class="auto-dot"></span>' : ''}
    </button>`).join('');
}

function renderTabs() {
  $('tabs').innerHTML = Object.entries(VIEWS).map(([id, v]) => `
    <button class="tab ${store.view === id ? 'on' : ''}" data-action="view" data-view="${id}">${v.label}</button>`).join('');
}

function renderStatus() {
  const h = store.health;
  const el = $('robot-status');
  let cls = 'off', text = 'Sin servidor';
  if (h?.ok) {
    if (h.busy) { cls = 'busy'; text = 'Robot trabajando'; }
    else if (h.simulate) { cls = 'sim'; text = 'Simulación'; }
    else if (!h.lerobot_found) { cls = 'off'; text = 'Falta lerobot'; }
    else { cls = 'ok'; text = 'Robot listo'; }
  }
  el.className = `robot-status ${cls}`;
  el.textContent = text;
  $('voice-btn').classList.toggle('off', !voiceEnabled());
}

function render() {
  renderStatus();
  if (!store.state) {
    $('view').innerHTML = `<div class="loading">${store.loadError
      ? `No puedo hablar con el servidor (${esc(store.loadError)}).<br>¿Está arrancado <code>python server.py</code>?`
      : 'Cargando…'}</div>`;
    return;
  }
  renderMoments();
  renderTabs();
  $('view').innerHTML = VIEWS[store.view].render();
  $('modal-root').innerHTML = renderModal();
}

subscribe(render);

// ----------------------------------------------------------------- acciones
onAction({
  view: (d) => { store.view = d.view; emit(); },
  moment: (d) => {
    store.momentOverride = d.moment === store.state.current_moment ? null : d.moment;
    emit();
  },
  serve: (d) => openServe(d.id, currentMoment()),
  start: () => startServe(),
  stop: () => stopRobot(),
  close: () => closeModal(),
  backdrop: (_d, el, e) => { if (e.target === el) closeModal(); },
  toggleLog: () => toggleLog(),
  voice: () => { toast(toggleVoice() ? 'Voz activada' : 'Voz desactivada'); renderStatus(); },
  refill: async (d) => {
    const p = store.state.pills.find((x) => x.key === d.key);
    await save(() => api.setStock(d.key, p.capacity), `${p.name} rellenado`);
  },
  reset: async (d) => {
    const msg = d.scope === 'all'
      ? '¿Volver a los datos de demo? Se borra TODO el historial y las pautas cambiadas.'
      : '¿Borrar lo servido hoy y rellenar los cuencos?';
    if (!confirm(msg)) return;
    await save(() => api.reset(d.scope), 'Listo');
  },
});

onChange({
  stock: (d, el) => save(() => api.setStock(d.key, Number(el.value) || 0)),
  schedule: (d, el) => {
    const r = residentById(d.resident);
    const schedule = structuredClone(r.schedule);
    schedule[d.moment] = { ...(schedule[d.moment] || {}), [d.key]: Math.max(0, Number(el.value) || 0) };
    save(() => api.setSchedule(r.id, schedule), 'Pauta guardada');
  },
});

async function save(fn, okMsg) {
  try {
    await fn();
    if (okMsg) toast(okMsg);
  } catch (e) {
    toast(e.message, 'err', 5000);
  }
  await refresh();
}

// ------------------------------------------------------------------ teclado
document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea, select')) return;

  // Espacio = parada de emergencia, haya ventana abierta o no
  if (e.code === 'Space') {
    if (isRunning() || store.health?.busy) { e.preventDefault(); stopRobot(); }
    return;
  }
  if (modal.open) {
    if (e.key === 'Enter' && modal.phase === 'confirm') { e.preventDefault(); startServe(); }
    if (e.key === 'Escape' || (e.key === 'Enter' && modal.phase === 'finished')) { e.preventDefault(); closeModal(); }
    return;
  }
  if (store.state && store.view === 'panel' && /^[1-9]$/.test(e.key)) {
    const r = store.state.residents[Number(e.key) - 1];
    if (r) openServe(r.id, currentMoment());
  }
});

// --------------------------------------------------------- reloj y sondeo
function tickClock() {
  $('clock').textContent = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

async function pollHealth() {
  const wasOk = store.health?.ok;
  try {
    store.health = await api.health();
  } catch {
    store.health = { ok: false };
  }
  if (store.health.ok && !wasOk) await refresh();               // el servidor ha vuelto
  if (store.health.active_job && !modal.open && store.state) attachToJob(store.health.active_job);
  renderStatus();
}

let lastMoment = null;
async function periodicRefresh() {
  // refresca de vez en cuando (por si cambia la toma con la hora), sin molestar mientras se edita
  if (store.view === 'settings' || isRunning()) return;
  await refresh();
  if (lastMoment && store.state && lastMoment !== store.state.current_moment) {
    store.momentOverride = null;
    toast(`Ahora toca: ${store.state.moments.find((m) => m.id === store.state.current_moment).label}`);
    emit();
  }
  lastMoment = store.state?.current_moment;
}

// ------------------------------------------------------------------ inicio
installDelegation();
tickClock();
setInterval(tickClock, 1000);
await pollHealth();
await refresh();
lastMoment = store.state?.current_moment;
setInterval(pollHealth, 2000);
setInterval(periodicRefresh, 30000);
