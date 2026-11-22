// Ventana de servir: confirmar -> robot trabajando -> resultado.
import { api } from '../api.js';
import { store, emit, refresh, momentInfo, pillByKey, residentById } from '../store.js';
import { esc, pillIcon, avatar, toast } from '../ui.js';
import { speak } from '../voice.js';

const STEP_LABEL = {
  pending: 'En cola',
  running: 'Cogiendo…',
  done: 'En el vaso',
  error: 'Error',
  stopped: 'Parado',
  skipped: 'Cancelado',
};
const FINAL = ['done', 'error', 'stopped'];

export const modal = {
  open: false,
  phase: null,        // confirm | running | finished
  residentId: null,
  moment: null,
  steps: [],
  jobId: null,
  jobState: null,
  log: [],
  alreadyAt: null,    // hora si esta toma ya se dio hoy
  error: null,
  starting: false,
  showLog: false,
};

export function toggleLog() {
  modal.showLog = !modal.showLog;
  emit();
}

let pollTimer = null;

export const isRunning = () => modal.open && modal.phase === 'running';

export function openServe(residentId, moment) {
  if (store.health?.busy && !modal.open) { toast('El robot está ocupado', 'warn'); return; }
  const r = residentById(residentId);
  const st = r?.status[moment];
  if (!st) return;
  if (!st.picks.length) { toast(`${r.name} no tiene pastillas en esta toma`); return; }
  Object.assign(modal, {
    open: true, phase: 'confirm', residentId, moment,
    steps: st.picks.map((pill) => ({ pill, state: 'pending' })),
    jobId: null, jobState: null, log: [], error: null, starting: false,
    alreadyAt: st.state === 'done' ? st.time : null,
  });
  emit();
}

/** Si se recarga la página con el robot en marcha, volvemos a enganchar el trabajo. */
export async function attachToJob(jobId) {
  try {
    const job = await api.job(jobId);
    Object.assign(modal, {
      open: true, phase: 'running', residentId: job.resident_id, moment: job.moment,
      jobId, alreadyAt: null, error: null,
    });
    applyJob(job);
    startPolling();
    emit();
  } catch { /* el trabajo ya no existe */ }
}

export async function startServe() {
  if (modal.phase !== 'confirm' || modal.starting) return;
  modal.starting = true;
  modal.error = null;
  emit();
  try {
    const job = await api.serve(modal.residentId, modal.moment, Boolean(modal.alreadyAt));
    modal.jobId = job.id;
    modal.phase = 'running';
    applyJob(job);
    startPolling();
  } catch (e) {
    modal.error = e.message;
  }
  modal.starting = false;
  emit();
}

export async function stopRobot() {
  try {
    toast('Parando el robot…', 'warn');
    await api.stop();
  } catch (e) {
    toast(`No se pudo parar: ${e.message}`, 'err', 6000);
  }
}

export function closeModal() {
  if (modal.phase === 'running') return;
  modal.open = false;
  emit();
}

function applyJob(job) {
  modal.steps = job.steps;
  modal.log = job.log;
  modal.jobState = job.state;
}

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const job = await api.job(modal.jobId);
      applyJob(job);
      if (FINAL.includes(job.state)) {
        clearInterval(pollTimer);
        await finish(job);
      }
      emit();
    } catch { /* fallo puntual de red: reintenta en el siguiente tick */ }
  }, 700);
}

async function finish(job) {
  modal.phase = 'finished';
  await refresh();
  const r = residentById(job.resident_id);
  const first = r ? r.name.split(' ')[0] : '';
  if (job.state === 'done') speak(`${first}, aquí tienes tus pastillas ${momentInfo(job.moment).phrase}.`);
  else if (job.state === 'error') speak('Atención: el robot ha tenido un problema.');
}

// ------------------------------------------------------------------ render
function stepItem(s) {
  const p = pillByKey(s.pill);
  return `<li class="step ${s.state}">${pillIcon(p)}
            <span>${esc(p.name)} <small class="meta">cuenco ${esc(p.bowl)}</small></span>
            <span class="step-state">${STEP_LABEL[s.state] || s.state}${s.took ? ` · ${s.took} s` : ''}</span></li>`;
}

