// Ajustes: stock de cuencos, pautas de cada residente y reinicio para ensayar la demo.
import { store } from '../store.js';
import { esc, pillIcon, avatar } from '../ui.js';

function stockCard(pills) {
  const rows = pills.map((p) => `
    <tr>
      <td>${pillIcon(p)} <b>${esc(p.name)}</b> <span class="meta">${esc(p.dose)}</span></td>
      <td>Cuenco ${esc(p.bowl)}</td>
      <td><input type="number" min="0" max="${p.capacity}" value="${p.stock}"
                 data-change="stock" data-key="${p.key}"> / ${p.capacity}</td>
      <td><button class="btn" data-action="refill" data-key="${p.key}">Rellenar</button></td>
    </tr>`).join('');
  return `
    <div class="settings-card">
      <h2>Cuencos</h2>
      <p class="help">Baja sola cada vez que el robot sirve una pastilla. Si rellenáis un cuenco, ponedlo aquí.</p>
      <div class="table-wrap"><table><tbody>${rows}</tbody></table></div>
    </div>`;
}

function scheduleCard(residents, pills, moments) {
  const head = moments.map((m) => `<th colspan="${pills.length}">${m.icon} ${esc(m.label)}</th>`).join('');
  const sub = moments.map(() => pills.map((p) => `<th>${pillIcon(p)}</th>`).join('')).join('');
  const rows = residents.map((r) => `
    <tr>
      <td><div class="card-top">${avatar(r)}<b>${esc(r.name)}</b></div></td>
      ${moments.map((m) => pills.map((p) => `
        <td><input type="number" min="0" max="3" value="${r.schedule[m.id]?.[p.key] || 0}"
                   data-change="schedule" data-resident="${r.id}" data-moment="${m.id}" data-key="${p.key}"></td>`
      ).join('')).join('')}
    </tr>`).join('');
  return `
    <div class="settings-card">
      <h2>Pautas</h2>
      <p class="help">Cuántas pastillas de cada tipo toma cada residente en cada toma. Se guarda al cambiar.</p>
      <div class="table-wrap"><table class="sched">
        <thead><tr><th rowspan="2">Residente</th>${head}</tr><tr>${sub}</tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </div>`;
}

const WORKER_STATE = { loading: 'Cargando…', ready: 'Listo', error: 'Error', off: 'Apagado' };

function systemCard() {
  const h = store.health || {};
  const w = h.worker;
  const mode = !h.ok ? 'Sin conexión con el servidor'
    : h.mode === 'sim' ? 'Simulación (sin robot)'
    : h.mode === 'worker' ? (w?.mock ? 'Worker con brazo simulado' : 'Worker (modelos cargados una vez)')
    : 'Un lerobot-rollout por pastilla';
  const models = Object.entries(h.models || {})
    .map(([k, path]) => `<div><b>${esc(k)}</b>: <code>${esc(path)}</code></div>`).join('');
  const robotButtons = w ? `
      <div class="row-actions" style="margin-top:14px">
        <button class="btn" data-action="robotHome" ${w.state !== 'ready' || h.busy ? 'disabled' : ''}>Llevar a reposo</button>
        <button class="btn" data-action="robotSetRest" ${w.state !== 'ready' || h.busy ? 'disabled' : ''}>Guardar postura actual como reposo</button>
        <button class="btn" data-action="robotRestart" ${h.busy ? 'disabled' : ''}>Reiniciar robot</button>
        <button class="btn ghost" data-action="robotLog">Ver salida del robot</button>
      </div>
      ${store.robotLog ? `<div class="log-box" style="margin-top:12px"><pre>${esc(store.robotLog.join('\n'))}</pre></div>` : ''}` : '';

  return `
    <div class="settings-card">
      <h2>Robot</h2>
      <dl class="kv">
        <dt>Modo</dt><dd>${mode}</dd>
        ${w ? `<dt>Estado</dt><dd>${WORKER_STATE[w.state] || esc(w.state)}${w.msg && w.msg !== 'Listo' ? ` — ${esc(w.msg)}` : ''}</dd>` : ''}
        ${h.mode === 'cli' ? `<dt>lerobot-rollout</dt><dd>${h.lerobot_found ? 'Encontrado' : '⚠ No encontrado (¿entorno activado?)'}</dd>` : ''}
        <dt>Modelos</dt><dd>${models}</dd>
      </dl>
      <p class="help" style="margin-top:14px">Puerto, cámaras, modelos y detección del fin de ciclo: <code>backend/config.py</code>.
        El brazo tiene que estar en reposo al arrancar el servidor.</p>
      ${robotButtons}
    </div>
    <div class="settings-card">
      <h2>Demo</h2>
      <div class="row-actions">
        <button class="btn" data-action="reset" data-scope="day">Reiniciar el día (borra lo de hoy y rellena cuencos)</button>
        <button class="btn danger" data-action="reset" data-scope="all">Restaurar datos de demo</button>
      </div>
    </div>`;
}

export function renderSettings() {
  const { residents, pills, moments } = store.state;
  return `
    <h1 class="page-title">Ajustes</h1>
    <div class="settings-grid">
      ${stockCard(pills)}
      ${scheduleCard(residents, pills, moments)}
      ${systemCard()}
    </div>`;
}
