import { T } from '../../i18n/tr.js';
import { h, icon, iconButton, clear } from '../ui.js';
import { fmtClock, clamp } from '../util.js';

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

/**
 * Ses/video oynatıcı. Zaman çizelgesi hem arama çubuğu hem konuşmacı haritasıdır.
 * getData() -> {segments, speakers, duration}
 */
export function createPlayer({ url, isVideo, hasMedia, getData, onTick, onError }) {
  const media = isVideo ? h('video', { class: 'player-video', playsinline: true, preload: 'metadata' }) : h('audio', { preload: 'metadata' });
  if (hasMedia) media.src = url;

  const playBtn = h('button', { type: 'button', class: 'btn btn-primary play-btn', 'aria-label': T.editor.play, title: `${T.editor.play} (Space)` });
  const back = h('button', { type: 'button', class: 'btn', title: `${T.editor.back5} (Alt+←)`, 'aria-label': T.editor.back5 }, icon('back', 16), '5');
  const fwd = h('button', { type: 'button', class: 'btn', title: `${T.editor.fwd5} (Alt+→)`, 'aria-label': T.editor.fwd5 }, '5', icon('fwd', 16));
  const timeLabel = h('span', { class: 'time-label', 'aria-live': 'off' }, '0:00 / 0:00');
  const speed = h('select', { class: 'input speed', 'aria-label': T.editor.speed, onChange: (e) => { media.playbackRate = +e.target.value; } },
    SPEEDS.map((s) => h('option', { value: s, selected: s === 1 }, `${String(s).replace('.', ',')}x`)));
  const canvas = h('canvas', { class: 'timeline-canvas', 'aria-hidden': 'true' });
  const range = h('input', { type: 'range', class: 'timeline-range', min: 0, max: 1, step: 0.01, value: 0, 'aria-label': T.editor.seek });
  const timeline = h('div', { class: 'timeline' }, canvas, range);
  const msg = h('p', { class: 'note note-warn', hidden: hasMedia }, T.editor.noMedia);

  const duration = () => (isFinite(media.duration) && media.duration > 0 ? media.duration : getData().duration || 0);
  const drawPlay = () => {
    clear(playBtn).append(icon(media.paused ? 'play' : 'pause', 18));
    playBtn.setAttribute('aria-label', media.paused ? T.editor.play : T.editor.pause);
  };
  const toggle = () => { if (!hasMedia) return; if (media.paused) media.play().catch(() => {}); else media.pause(); };
  const seek = (t) => { if (!hasMedia) return; media.currentTime = clamp(t, 0, duration() || t); update(); };
  const skip = (d) => seek(media.currentTime + d);

  playBtn.addEventListener('click', toggle);
  back.addEventListener('click', () => skip(-5));
  fwd.addEventListener('click', () => skip(5));
  range.addEventListener('input', () => seek(+range.value));
  media.addEventListener('play', () => { drawPlay(); loop(); });
  media.addEventListener('pause', drawPlay);
  media.addEventListener('ended', drawPlay);
  media.addEventListener('seeked', update);
  media.addEventListener('timeupdate', update);
  media.addEventListener('loadedmetadata', () => { update(); drawTimeline(); });
  media.addEventListener('error', () => { if (hasMedia) { msg.hidden = false; msg.textContent = T.editor.mediaError; onError?.(); } });

  let raf = 0;
  function loop() {
    cancelAnimationFrame(raf);
    const step = () => { update(); if (!media.paused && !media.ended) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
  }

  function update() {
    const t = media.currentTime || 0;
    const d = duration();
    range.max = String(d || 1);
    range.value = String(t);
    timeLabel.textContent = `${fmtClock(t)} / ${fmtClock(d)}`;
    range.style.setProperty('--pos', d ? `${(t / d) * 100}%` : '0%');
    onTick?.(t);
  }

  // ---- zaman çizelgesi ----
  let drawQueued = false;
  function drawTimeline() {
    if (drawQueued) return;
    drawQueued = true;
    requestAnimationFrame(() => {
      drawQueued = false;
      const { segments, speakers } = getData();
      const d = duration();
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth, hgt = canvas.clientHeight;
      if (!w || !hgt) return;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(hgt * dpr);
      const ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);
      const css = getComputedStyle(canvas);
      ctx.fillStyle = css.getPropertyValue('--tl-bg') || '#ddd';
      ctx.fillRect(0, 0, w, hgt);
      if (!d) return;
      for (const s of segments) {
        const x = (s.start / d) * w;
        const bw = Math.max(1.5, ((s.end - s.start) / d) * w);
        ctx.fillStyle = (s.speaker && speakers[s.speaker]?.color) || css.getPropertyValue('--tl-seg') || '#6b7280';
        ctx.globalAlpha = 0.85;
        ctx.fillRect(x, hgt * 0.2, bw, hgt * 0.6);
      }
      ctx.globalAlpha = 1;
    });
  }
  const ro = new ResizeObserver(drawTimeline);
  ro.observe(canvas);

  drawPlay();
  const controls = h('div', { class: 'player-controls' },
    h('div', { class: 'player-row' }, back, playBtn, fwd, timeLabel, h('span', { class: 'spacer' }), h('label', { class: 'speed-wrap' }, h('span', { class: 'sr-only' }, T.editor.speed), speed)),
    timeline, msg);
  const el = h('section', { class: `player card ${isVideo ? 'has-video' : ''}` }, isVideo ? h('div', { class: 'video-box' }, media) : media, controls);

  return {
    el, media, toggle, seek, skip, drawTimeline, update,
    get time() { return media.currentTime || 0; },
    get paused() { return media.paused; },
    destroy() { cancelAnimationFrame(raf); ro.disconnect(); media.pause(); media.removeAttribute('src'); media.load(); },
  };
}
