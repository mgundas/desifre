import { T, fmt } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, icon, iconButton, clear, statusChip, emptyState, toast } from '../ui.js';
import { onJobs, live } from '../events.js';
import { fmtDuration, fmtClock } from '../util.js';

export async function mount(root) {
  const box = h('div', { class: 'stack-lg' });
  root.append(h('div', { class: 'page page-narrow' }, h('h1', null, T.queue.title), box));

  async function act(fn) {
    try { await fn(); } catch (e) { toast(e.message, 'error'); }
  }

  function jobCard(j, queuedIds) {
    const running = j.status === 'işleniyor';
    const actions = [];
    if (j.status === 'beklemede') {
      const i = queuedIds.indexOf(j.id);
      actions.push(
        iconButton('up', T.queue.moveUp, () => act(() => api.post('/api/jobs/reorder', { ids: swap(queuedIds, i, i - 1) })), { disabled: i <= 0 }),
        iconButton('down', T.queue.moveDown, () => act(() => api.post('/api/jobs/reorder', { ids: swap(queuedIds, i, i + 1) })), { disabled: i >= queuedIds.length - 1 }));
    }
    if (j.status === 'beklemede' || running) {
      const btn = h('button', { type: 'button', class: 'btn', onClick: () => { btn.disabled = true; if (running) btn.textContent = T.queue.cancelling; act(() => api.post(`/api/jobs/${j.id}/cancel`)); } }, T.queue.cancel);
      actions.push(btn);
    }
    if (j.status === 'hata' || j.status === 'iptal') actions.push(h('button', { type: 'button', class: 'btn', onClick: () => act(() => api.post(`/api/jobs/${j.id}/retry`)) }, T.queue.retry));
    if (j.status === 'tamamlandı') actions.push(h('a', { class: 'btn', href: `#/t/${j.id}` }, T.queue.openResult));

    const pct = Math.round(j.progress || 0);
    return h('article', { class: `card job ${running ? 'job-running' : ''}` },
      h('div', { class: 'job-head' }, h('strong', { class: 'job-title' }, j.title || j.orig_name), statusChip(j.status)),
      running ? h('div', { class: 'job-progress' },
        h('div', { class: 'job-stage' }, j.stage || T.stage.prepare, h('span', { class: 'job-pct' }, `%${pct}`)),
        h('progress', { max: '100', value: String(pct), 'aria-label': j.stage || T.queue.running }),
        h('div', { class: 'muted job-times' }, `${T.queue.elapsed}: ${fmtDuration(j.elapsed) || '0 ' + T.common.seconds}`, j.eta ? ` · ${T.queue.eta}: ${fmtDuration(j.eta)}` : '')) : null,
      j.status === 'hata' && j.error ? h('p', { class: 'note note-error' }, j.error) : null,
      j.notice ? h('p', { class: 'note note-warn' }, `${T.queue.notice}: ${j.notice}`) : null,
      actions.length ? h('div', { class: 'job-actions' }, actions) : null);
  }

  const swap = (arr, i, k) => { const a = arr.slice(); if (k < 0 || k >= a.length) return a; [a[i], a[k]] = [a[k], a[i]]; return a; };

  function section(title, jobs, queuedIds) {
    if (!jobs.length) return null;
    return h('section', null, h('h2', { class: 'section-title' }, title), h('div', { class: 'stack' }, jobs.map((j) => jobCard(j, queuedIds))));
  }

  function draw() {
    const all = [...live.jobs.values()];
    const running = all.filter((j) => j.status === 'işleniyor');
    const queued = all.filter((j) => j.status === 'beklemede').sort((a, b) => a.position - b.position);
    const finished = all.filter((j) => ['tamamlandı', 'hata', 'iptal'].includes(j.status))
      .sort((a, b) => (b.finished_at || 0) - (a.finished_at || 0)).slice(0, 15);
    const ids = queued.map((j) => j.id);
    clear(box);
    if (!all.length) { box.append(emptyState(T.queue.empty, h('a', { class: 'btn btn-primary', href: '#/upload' }, T.nav.upload))); return; }
    box.append(...[section(T.queue.running, running, ids), section(T.queue.waiting, queued, ids), section(T.queue.finished, finished, ids)].filter(Boolean));
  }

  // İlerleme çubuğu her saniye yeniden çizilirken düğmelere basmayı zorlaştırmasın diye yalnızca durum değişince tam çizim yapılır.
  let sig = '';
  const off = onJobs(() => {
    const next = [...live.jobs.values()].map((j) => `${j.id}:${j.status}:${j.position}:${j.error}:${j.notice}`).join('|');
    if (next !== sig) { sig = next; draw(); return; }
    // yalnızca ilerleme alanlarını güncelle
    const running = [...live.jobs.values()].find((j) => j.status === 'işleniyor');
    const card = box.querySelector('.job-running');
    if (running && card) {
      const pct = Math.round(running.progress || 0);
      card.querySelector('.job-stage').firstChild.textContent = running.stage || T.stage.prepare;
      card.querySelector('.job-pct').textContent = `%${pct}`;
      card.querySelector('progress').value = pct;
      card.querySelector('.job-times').textContent = `${T.queue.elapsed}: ${fmtDuration(running.elapsed) || '0 ' + T.common.seconds}${running.eta ? ` · ${T.queue.eta}: ${fmtDuration(running.eta)}` : ''}`;
    }
  });
  if (!live.ready) box.append(h('p', { class: 'muted' }, T.common.loading));
  return off;
}
