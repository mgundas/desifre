import { T, fmt } from '../../i18n/tr.js';
import { api } from '../api.js';
import { h, icon, clear, combobox, field, checkbox, toast } from '../ui.js';
import { fmtBytes, fmtInt } from '../util.js';

export async function mount(root) {
  const [s, sys, langs] = await Promise.all([api.get('/api/settings'), api.get('/api/system'), api.get('/api/languages')]);
  const sub = { ...s.subtitle };
  const v = {
    language: s.language, model: s.model, compute_type: s.compute_type, batch_size: s.batch_size, device: s.device,
    vad: s.vad, align: s.align, diarize: s.diarize, bom: s.bom, csv_delimiter: s.csv_delimiter, allow_lan: s.allow_lan,
    max_upload_mb: s.max_upload_mb, data_dir: s.data_dir_pending || s.data_dir,
  };
  let newToken = '';

  const sel = (key, options, label) => field(label, h('select', { class: 'input', onChange: (e) => { v[key] = e.target.value; } },
    options.map(([val, text]) => h('option', { value: val, selected: String(val) === String(v[key]) }, text))));
  const num = (obj, key, label, min, max, step = 1, help) => field(label, h('input', { type: 'number', class: 'input', min, max, step, value: obj[key], onInput: (e) => { obj[key] = e.target.value === '' ? obj[key] : +e.target.value; } }), help);

  const lang = combobox({
    items: [{ value: 'auto', label: T.upload.autoDetect }, ...langs.languages.map((l) => ({ value: l.code, label: l.name }))],
    value: v.language, label: T.settings.defaultLanguage, placeholder: T.upload.languageSearch, noResults: T.upload.noLanguage, onChange: (x) => { v.language = x; },
  });

  // ---- belirteç ----
  const tokenInput = h('input', { type: 'password', class: 'input', autocomplete: 'off', spellcheck: 'false', placeholder: s.hf_token_set ? T.settings.hfReplace : 'hf_…', onInput: (e) => { newToken = e.target.value.trim(); } });
  const tokenMsg = h('p', { class: 'note', hidden: true, role: 'status' });
  const savedInfo = h('p', { class: 'muted' }, s.hf_token_set ? `${T.settings.hfTokenSaved}: ${s.hf_token_masked}` : T.settings.hfNoToken);
  const testBtn = h('button', { type: 'button', class: 'btn', onClick: async () => {
    testBtn.disabled = true; testBtn.textContent = T.settings.hfTesting;
    try {
      const r = await api.post('/api/settings/hf-test', { token: newToken });
      tokenMsg.hidden = false; tokenMsg.className = `note ${r.ok ? 'note-ok' : 'note-error'}`; tokenMsg.textContent = r.message;
    } catch (e) { toast(e.message, 'error'); }
    testBtn.disabled = false; testBtn.textContent = T.common.test;
  } }, T.common.test);
  const clearBtn = h('button', { type: 'button', class: 'btn btn-ghost', hidden: !s.hf_token_set, onClick: async () => {
    try { await api.put('/api/settings', { hf_token: '' }); toast(T.settings.saved, 'success'); location.reload(); } catch (e) { toast(e.message, 'error'); }
  } }, T.settings.hfClear);

  // ---- sistem bilgisi ----
  const row = (k, val, ok) => h('tr', null, h('th', { scope: 'row' }, k), h('td', null, ok === undefined ? val : h('span', { class: ok ? 'file-ok' : 'file-err' }, icon(ok ? 'check' : 'x', 16), val)));
  const st = sys.storage;
  const sysTable = h('table', { class: 'table table-kv' }, h('tbody', null,
    row(T.settings.gpu, sys.gpu.name || T.settings.noGpu),
    sys.gpu.vram_mb ? row(T.settings.vram, `${fmtInt(Math.round(sys.gpu.vram_mb / 1024 * 10) / 10)} GB`) : null,
    sys.gpu.driver ? row(T.settings.driver, sys.gpu.driver) : null,
    row(T.settings.cuda, sys.cuda_available ? T.common.yes : T.common.no, sys.cuda_available),
    row(T.settings.ffmpeg, sys.ffmpeg ? T.common.yes : T.common.no, sys.ffmpeg),
    row(T.settings.python, sys.python), row(T.settings.whisperx, sys.whisperx || T.common.unknown), row(T.settings.ctranslate2, sys.ctranslate2 || T.common.unknown),
    row(T.settings.models, h('ul', { class: 'plain' }, sys.models.map((m) => h('li', null, `${m.name}: `, m.downloaded ? `${T.settings.downloaded} (${fmtBytes(m.size)})` : T.settings.notDownloaded))))));

  const dirInput = h('input', { type: 'text', class: 'input', value: v.data_dir, onInput: (e) => { v.data_dir = e.target.value.trim(); } });
  const saveBtn = h('button', { type: 'button', class: 'btn btn-primary btn-lg', onClick: save }, T.settings.saveBtn);

  async function save() {
    const body = { ...v, subtitle: sub };
    if (newToken) body.hf_token = newToken;
    if (body.data_dir === (s.data_dir_pending || s.data_dir)) delete body.data_dir;
    saveBtn.disabled = true;
    try {
      const r = await api.put('/api/settings', body);
      toast(r.restart_required ? `${T.settings.saved} ${T.settings.restartNeeded}` : T.settings.saved, 'success');
      if (newToken) location.reload();
    } catch (e) { toast(e.message, 'error'); }
    saveBtn.disabled = false;
  }

  const lanWarn = h('p', { class: 'note note-warn', hidden: !v.allow_lan }, T.settings.lanWarn);

  root.append(h('div', { class: 'page page-narrow' },
    h('h1', null, T.settings.title),
    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.general),
      h('div', { class: 'grid-2' },
        h('div', { class: 'field' }, h('span', { class: 'field-label' }, T.settings.defaultLanguage), lang.el),
        sel('model', s.models.map((m) => [m, m]), T.settings.defaultModel),
        sel('compute_type', s.compute_types.map((c) => [c, c === 'auto' ? T.common.auto : c]), T.settings.computeType),
        sel('device', [['auto', T.settings.deviceAuto], ['cuda', T.settings.deviceCuda], ['cpu', T.settings.deviceCpu]], T.settings.device),
        field(T.settings.batchSize, h('input', { type: 'number', class: 'input', min: 1, max: 64, value: v.batch_size, onInput: (e) => { v.batch_size = +e.target.value || v.batch_size; } }), T.settings.batchHelp)),
      h('p', { class: 'field-help' }, T.settings.computeHelp),
      checkbox(T.settings.vad, v.vad, (x) => { v.vad = x; }, T.settings.vadHelp).el,
      checkbox(T.settings.align, v.align, (x) => { v.align = x; }, T.settings.alignHelp).el,
      checkbox(T.settings.defaultDiarize, v.diarize, (x) => { v.diarize = x; }).el),

    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.diarization),
      field(T.settings.hfToken, tokenInput, T.settings.hfTokenHelp), savedInfo,
      h('div', { class: 'row' }, testBtn, clearBtn), tokenMsg,
      h('details', { class: 'details' }, h('summary', null, T.settings.hfStepsTitle),
        h('ol', null, T.settings.hfSteps.map((t) => h('li', null, t))))),

    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.subtitles),
      h('div', { class: 'grid-2' },
        num(sub, 'max_chars', T.settings.maxChars, 10, 120), num(sub, 'max_lines', T.settings.maxLines, 1, 4),
        num(sub, 'max_dur', T.settings.maxDur, 1, 30, 0.5), num(sub, 'min_dur', T.settings.minDur, 0, 10, 0.5)),
      checkbox(T.settings.prefix, sub.speaker_prefix, (x) => { sub.speaker_prefix = x; }).el),

    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.files),
      checkbox(T.settings.bom, v.bom, (x) => { v.bom = x; }, T.settings.bomHelp).el,
      sel('csv_delimiter', [[';', ';'], [',', ','], ['\t', 'Tab']], T.settings.csvDelimiter), h('p', { class: 'field-help' }, T.settings.csvHelp)),

    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.storage),
      field(T.settings.storageFolder, dirInput, T.settings.storageHelp),
      s.data_dir_pending ? h('p', { class: 'note note-warn' }, `${T.settings.storagePending}: ${s.data_dir_pending}`) : null,
      h('table', { class: 'table table-kv' }, h('tbody', null,
        row(T.settings.diskUsed, fmtBytes(st.total_bytes)), row(T.settings.diskUploads, fmtBytes(st.uploads_bytes)), row(T.settings.diskFree, fmtBytes(st.disk_free_bytes)))),
      num(v, 'max_upload_mb', T.settings.maxUpload, 1, 102400, 1)),

    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.network),
      checkbox(T.settings.allowLan, v.allow_lan, (x) => { v.allow_lan = x; lanWarn.hidden = !x; }).el, lanWarn),

    h('section', { class: 'card stack' }, h('h2', { class: 'section-title' }, T.settings.system), sysTable,
      !sys.ffmpeg ? h('p', { class: 'note note-error' }, T.settings.ffmpegHelp) : null,
      h('p', { class: 'field-help' }, T.settings.modelsHelp)),

    h('div', { class: 'actions-end sticky-actions' }, saveBtn)));
}
