import test from 'node:test';
import assert from 'node:assert/strict';
import * as ops from '../../static/js/editor/ops.js';

const W = (items) => items.map(([word, start, end]) => ({ word, start, end }));
const seg = (id, items, speaker = null) => {
  const words = W(items);
  return { id, start: words[0].start, end: words.at(-1).end, speaker, text: words.map((w) => w.word).join(' '), words };
};
const base = () => [
  seg('s0', [['Merhaba', 0, 0.5], ['nasılsınız', 0.6, 1.4], ['bugün', 1.5, 2.0]], 'SPEAKER_00'),
  seg('s1', [['İyiyim', 2.2, 2.8], ['teşekkürler', 2.9, 3.6]], 'SPEAKER_01'),
];

test('splitAt böler ve kelime zamanlarını korur', () => {
  const out = ops.splitAt(base(), 0, 1);
  assert.equal(out.length, 3);
  assert.equal(out[0].text, 'Merhaba');
  assert.equal(out[1].text, 'nasılsınız bugün');
  assert.equal(out[1].start, 0.6);
  assert.equal(out[1].end, 2.0);
  assert.equal(out[0].end, 0.5);
  assert.equal(out[1].speaker, 'SPEAKER_00');
  assert.notEqual(out[0].id, out[1].id);
  assert.equal(new Set(out.map((s) => s.id)).size, 3);
});

test('splitAt uçlarda işlem yapmaz', () => {
  const b = base();
  assert.equal(ops.splitAt(b, 0, 0), b);
  assert.equal(ops.splitAt(b, 0, 3), b);
});

test('splitAtChar en yakın kelime sınırını seçer', () => {
  // "Merhaba nasılsınız bugün": sınırlar 8 ve 19
  assert.equal(ops.splitAtChar(base(), 0, 7)[0].text, 'Merhaba');
  assert.equal(ops.splitAtChar(base(), 0, 12)[0].text, 'Merhaba');
  assert.equal(ops.splitAtChar(base(), 0, 18)[0].text, 'Merhaba nasılsınız');
  assert.equal(ops.splitAtChar(base(), 0, 0)[0].text, 'Merhaba'); // başta en yakın ilk sınırdan bölünür
});

test('splitAtTime zamana göre böler', () => {
  const out = ops.splitAtTime(base(), 0, 1.45);
  assert.deepEqual(out.slice(0, 2).map((s) => s.text), ['Merhaba nasılsınız', 'bugün']);
});

test('mergeNext birleştirir, ilk konuşmacıyı ve zaman aralığını korur', () => {
  const out = ops.mergeNext(base(), 0);
  assert.equal(out.length, 1);
  assert.equal(out[0].text, 'Merhaba nasılsınız bugün İyiyim teşekkürler');
  assert.equal(out[0].speaker, 'SPEAKER_00');
  assert.equal(out[0].start, 0);
  assert.equal(out[0].end, 3.6);
  assert.equal(out[0].words.length, 5);
  const b = base();
  assert.equal(ops.mergeNext(b, 1), b);
});

test('böl ardından birleştir özgün veriyi geri verir', () => {
  const b = base();
  const back = ops.mergeNext(ops.splitAt(b, 0, 2), 0);
  assert.deepEqual(back[0].words, b[0].words);
  assert.equal(back[0].text, b[0].text);
});

test('setText aynı sayıda kelimede zamanları korur', () => {
  const out = ops.setText(base(), 0, 'Merhaba nasılsınız yarın');
  assert.deepEqual(out[0].words.map((w) => w.word), ['Merhaba', 'nasılsınız', 'yarın']);
  assert.equal(out[0].words[2].start, 1.5);
  assert.equal(out[0].words[2].end, 2.0);
  assert.equal(out[0].words[0].end, 0.5);
});

test('setText araya kelime eklenince boşluğa dağıtır, zamanlar sıralı kalır', () => {
  const out = ops.setText(base(), 0, 'Merhaba çok sevgili nasılsınız bugün');
  const w = out[0].words;
  assert.equal(w.length, 5);
  for (let i = 1; i < w.length; i++) assert.ok(w[i].start >= w[i - 1].start, `sıra ${i}`);
  assert.ok(w[1].start >= 0.5 - 1e-9 && w[2].end <= 0.6 + 1e-9, 'eklenenler boşluğa sığar');
  assert.equal(w[3].word, 'nasılsınız');
  assert.equal(w[3].start, 0.6);
});

test('setText noktalama ve büyük/küçük harf farkını eşleşme sayar', () => {
  const out = ops.setText(base(), 0, 'merhaba, nasılsınız bugün.');
  assert.equal(out[0].words[0].start, 0);
  assert.equal(out[0].words[0].end, 0.5);
  assert.equal(out[0].words[0].word, 'merhaba,');
});

test('setText tamamen yeni metinde bölüm süresine dağıtır', () => {
  const out = ops.setText(base(), 1, 'hiç alakasız bir cümle');
  assert.equal(out[1].words.length, 4);
  assert.equal(out[1].start, 2.2);
  assert.ok(Math.abs(out[1].end - 3.6) < 0.01);
});

