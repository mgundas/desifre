import { T } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, openDialog, field, checkbox, toast } from '../ui.js';

const FORMATS = ['txt', 'srt', 'vtt', 'docx', 'json', 'csv'];

/** Dışa aktarma seçeneklerini sorar, sonra dosyayı indirir. beforeDownload kaydı sunucuya yazmak için kullanılır. */
export async function exportDialog(transcriptId, { beforeDownload } = {}) {
  const s = await api.get('/api/settings');
  const sub = s.subtitle;
  const state = { fmt: 'srt', timestamps: true, speakers: true, prefix: !!sub.speaker_prefix, max_chars: sub.max_chars, max_lines: sub.max_lines, max_dur: sub.max_dur, min_dur: sub.min_dur };

  const subtitleBox = h('div', { class: 'stack' });
  const textBox = h('div', { class: 'stack' });
  const num = (label, key, min, max, step = 1) => field(label, h('input', { type: 'number', class: 'input', min, max, step, value: state[key], onInput: (e) => { state[key] = +e.target.value; } }));

  function refresh() {
    const isSub = state.fmt === 'srt' || state.fmt === 'vtt';
    const isText = state.fmt === 'txt' || state.fmt === 'docx';
    subtitleBox.hidden = !isSub;
    textBox.hidden = !isText;
  }

  textBox.append(
    checkbox(T.export.timestamps, state.timestamps, (v) => { state.timestamps = v; }).el,
    checkbox(T.export.speakerNames, state.speakers, (v) => { state.speakers = v; }).el);
  subtitleBox.append(
    h('h3', { class: 'section-title' }, T.export.subtitleRules),
    h('div', { class: 'grid-2' }, num(T.export.maxChars, 'max_chars', 10, 120), num(T.export.maxLines, 'max_lines', 1, 4), num(T.export.maxDur, 'max_dur', 1, 30, 0.5), num(T.export.minDur, 'min_dur', 0, 10, 0.5)),
    checkbox(T.export.speakerPrefix, state.prefix, (v) => { state.prefix = v; }).el);

  const radios = h('div', { class: 'radio-group', role: 'radiogroup', 'aria-label': T.export.format },
    FORMATS.map((f) => h('label', { class: 'radio' }, h('input', { type: 'radio', name: 'fmt', value: f, checked: f === state.fmt, onChange: () => { state.fmt = f; refresh(); } }), T.export.formats[f])));

  openDialog({
    title: T.export.title,
    body: h('div', { class: 'stack' }, radios, textBox, subtitleBox),
    actions: [
      { label: T.common.cancel, value: null },
      { label: T.export.download, primary: true, onClick: async (close) => {
        try { if (beforeDownload) await beforeDownload(); } catch (e) { toast(e.message, 'error'); return false; }
        const q = new URLSearchParams();
        if (state.fmt === 'txt' || state.fmt === 'docx') { q.set('timestamps', state.timestamps ? '1' : '0'); q.set('speakers', state.speakers ? '1' : '0'); }
        if (state.fmt === 'srt' || state.fmt === 'vtt') {
          q.set('max_chars', state.max_chars); q.set('max_lines', state.max_lines); q.set('max_dur', state.max_dur); q.set('min_dur', state.min_dur); q.set('speaker_prefix', state.prefix ? '1' : '0');
        }
        const a = h('a', { href: `/api/transcripts/${transcriptId}/export/${state.fmt}?${q}`, download: '' });
        document.body.append(a); a.click(); a.remove();
        close(true);
      } },
    ],
  });
  refresh();
}
