import { T, fmt } from '../i18n/tr.js';
import { h, icon, toast, clear } from './ui.js';
import { startEvents, onJobs, activeJobs } from './events.js';
import { storageGet, storageSet } from './util.js';

const NAV = [
  { id: 'upload', label: T.nav.upload, icon: 'upload' },
  { id: 'library', label: T.nav.library, icon: 'library' },
  { id: 'queue', label: T.nav.queue, icon: 'queue' },
  { id: 'settings', label: T.nav.settings, icon: 'settings' },
];

const VIEWS = {
  upload: () => import('./views/upload.js'),
  library: () => import('./views/library.js'),
  queue: () => import('./views/queue.js'),
  settings: () => import('./views/settings.js'),
  t: () => import('./views/editor.js'),
};

let cleanup = null;
let navToken = 0;

// ---- tema ----
const THEMES = ['auto', 'light', 'dark'];
function applyTheme(t) {
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
  else delete document.documentElement.dataset.theme;
}
function themeButton() {
  let cur = storageGet('desifre:theme', 'auto');
  const btn = h('button', { type: 'button', class: 'btn nav-theme' });
  const label = () => ({ auto: T.nav.themeAuto, light: T.nav.themeLight, dark: T.nav.themeDark })[cur];
  const draw = () => {
    clear(btn);
    btn.append(icon({ auto: 'monitor', light: 'sun', dark: 'moon' }[cur], 18), h('span', { class: 'nav-label' }, `${T.nav.theme}: ${label()}`));
    btn.title = `${T.nav.theme}: ${label()}`;
    btn.setAttribute('aria-label', btn.title);
  };
  btn.addEventListener('click', () => {
    cur = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
    storageSet('desifre:theme', cur);
    applyTheme(cur);
    draw();
  });
  draw();
  return btn;
}

// ---- kabuk ----
function buildShell() {
  const app = document.getElementById('app');
  const badge = h('span', { class: 'badge', hidden: true });
  const links = NAV.map((n) => h('a', { href: `#/${n.id}`, class: 'nav-link', 'data-nav': n.id },
    icon(n.icon, 20), h('span', { class: 'nav-label' }, n.label), n.id === 'queue' ? badge : null));
  const sidebar = h('nav', { class: 'sidebar', 'aria-label': T.nav.main },
    h('div', { class: 'brand' }, h('span', { class: 'brand-mark', 'aria-hidden': 'true' }, 'D'), h('span', { class: 'brand-text' }, h('strong', null, T.app.name), h('small', null, T.app.tagline))),
    h('div', { class: 'nav-links' }, links),
    h('div', { class: 'nav-foot' }, themeButton()));
  const main = h('main', { id: 'main', class: 'main', tabindex: '-1' });
  clear(app).append(sidebar, main);
  onJobs(() => {
    const n = activeJobs().length;
    badge.hidden = n === 0;
    badge.textContent = String(n);
  });
  return main;
}

function setActive(name) {
  const key = name === 't' ? 'library' : name;
  document.querySelectorAll('.nav-link').forEach((a) => {
    const on = a.dataset.nav === key;
    a.classList.toggle('active', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}

async function route(main) {
  const token = ++navToken;
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  let name = parts[0] || 'upload';
  if (!VIEWS[name]) name = 'upload';
  if (cleanup) { try { cleanup(); } catch (e) { console.error(e); } cleanup = null; }
  setActive(name);
  clear(main);
  main.classList.toggle('main-editor', name === 't');
  try {
    const mod = await VIEWS[name]();
    if (token !== navToken) return;
    const res = await mod.mount(main, { id: parts[1] });
    if (token !== navToken) { res?.(); return; }
    cleanup = typeof res === 'function' ? res : null;
  } catch (e) {
    console.error(e);
    main.append(h('div', { class: 'empty' }, icon('alert', 36), h('p', null, T.errors.loadFailed)));
  }
}

function init() {
  const main = buildShell();
  startEvents();
  onJobs((changes) => {
    for (const c of changes) {
      if (!c.from) continue;
      if (c.to === 'tamamlandı' && c.from === 'işleniyor') toast(`${c.job.title || c.job.orig_name}: ${T.toast.jobDone}`, 'success');
      if (c.to === 'hata' && c.from === 'işleniyor') toast(`${c.job.title || c.job.orig_name}: ${c.job.error || T.toast.jobFailed}`, 'error', 8000);
    }
  });
  window.addEventListener('hashchange', () => route(main));
  route(main);
}

init();
