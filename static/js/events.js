// İş ilerlemesi: Server-Sent Events, bağlantı koparsa yoklama (polling) ile devam eder.
import { api } from './api.js';

export const live = { jobs: new Map(), ready: false };
const listeners = new Set();
let es = null;
let pollTimer = null;

function apply(list) {
  const changes = [];
  for (const j of list) {
    const prev = live.jobs.get(j.id);
    live.jobs.set(j.id, { ...prev, ...j });
    if (!prev || prev.status !== j.status) changes.push({ id: j.id, from: prev?.status, to: j.status, job: live.jobs.get(j.id) });
  }
  live.ready = true;
  for (const cb of listeners) cb(changes);
}

async function poll() {
  try {
    const { jobs } = await api.get('/api/jobs?scope=queue');
    apply(jobs);
  } catch { /* sunucu kapalıysa sessizce yeniden dene */ }
}

function startPolling() {
  if (pollTimer) return;
  poll();
  pollTimer = setInterval(poll, 2000);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

export function startEvents() {
  if (es || typeof EventSource === 'undefined') { startPolling(); return; }
  es = new EventSource('/api/events');
  es.addEventListener('jobs', (e) => {
    stopPolling();
    try { apply(JSON.parse(e.data).jobs); } catch { /* bozuk paketi yoksay */ }
  });
  es.onerror = () => startPolling();
}

/** Dinleyici ekler; hemen mevcut durumla da bir kez çağrılır. Çıkış için dönen işlevi çağırın. */
export function onJobs(cb) {
  listeners.add(cb);
  if (live.ready) cb([]);
  return () => listeners.delete(cb);
}

export const activeJobs = () => [...live.jobs.values()].filter((j) => j.status === 'beklemede' || j.status === 'işleniyor');
