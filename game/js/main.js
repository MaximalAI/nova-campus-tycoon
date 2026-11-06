// ---------------------------------------------------------------------------
// Game: scene, camera, lighting, input, main loop, data from Python
// ---------------------------------------------------------------------------
class Game {
  constructor(root) {
    this.root = root.querySelector("#nct");
    this.view = null;
    this.config = null;
    this.lighting = [];
    this.session = null;
    this.planDay = null;
    this.screen = null;
    this.clock = { t: 5, speed: 1, paused: false, running: false };
    this.input = { up: false, down: false, left: false, right: false };
    this.camYaw = -Math.PI / 2;
    this.camZoom = 1;
    this.camPos = new THREE.Vector3(-34, 10, 0);
    this.camLook = new THREE.Vector3(-24, 0, 0);
    this.hudTimer = 0;
    this.highlighted = null;
    this.bridge = new Bridge(this);
    this.ui = new UI(this, this.root);
  }

  init(config) {
    this.config = config;
    const vp = this.root.querySelector("#viewport");
    const r = new THREE.WebGLRenderer({ antialias: true });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.setSize(window.innerWidth, window.innerHeight);
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.toneMapping = THREE.NoToneMapping;
    vp.appendChild(r.domElement);
    this.renderer = r;
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0xbfe3ff, 70, 190);
    this.camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 400);
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x4c7a3a, 0.7);
    this.scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xffffff, 1.4);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    Object.assign(this.sun.shadow.camera, { left: -75, right: 75, top: 75, bottom: -75, near: 1, far: 260 });
    this.sun.shadow.bias = -0.0005;
    this.scene.add(this.sun, this.sun.target);
    this.world = new World(this);
    this.player = new Player(this);
    this.flow = new Flow(this);
    this.staff = {
      cashier: new Figure(this.scene, { shirt: 0x52796f, pants: 0x2b2d42, hair: 0x111111, skin: 0xc68642 }, { apron: true }),
      rival: new Figure(this.scene, { shirt: 0xb83a3a, pants: 0x22223b, hair: 0x5a3825, skin: 0xf1c27d }, { apron: true }),
      cafeManager: new Figure(this.scene, { shirt: 0x2a9d8f, pants: 0x22223b, hair: 0xd4a017, skin: 0xffdbac }, { apron: true, cap: 0x264653 }),
    };
    this.staff.cashier.place(this.world.cashierPos); this.staff.cashier.group.rotation.y = Math.PI;
    this.staff.rival.place(P.rival.staff); this.staff.rival.group.rotation.y = 0;
    this.staff.cafeManager.place(P.cafe.staff); this.staff.cafeManager.group.rotation.y = Math.PI / 2;
    this.raycaster = new THREE.Raycaster();
    this.bindInput();
    window.addEventListener("resize", () => {
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
    });
    this.root.querySelector("#loading").classList.add("hidden");
    this.last = performance.now();
    const loop = () => { this.frame(); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
    window.__nct = this; // for automated play-testing
  }

  focus() { try { this.root.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
  isManual(shop) {
    const v = this.view;
    return !!(v && v.open && v.shops[shop].owner === "player" && !v.shops[shop].auto);
  }
  setSpeed(s) { if (this.config.time.speeds.includes(s)) this.clock.speed = s; this.ui.updateHud(); }
  startSession(kind) {
    this.ui.queue = []; if (this.ui.current) { this.ui.current.busy = false; this.ui.closeDialog(); }
    this.bridge.send(kind, {}, () => {});
  }
  fade(cb) {
    const f = this.root.querySelector("#fade");
    f.classList.add("on");
    setTimeout(cb, 700);
    setTimeout(() => f.classList.remove("on"), 2600);
  }

  // ------------------------------------------------------------ data from Python
  onData(data) {
    if (!data) return;
    if (!this.renderer) { this.lighting = data.lighting; this.init(data.config); }
    this.lighting = data.lighting;
    const prevView = this.view;
    if (data.view) this.view = data.view;
    const sessionChanged = data.session !== this.session;
    this.session = data.session;
    if (sessionChanged || data.screen !== this.screen) {
      this.screen = data.screen;
      if (data.screen === "title") {
        this.view = null; this.planDay = null;
        this.flow.resetDay({ schedule: {} }, { time: 5, students: {}, open: false, closed: false, in_wholesaler: false });
        this.ui.showHud(false);
        this.ui.queue = []; if (this.ui.current) this.ui.closeDialog();
        this.flow.showTitle(data.has_save);
      }
    }
    this.bridge.receive(data);
    if (this.screen === "game" && data.plan && (data.plan.day !== this.planDay || sessionChanged)) {
      const continuing = sessionChanged && data.view.time > 5.001;
      this.planDay = data.plan.day;
      this.startDay(data.plan, data.view, continuing);
    }
    if (prevView !== this.view && this.ui.current && this.ui.current.refreshOnView !== false && ["P18"].includes(this.ui.current.id)) this.ui.refreshDialog();
    this.ui.updateHud();
  }

  startDay(plan, view, continuing) {
    this.flow.resetDay(plan, view);
    this.clock.t = view.time;
    this.clock.speed = 1;
    this.clock.paused = false;
    this.ui.showHud(true);
    if (this.ui.current && this.ui.current.id === "P00") this.ui.closeDialog();
    this.player.teleport(P.spawn, Math.PI / 2);
    this.camYaw = -Math.PI / 2;
    this.root.querySelector("#fade").classList.remove("on");
    if (continuing) this.bridge.send("resume", {}, () => {});
    if (view.status !== "running") return this.flow.openEnd();
    if (view.day_state === "DAY_SUMMARY") return this.flow.openSummary();
    if (view.day_state === "MORNING_PLANNING" && view.time < 5.01) this.flow.openMorning();
    this.focus();
  }

  // ------------------------------------------------------------------- input
  bindInput() {
    const keys = { ArrowUp: "up", KeyW: "up", ArrowDown: "down", KeyS: "down", ArrowLeft: "left", KeyA: "left", ArrowRight: "right", KeyD: "right" };
    window.addEventListener("keydown", (e) => {
      if (!this.view && e.code !== "Enter") return;
      if (keys[e.code]) { this.input[keys[e.code]] = true; e.preventDefault(); }
      if (e.code === "Tab") { e.preventDefault(); if (this.view) this.ui.toggleTab(true); }
      if (e.repeat) return;
      if (e.code === "Enter") { e.preventDefault(); this.ui.pressPrimary(); }
      if (e.code === "Escape") { e.preventDefault(); if (this.ui.current && !this.ui.current.noEsc) this.ui.pressSecondary(); }
      if (e.code === "KeyE" && !this.ui.dialogOpen) this.interact();
      if (e.code === "KeyP") this.flow.openPause();
    });
    window.addEventListener("keyup", (e) => {
      if (keys[e.code]) this.input[keys[e.code]] = false;
      if (e.code === "Tab") this.ui.toggleTab(false);
    });
    window.addEventListener("blur", () => { for (const k in this.input) this.input[k] = false; });
    const canvas = this.renderer.domElement;
    let drag = null;
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
    canvas.addEventListener("pointerdown", (e) => {
      this.focus();
      if (e.button === 2) { drag = { x: e.clientX, yaw: this.camYaw }; return; }
      if (e.button === 0 && !this.ui.dialogOpen && this.view) this.clickAt(e.clientX, e.clientY);
    });
    window.addEventListener("pointermove", (e) => { if (drag) this.camYaw = drag.yaw - (e.clientX - drag.x) * 0.006; });
    canvas.addEventListener("wheel", (e) => { e.preventDefault(); this.camZoom = clamp(this.camZoom * (e.deltaY > 0 ? 1.1 : 0.9), 0.6, 2.6); }, { passive: false });
    window.addEventListener("pointerup", () => { drag = null; });
  }

  nearestInteractable() {
    let best = null;
    const p = this.player.pos;
    for (const it of this.world.interactables) {
      const d = dist2(p, it.pos);
      if (d > it.radius || !it.enabled()) continue;
      const score = d - (it.priority || 0) * 1.5;
      if (!best || score < best.score) best = { it, score };
    }
    return best && best.it;
  }

  interact() { const it = this.nearestInteractable(); if (it) it.action(); }

  clickAt(x, y) {
    const mouse = new THREE.Vector2((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1);
    this.raycaster.setFromCamera(mouse, this.camera);
    const targets = [];
    for (const it of this.world.interactables) for (const m of it.meshes) targets.push(m);
    for (const a of this.flow.agents.values()) if (a.figure.visible) targets.push(a.figure.group);
    const hits = this.raycaster.intersectObjects(targets, true);
    for (const h of hits) {
      let o = h.object;
      while (o && !o.userData.interactable && !o.userData.agentId) o = o.parent;
      if (!o) continue;
      if (o.userData.interactable) {
        const it = o.userData.interactable;
        if (!it.enabled()) continue;
        if (dist2(this.player.pos, it.pos) > it.radius + 0.8) return this.ui.toast("Geh näher heran");
        return it.action();
      }
      const a = this.flow.agents.get(o.userData.agentId);
      if (a && a.shop && this.flow.queues[a.shop][0] === a.id && this.isManual(a.shop)) {
        if (!this.flow.playerIn(a.shop) || dist2(this.player.pos, a.pos) > 3.2) return this.ui.toast("Geh näher heran");
        return this.flow.useCounterFront(a.shop);
      }
      return;
    }
  }

  // ------------------------------------------------------------------ lighting
  applyLighting(t) {
    const L = this.lighting;
    if (!L || !L.length) return;
    const step = (L[1].t - L[0].t);
    const i = clamp(Math.floor((t - L[0].t) / step), 0, L.length - 2);
    const a = L[i], b = L[i + 1], w = clamp((t - a.t) / step, 0, 1);
    const mix = (k) => lerp(a[k], b[k], w);
    const sky = new THREE.Color(lerp(a.sky[0], b.sky[0], w), lerp(a.sky[1], b.sky[1], w), lerp(a.sky[2], b.sky[2], w));
    this.scene.background = sky;
    this.scene.fog.color.copy(sky);
    this.hemi.intensity = mix("ambient") * 1.25;
    this.hemi.color.copy(sky).lerp(new THREE.Color(1, 1, 1), 0.55);
    this.sun.intensity = mix("sun") * 1.35;
    this.sun.color.setRGB(lerp(a.sun_color[0], b.sun_color[0], w), lerp(a.sun_color[1], b.sun_color[1], w), lerp(a.sun_color[2], b.sun_color[2], w));
    const el_ = mix("elevation") * Math.PI / 180, az = mix("azimuth") * Math.PI / 180;
    const center = this.player ? new THREE.Vector3(this.player.pos.x * 0.5, 0, this.player.pos.z * 0.5) : new THREE.Vector3();
    this.sun.target.position.copy(center);
    this.sun.position.set(center.x + Math.cos(el_) * Math.sin(az) * 120, Math.max(4, Math.sin(el_) * 120), center.z - Math.cos(el_) * Math.cos(az) * 120);
    const lamps = mix("lamps");
    for (const l of this.world.lampLights) l.intensity = lamps * 22;
    for (const m of this.world.lampBulbs) m.color.setRGB(0.35 + 0.65 * lamps, 0.35 + 0.55 * lamps, 0.35 + 0.25 * lamps);
    for (const m of this.world.windowMats) m.emissiveIntensity = lamps * 1.3;
  }

  // ------------------------------------------------------------------- camera
  updateCamera(dt) {
    const p = this.player.pos;
    let pos, look, k = 1 - Math.pow(0.0015, dt);
    if (this.screen !== "game") {
      const a = performance.now() / 14000;
      pos = new THREE.Vector3(Math.sin(a) * 52, 30, Math.cos(a) * 52);
      look = new THREE.Vector3(0, 0, -2);
      k = 1;
    } else {
      const counterShop = ["cafe", "rival"].find((s) => {
        const z = P[s].counterZone;
        return this.view && this.view.open && this.view.shops[s].owner === "player" && !this.view.shops[s].auto &&
          p.x > z.x0 && p.x < z.x1 && p.z > z.z0 && p.z < z.z1;
      });
      if (counterShop) {
        const c = P[counterShop].cam;
        pos = new THREE.Vector3(c.x, c.y, c.z);
        look = new THREE.Vector3(c.lx, c.ly, c.lz);
        this.camYaw = counterShop === "cafe" ? -Math.PI / 2 : Math.PI;
      } else {
        const inside = this.world.buildingAt(p);
        const z = inside ? Math.min(this.camZoom, 1.2) : this.camZoom;
        const d = (inside ? 4.4 : 7.5) * z, h = (inside ? 4.8 : 5.0) * z;
        pos = new THREE.Vector3(p.x + Math.sin(this.camYaw) * d, h, p.z + Math.cos(this.camYaw) * d);
        look = new THREE.Vector3(p.x, 1.2, p.z);
      }
    }
    this.camPos.lerp(pos, k);
    this.camLook.lerp(look, k);
    this.camera.position.copy(this.camPos);
    this.camera.lookAt(this.camLook);
  }

  // --------------------------------------------------------------------- frame
  frame() {
    const now = performance.now();
    const dt = Math.min(this.maxDt || 0.05, (now - this.last) / 1000);
    this.last = now;
    this.bridge.flush();
    const v = this.view;
    let dtGameMin = 0;
    if (this.screen === "game" && v) {
      const c = this.clock;
      c.running = v.status === "running" && v.day_state !== "DAY_SUMMARY" && !c.paused &&
        !(this.ui.dialogOpen && c.t < this.config.time.dialogs_pause_clock_before) && c.t < this.config.time.day_end;
      if (c.running) {
        const before = c.t;
        c.t = Math.min(this.config.time.day_end, c.t + dt * c.speed / this.config.time.real_seconds_per_game_hour);
        dtGameMin = (c.t - before) * 60;
      }
      this.flow.sendTicks();
      if (this.flow.progress && dtGameMin > 0) {
        const pr = this.flow.progress;
        pr.done += dtGameMin;
        const bar = pr.bar(); if (bar) bar.style.width = `${clamp(pr.done / pr.minutes, 0, 1) * 100}%`;
        if (pr.done >= pr.minutes) { this.flow.progress = null; pr.onDone(); }
      } else if (this.flow.progress && this.ui.current?.id === "P15" && !c.running && !c.paused) {
        // after 21:00 the clock is stopped; cleaning still completes
        const pr = this.flow.progress; pr.done += dt; const bar = pr.bar(); if (bar) bar.style.width = `${clamp(pr.done / pr.minutes, 0, 1) * 100}%`;
        if (pr.done >= pr.minutes) { this.flow.progress = null; pr.onDone(); }
      }
      this.player.update(dt, this.input, this.camYaw, this.ui.dialogOpen);
      this.flow.updateGate();
      this.flow.updateZones();
      this.flow.updateStudents(dt, dtGameMin);
      this.updateWorldState(now);
    }
    this.applyLighting(this.screen === "game" ? this.clock.t : 12.5);
    this.updateCamera(dt);
    this.updateLabels();
    this.renderer.render(this.scene, this.camera);
    this.hudTimer += dt;
    if (this.hudTimer > 0.1 && this.view) { this.hudTimer = 0; this.ui.updateHud(); }
  }

  updateWorldState(now) {
    const v = this.view, w = this.world;
    // Highlight the object in range
    const it = this.nearestInteractable();
    if (this.highlighted !== it) {
      if (this.highlighted) for (const m of this.highlighted.meshes) if (m.material?.emissive) m.material.emissive.setHex(0x000000);
      if (it) for (const m of it.meshes) if (m.material?.emissive) m.material.emissive.setHex(0x664400);
      this.highlighted = it;
    }
    this.currentHint = it && !this.ui.dialogOpen ? it : null;
    // Building walls fade while the player is inside
    const inside = w.buildingAt(this.player.pos);
    for (const [key, parts] of Object.entries(w.buildingParts)) {
      const on = key === inside;
      for (const m of parts.wallMats) { m.opacity = on ? 0.18 : 1; m.depthWrite = !on; }
      parts.roof.visible = !on;
    }
    // Roof colour shows the owner: green = yours, red = competitor
    const rivalRoof = w.buildingParts.rival.roof.material;
    rivalRoof.color.setHex(v.shops.rival.owner === "player" ? 0x2e8b57 : BUILDINGS.rival.roof);
    // Staff
    this.staff.rival.visible = v.shops.rival.auto;
    this.staff.cafeManager.visible = v.shops.cafe.manager;
    this.staff.rival.animate(0); this.staff.cafeManager.animate(0); this.staff.cashier.animate(0);
    // Objective marker
    const target = this.flow.objectiveTarget();
    const ring = w.markers.ring, arrow = w.markers.arrow;
    ring.visible = !!target;
    if (target) {
      ring.position.set(target.x, 0.06, target.z);
      const s = 1 + Math.sin(now / 250) * 0.12; ring.scale.set(s, s, s);
      const d = dist2(this.player.pos, target);
      arrow.visible = d > 4;
      const ang = Math.atan2(target.x - this.player.pos.x, target.z - this.player.pos.z);
      arrow.position.set(this.player.pos.x + Math.sin(ang) * 1.4, 0.07, this.player.pos.z + Math.cos(ang) * 1.4);
      arrow.rotation.set(-Math.PI / 2, 0, ang + Math.PI);
    } else arrow.visible = false;
  }

  updateLabels() {
    const ui = this.ui, W = window.innerWidth, H = window.innerHeight;
    ui.beginLabels();
    if (this.screen === "game" && this.view) {
      if (this.currentHint) {
        const e = ui.label("hint", `<div class="hint"><b>E</b>${esc(this.currentHint.label())}</div>`);
        ui.placeLabel(e, new THREE.Vector3(this.currentHint.pos.x, 2.5, this.currentHint.pos.z), this.camera, W, H);
      }
      for (const a of this.flow.agents.values()) {
        if (!a.figure.visible || !["to_shop", "queue", "served"].includes(a.mode)) continue;
        if (dist2(a.pos, this.player.pos) > 40) continue;
        const items = a.order || a.wanted || [];
        if (!items.length && !(a.soldOut || []).length) continue;
        const icons = items.map((p) => this.config.products[p].icon).join("") +
          (a.soldOut || []).map((p) => `<span class="gone">${this.config.products[p].icon}</span>`).join("");
        let pat = "";
        if ((a.mode === "queue" || a.mode === "served") && this.view.open) {
          const f = clamp(a.patience / a.patienceMax, 0, 1);
          pat = `<div class="patience"><div style="width:${f * 100}%;background:${f > 0.5 ? "#2f9e5b" : f > 0.25 ? "#f2c94c" : "#d9534f"}"></div></div>`;
        }
        const e = ui.label("b" + a.id, `${pat}<div class="bubble" style="position:relative">${icons}</div>`);
        ui.placeLabel(e, new THREE.Vector3(a.pos.x, 2.15, a.pos.z), this.camera, W, H);
      }
    }
    ui.endLabels();
  }
}

// Streamlit v2 component entry point: called on every render with new data.
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let game = parentElement.__nctGame;
  if (!game) {
    game = new Game(parentElement);
    parentElement.__nctGame = game;
  }
  game.bridge.setTrigger = setTriggerValue;
  game.onData(data);
}
