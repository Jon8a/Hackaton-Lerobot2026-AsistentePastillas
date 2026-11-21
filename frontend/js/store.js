// Estado de la interfaz. Los datos "de verdad" viven en el servidor;
// aquí solo guardamos la última copia y lo que es propio de la pantalla.
import { api } from './api.js';

export const store = {
  state: null,            // lo que devuelve /api/state
  health: null,           // lo que devuelve /api/health (o {ok:false})
  view: 'panel',          // panel | history | settings
  momentOverride: null,   // null = según la hora
  loadError: null,
};

const listeners = new Set();
export const subscribe = (fn) => listeners.add(fn);
export const emit = () => listeners.forEach((fn) => fn());

export async function refresh() {
  try {
    store.state = await api.state();
    store.loadError = null;
  } catch (e) {
    store.loadError = e.message;
  }
  emit();
}

export const currentMoment = () => store.momentOverride || store.state?.current_moment;
export const momentInfo = (id) => store.state.moments.find((m) => m.id === id);
export const pillByKey = (key) => store.state.pills.find((p) => p.key === key);
export const residentById = (id) => store.state.residents.find((r) => r.id === id);

/** ["metformina","metformina","sintrom"] -> [{pill, qty:2}, {pill, qty:1}] */
export function groupPicks(picks) {
  const counts = new Map();
  picks.forEach((k) => counts.set(k, (counts.get(k) || 0) + 1));
  return [...counts].map(([key, qty]) => ({ pill: pillByKey(key), qty })).filter((g) => g.pill);
}
