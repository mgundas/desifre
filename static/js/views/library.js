import { T, fmt } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, icon, iconButton, clear, statusChip, emptyState, toast, confirmDialog, promptDialog, checkbox } from '../ui.js';
import { onJobs, live } from '../events.js';
import { debounce, fmtDate, fmtClock, fmtInt, storageGet, storageSet } from '../util.js';
import { exportDialog } from './export-dialog.js';

export async function mount(root) {
  const state = { q: '', sort: storageGet('desifre:lib:sort', 'date'), order: storageGet('desifre:lib:order', 'desc') };
  const body = h('div', null);
  const count = h('span', { class: 'muted' });
  let reqId = 0;

  const search = h('input', { type: 'search', class: 'input search', placeholder: T.library.search, 'aria-label': T.library.search, onInput: debounce((e) => { state.q = e.target.value; load(); }, 250) });
  const sort = h('select', { class: 'input', 'aria-label': T.library.sort, onChange: (e) => { state.sort = e.target.value; storageSet('desifre:lib:sort', state.sort); load(); } },
    [['date', T.library.sortDate], ['title', T.library.sortTitle], ['duration', T.library.sortDuration]].map(([v, l]) => h('option', { value: v, selected: v === state.sort }, l)));
  const order = h('button', { type: 'button', class: 'btn', onClick: () => { state.order = state.order === 'asc' ? 'desc' : 'asc'; storageSet('desifre:lib:order', state.order); drawOrder(); load(); } });
  const drawOrder = () => { clear(order).append(icon(state.order === 'asc' ? 'up' : 'down', 16), state.order === 'asc' ? T.library.asc : T.library.desc); };
  drawOrder();

  root.append(h('div', { class: 'page' },
    h('div', { class: 'page-head' }, h('h1', null, T.library.title), count),
    h('div', { class: 'toolbar' }, search, sort, order), body));

  async function load() {
    const my = ++reqId;
    let items;
    try { items = (await api.get(`/api/transcripts?q=${encodeURIComponent(state.q)}&sort=${state.sort}&order=${state.order}`)).items; }
    catch (e) { toast(e.message, 'error'); return; }
    if (my !== reqId) return;
    draw(items);
  }

  async function rename(it) {
    const title = await promptDialog({ title: T.library.renamePrompt, label: T.library.colTitle, value: it.title });
    if (!title) return;
    try { await api.put(`/api/transcripts/${it.id}`, { title }); toast(T.library.renamed, 'success'); load(); } catch (e) { toast(e.message, 'error'); }
  }

  async function remove(it) {
    let delMedia = true;
    const cb = checkbox(T.library.deleteMedia, true, (v) => { delMedia = v; });
    const ok = await confirmDialog({
      title: T.library.deleteTitle, message: `"${it.title}" ${T.library.deleteText}`, confirmLabel: T.common.delete, danger: true,
      extra: h('div', { class: 'stack' }, cb.el, h('small', { class: 'muted' }, T.library.deleteMediaKept)),
    });
    if (!ok) return;
    try { await api.del(`/api/transcripts/${it.id}?delete_media=${delMedia}`); live.jobs.delete(it.id); toast(T.library.deleted, 'success'); load(); } catch (e) { toast(e.message, 'error'); }
  }

  function draw(items) {
    clear(body);
    count.textContent = `${fmtInt(items.length)} ${T.library.count}`;
    if (!items.length) {
      body.append(emptyState(state.q ? T.library.emptySearch : T.library.empty, state.q ? null : h('a', { class: 'btn btn-primary', href: '#/upload' }, T.nav.upload)));
      return;
    }
    const head = h('tr', null, [T.library.colTitle, T.library.colDate, T.library.colDuration, T.library.colLanguage, T.library.colModel, T.library.colSpeakers, T.library.colStatus, T.library.colActions].map((t) => h('th', { scope: 'col' }, t)));
    const rows = items.map((it) => {
      const done = it.status === 'tamamlandı';
      return h('tr', null,
        h('td', { class: 'cell-title' }, done ? h('a', { href: `#/t/${it.id}` }, it.title) : h('span', null, it.title)),
        h('td', null, fmtDate(it.created_at)),
        h('td', null, done ? fmtClock(it.duration) : ''),
        h('td', null, done ? langName(it.language) : ''),
        h('td', null, it.model || ''),
        h('td', null, done && it.speaker_count ? String(it.speaker_count) : ''),
        h('td', null, statusChip(it.status)),
        h('td', { class: 'cell-actions' },
          done ? iconButton('download', T.common.export, () => exportDialog(it.id)) : null,
          iconButton('edit', T.common.rename, () => rename(it)),
          iconButton('trash', T.common.delete, () => remove(it), { disabled: it.status === 'işleniyor' })));
    });
    body.append(h('div', { class: 'table-wrap' }, h('table', { class: 'table' }, h('thead', null, head), h('tbody', null, rows))));
  }

  let names = {};
  try { (await api.get('/api/languages')).languages.forEach((l) => { names[l.code] = l.name; }); } catch { /* yoksay */ }
  const langName = (c) => names[c] || c || '';

  await load();
  // iş durumu değişince listeyi tazele
  let sig = '';
  const off = onJobs(() => {
    const next = [...live.jobs.values()].map((j) => `${j.id}:${j.status}`).join('|');
    if (next !== sig) { const first = sig === ''; sig = next; if (!first) load(); }
  });
  return off;
}
