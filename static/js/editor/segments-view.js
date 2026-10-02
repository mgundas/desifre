// "Metin" görünümü: konuşmacı turlarına ayrılmış, tıklanınca oynatan, çift tıklanınca düzenlenen bölüm listesi.
import { T, fmt } from '../../i18n/tr.js';
import { h, icon, clear, reconcile } from '../ui.js';
import * as ops from './ops.js';
import { fmtClock } from '../util.js';

export function createSegmentsView(ctx) {
  const { store } = ctx;
  const el = h('div', { class: 'seg-list', role: 'list', tabindex: '0', 'aria-label': T.editor.viewText });
  let rows = new Map();
  let playingId = null;
  let playingWord = -1;
  let userScrollUntil = 0;

  const idxOf = (id) => store.state.segments.findIndex((s) => s.id === id);
  const spkColor = (id) => store.state.speakers[id]?.color || 'var(--muted)';
  const spkName = (id) => (store.state.speakers[id]?.name || '').trim() || ops.defaultSpeakerName(id);
  const apply = (segments, key) => store.apply({ segments }, { key });

  // ---- satır çizimi ----
  function chip(id) {
    return h('span', { class: 'spk-chip', dataset: { spk: id }, style: { '--c': spkColor(id) } }, h('i', { class: 'dot' }), h('span', null, spkName(id)));
  }

  function btn(act, label, extra = {}) {
    return h('button', { type: 'button', class: `btn btn-sm ${extra.class || ''}`, dataset: { act }, title: extra.title || label, 'aria-label': extra.title || label, disabled: extra.disabled }, extra.icon ? icon(extra.icon, 15) : null, label);
  }

  function toolbar(seg, i) {
    const segs = store.state.segments;
    const options = [h('option', { value: '' }, T.editor.noSpeaker), ...Object.keys(store.state.speakers).map((id) => h('option', { value: id, selected: id === seg.speaker }, spkName(id))), h('option', { value: '__new' }, `+ ${T.editor.newSpeaker}`)];
    const select = h('select', { class: 'input input-sm', dataset: { act: 'speaker' }, 'aria-label': T.editor.speakerOf }, options);
    if (!seg.speaker) select.value = '';
    const group = (label, ...kids) => h('div', { class: 'tool-group' }, h('span', { class: 'tool-label' }, label), kids);
    return h('div', { class: 'seg-tools', role: 'toolbar', 'aria-label': T.editor.speakerOf },
      group(T.editor.speakerOf, select),
      group(T.editor.startTime, btn('start-', T.editor.nudgeMinus), btn('start+', T.editor.nudgePlus), btn('start-now', T.editor.setNow)),
      group(T.editor.endTime, btn('end-', T.editor.nudgeMinus), btn('end+', T.editor.nudgePlus), btn('end-now', T.editor.setNow)),
      h('div', { class: 'tool-group tool-actions' },
        btn('play', T.editor.playSeg, { icon: 'play' }),
        btn('split', T.editor.split, { icon: 'split', title: T.editor.splitHelp }),
        btn('merge', T.editor.merge, { icon: 'merge', disabled: i >= segs.length - 1 }),
        btn('delete', T.editor.deleteSeg, { icon: 'trash', class: 'btn-danger-ghost' })));
  }

  function wordsEl(seg) {
    const words = seg.words && seg.words.length ? seg.words : ops.ensureWords(seg).words;
    const marks = ctx.find.bySegId.get(seg.id) || [];
    const box = h('div', { class: 'seg-text', title: T.editor.editHint });
    let off = 0;
    words.forEach((w, i) => {
      const len = w.word.length;
      const m = marks.find((x) => off < x.to && off + len > x.from);
      box.append(h('span', { class: `w${m ? (m.current ? ' match match-cur' : ' match') : ''}`, dataset: { i } }, w.word), ' ');
      off += len + 1;
    });
    if (!words.length) box.append(h('span', { class: 'muted' }, '…'));
    return box;
  }

  function editor(seg, row) {
    const ta = h('textarea', { class: 'seg-edit', rows: 1, 'aria-label': T.editor.editing, spellcheck: 'true', lang: 'tr' });
    ta.value = seg.text;
    const fit = () => { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight}px`; };
    ta.addEventListener('input', () => {
      fit();
      const i = idxOf(seg.id);
      if (i >= 0) apply(ops.setText(store.state.segments, i, ta.value), `text:${seg.id}`);
    });
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.shiftKey) { e.preventDefault(); e.stopPropagation(); splitFromTextarea(seg.id, ta); return; }
      if (e.key === 'Enter' || e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); stopEdit(); el.focus({ preventScroll: true }); }
    });
    ta.addEventListener('focusout', () => {
      setTimeout(() => { if (ctx.editingId === seg.id && !row.contains(document.activeElement)) stopEdit(); }, 0);
    });
    requestAnimationFrame(fit);
    return ta;
  }

  function sigOf(seg, ts) {
    const sel = ctx.selectedId === seg.id;
    const marks = (ctx.find.bySegId.get(seg.id) || []).map((m) => `${m.from}-${m.to}${m.current ? 'c' : ''}`).join(',');
    return `${ts}|${sel}|${ctx.editingId === seg.id}|${ctx.showTimes}|${marks}|${sel ? ctx.speakersRev : ''}|${sel ? store.state.segments.length : ''}`;
  }

  function fill(row, seg, i, ts) {
    const editing = ctx.editingId === seg.id;
    const selected = ctx.selectedId === seg.id;
    row.className = `seg${selected ? ' selected' : ''}${editing ? ' editing' : ''}${ts ? ' turn-start' : ''}${seg.id === playingId ? ' playing' : ''}${seg.text ? '' : ' empty'}`;
    row.style.setProperty('--c', seg.speaker ? spkColor(seg.speaker) : 'transparent');
    clear(row);
    if (ts && seg.speaker) row.append(h('div', { class: 'seg-head' }, chip(seg.speaker)));
    const body = editing ? editor(seg, row) : wordsEl(seg);
    row.append(h('div', { class: 'seg-main' },
      ctx.showTimes ? h('button', { type: 'button', class: 'seg-time', dataset: { act: 'seek' }, title: T.editor.playSeg }, h('span', { class: 'seg-t-start' }, fmtClock(seg.start, true)), h('span', { class: 'seg-t-end' }, fmtClock(seg.end, true))) : null,
      body));
    if (selected) row.append(toolbar(seg, i));
    row.__seg = seg;
    row.__sig = sigOf(seg, ts);
    row.__editing = editing;
    if (seg.id === playingId && playingWord >= 0) markWord(row, playingWord, true);
  }

  function refreshTimes(row, seg) {
    const a = row.querySelector('.seg-t-start'), b = row.querySelector('.seg-t-end');
    if (a) a.textContent = fmtClock(seg.start, true);
    if (b) b.textContent = fmtClock(seg.end, true);
  }

  function render() {
    const segs = store.state.segments;
    if (!segs.length) { clear(el); rows.clear(); el.append(h('div', { class: 'empty' }, h('p', null, T.editor.emptyTranscript))); return; }
    const items = segs.map((s, i) => ({ s, i, ts: i === 0 || (segs[i - 1].speaker || null) !== (s.speaker || null) }));
    reconcile(el, items, (it) => it.s.id,
      (it) => { const row = h('div', { role: 'listitem', dataset: { id: it.s.id } }); fill(row, it.s, it.i, it.ts); return row; },
      (row, it) => {
        if (row.__editing && ctx.editingId === it.s.id) { row.__seg = it.s; refreshTimes(row, it.s); return; }
        if (row.__seg === it.s && row.__sig === sigOf(it.s, it.ts)) return;
        fill(row, it.s, it.i, it.ts);
      });
    el.querySelector(':scope > .empty')?.remove();
    rows = new Map([...el.children].filter((c) => c.__key !== undefined).map((c) => [c.__key, c]));
  }

  // ---- seçim ve düzenleme ----
  function select(id, { seek = false, scroll = false } = {}) {
    if (ctx.selectedId === id && !seek && !scroll) return;
    ctx.selectedId = id;
    render();
    const row = rows.get(id);
    if (scroll && row) scrollToRow(row, true);
    if (seek) { const seg = store.state.segments[idxOf(id)]; if (seg) ctx.player.seek(seg.start); }
  }

  function startEdit(id, wordIndex = null) {
    const i = idxOf(id);
    if (i < 0) return;
    ctx.editingId = id;
    ctx.selectedId = id;
    render();
    const ta = rows.get(id)?.querySelector('textarea');
    if (!ta) return;
    ta.focus({ preventScroll: true });
    let pos = ta.value.length;
    if (wordIndex !== null) {
      const words = store.state.segments[i].words || [];
      pos = words.slice(0, wordIndex).reduce((a, w) => a + w.word.length + 1, 0);
    }
    ta.setSelectionRange(pos, pos);
  }

  function stopEdit() {
    if (!ctx.editingId) return;
    ctx.editingId = null;
    render();
  }

  function splitFromTextarea(id, ta) {
    const i = idxOf(id);
    if (i < 0) return;
    let segs = ops.setText(store.state.segments, i, ta.value);
    const caret = ta.value.slice(0, ta.selectionStart).replace(/\s+/g, ' ').trimStart().length;
    const next = ops.splitAtChar(segs, i, caret);
    if (next === segs) return;
    store.apply({ segments: next }, { key: null });
    ctx.editingId = null;
    render();
    startEdit(next[i + 1].id, 0);
  }

  function doSplit(id) {
    const i = idxOf(id);
    const seg = store.state.segments[i];
    if (!seg) return;
    const ta = ctx.editingId === id ? rows.get(id)?.querySelector('textarea') : null;
    if (ta) { splitFromTextarea(id, ta); return; }
    const t = ctx.player.time;
    const words = ops.ensureWords(seg).words;
    let next;
    if (t > seg.start && t < seg.end) next = ops.splitAtTime(store.state.segments, i, t);
    else next = ops.splitAt(store.state.segments, i, Math.ceil(words.length / 2));
    apply(next, null);
  }

  function newSpeaker() {
    const id = ops.nextSpeakerId(store.state.speakers, store.state.segments);
    const color = ctx.nextColor();
    store.apply({ speakers: { ...store.state.speakers, [id]: { name: '', color } } });
    ctx.speakersRev++;
    return id;
  }

  function act(name, id, target) {
    const i = idxOf(id);
    if (i < 0) return;
    const segs = store.state.segments;
    const seg = segs[i];
    switch (name) {
      case 'seek': ctx.player.seek(seg.start); break;
      case 'start-': apply(ops.nudge(segs, i, 'start', -0.1), `nudge:${id}:s`); break;
      case 'start+': apply(ops.nudge(segs, i, 'start', 0.1), `nudge:${id}:s`); break;
      case 'end-': apply(ops.nudge(segs, i, 'end', -0.1), `nudge:${id}:e`); break;
      case 'end+': apply(ops.nudge(segs, i, 'end', 0.1), `nudge:${id}:e`); break;
      case 'start-now': apply(ops.setTime(segs, i, 'start', ctx.player.time)); break;
      case 'end-now': apply(ops.setTime(segs, i, 'end', ctx.player.time)); break;
      case 'play': ctx.player.seek(seg.start); ctx.player.media.play().catch(() => {}); break;
      case 'split': doSplit(id); break;
      case 'merge': apply(ops.mergeNext(segs, i)); break;
      case 'delete': {
        const nextId = segs[i + 1]?.id || segs[i - 1]?.id || null;
        ctx.selectedId = nextId;
        if (ctx.editingId === id) ctx.editingId = null;
        apply(ops.deleteSegment(segs, i));
        break;
      }
      case 'speaker': {
        let val = target.value;
        if (val === '__new') {
          val = newSpeaker();
          apply(ops.setSpeaker(store.state.segments, i, val));
        } else apply(ops.setSpeaker(segs, i, val || null));
        break;
      }
      default: break;
    }
  }

  // ---- olaylar (olay delegasyonu) ----
  el.addEventListener('mousedown', (e) => {
    // araç çubuğu düğmeleri odağı metin alanından çalmasın
    if (e.target.closest('.seg-tools button')) e.preventDefault();
  });
  el.addEventListener('click', (e) => {
    const rowEl = e.target.closest('.seg');
    if (!rowEl) return;
    const id = rowEl.dataset.id;
    const actEl = e.target.closest('[data-act]');
    if (actEl && actEl.tagName !== 'SELECT') { if (ctx.selectedId !== id) { ctx.selectedId = id; } act(actEl.dataset.act, id, actEl); if (!ctx.editingId || ctx.editingId !== id) render(); return; }
    if (e.target.closest('textarea,select,.seg-tools')) return;
    const w = e.target.closest('.w');
    select(id);
    const seg = store.state.segments[idxOf(id)];
    if (!seg) return;
    if (w && seg.words?.[+w.dataset.i]) ctx.player.seek(seg.words[+w.dataset.i].start);
    else ctx.player.seek(seg.start);
  });
  el.addEventListener('change', (e) => {
    const sel = e.target.closest('select[data-act]');
    if (!sel) return;
    const rowEl = sel.closest('.seg');
    act(sel.dataset.act, rowEl.dataset.id, sel);
  });
  el.addEventListener('dblclick', (e) => {
    const rowEl = e.target.closest('.seg');
    if (!rowEl || e.target.closest('.seg-tools,textarea,.seg-time')) return;
    const w = e.target.closest('.w');
    startEdit(rowEl.dataset.id, w ? +w.dataset.i : null);
    window.getSelection()?.removeAllRanges();
  });
  el.addEventListener('keydown', (e) => {
    if (e.target !== el || e.ctrlKey || e.altKey || e.metaKey) return;
    const segs = store.state.segments;
    const cur = idxOf(ctx.selectedId);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const n = Math.min(segs.length - 1, Math.max(0, cur + (e.key === 'ArrowDown' ? 1 : -1)));
      if (segs[n]) select(segs[n].id, { scroll: true });
    }
  });

  // ---- oynatma eşleşmesi ----
  function markWord(row, wi, on) {
    const w = row.querySelector(`.w[data-i="${wi}"]`);
    if (w) w.classList.toggle('cur-word', on);
  }

  function scrollToRow(row, force = false) {
    const box = ctx.scroller;
    const top = row.offsetTop, bottom = top + row.offsetHeight;
    const vTop = box.scrollTop, vBot = vTop + box.clientHeight;
    if (force || top < vTop + 24 || bottom > vBot - 80) box.scrollTo({ top: Math.max(0, top - box.clientHeight * 0.3), behavior: force ? 'auto' : 'smooth' });
  }

  function onTime(t) {
    const segs = store.state.segments;
    const idx = ops.segmentAt(segs, t);
    const id = idx >= 0 ? segs[idx].id : null;
    if (id !== playingId) {
      const old = rows.get(playingId);
      if (old) { old.classList.remove('playing'); if (playingWord >= 0) markWord(old, playingWord, false); }
      playingId = id;
      playingWord = -1;
      const row = id ? rows.get(id) : null;
      if (row) {
        row.classList.add('playing');
        if (ctx.follow && Date.now() > userScrollUntil && !ctx.player.paused) scrollToRow(row);
      }
    }
    if (id) {
      const wi = ops.wordAt(segs[idx], t);
      if (wi !== playingWord) {
        const row = rows.get(id);
        if (row) { if (playingWord >= 0) markWord(row, playingWord, false); if (wi >= 0) markWord(row, wi, true); }
        playingWord = wi;
      }
    }
  }

  const noteUserScroll = () => { userScrollUntil = Date.now() + 4000; };

  function refreshChips() {
    el.querySelectorAll('.spk-chip').forEach((c) => {
      const id = c.dataset.spk;
      c.style.setProperty('--c', spkColor(id));
      c.lastChild.textContent = spkName(id);
    });
    el.querySelectorAll('.seg').forEach((r) => {
      const seg = r.__seg;
      r.style.setProperty('--c', seg?.speaker ? spkColor(seg.speaker) : 'transparent');
    });
  }

  return { el, render, onTime, select, startEdit, stopEdit, refreshChips, noteUserScroll, rowFor: (id) => rows.get(id), scrollToRow, idxOf };
}
