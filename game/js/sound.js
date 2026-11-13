// ---------------------------------------------------------------------------
// v8: sound. Everything is synthesised with the Web Audio API (no audio files):
// a quiet background ambience and a short sound for each activity. Music and effects
// can be switched off separately (pause menu); the choice is kept in the browser.
// ---------------------------------------------------------------------------
const SOUND_KEY = "nct-sound-v8";

class Sound {
  constructor(game) {
    this.game = game;
    this.ctx = null;
    this.mood = "campus";
    const saved = this.load();
    this.musicOn = saved.music !== false;
    this.sfxOn = saved.sfx !== false;
    this.chordIndex = 0;
    this.voices = [];
  }

  load() {
    try { return JSON.parse(window.localStorage.getItem(SOUND_KEY) || "{}") || {}; } catch (e) { return {}; }
  }
  save() {
    try { window.localStorage.setItem(SOUND_KEY, JSON.stringify({ music: this.musicOn, sfx: this.sfxOn })); } catch (e) { /* storage blocked */ }
  }

  // Browsers only allow sound after a click or key press: called from the input handlers.
  unlock() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      try { this.ctx = new AC(); } catch (e) { return; }
      const c = this.ctx;
      this.master = c.createGain(); this.master.gain.value = 0.9; this.master.connect(c.destination);
      this.musicGain = c.createGain(); this.musicGain.gain.value = this.musicOn ? 0.05 : 0; this.musicGain.connect(this.master);
      this.sfxGain = c.createGain(); this.sfxGain.gain.value = this.sfxOn ? 0.32 : 0; this.sfxGain.connect(this.master);
      this.noiseBuf = c.createBuffer(1, c.sampleRate, c.sampleRate);
      const d = this.noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      this.startMusic();
    }
    if (this.ctx.state === "suspended") this.ctx.resume().catch(() => {});
  }

  setMusic(on) {
    this.musicOn = on; this.save();
    if (this.ctx) this.musicGain.gain.setTargetAtTime(on ? 0.05 : 0, this.ctx.currentTime, 0.3);
  }
  setSfx(on) {
    this.sfxOn = on; this.save();
    if (this.ctx) this.sfxGain.gain.setTargetAtTime(on ? 0.32 : 0, this.ctx.currentTime, 0.05);
    if (on) this.play("click");
  }
  setMood(mood) {
    if (this.mood === mood) return;
    this.mood = mood;
    if (this.ctx) this.nextChord(true);
  }

  // ------------------------------------------------------------ background
  // A soft pad that changes chords every few seconds, plus a few quiet plucked notes.
  startMusic() {
    this.nextChord(true);
    this.musicTimer = setInterval(() => this.nextChord(false), 7000);
    this.pluckTimer = setInterval(() => this.pluck(), 2300);
  }
  chords() {
    // frequencies in Hz: calm major chords on the campus, minor and lower in the casino
    if (this.mood === "casino") return [[110, 130.8, 164.8, 207.7], [98, 116.5, 146.8, 185], [87.3, 110, 130.8, 164.8], [103.8, 123.5, 155.6, 196]];
    return [[130.8, 196, 246.9, 329.6], [110, 164.8, 220, 261.6], [87.3, 174.6, 220, 261.6], [98, 146.8, 196, 246.9]];
  }
  nextChord(now) {
    const c = this.ctx; if (!c) return;
    const t = c.currentTime, fade = now ? 0.6 : 2.5;
    for (const v of this.voices) {
      v.g.gain.cancelScheduledValues(t); v.g.gain.setTargetAtTime(0, t, fade / 3);
      v.o.stop(t + fade * 2);
    }
    const list = this.chords();
    const freqs = list[this.chordIndex++ % list.length];
    this.voices = freqs.map((f, i) => {
      const o = c.createOscillator(), g = c.createGain(), lp = c.createBiquadFilter();
      o.type = i === 0 ? "sine" : "triangle";
      o.frequency.value = f; o.detune.value = (i % 2 ? 6 : -6);
      lp.type = "lowpass"; lp.frequency.value = this.mood === "casino" ? 700 : 1100;
      g.gain.value = 0; g.gain.setTargetAtTime(i === 0 ? 0.5 : 0.28, t, fade / 3);
      o.connect(lp); lp.connect(g); g.connect(this.musicGain); o.start(t);
      return { o, g };
    });
  }
  pluck() {
    const c = this.ctx; if (!c || !this.musicOn || Math.random() < 0.35) return;
    const scale = this.mood === "casino" ? [220, 261.6, 293.7, 329.6, 392, 415.3] : [392, 440, 523.3, 587.3, 659.3, 784];
    this.tone(scale[Math.floor(Math.random() * scale.length)], 0.0, 1.4, "sine", 0.35, this.musicGain);
  }

  // ------------------------------------------------------------ building blocks
  tone(freq, delay, dur, type = "sine", vol = 1, out = null, slideTo = null) {
    out = out || this.bus;
    const c = this.ctx; if (!c) return;
    const t = c.currentTime + delay;
    const o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(out || this.sfxGain);
    o.start(t); o.stop(t + dur + 0.05);
  }
  noise(delay, dur, freq = 1200, q = 0.8, vol = 0.6, type = "bandpass", sweepTo = null) {
    const c = this.ctx; if (!c) return;
    const t = c.currentTime + delay;
    const src = c.createBufferSource(); src.buffer = this.noiseBuf; src.loop = true;
    const f = c.createBiquadFilter(); f.type = type; f.frequency.setValueAtTime(freq, t); f.Q.value = q;
    if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, t + dur);
    const g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + Math.min(0.05, dur / 3));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f); f.connect(g); g.connect(this.bus || this.sfxGain);
    src.start(t); src.stop(t + dur + 0.05);
  }

  // ------------------------------------------------------------ effects
  // v9: how loud an effect at this spot is for the player: full within 8 m, silent from 30 m,
  // and nothing from the campus while the player is down in the casino (and the other way round)
  gainAt(pos) {
    const g = this.game;
    if (!pos || !g.player) return 1;
    const inCasinoSpot = pos.z < -120;
    if (!!g.inCasino !== inCasinoSpot) return 0;
    const d = Math.hypot(pos.x - g.player.pos.x, pos.z - g.player.pos.z);
    return Math.max(0, Math.min(1, 1 - (d - 8) / 22));
  }
  playAt(name, pos) { this.play(name, this.gainAt(pos)); }
  // the middle of a shop's building, for sounds that belong to a shop
  shopPos(shop) {
    const b = typeof BUILDINGS !== "undefined" && BUILDINGS[shop];
    return b ? { x: (b.x0 + b.x1) / 2, z: (b.z0 + b.z1) / 2 } : null;
  }

  play(name, gain = 1) {
    if (!this.ctx || !this.sfxOn || gain < 0.03) return;
    this.bus = null;
    if (gain < 0.99) { this.bus = this.ctx.createGain(); this.bus.gain.value = gain; this.bus.connect(this.sfxGain); }
    try { this.effect(name); } finally { this.bus = null; }
  }

  effect(name) {
    const T = (f, d, len, type, vol, slide) => this.tone(f, d, len, type, vol, null, slide);
    switch (name) {
      case "click": T(880, 0, 0.05, "square", 0.08); break;
      case "error": T(160, 0, 0.18, "square", 0.12); T(120, 0.12, 0.2, "square", 0.1); break;
      case "coin": T(988, 0, 0.08, "square", 0.12); T(1319, 0.07, 0.25, "square", 0.12); break;
      case "register": this.noise(0, 0.08, 3000, 2, 0.4); T(2093, 0.06, 0.5, "sine", 0.25); T(2637, 0.06, 0.5, "sine", 0.15); break;
      case "brew": this.noise(0, 0.9, 900, 1.5, 0.35, "bandpass", 500); T(220, 0.1, 0.5, "sine", 0.08); break;
      case "pour": this.noise(0, 0.5, 1800, 3, 0.3, "bandpass", 900); break;
      case "pick": T(660, 0, 0.06, "triangle", 0.15); T(990, 0.05, 0.08, "triangle", 0.12); break;
      case "handover": T(523, 0, 0.1, "sine", 0.2); T(784, 0.08, 0.18, "sine", 0.2); break;
      case "clean": this.noise(0, 0.25, 2500, 0.7, 0.35, "highpass"); this.noise(0.3, 0.25, 2500, 0.7, 0.3, "highpass"); break;
      case "box": this.noise(0, 0.12, 300, 1, 0.6, "lowpass"); T(110, 0, 0.15, "sine", 0.3); break;
      case "door": T(1568, 0, 0.6, "sine", 0.18); T(1175, 0.18, 0.8, "sine", 0.16); break;
      case "refill": for (let i = 0; i < 4; i++) { this.noise(i * 0.09, 0.05, 2000, 4, 0.35); } T(660, 0.4, 0.15, "triangle", 0.12); break;
      case "broken": T(400, 0, 0.5, "sawtooth", 0.08, 90); this.noise(0.05, 0.3, 600, 1, 0.3, "lowpass"); break;
      case "repair": for (let i = 0; i < 3; i++) T(1800, i * 0.12, 0.05, "square", 0.08); T(880, 0.4, 0.2, "triangle", 0.12); break;
      case "chime": [523, 659, 784].forEach((f, i) => T(f, i * 0.09, 0.4, "sine", 0.18)); break;
      case "fanfare": [523, 659, 784, 1047].forEach((f, i) => T(f, i * 0.12, 0.5, "triangle", 0.2)); T(1047, 0.5, 0.9, "sine", 0.15); break;
      case "day_end": [784, 659, 523, 392].forEach((f, i) => T(f, i * 0.18, 0.6, "sine", 0.15)); break;
      case "lighter": this.noise(0, 0.06, 4000, 3, 0.4); this.noise(0.08, 0.4, 600, 0.6, 0.25, "lowpass"); break;
      case "smoke": this.noise(0, 1.4, 700, 0.5, 0.25, "lowpass", 300); break;
      case "ladder": for (let i = 0; i < 4; i++) { T(140 - i * 8, i * 0.22, 0.1, "sine", 0.35); this.noise(i * 0.22, 0.06, 500, 1, 0.3, "lowpass"); } break;
      case "spin": {
        // ball clicking over the wheel, slowing down (about 2.6 s)
        let t = 0, gap = 0.04;
        while (t < 2.6) { this.noise(t, 0.03, 3500, 5, 0.25); t += gap; gap *= 1.08; }
        break;
      }
      case "win": [523, 659, 784, 1047, 1319].forEach((f, i) => T(f, i * 0.08, 0.35, "square", 0.08)); break;
      case "lose": T(392, 0, 0.3, "triangle", 0.15); T(311, 0.25, 0.5, "triangle", 0.15); break;
      default: break;
    }
  }

  machinePos(shop, id) {
    const m = P[shop] && P[shop].machines && P[shop].machines[id];
    return m ? m.pos : this.shopPos(shop);
  }

  // Every event that went through the bridge: the matching sound (called in Bridge.receive)
  onEvent(ev, r) {
    if (!this.ctx || !this.sfxOn) return;
    if (!r.ok) {
      if (!["tick", "autosave", "decide", "student_arrive", "student_leave", "join_queue", "at_counter", "auto_serve", "queue_full", "patience_expired", "resume"].includes(ev.type)) this.play("error");
      return;
    }
    const res = r.result || {};
    // v9: sounds of a shop or a machine are only heard near it
    const spot = ev.machine ? this.machinePos(ev.shop, ev.machine) : ev.shop ? this.shopPos(ev.shop) : null;
    const play = (name) => this.play(name, spot ? this.gainAt(spot) : 1);
    switch (ev.type) {
      case "pay": play("register"); break;
      case "stock_goods": case "fill_front": play("box"); break;
      case "prepare": case "assemble": play(String(ev.product || "").includes("juice") ? "pour" : "brew"); break;
      case "handover": case "checkout": play("coin"); break;
      case "auto_serve": if (this.game.flow.playerIn(ev.shop) || ev.machine) play("coin"); break;
            case "open_shop": play("door"); break;
      case "refill_machine": play("refill"); break;
      case "collect_cash": case "deposit_cash": play("register"); break;
      case "repair": play("repair"); break;
      case "set_prices": case "confirm_plan": case "confirm_manager_plan": case "set_happy_hour": play("click"); break;
      case "buy_upgrade": case "hire_manager": play("chime"); break;
      case "buy_shop": case "buy_competitor": play("fanfare"); break;
      case "next_day": play("chime"); break;
      case "tick":
        if ((res.toasts || []).some((t) => t.includes("broken"))) play("broken");
        if (res.summary) play("day_end");
        break;
      default: break;
    }
  }
}
