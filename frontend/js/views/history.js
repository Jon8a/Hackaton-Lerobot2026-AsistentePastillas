// Historial: quién tomó qué y cuándo.
import { store, momentInfo, pillByKey } from '../store.js';
import { esc, pillIcon } from '../ui.js';

const STATUS = {
  done: '<span class="badge ok">Servido</span>',
  error: '<span class="badge failed">Error del robot</span>',
  stopped: '<span class="badge missed">Parado</span>',
};

function picksCell(e) {
  // las que no llegaron al vaso salen apagadas
  const remaining = [...e.done];
  return `<div class="picks-inline">${e.picks.map((k) => {
    const p = pillByKey(k);
    if (!p) return esc(k);
    const i = remaining.indexOf(k);
    const ok = i >= 0;
    if (ok) remaining.splice(i, 1);
    return `<span class="${ok ? '' : 'missing'}">${pillIcon(p)}</span>`;
  }).join('')}</div>`;
}

export function renderHistory() {
  const { log, date } = store.state;
  if (!log.length) {
    return `<h1 class="page-title">Historial</h1><div class="empty-state">Todavía no se ha servido nada.</div>`;
  }
  const rows = log.map((e) => {
    const m = momentInfo(e.moment);
    return `<tr>
      <td>${e.date === date ? 'Hoy' : esc(e.date)} · <b>${esc(e.time)}</b></td>
      <td>${esc(e.resident_name)}</td>
      <td>${m ? `${m.icon} ${esc(m.label)}` : esc(e.moment)}</td>
      <td>${picksCell(e)}</td>
      <td>${STATUS[e.status] || esc(e.status)}${e.forced ? ' <span class="badge missed">Repetida</span>' : ''}</td>
    </tr>`;
  }).join('');

  return `
    <h1 class="page-title">Historial</h1>
    <div class="table-wrap"><table>
      <thead><tr><th>Cuándo</th><th>Residente</th><th>Toma</th><th>Pastillas</th><th>Estado</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}
