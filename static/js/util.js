import { T } from '../i18n/tr.js';

export const trLower = (s) => (s || '').toLocaleLowerCase('tr-TR');
export const trUpper = (s) => (s || '').toLocaleUpperCase('tr-TR');
export const trIncludes = (hay, needle) => trLower(hay).includes(trLower(needle));

const dateFmt = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'medium', timeStyle: 'short' });
const numFmt = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1 });
const intFmt = new Intl.NumberFormat('tr-TR');

export const fmtDate = (epochSec) => (epochSec ? dateFmt.format(new Date(epochSec * 1000)) : '');
export const fmtNum = (n) => numFmt.format(n);
export const fmtInt = (n) => intFmt.format(n);

/** 3725.4 -> "1:02:05" ; 65 -> "1:05" ; ms=true -> "1:05,4" gibi ondalık ekler. */
export function fmtClock(sec, withMs = false) {
  sec = Math.max(0, sec || 0);
  const total = Math.floor(sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const base = h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
  if (!withMs) return base;
  return `${base},${String(Math.floor((sec - total) * 10))}`;
}

/** 135 -> "2 dk 15 sn" (insan okuyabilir süre) */
export function fmtDuration(sec) {
  if (sec == null || !isFinite(sec)) return '';
  sec = Math.round(sec);
  if (sec < 1) return `0 ${T.common.seconds}`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const parts = [];
  if (h) parts.push(`${h} ${T.common.hours}`);
  if (m) parts.push(`${m} ${T.common.minutes}`);
  if (s && !h) parts.push(`${s} ${T.common.seconds}`);
  return parts.join(' ');
}

export function fmtBytes(n) {
  const u = T.units.bytes;
  let i = 0;
  let v = n || 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${numFmt.format(v)} ${u[i]}`;
}

export function debounce(fn, ms) {
  let t;
  const wrapped = (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  wrapped.flush = (...a) => { clearTimeout(t); fn(...a); };
  wrapped.cancel = () => clearTimeout(t);
  return wrapped;
}

export function storageGet(key, fallback = null) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v; } catch { return fallback; }
}
export function storageSet(key, value) {
  try { localStorage.setItem(key, value); return true; } catch { return false; }
}
export function storageRemove(key) {
  try { localStorage.removeItem(key); } catch { /* yoksay */ }
}

export const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

const PALETTE = ['#3b82f6', '#f97316', '#10b981', '#a855f7', '#ef4444', '#14b8a6', '#eab308', '#ec4899', '#6366f1', '#84cc16'];
export const paletteColor = (i) => PALETTE[i % PALETTE.length];
