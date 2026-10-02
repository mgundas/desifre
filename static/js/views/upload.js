import { T, fmt } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, icon, clear, combobox, field, checkbox, toast } from '../ui.js';
import { fmtBytes } from '../util.js';

const EXTS = new Set(['mp3', 'wav', 'm4a', 'aac', 'ogg', 'opus', 'flac', 'wma', 'mp4', 'mkv', 'mov', 'webm', 'avi']);
const extOf = (name) => (name.split('.').pop() || '').toLowerCase();

export async function mount(root) {
  const [settings, langs] = await Promise.all([api.get('/api/settings'), api.get('/api/languages')]);
  const opts = {
    language: settings.language, model: settings.model, task: settings.task, diarize: settings.diarize,
    min_speakers: null, max_speakers: null, initial_prompt: '',
  };
  let items = [];
  let busy = false;

  const fileInput = h('input', { type: 'file', multiple: true, class: 'sr-only', tabindex: '-1', accept: [...EXTS].map((e) => '.' + e).join(','), onChange: (e) => { addFiles(e.target.files); e.target.value = ''; } });
  const drop = h('div', {
    class: 'dropzone', role: 'button', tabindex: '0', 'aria-label': T.upload.choose,
    onClick: () => fileInput.click(),
    onKeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); } },
  },
  icon('upload', 40), h('strong', null, T.upload.dropTitle), h('span', null, T.upload.dropHint), h('small', null, T.upload.formats),
  h('span', { class: 'btn btn-primary', 'aria-hidden': 'true' }, T.upload.choose));
  ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', (e) => addFiles(e.dataTransfer.files));

  const listBox = h('div', { class: 'file-list' });
  const startBtn = h('button', { type: 'button', class: 'btn btn-primary btn-lg', onClick: start }, T.upload.start);

  function addFiles(fileList) {
    for (const f of fileList) {
      const ok = EXTS.has(extOf(f.name));
      items.push({ file: f, progress: 0, state: ok ? 'ready' : 'bad', error: ok ? '' : T.upload.unsupported });
    }
    drawList();
  }

  function drawList() {
    clear(listBox);
    if (!items.length) { listBox.append(h('p', { class: 'muted' }, T.upload.noFiles)); startBtn.disabled = true; return; }
    listBox.append(h('h2', { class: 'section-title' }, T.upload.files));
    items.forEach((it, i) => {
      const status = it.state === 'bad' ? h('span', { class: 'file-err' }, it.error)
        : it.state === 'error' ? h('span', { class: 'file-err' }, it.error)
          : it.state === 'done' ? h('span', { class: 'file-ok' }, icon('check', 16), T.upload.uploaded)
            : it.state === 'uploading' ? (it.bar = h('progress', { max: '1', value: String(it.progress), 'aria-label': it.file.name })) : null;
      listBox.append(h('div', { class: 'file-row' },
        h('span', { class: 'file-name' }, it.file.name), h('span', { class: 'muted' }, fmtBytes(it.file.size)), status,
        !busy && it.state !== 'done' ? h('button', { type: 'button', class: 'btn btn-ghost', onClick: () => { items.splice(i, 1); drawList(); } }, T.upload.remove) : null));
    });
    startBtn.disabled = busy || !items.some((i) => i.state === 'ready' || i.state === 'error');
  }

  async function start() {
    busy = true;
    startBtn.disabled = true;
    startBtn.textContent = T.upload.uploading;
    let okCount = 0;
    for (const it of items) {
      if (it.state !== 'ready' && it.state !== 'error') continue;
      it.state = 'uploading'; it.progress = 0; drawList();
      try {
        await api.upload(it.file, opts, (p) => { it.progress = p; if (it.bar) it.bar.value = p; });
        it.state = 'done'; okCount++;
      } catch (e) { it.state = 'error'; it.error = e.message; }
      drawList();
    }
    busy = false;
    startBtn.textContent = T.upload.start;
    drawList();
    if (okCount) {
      toast(`${okCount} ${T.upload.added}`, 'success');
      if (!items.some((i) => i.state === 'error')) location.hash = '#/queue';
    }
  }
  // ---- seçenekler ----
  const langItems = [{ value: 'auto', label: T.upload.autoDetect }, ...langs.languages.map((l) => ({ value: l.code, label: l.name }))];
  const lang = combobox({ items: langItems, value: opts.language, label: T.upload.language, placeholder: T.upload.languageSearch, noResults: T.upload.noLanguage, onChange: (v) => { opts.language = v; } });
  const model = h('select', { class: 'input', onChange: (e) => { opts.model = e.target.value; hint.textContent = T.upload.modelHints[opts.model] || ''; } },
    settings.models.map((m) => h('option', { value: m, selected: m === opts.model }, m)));
  const hint = h('span', { class: 'field-help' }, T.upload.modelHints[opts.model] || '');
  const task = h('select', { class: 'input', onChange: (e) => { opts.task = e.target.value; } },
    h('option', { value: 'transcribe', selected: opts.task === 'transcribe' }, T.upload.taskTranscribe),
    h('option', { value: 'translate', selected: opts.task === 'translate' }, T.upload.taskTranslate));
  const minSp = h('input', { type: 'number', class: 'input', min: 1, max: 20, disabled: !opts.diarize, onInput: (e) => { opts.min_speakers = e.target.value ? +e.target.value : null; } });
  const maxSp = h('input', { type: 'number', class: 'input', min: 1, max: 20, disabled: !opts.diarize, onInput: (e) => { opts.max_speakers = e.target.value ? +e.target.value : null; } });
  const warn = h('p', { class: 'note note-warn', hidden: !(opts.diarize && !settings.hf_token_set) }, T.upload.diarizeNeedsToken);
  const diar = checkbox(T.upload.diarize, opts.diarize, (v) => {
    opts.diarize = v; minSp.disabled = maxSp.disabled = !v; warn.hidden = !(v && !settings.hf_token_set);
  });
  const prompt = h('textarea', { class: 'input', rows: 2, maxlength: 1000, placeholder: T.upload.promptHint, onInput: (e) => { opts.initial_prompt = e.target.value; } });

  const optionsCard = h('section', { class: 'card' },
    h('h2', { class: 'section-title' }, T.upload.options),
    h('div', { class: 'grid-2' },
      h('div', { class: 'field' }, h('span', { class: 'field-label' }, T.upload.language), lang.el),
      h('label', { class: 'field' }, h('span', { class: 'field-label' }, T.upload.model), model, hint),
      field(T.upload.task, task)),
    h('div', { class: 'stack' }, diar.el,
      h('div', { class: 'grid-2' }, field(T.upload.minSpeakers, minSp), field(T.upload.maxSpeakers, maxSp)), warn),
    field(T.upload.prompt, prompt));

  root.append(h('div', { class: 'page page-narrow' },
    h('h1', null, T.upload.title), fileInput, drop, listBox, optionsCard, h('div', { class: 'actions-end' }, startBtn)));
  drawList();
}
