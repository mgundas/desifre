// Kayıt düzenleyici: oynatıcı, metin ve altyazı görünümleri, konuşmacılar, bul/değiştir, otomatik kaydetme.
import { T, fmt } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, icon, iconButton, clear, toast, openDialog, checkbox } from '../ui.js';
import { Store } from '../editor/store.js';
import { createPlayer } from '../editor/player.js';
import { createSegmentsView } from '../editor/segments-view.js';
import { createCuesView } from '../editor/cues-view.js';
import * as ops from '../editor/ops.js';
import { debounce, paletteColor, storageGet, storageSet, storageRemove } from '../util.js';
import { exportDialog } from './export-dialog.js';

const SAVE_DELAY = 1500;

export async function mount(root, { id }) {
  let tr, settings;
  try {
    [tr, settings] = await Promise.all([api.get(`/api/transcripts/${id}`), api.get('/api/settings')]);
  } catch (e) {
    root.append(h('div', { class: 'empty' }, icon('alert', 36), h('p', null, e.status === 404 ? T.errors.notFound : e.message), h('a', { class: 'btn', href: '#/library' }, T.editor.back)));
    return;
  }
  if (tr.status !== 'tamamlandı') {
    root.append(h('div', { class: 'empty' }, icon('alert', 36), h('p', null, tr.status === 'hata' ? `${T.editor.failedJob}: ${tr.error || ''}` : T.editor.notDone), h('a', { class: 'btn', href: '#/queue' }, T.nav.queue)));
    return;
  }

  // ---- başlangıç durumu ----
  let segments = tr.segments.map((s) => ops.ensureWords(s));
  const speakers = { ...tr.speakers };
  for (const s of segments) if (s.speaker && !speakers[s.speaker]) speakers[s.speaker] = { name: '', color: '' };
  Object.keys(speakers).forEach((k, i) => { speakers[k] = { name: speakers[k].name || '', color: speakers[k].color || paletteColor(i) }; });
  let draftNote = false;
  const draftKey = `desifre:draft:${id}`;
  try {
    const d = JSON.parse(storageGet(draftKey, 'null'));
    if (d && d.savedAt > tr.updated_at * 1000 && JSON.stringify({ s: d.segments, p: d.speakers, t: d.title }) !== JSON.stringify({ s: segments, p: speakers, t: tr.title })) {
      segments = d.segments; Object.assign(speakers, d.speakers); tr.title = d.title; draftNote = true;
    } else if (d) storageRemove(draftKey);
  } catch { storageRemove(draftKey); }

  const store = new Store({ segments, speakers, title: tr.title });
  const ctx = {
    id, store, tr, rules: settings.subtitle,
    selectedId: null, editingId: null, speakersRev: 0, showTimes: storageGet('desifre:ed:times', '1') === '1', follow: storageGet('desifre:ed:follow', '1') === '1',
    find: { open: false, query: '', replace: '', cs: false, matches: [], current: -1, bySegId: new Map() },
    nextColor: () => paletteColor(Object.keys(store.state.speakers).length),
  };
  let view = storageGet('desifre:ed:view', 'text') === 'subs' ? 'subs' : 'text';

  // ---- oynatıcı ----
  const player = createPlayer({
    url: `/api/transcripts/${id}/media`, isVideo: tr.is_video && tr.has_media, hasMedia: tr.has_media,
    getData: () => ({ segments: store.state.segments, speakers: store.state.speakers, duration: tr.duration }),
    onTick: (t) => { segView.onTime(t); if (view === 'subs') cuesView.onTime(t); },
  });
  ctx.player = player;

  const scroller = h('div', { class: 'ed-list' });
  ctx.scroller = scroller;
  ctx.userScrollUntil = () => userScrollUntil;
  let userScrollUntil = 0;
  const segView = createSegmentsView(ctx);
  ctx.scrollToRow = segView.scrollToRow;
  const cuesView = createCuesView(ctx);
  const noteScroll = () => { userScrollUntil = Date.now() + 4000; };
  ['wheel', 'touchmove'].forEach((ev) => scroller.addEventListener(ev, noteScroll, { passive: true }));

  // ---- kaydetme ----
  const status = h('span', { class: 'save-status', role: 'status', 'aria-live': 'polite' }, T.editor.saved);
  let savedVersion = 0, saving = false, saveFailed = false;
  const dirty = () => store.version !== savedVersion;
  function drawStatus() {
    status.className = `save-status ${saveFailed ? 'bad' : dirty() || saving ? 'busy' : 'ok'}`;
    status.textContent = saveFailed ? T.editor.saveFailed : saving ? T.editor.saving : dirty() ? T.editor.unsaved : T.editor.saved;
  }
  const writeDraft = debounce(() => {
    if (!dirty()) return;
    storageSet(draftKey, JSON.stringify({ savedAt: Date.now(), segments: store.state.segments, speakers: store.state.speakers, title: store.state.title }));
  }, 500);
  async function saveNow() {
    if (saving) return;
    if (!dirty()) { drawStatus(); return; }
    saving = true; saveFailed = false; drawStatus();
    const ver = store.version;
    try {
      await api.put(`/api/transcripts/${id}`, { title: store.state.title, segments: store.state.segments, speakers: store.state.speakers });
      savedVersion = ver;
      if (!dirty()) storageRemove(draftKey);
    } catch (e) {
      saveFailed = true;
      if (e.status === 404) toast(e.message, 'error');
    }
    saving = false;
    drawStatus();
    if (dirty()) saveSoon(saveFailed ? 4000 : 0);
  }
  let saveTimer = 0;
  function saveSoon(ms = SAVE_DELAY) { clearTimeout(saveTimer); saveTimer = setTimeout(saveNow, ms); }
  async function flush() {
    clearTimeout(saveTimer);
    for (let n = 0; n < 5 && (dirty() || saving); n++) {
      if (saving) await new Promise((r) => setTimeout(r, 100)); else await saveNow();
      if (saveFailed) throw new Error(T.editor.saveFailed);
    }
  }

  // ---- değişiklikleri işle ----
  const countEl = h('span', { class: 'muted ed-count' });
  function recomputeFind() {
    const f = ctx.find;
    f.matches = f.open && f.query ? ops.findMatches(store.state.segments, f.query, f.cs) : [];
    if (f.current >= f.matches.length) f.current = f.matches.length - 1;
    if (f.current < 0 && f.matches.length) f.current = 0;
    f.bySegId = new Map();
    f.matches.forEach((m, i) => {
      const sid = store.state.segments[m.seg].id;
      if (!f.bySegId.has(sid)) f.bySegId.set(sid, []);
      f.bySegId.get(sid).push({ from: m.from, to: m.to, current: i === f.current });
    });
    drawFindCount();
  }

  let lastSpeakers = store.state.speakers;
  let lastSegments = store.state.segments;
  store.subscribe((source) => {
    const s = store.state;
    if (s.speakers !== lastSpeakers) { lastSpeakers = s.speakers; ctx.speakersRev++; segView.refreshChips(); if (source !== 'edit' || !speakerInputFocused()) renderSpeakers(); }
    if (s.segments !== lastSegments) {
      lastSegments = s.segments;
      recomputeFind();
      segView.render();
      player.drawTimeline();
      if (view === 'subs') cuesView.refreshSoon();
    } else if (view === 'text') segView.render();
    countEl.textContent = view === 'text' ? `${s.segments.length} ${T.editor.segmentsCount}` : `${cuesView.count} ${T.editor.cueCount}`;
    drawUndo();
    drawStatus();
    writeDraft();
    saveSoon();
  });

  // ---- başlık ----
  const titleInput = h('input', { class: 'input title-input', value: tr.title, 'aria-label': T.editor.title, maxlength: 200, onInput: (e) => store.setTitle(e.target.value) });

  // ---- araç çubuğu ----
  const undoBtn = iconButton('undo', `${T.editor.undo} (Ctrl+Z)`, () => doUndo());
  const redoBtn = iconButton('redo', `${T.editor.redo} (Ctrl+Y)`, () => doRedo());
  const drawUndo = () => { undoBtn.disabled = !store.canUndo; redoBtn.disabled = !store.canRedo; };
  function doUndo() { segView.stopEdit(); store.undo(); }
  function doRedo() { segView.stopEdit(); store.redo(); }

  const findBtn = iconButton('search', `${T.editor.find} (Ctrl+F)`, () => toggleFind());
  const spkBtn = iconButton('users', T.editor.speakers, () => toggleSpeakers());
  const helpBtn = iconButton('help', `${T.editor.shortcuts} (F1)`, () => showShortcuts());
  const exportBtn = h('button', { type: 'button', class: 'btn btn-primary', onClick: () => exportDialog(id, { beforeDownload: flush }) }, icon('download', 16), T.editor.export);

  const viewBtn = (v, label) => h('button', { type: 'button', class: `seg-btn${view === v ? ' active' : ''}`, dataset: { v }, 'aria-pressed': String(view === v), onClick: () => setView(v) }, label);
  const viewToggle = h('div', { class: 'seg-toggle', role: 'group', 'aria-label': T.editor.viewText }, viewBtn('text', T.editor.viewText), viewBtn('subs', T.editor.viewSubs));
  const timesCb = checkbox(T.editor.showTimes, ctx.showTimes, (v) => { ctx.showTimes = v; storageSet('desifre:ed:times', v ? '1' : '0'); segView.render(); });
  const followCb = checkbox(T.editor.follow, ctx.follow, (v) => { ctx.follow = v; storageSet('desifre:ed:follow', v ? '1' : '0'); });

  function setView(v) {
    view = v;
    storageSet('desifre:ed:view', v);
    viewToggle.querySelectorAll('.seg-btn').forEach((b) => { const on = b.dataset.v === v; b.classList.toggle('active', on); b.setAttribute('aria-pressed', String(on)); });
    clear(scroller);
    if (v === 'text') { scroller.append(segView.el); segView.render(); timesCb.el.hidden = false; }
    else { scroller.append(h('p', { class: 'muted hint' }, T.editor.subsHint), cuesView.el); timesCb.el.hidden = true; cuesView.refresh(); }
    countEl.textContent = v === 'text' ? `${store.state.segments.length} ${T.editor.segmentsCount}` : '';
    player.update();
  }

  // ---- bul / değiştir ----
  const findInput = h('input', { class: 'input', type: 'search', placeholder: T.editor.findPlaceholder, 'aria-label': T.editor.findPlaceholder });
  const replInput = h('input', { class: 'input', type: 'text', placeholder: T.editor.replacePlaceholder, 'aria-label': T.editor.replacePlaceholder });
  const findCount = h('span', { class: 'find-count', role: 'status', 'aria-live': 'polite' });
  const findPanel = h('div', { class: 'ed-panel find-panel', hidden: true, role: 'search' },
    findInput, replInput,
    iconButton('up', T.editor.prev, () => stepFind(-1)), iconButton('down', T.editor.next, () => stepFind(1)),
    h('button', { type: 'button', class: 'btn', onClick: () => replaceCurrent() }, T.editor.replace),
    h('button', { type: 'button', class: 'btn', onClick: () => replaceEverything() }, T.editor.replaceAll),
    checkbox(T.editor.caseSensitive, false, (v) => { ctx.find.cs = v; refreshFind(); }).el,
    findCount, iconButton('x', T.common.close, () => toggleFind(false)));

  function drawFindCount() {
    const f = ctx.find;
    findCount.textContent = !f.query ? '' : f.matches.length ? `${f.current + 1} / ${f.matches.length} ${T.editor.matches}` : T.editor.noMatch;
  }
  function refreshFind() { recomputeFind(); segView.render(); }
  function gotoMatch() {
    const f = ctx.find;
    if (f.current < 0 || !f.matches[f.current]) return;
    const seg = store.state.segments[f.matches[f.current].seg];
    if (view === 'text') segView.select(seg.id, { scroll: true });
    ctx.selectedId = seg.id;
  }
  function stepFind(d) {
    const f = ctx.find;
    if (!f.matches.length) return;
    f.current = (f.current + d + f.matches.length) % f.matches.length;
    recomputeFind();
    segView.render();
    gotoMatch();
  }
  function toggleFind(open = !ctx.find.open) {
    ctx.find.open = open;
    findPanel.hidden = !open;
    if (open) { if (view !== 'text') setView('text'); findInput.focus(); findInput.select(); } else { recomputeFind(); segView.render(); }
  }
  function replaceCurrent() {
    const f = ctx.find;
    const m = f.matches[f.current];
    if (!m) return;
    store.apply({ segments: ops.replaceMatch(store.state.segments, m, f.replace) });
    gotoMatch();
  }
  function replaceEverything() {
    const f = ctx.find;
    if (!f.query) return;
    const r = ops.replaceAll(store.state.segments, f.query, f.replace, f.cs);
    if (r.count) { store.apply({ segments: r.segments }); toast(`${r.count} ${T.editor.replacedCount}`, 'success'); }
  }
  findInput.addEventListener('input', () => { ctx.find.query = findInput.value; ctx.find.current = 0; refreshFind(); gotoMatch(); });
  replInput.addEventListener('input', () => { ctx.find.replace = replInput.value; });
  findInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); stepFind(e.shiftKey ? -1 : 1); } if (e.key === 'Escape') toggleFind(false); });

  // ---- konuşmacılar paneli ----
  const spkList = h('div', { class: 'spk-list' });
  const spkPanel = h('div', { class: 'ed-panel spk-panel', hidden: true },
    h('div', { class: 'panel-head' }, h('strong', null, T.editor.speakersTitle), h('span', { class: 'muted' }, T.editor.speakersHelp), iconButton('x', T.common.close, () => toggleSpeakers(false))), spkList);
  const speakerInputFocused = () => spkPanel.contains(document.activeElement);

  function renderSpeakers() {
    if (spkPanel.hidden) return;
    clear(spkList);
    const ids = Object.keys(store.state.speakers);
    if (!ids.length) spkList.append(h('p', { class: 'muted' }, T.editor.noSpeakers));
    for (const sid of ids) {
      const info = store.state.speakers[sid];
      const count = store.state.segments.filter((s) => s.speaker === sid).length;
      const setInfo = (patch, key) => store.apply({ speakers: { ...store.state.speakers, [sid]: { ...store.state.speakers[sid], ...patch } } }, { key });
      spkList.append(h('div', { class: 'spk-row' },
        h('input', { type: 'color', class: 'color-input', value: info.color || '#3b82f6', 'aria-label': `${T.editor.speakerColor}: ${ops.defaultSpeakerName(sid)}`, onInput: (e) => setInfo({ color: e.target.value }, `spkc:${sid}`) }),
        h('input', { type: 'text', class: 'input', value: info.name, maxlength: 80, placeholder: ops.defaultSpeakerName(sid), 'aria-label': `${T.editor.speakerName}: ${ops.defaultSpeakerName(sid)}`, onInput: (e) => setInfo({ name: e.target.value }, `spkn:${sid}`) }),
        h('span', { class: 'muted' }, `${count} ${T.editor.segmentsCount}`)));
    }
    spkList.append(h('button', { type: 'button', class: 'btn', onClick: () => { const sid = ops.nextSpeakerId(store.state.speakers, store.state.segments); store.apply({ speakers: { ...store.state.speakers, [sid]: { name: '', color: ctx.nextColor() } } }); renderSpeakers(); } }, icon('plus', 16), T.editor.newSpeaker));
  }
  function toggleSpeakers(open = spkPanel.hidden) { spkPanel.hidden = !open; if (open) renderSpeakers(); }

  // ---- kısayol paneli ----
  function showShortcuts() {
    openDialog({ title: T.editor.shortcutsTitle, body: h('table', { class: 'table table-kv shortcuts' }, h('tbody', null, T.editor.shortcutList.map(([k, d]) => h('tr', null, h('th', { scope: 'row' }, h('kbd', null, k)), h('td', null, d))))), actions: [{ label: T.common.close, primary: true, value: true }] });
  }

  // ---- klavye ----
  function onKey(e) {
    if (document.querySelector('dialog[open]')) return;
    const t = e.target;
    const tag = t instanceof HTMLElement ? t.tagName : '';
    const inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t instanceof HTMLElement && t.isContentEditable);
    const inSegEdit = tag === 'TEXTAREA' && t.classList.contains('seg-edit');
    const mod = e.ctrlKey || e.metaKey;
    const k = e.key.toLowerCase();
    if (e.key === 'F1') { e.preventDefault(); showShortcuts(); return; }
    if (mod && !e.shiftKey && k === 'z' && (!inField || inSegEdit)) { e.preventDefault(); doUndo(); return; }
    if (mod && (k === 'y' || (e.shiftKey && k === 'z')) && (!inField || inSegEdit)) { e.preventDefault(); doRedo(); return; }
    if (mod && k === 'f') { e.preventDefault(); toggleFind(true); return; }
    if (mod && k === 's') { e.preventDefault(); saveNow(); return; }
    if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); player.skip(-5); return; }
    if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); player.skip(5); return; }
    if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown') && view === 'text') {
      e.preventDefault();
      const segs = store.state.segments;
      const cur = segView.idxOf(ctx.selectedId);
      const n = Math.min(segs.length - 1, Math.max(0, (cur < 0 ? 0 : cur) + (e.key === 'ArrowDown' ? 1 : -1)));
      if (segs[n]) { segView.stopEdit(); segView.select(segs[n].id, { scroll: true }); }
      return;
    }
    if (mod && e.code === 'Space') { e.preventDefault(); player.toggle(); return; }
    if (e.code === 'Space' && !mod && !e.altKey && !inField && !t.closest?.('button,a,summary,[role="button"]')) { e.preventDefault(); player.toggle(); return; }
    if (e.key === 'Escape' && !inField) { if (ctx.find.open) toggleFind(false); return; }
    if ((e.key === 'Enter' || e.key === 'F2') && !inField && !mod && view === 'text' && ctx.selectedId && !t.closest?.('button,a,summary')) { e.preventDefault(); segView.startEdit(ctx.selectedId); }
  }
  document.addEventListener('keydown', onKey);
  const onBeforeUnload = (e) => { writeDraft.flush(); if (dirty() || saving) { e.preventDefault(); e.returnValue = T.editor.leaveWarning; } };
  window.addEventListener('beforeunload', onBeforeUnload);
  window.addEventListener('pagehide', writeDraft.flush);

  // ---- yerleşim ----
  const jobNote = tr.notice ? h('p', { class: 'note note-warn' }, `${T.queue.notice}: ${tr.notice}`) : null;
  const head = h('header', { class: 'ed-head' },
    h('a', { class: 'btn btn-ghost', href: '#/library' }, icon('library', 16), T.editor.back),
    titleInput, status,
    h('div', { class: 'ed-actions' }, undoBtn, redoBtn, findBtn, spkBtn, helpBtn, exportBtn));
  const bar = h('div', { class: 'ed-bar' }, viewToggle, timesCb.el, followCb.el, countEl);
  root.append(h('div', { class: 'editor' }, head, jobNote, player.el, bar, findPanel, spkPanel, scroller));
  if (draftNote) toast(T.editor.draftRestored, 'info', 7000);

  setView(view);
  drawUndo();
  drawStatus();
  if (dirty() || draftNote) { savedVersion = -1; drawStatus(); saveSoon(); }
  requestAnimationFrame(() => player.drawTimeline());

  return () => {
    document.removeEventListener('keydown', onKey);
    window.removeEventListener('beforeunload', onBeforeUnload);
    window.removeEventListener('pagehide', writeDraft.flush);
    clearTimeout(saveTimer);
    writeDraft.cancel();
    if (dirty()) { saveNow().catch(() => {}); }
    player.destroy();
  };
}
