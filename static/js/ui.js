// Küçük arayüz yardımcıları: DOM kurucu, simgeler, iletişim kutusu, bildirim, arama kutusu.
import { T } from '../i18n/tr.js';
import { trIncludes } from './util.js';

const PROPS = new Set(['value', 'checked', 'disabled', 'selected', 'hidden', 'readOnly', 'indeterminate', 'min', 'max', 'step', 'rows']);

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (PROPS.has(k)) el[k] = v;
      else el.setAttribute(k, v === true ? '' : String(v));
    }
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function clear(el) { el.replaceChildren(); return el; }

const ICONS = {
  upload: 'M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3',
  library: 'M4 6h16M4 12h16M4 18h10',
  queue: 'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  settings: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5a2 2 0 100 4 2 2 0 000-4zM9 15a2 2 0 100 4 2 2 0 000-4z',
  play: 'M7 4.5v15l12-7.5z',
  pause: 'M8 5v14M16 5v14',
  back: 'M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8M3 3v5h5',
  fwd: 'M21 12a9 9 0 11-9-9 9 9 0 016.4 2.6L21 8M21 3v5h-5',
  undo: 'M9 14L4 9l5-5M4 9h10a6 6 0 010 12h-3',
  redo: 'M15 14l5-5-5-5M20 9H10a6 6 0 000 12h3',
  search: 'M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-4.3-4.3',
  download: 'M12 4v12m0 0l-4-4m4 4l4-4M4 20h16',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  edit: 'M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4',
  sun: 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M5 19l1.4-1.4M17.6 6.4L19 5',
  moon: 'M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z',
  monitor: 'M3 5h18v11H3zM8 20h8M12 16v4',
  check: 'M5 12l5 5 9-10',
  x: 'M6 6l12 12M18 6L6 18',
  help: 'M12 21a9 9 0 100-18 9 9 0 000 18zM9.5 9.5a2.5 2.5 0 114 2c-.9.6-1.5 1-1.5 2M12 17h.01',
  up: 'M6 15l6-6 6 6',
  down: 'M6 9l6 6 6-6',
  plus: 'M12 5v14M5 12h14',
  split: 'M12 3v18M7 8l-4 4 4 4M17 8l4 4-4 4',
  merge: 'M12 3v6m0 0l-4-3m4 3l4-3M12 21v-6m0 0l-4 3m4-3l4 3',
  users: 'M16 20v-1a4 4 0 00-4-4H7a4 4 0 00-4 4v1M9.5 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM21 20v-1a4 4 0 00-3-3.9M16 4.1a3.5 3.5 0 010 6.8',
  alert: 'M12 9v4m0 4h.01M10.3 4l-8 14a2 2 0 001.7 3h16a2 2 0 001.7-3l-8-14a2 2 0 00-3.4 0z',
  file: 'M7 3h7l5 5v13H7zM14 3v5h5',
};
const FILLED = new Set(['play']);

export function icon(name, size = 18) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.setAttribute('class', 'icon');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', ICONS[name] || '');
  if (FILLED.has(name)) { p.setAttribute('fill', 'currentColor'); p.setAttribute('stroke', 'none'); }
  else { p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'currentColor'); p.setAttribute('stroke-width', '2'); p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round'); }
  svg.append(p);
  return svg;
}

/** Simgeli düğme. label erişilebilir ad ve ipucu olur. */
export function iconButton(name, label, onClick, extra = {}) {
  return h('button', { type: 'button', class: `btn icon-btn ${extra.class || ''}`, title: label, 'aria-label': label, onClick, disabled: extra.disabled }, icon(name, extra.size || 18));
}

// ---- bildirim ----
let toastHost = null;
export function toast(message, kind = 'info', ms = 4500) {
  if (!toastHost) {
    toastHost = h('div', { class: 'toasts', role: 'status', 'aria-live': 'polite' });
    document.body.append(toastHost);
  }
  const el = h('div', { class: `toast toast-${kind}` }, message);
  toastHost.append(el);
  setTimeout(() => el.remove(), ms);
}

// ---- iletişim kutusu ----
/** İçeriği verilen bir modal gösterir. close() çağrısı ya da Esc ile kapanır. */
export function openDialog({ title, body, actions = [], wide = false, onClose }) {
  const dlg = h('dialog', { class: `dialog ${wide ? 'wide' : ''}`, 'aria-labelledby': 'dlg-title' });
  const close = (result) => { dlg.close(); dlg.remove(); onClose?.(result); };
  const head = h('div', { class: 'dialog-head' }, h('h2', { id: 'dlg-title' }, title), iconButton('x', T.common.close, () => close(null)));
  const foot = actions.length ? h('div', { class: 'dialog-foot' }, actions.map((a) => h('button', {
    type: 'button', class: `btn ${a.primary ? 'btn-primary' : a.danger ? 'btn-danger' : ''}`,
    onClick: () => { if (a.onClick) { const r = a.onClick(close); if (r === false) return; } else close(a.value); },
  }, a.label))) : null;
  dlg.append(head, h('div', { class: 'dialog-body' }, body), foot);
  dlg.addEventListener('cancel', (e) => { e.preventDefault(); close(null); });
  document.body.append(dlg);
  dlg.showModal();
  dlg.querySelector('input,select,textarea,button.btn-primary')?.focus();
  return { close, el: dlg };
}

