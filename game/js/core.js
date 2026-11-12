// Nova Campus Tycoon v2: browser part (rendering, input, animation, HUD, pop-ups).
// Game rules live in Python (logic.py). This code only animates and reports events.
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, w) => a + (b - a) * w;
const euro = (c) => {
  const neg = c < 0; c = Math.abs(Math.round(c));
  return `${neg ? "-" : ""}€${Math.floor(c / 100)}.${String(c % 100).padStart(2, "0")}`;
};
const fmtTime = (t) => {
  const m = Math.floor(t * 60 + 1e-6);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
function hashRand(str) {
  // Deterministic 0..1 from a string (for visual variety only).
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return ((h >>> 0) % 100000) / 100000;
}
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dist2 = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);

// ---------------------------------------------------------------------------
// Bridge: batches of events to Python, results back with the next render.
// ---------------------------------------------------------------------------
class Bridge {
  constructor(game) {
    this.game = game;
    this.outbox = [];
    this.inflight = null; // {seq, events, sentAt}
    this.seq = Math.floor(Math.random() * 1e6) * 1000;
    this.cid = 0;
    this.callbacks = new Map();
    this.setTrigger = null;
  }
  send(type, payload = {}, onResult = null) {
    const cid = ++this.cid;
    const ev = Object.assign({ type, cid, t: this.game.clock ? this.game.clock.t : 5 }, payload);
    if (onResult) this.callbacks.set(cid, onResult);
    this.outbox.push(ev);
    this.flush();
    return cid;
  }
  flush() {
    if (!this.setTrigger) return;
    if (this.inflight) {
      if (performance.now() - this.inflight.sentAt > 4000) {
        this.inflight.sentAt = performance.now(); // resend the same batch, Python ignores duplicates
        this.setTrigger("events", { seq: this.inflight.seq, events: this.inflight.events });
      }
      return;
    }
    if (!this.outbox.length) return;
    const events = this.outbox.splice(0, 60);
    this.seq += 1;
    this.inflight = { seq: this.seq, events, sentAt: performance.now() };
    this.setTrigger("events", { seq: this.seq, events });
  }
  receive(data) {
    if (!this.inflight || data.ack !== this.inflight.seq) return false;
    const done = this.inflight;
    this.inflight = null;
    const byCid = new Map((data.results || []).map((r) => [r.cid, r]));
    for (const ev of done.events) {
      const r = byCid.get(ev.cid) || { ok: false, error: "No answer from the game server" };
      const cb = this.callbacks.get(ev.cid);
      this.callbacks.delete(ev.cid);
      if (!r.ok && !cb && r.error) this.game.ui.toast(r.error, true);
      if (cb) { try { cb(r); } catch (e) { console.error(e); } }
      try { this.game.sound.onEvent(ev, r); } catch (e) { /* sound is optional */ }
    }
    this.flush();
    return true;
  }
}
