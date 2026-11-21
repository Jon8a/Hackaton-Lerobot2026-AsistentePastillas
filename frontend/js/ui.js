// Utilidades de interfaz: escapar texto, iconos, toasts y delegación de eventos.

export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const initials = (name) =>
  name.split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();

export const pillIcon = (p, size) =>
  `<span class="pill-icon" style="--bowl:${p.bowl_color};--pill:${p.pill_color};${size ? `--s:${size}px` : ''}"
     title="${esc(p.name)} (cuenco ${esc(p.bowl)})"></span>`;

export const avatar = (r) =>
  `<div class="avatar" style="background:${r.color}">${esc(initials(r.name))}</div>`;

export function toast(msg, type = 'info', ms = 3200) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), ms);
}

// --- delegación: <button data-action="serve" data-id="maite"> llama a actions.serve(dataset, el)
const actions = {};
const changes = {};
export const onAction = (map) => Object.assign(actions, map);
export const onChange = (map) => Object.assign(changes, map);

export function installDelegation() {
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el || el.disabled) return;
    const fn = actions[el.dataset.action];
    if (fn) { e.preventDefault(); fn(el.dataset, el, e); }
  });
  document.addEventListener('change', (e) => {
    const el = e.target.closest('[data-change]');
    const fn = el && changes[el.dataset.change];
    if (fn) fn(el.dataset, el, e);
  });
}
