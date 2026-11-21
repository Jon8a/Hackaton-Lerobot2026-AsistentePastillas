// Pantalla principal: los residentes y lo que les toca en la toma actual.
import { store, currentMoment, momentInfo, groupPicks } from '../store.js';
import { esc, pillIcon, avatar } from '../ui.js';

const BADGE = {
  pending: () => `<span class="badge pending">Pendiente</span>`,
  missed: () => `<span class="badge missed">Sin dar</span>`,
  failed: () => `<span class="badge failed">Incompleto</span>`,
  none: () => `<span class="badge none">Nada en esta toma</span>`,
  done: (st) => `<span class="badge ok">✓ Servido ${esc(st.time)}</span>`,
};

function actionButton(r, st) {
  switch (st.state) {
    case 'none': return '';
    case 'done': return `<button class="btn ghost" data-action="serve" data-id="${r.id}">Repetir…</button>`;
    case 'failed': return `<button class="btn primary" data-action="serve" data-id="${r.id}">Reintentar</button>`;
    default: return `<button class="btn primary" data-action="serve" data-id="${r.id}">Servir</button>`;
  }
}

function residentCard(r, index, moment) {
  const st = r.status[moment];
  const groups = groupPicks(st.picks);

  const meds = groups.length
    ? groups.map(({ pill, qty }) => `
        <div class="med">${pillIcon(pill)}<span>${esc(pill.name)} <small class="meta">${esc(pill.dose)}</small></span>
          <span class="qty">×${qty}</span></div>`).join('')
    : `<div class="med-empty">Sin pastillas en esta toma</div>`;

  // tomas anteriores de hoy que no se dieron
  const missed = store.state.moments
    .filter((m) => m.id !== moment && r.status[m.id].state === 'missed')
    .map((m) => m.label.toLowerCase());
  const alert = missed.length
    ? `<div class="alert">⚠ No ha tomado: ${esc(missed.join(', '))}</div>` : '';

  return `
    <article class="card ${st.state}">
      <span class="key-hint"><kbd>${index + 1}</kbd></span>
      <div class="card-top">
        ${avatar(r)}
        <div>
          <div class="name">${esc(r.name)}</div>
          <div class="meta">Hab. ${esc(r.room)} · ${esc(r.age)} años</div>
        </div>
      </div>
      <div class="meds">${meds}</div>
      ${alert}
      <div class="card-foot">${BADGE[st.state](st)}${actionButton(r, st)}</div>
    </article>`;
}

function bowlCard(p) {
  const pct = Math.round((p.stock / p.capacity) * 100);
  return `
    <div class="bowl ${p.low ? 'low' : ''}">
      ${pillIcon(p, 56)}
      <div class="bowl-name">${esc(p.name)} <small class="meta">${esc(p.dose)}</small></div>
      <div class="bowl-desc">Cuenco ${esc(p.bowl)} · pastilla ${esc(p.pill_desc)}</div>
      <div class="stock-bar"><span style="width:${pct}%"></span></div>
      <div class="stock-text">${p.low ? '⚠ Quedan ' : ''}${p.stock} de ${p.capacity}${p.low ? ' — rellenar' : ''}</div>
    </div>`;
}

export function renderPanel() {
  const { residents, pills } = store.state;
  const moment = currentMoment();
  const info = momentInfo(moment);

  const withPills = residents.filter((r) => r.status[moment].picks.length);
  const served = withPills.filter((r) => r.status[moment].state === 'done').length;
  const missedTotal = residents.reduce(
    (n, r) => n + Object.values(r.status).filter((s) => s.state === 'missed').length, 0);
  const lowBowls = pills.filter((p) => p.low).length;

  return `
    <section class="panel-head">
      <div>
        <div class="eyebrow">${store.momentOverride ? 'Toma seleccionada' : 'Toma actual'}</div>
        <h1>${info.icon} ${esc(info.label)}</h1>
      </div>
      <div class="summary">
        <span class="summary-pill"><b>${served}</b> de <b>${withPills.length}</b> servidos</span>
        ${missedTotal ? `<span class="summary-pill warn">⚠ ${missedTotal} toma${missedTotal > 1 ? 's' : ''} sin dar hoy</span>` : ''}
        ${lowBowls ? `<span class="summary-pill warn">⚠ ${lowBowls} cuenco${lowBowls > 1 ? 's' : ''} casi vacío${lowBowls > 1 ? 's' : ''}</span>` : ''}
      </div>
    </section>

    <section class="residents">
      ${residents.map((r, i) => residentCard(r, i, moment)).join('')}
    </section>

    <h2 class="section-title">Cuencos del robot</h2>
    <section class="bowls">${pills.map(bowlCard).join('')}</section>`;
}