export function confirmDialog({ title, message, confirmLabel, danger = false, extra = null }) {
  return new Promise((resolve) => {
    openDialog({
      title, body: [h('p', null, message), extra],
      actions: [{ label: T.common.cancel, value: false }, { label: confirmLabel, primary: !danger, danger, value: true }],
      onClose: (r) => resolve(r === true),
    });
  });
}

export function promptDialog({ title, label, value = '' }) {
  return new Promise((resolve) => {
    const input = h('input', { type: 'text', class: 'input', value, 'aria-label': label, maxlength: 200 });
    let result = null;
    const d = openDialog({
      title,
      body: h('label', { class: 'field' }, h('span', { class: 'field-label' }, label), input),
      actions: [{ label: T.common.cancel, value: null }, { label: T.common.save, primary: true, onClick: (close) => { result = input.value.trim(); if (!result) return false; close(result); } }],
      onClose: (r) => resolve(r),
    });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const v = input.value.trim(); if (v) d.close(v); } });
    input.select();
  });
}

// ---- arama kutusu (Türkçe harf duyarlı) ----
export function combobox({ items, value, onChange, placeholder, label, noResults }) {
  const input = h('input', { type: 'text', class: 'input', role: 'combobox', 'aria-expanded': 'false', 'aria-autocomplete': 'list', 'aria-label': label, placeholder, autocomplete: 'off' });
  const list = h('ul', { class: 'combo-list', role: 'listbox', hidden: true });
  const wrap = h('div', { class: 'combo' }, input, list);
  let current = value;
  let active = -1;
  let shown = [];
  const labelOf = (v) => items.find((i) => i.value === v)?.label ?? '';
  const setInput = () => { input.value = labelOf(current); };
  const open = () => { list.hidden = false; input.setAttribute('aria-expanded', 'true'); };
  const closeList = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; };
  const choose = (it) => { current = it.value; setInput(); closeList(); onChange?.(current); };
  const render = (q) => {
    shown = q ? items.filter((i) => trIncludes(i.label, q)) : items;
    clear(list);
    if (!shown.length) list.append(h('li', { class: 'combo-empty' }, noResults));
    shown.forEach((it, idx) => list.append(h('li', {
      role: 'option', class: `combo-item ${it.value === current ? 'selected' : ''}`, 'aria-selected': String(it.value === current),
      onMousedown: (e) => { e.preventDefault(); choose(it); },
    }, it.label)));
    active = shown.length ? 0 : -1;
    mark();
  };
  const mark = () => [...list.children].forEach((li, i) => { li.classList.toggle('active', i === active); if (i === active) li.scrollIntoView({ block: 'nearest' }); });
  input.addEventListener('focus', () => { input.select(); render(''); open(); });
  input.addEventListener('input', () => { render(input.value); open(); });
  input.addEventListener('blur', () => { closeList(); setInput(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); if (list.hidden) { render(''); open(); } else { active = Math.min(active + 1, shown.length - 1); mark(); } }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(active - 1, 0); mark(); }
    else if (e.key === 'Enter') { if (!list.hidden && shown[active]) { e.preventDefault(); choose(shown[active]); } }
    else if (e.key === 'Escape') { closeList(); setInput(); }
  });
  setInput();
  return { el: wrap, get value() { return current; }, set value(v) { current = v; setInput(); } };
}

/** Etiketli form alanı. */
export function field(labelText, control, help) {
  return h('label', { class: 'field' }, h('span', { class: 'field-label' }, labelText), control, help ? h('span', { class: 'field-help' }, help) : null);
}

export function checkbox(labelText, checked, onChange, help) {
  const input = h('input', { type: 'checkbox', checked, onChange: (e) => onChange?.(e.target.checked) });
  return { el: h('label', { class: 'check' }, input, h('span', null, labelText, help ? h('small', { class: 'field-help' }, help) : null)), input };
}

export function statusChip(status) {
  return h('span', { class: `chip chip-${{ 'beklemede': 'wait', 'işleniyor': 'run', 'tamamlandı': 'done', 'hata': 'err', 'iptal': 'cancel' }[status] || 'wait'}` }, T.status[status] || status);
}

export function emptyState(text, action) {
  return h('div', { class: 'empty' }, icon('file', 36), h('p', null, text), action);
}

/** Anahtarlı uzlaştırma: mevcut DOM düğümlerini yeniden kullanarak listeyi günceller. */
export function reconcile(container, items, keyOf, create, update) {
  const existing = new Map();
  for (const child of [...container.children]) if (child.__key !== undefined) existing.set(child.__key, child);
  let ref = container.firstElementChild;
  const seen = new Set();
  for (const item of items) {
    const key = keyOf(item);
    seen.add(key);
    let el = existing.get(key);
    if (!el) { el = create(item); el.__key = key; }
    else update(el, item);
    if (el === ref) ref = ref.nextElementSibling;
    else container.insertBefore(el, ref);
  }
  for (const [key, el] of existing) if (!seen.has(key)) el.remove();
}
