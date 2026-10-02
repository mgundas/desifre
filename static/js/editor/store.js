// Düzenleyici durumu: bölümler, konuşmacılar, başlık, geri al / yinele.
// Bölümler değişmez (immutable) olduğundan geri alma yığını yalnızca başvuruları saklar.

const MAX_UNDO = 300;
const COALESCE_MS = 1200;

export class Store {
  constructor({ segments, speakers, title }) {
    this.state = { segments, speakers, title };
    this.undoStack = [];
    this.redoStack = [];
    this.listeners = new Set();
    this.version = 0;
  }

  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(source) { for (const fn of this.listeners) fn(source); }

  get canUndo() { return this.undoStack.length > 0; }
  get canRedo() { return this.redoStack.length > 0; }

  /** patch: {segments?, speakers?}. key verilirse aynı anahtarla yakın zamanda yapılan değişiklikler tek adımda birleşir. */
  apply(patch, { key = null } = {}) {
    const next = { ...this.state, ...patch };
    if (next.segments === this.state.segments && next.speakers === this.state.speakers) return false;
    const now = Date.now();
    const last = this.undoStack[this.undoStack.length - 1];
    if (key && last && last.key === key && now - last.time < COALESCE_MS) {
      last.time = now;
    } else {
      this.undoStack.push({ segments: this.state.segments, speakers: this.state.speakers, key, time: now });
      if (this.undoStack.length > MAX_UNDO) this.undoStack.shift();
    }
    this.redoStack = [];
    this.state = next;
    this.version++;
    this.emit('edit');
    return true;
  }

  setTitle(title) {
    if (title === this.state.title) return;
    this.state = { ...this.state, title };
    this.version++;
    this.emit('title');
  }

  undo() {
    const e = this.undoStack.pop();
    if (!e) return false;
    this.redoStack.push({ segments: this.state.segments, speakers: this.state.speakers });
    this.state = { ...this.state, segments: e.segments, speakers: e.speakers };
    this.version++;
    this.emit('undo');
    return true;
  }

  redo() {
    const e = this.redoStack.pop();
    if (!e) return false;
    this.undoStack.push({ segments: this.state.segments, speakers: this.state.speakers, key: null, time: 0 });
    this.state = { ...this.state, segments: e.segments, speakers: e.speakers };
    this.version++;
    this.emit('redo');
    return true;
  }
}
