// "Altyazı" görünümü: sunucudaki segmenter kurallarıyla üretilen kesitler, düzenlenebilir.
import { T, fmt } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, reconcile, toast } from '../ui.js';
import * as ops from './ops.js';
import { debounce, fmtClock, fmtNum } from '../util.js';

const MAX_CPS = 20;

export function createCuesView(ctx) {
  const { store } = ctx;
  const el = h('div', { class: 'cue-list', role: 'list' });
  let cues = [];
  let token = 0;
  let playingIdx = -1;

  async function refresh() {
    const my = ++token;
    try {
      const r = await api.post('/api/cues', { segments: store.state.segments });
      if (my !== token) return;
      cues = r.cues;
      render();
      ctx.onCuesChanged?.(cues.length);
    } catch (e) { toast(e.message, 'error'); }
  }
  const refreshSoon = debounce(refresh, 350);

  const btn = (act, label) => h('button', { type: 'button', class: 'btn btn-sm', dataset: { act }, 'aria-label': label, title: label }, label);

  function create({ c, i }) {
    const ta = h('textarea', { class: 'cue-edit', rows: 2, lang: 'tr', spellcheck: 'true', 'aria-label': T.editor.cueText });
    ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ta.blur(); } if (e.key === 'Escape') ta.blur(); });
    ta.addEventListener('change', () => commit(row));
    ta.addEventListener('input', () => fit(ta));
    const row = h('div', { class: 'cue', role: 'listitem' },
      h('div', { class: 'cue-meta' },
        h('span', { class: 'cue-n' }), h('button', { type: 'button', class: 'cue-time', dataset: { act: 'seek' }, title: T.editor.playSeg }),
        h('span', { class: 'cue-stats muted' })),
      ta,
      h('div', { class: 'cue-tools' },
        h('div', { class: 'tool-group' }, h('span', { class: 'tool-label' }, T.editor.cueStart), btn('start-', T.editor.nudgeMinus), btn('start+', T.editor.nudgePlus), btn('start-now', T.editor.setNow)),
        h('div', { class: 'tool-group' }, h('span', { class: 'tool-label' }, T.editor.cueEnd), btn('end-', T.editor.nudgeMinus), btn('end+', T.editor.nudgePlus), btn('end-now', T.editor.setNow))));
    row.__ta = ta;
    update(row, { c, i });
    return row;
  }

  function fit(ta) { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight}px`; }

  function update(row, { c, i }) {
    row.__cue = c;
    row.__idx = i;
    row.querySelector('.cue-n').textContent = String(i + 1);
    row.querySelector('.cue-time').textContent = `${fmtClock(c.start, true)} → ${fmtClock(c.end, true)}`;
    const dur = c.end - c.start;
    const chars = c.text.replace(/\n/g, '').length;
    const cps = dur > 0 ? chars / dur : 0;
    const longDur = dur > ctx.rules.max_dur + 0.01;
    const fast = cps > MAX_CPS;
    row.classList.toggle('warn', longDur || fast);
    row.querySelector('.cue-stats').textContent = `${fmtNum(dur)} ${T.common.seconds} · ${fmtNum(cps)} ${T.editor.cueChars}${longDur ? ` · ${T.editor.cueTooLong}` : ''}${fast ? ` · ${T.editor.cueFast}` : ''}`;
    const ta = row.__ta;
    if (document.activeElement !== ta && ta.value !== c.text) ta.value = c.text;
    ta.rows = Math.max(1, c.lines.length);
    requestAnimationFrame(() => fit(ta));
    row.classList.toggle('playing', i === playingIdx);
  }

  function render() {
    reconcile(el, cues.map((c, i) => ({ c, i })), (it) => `c${it.i}`, create, update);
  }

  function commit(row) {
    const cue = row.__cue;
    const segs = store.state.segments;
    const si = segs.findIndex((s) => s.id === cue.seg_id);
    if (si < 0) return;
    const words = ops.ensureWords(segs[si]).words;
    const current = words.slice(cue.w0, cue.w1).map((w) => w.word).join(' ');
    if (current !== cue.text.replace(/\n/g, ' ')) { refresh(); return; } // eskimiş kesit, uygulamadan yenile
    const text = row.__ta.value.replace(/\s+/g, ' ').trim();
    if (!text || text === current) { row.__ta.value = cue.text; return; }
    store.apply({ segments: ops.replaceCueText(segs, si, cue.w0, cue.w1, text) });
  }

  function act(name, row) {
    const cue = row.__cue;
    const segs = store.state.segments;
    const si = segs.findIndex((s) => s.id === cue.seg_id);
    if (si < 0) return;
    const key = `cue:${cue.seg_id}:${cue.w0}`;
    const apply = (s, k) => store.apply({ segments: s }, { key: k });
    switch (name) {
      case 'seek': ctx.player.seek(cue.start); ctx.player.media.play().catch(() => {}); break;
      case 'start-': apply(ops.nudgeWord(segs, si, cue.w0, 'start', -0.1), `${key}:s`); break;
      case 'start+': apply(ops.nudgeWord(segs, si, cue.w0, 'start', 0.1), `${key}:s`); break;
      case 'end-': apply(ops.nudgeWord(segs, si, cue.w1 - 1, 'end', -0.1), `${key}:e`); break;
      case 'end+': apply(ops.nudgeWord(segs, si, cue.w1 - 1, 'end', 0.1), `${key}:e`); break;
      case 'start-now': apply(ops.setWordTime(segs, si, cue.w0, 'start', ctx.player.time)); break;
      case 'end-now': apply(ops.setWordTime(segs, si, cue.w1 - 1, 'end', ctx.player.time)); break;
      default: break;
    }
  }

  el.addEventListener('mousedown', (e) => { if (e.target.closest('.cue-tools button')) e.preventDefault(); });
  el.addEventListener('click', (e) => {
    const row = e.target.closest('.cue');
    if (!row) return;
    const a = e.target.closest('[data-act]');
    if (a) { act(a.dataset.act, row); return; }
    if (!e.target.closest('textarea')) ctx.player.seek(row.__cue.start);
  });

  function onTime(t) {
    const idx = ops.segmentAt(cues, t);
    if (idx === playingIdx) return;
    el.children[playingIdx]?.classList.remove('playing');
    playingIdx = idx;
    const row = el.children[idx];
    if (row) {
      row.classList.add('playing');
      if (ctx.follow && Date.now() > ctx.userScrollUntil() && !ctx.player.paused) ctx.scrollToRow(row);
    }
  }

  return { el, refresh, refreshSoon, render, onTime, get count() { return cues.length; } };
}
