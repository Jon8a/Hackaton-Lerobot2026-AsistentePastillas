// Todas las llamadas al servidor (server.py) pasan por aquí.

async function request(method, url, body, timeoutMs = 8000) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  let data = null;
  try { data = await res.json(); } catch { /* sin cuerpo */ }
  if (!res.ok) {
    const detail = data && data.detail;
    const err = new Error(typeof detail === 'string' ? detail : `Error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  health: () => request('GET', '/api/health', null, 2500),
  state: () => request('GET', '/api/state'),
  serve: (residentId, moment, force = false) =>
    request('POST', '/api/serve', { resident_id: residentId, moment, force }),
  job: (id) => request('GET', `/api/jobs/${id}`, null, 3000),
  stop: () => request('POST', '/api/stop', null, 12000),
  setStock: (key, stock) => request('PUT', `/api/pills/${key}`, { stock }),
  setSchedule: (residentId, schedule) => request('PUT', `/api/residents/${residentId}`, { schedule }),
  reset: (scope) => request('POST', '/api/reset', { scope }),
  robotHome: () => request('POST', '/api/robot/home'),
  robotSetRest: () => request('POST', '/api/robot/rest'),
  robotRestart: () => request('POST', '/api/robot/restart'),
  robotLog: () => request('GET', '/api/robot/log'),
};