test('setText boş metinde kelimeleri temizler, değişmeyende aynı diziyi döndürür', () => {
  const b = base();
  assert.equal(ops.setText(b, 0, b[0].text), b);
  assert.equal(ops.setText(b, 0, '   ')[0].words.length, 0);
});

test('nudge ve setTime ilk/son kelimeyi de taşır', () => {
  const out = ops.nudge(base(), 0, 'start', 0.1);
  assert.equal(out[0].start, 0.1);
  assert.equal(out[0].words[0].start, 0.1);
  const out2 = ops.nudge(base(), 0, 'end', -0.1);
  assert.equal(out2[0].end, 1.9);
  assert.equal(out2[0].words.at(-1).end, 1.9);
});

test('setTime çok küçük/negatif süreye izin vermez', () => {
  const out = ops.setTime(base(), 0, 'start', 5);
  assert.ok(out[0].start < out[0].end);
  assert.equal(ops.setTime(base(), 0, 'start', -3)[0].start, 0);
});

test('replaceCueText yalnızca kesitin kelimelerini değiştirir', () => {
  const out = ops.replaceCueText(base(), 0, 1, 3, 'çok iyisiniz');
  assert.equal(out[0].text, 'Merhaba çok iyisiniz');
  assert.equal(out[0].words[0].end, 0.5);
});

test('nudgeWord tek kelimeyi taşır', () => {
  const out = ops.nudgeWord(base(), 0, 0, 'end', 0.1);
  assert.equal(out[0].words[0].end, 0.6);
});

test('Türkçe büyük/küçük harfe duyarsız arama', () => {
  const segs = [seg('s0', [['IŞIK', 0, 1], ['İstanbul', 1, 2], ['ığdır', 2, 3]])];
  assert.equal(ops.findMatches(segs, 'ışık').length, 1);
  assert.equal(ops.findMatches(segs, 'istanbul').length, 1);
  assert.equal(ops.findMatches(segs, 'IĞDIR').length, 1);
  assert.equal(ops.findMatches(segs, 'igdir').length, 0);
  assert.equal(ops.findMatches(segs, 'ışık', true).length, 0);
  assert.deepEqual(ops.findMatches(segs, 'İSTANBUL')[0], { seg: 0, from: 5, to: 13 });
});

test('birden çok eşleşme bulunur ve sayılır', () => {
  const segs = [seg('s0', [['bu', 0, 1], ['bu', 1, 2], ['bubu', 2, 3]])];
  assert.equal(ops.findMatches(segs, 'bu').length, 4);
  assert.equal(ops.findMatches(segs, '').length, 0);
});

test('tümünü değiştir Türkçe harflerle çalışır ve sayıyı bildirir', () => {
  const segs = [seg('s0', [['Işık', 0, 1], ['ışık', 1, 2], ['gün', 2, 3]])];
  const { segments, count } = ops.replaceAll(segs, 'IŞIK', 'lamba');
  assert.equal(count, 2);
  assert.equal(segments[0].text, 'lamba lamba gün');
  assert.equal(segments[0].words.length, 3);
});

test('replaceMatch tek eşleşmeyi değiştirir', () => {
  const segs = base();
  const m = ops.findMatches(segs, 'nasılsınız')[0];
  assert.equal(ops.replaceMatch(segs, m, 'nasılsın')[0].text, 'Merhaba nasılsın bugün');
});

test('segmentAt ve wordAt', () => {
  const b = base();
  assert.equal(ops.segmentAt(b, 0.2), 0);
  assert.equal(ops.segmentAt(b, 2.1), 0); // küçük tolerans
  assert.equal(ops.segmentAt(b, 2.3), 1);
  assert.equal(ops.segmentAt(b, 10), -1);
  assert.equal(ops.wordAt(b[0], 1.55), 2);
  assert.equal(ops.wordAt(b[0], -1), -1);
});

test('speakerTurns ardışık konuşmacıları gruplar', () => {
  const b = base();
  b.push({ ...b[1], id: 's2' });
  assert.deepEqual(ops.speakerTurns(b).map((t) => t.items), [[0], [1, 2]]);
});

test('nextSpeakerId ilk boş kimliği verir', () => {
  assert.equal(ops.nextSpeakerId({ SPEAKER_00: {}, SPEAKER_02: {} }, []), 'SPEAKER_01');
});

test('ensureWords kelime olmayan bölüme zamanlı kelime üretir', () => {
  const s = ops.ensureWords({ id: 'a', start: 0, end: 3, text: 'bir iki üç', words: [] });
  assert.equal(s.words.length, 3);
  assert.equal(s.words[0].start, 0);
  assert.ok(Math.abs(s.words[2].end - 3) < 0.01);
});

test('işlemler girdiyi değiştirmez', () => {
  const b = base();
  const snapshot = JSON.stringify(b);
  ops.splitAt(b, 0, 1); ops.mergeNext(b, 0); ops.setText(b, 0, 'yeni metin burada'); ops.nudge(b, 1, 'end', 0.3);
  ops.replaceAll(b, 'bu', 'x');
  assert.equal(JSON.stringify(b), snapshot);
});