function resultNotice() {
  const done = modal.steps.filter((s) => s.state === 'done').length;
  const total = modal.steps.length;
  if (modal.jobState === 'done') return `<div class="notice ok">✓ Todas las pastillas están en el vaso</div>`;
  if (modal.jobState === 'stopped') return `<div class="notice warn">Robot parado. Se han servido ${done} de ${total}. Revisa el vaso antes de dárselo.</div>`;
  const failed = modal.steps.find((s) => s.state === 'error');
  const name = failed ? pillByKey(failed.pill).name : '';
  const why = failed?.reason ? ` Motivo: ${esc(failed.reason)}.` : '';
  return `<div class="notice err">✗ Ha fallado al coger ${esc(name)}.${why} Se han servido ${done} de ${total}.</div>`;
}

function confirmWarnings() {
  const out = [];
  if (modal.alreadyAt) {
    out.push(`<div class="notice warn">⚠ Esta toma ya se sirvió hoy a las ${esc(modal.alreadyAt)}. ¿Seguro que quieres darla otra vez?</div>`);
    modal.steps.map((s) => pillByKey(s.pill)).filter((p) => p.warning)
      .forEach((p) => out.push(`<div class="notice err">${esc(p.name)}: ${esc(p.warning)}</div>`));
  }
  if (modal.error) out.push(`<div class="notice err">${esc(modal.error)}</div>`);
  return out.join('');
}

function footer() {
  if (modal.phase === 'confirm') {
    return `<div class="dialog-actions">
      <button class="btn" data-action="close">Cancelar</button>
      <button class="btn ${modal.alreadyAt ? 'danger' : 'primary'} big" data-action="start" ${modal.starting ? 'disabled' : ''}>
        ${modal.starting ? 'Arrancando…' : modal.alreadyAt ? 'Servir otra vez' : 'Servir'} <kbd>Enter</kbd></button></div>`;
  }
  if (modal.phase === 'running') {
    return `<button class="btn stop" data-action="stop">■ PARAR ROBOT <kbd>Espacio</kbd></button>`;
  }
  return `${resultNotice()}<div class="dialog-actions"><button class="btn primary big" data-action="close">Cerrar</button></div>`;
}

export function renderModal() {
  if (!modal.open) return '';
  const r = residentById(modal.residentId);
  const info = momentInfo(modal.moment);
  const done = modal.steps.filter((s) => s.state === 'done').length;
  const pct = modal.steps.length ? Math.round((done / modal.steps.length) * 100) : 0;
  const title = modal.phase === 'confirm' ? 'Va a servir' : modal.phase === 'running' ? 'Sirviendo…' : 'Resultado';

  return `
    <div class="overlay" data-action="${modal.phase === 'running' ? '' : 'backdrop'}">
      <div class="dialog" role="dialog" aria-modal="true">
        <div class="dialog-head">
          ${r ? avatar(r) : ''}
          <div>
            <div class="eyebrow">${title} · ${info.icon} ${esc(info.label)}</div>
            <h2>${esc(r ? r.name : '')}</h2>
            ${r ? `<div class="meta">Hab. ${esc(r.room)}</div>` : ''}
          </div>
        </div>
        ${modal.phase !== 'confirm' ? `<div class="progress"><span style="width:${pct}%"></span></div>` : ''}
        <ul class="steps">${modal.steps.map(stepItem).join('')}</ul>
        ${modal.phase === 'confirm' ? confirmWarnings() : ''}
        ${footer()}
        ${modal.log.length ? `<details class="log-box" ${modal.showLog ? 'open' : ''}>
          <summary data-action="toggleLog">${modal.showLog ? 'Ocultar' : 'Ver'} salida del robot</summary>
          <pre>${esc(modal.log.join('\n'))}</pre></details>` : ''}
      </div>
    </div>`;
}
