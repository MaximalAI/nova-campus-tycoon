// ---------------------------------------------------------------------------
// Game: scene, third-person camera, lighting, input, minimap, main loop
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
    this.input = { up: false, down: false, left: false, right: false, run: false };
    // Third-person camera: yaw/pitch from the mouse, distance from the wheel
    this.camYaw = -Math.PI / 2;
    this.camPitch = 0.42;
    this.camDist = 7.5;
    this.camPos = new THREE.Vector3(-34, 10, 0);
    this.camLook = new THREE.Vector3(-24, 0, 0);
    this.pointerLocked = false;
    this.hudTimer = 0;
    this.highlighted = null;
    this.bridge = new Bridge(this);
    this.sound = new Sound(this); // v8
    this.inCasino = false; // v8: underground casino (easter egg)
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
    this.camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 400);
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
    };
    this.staff.cashier.place(this.world.cashierPos); this.staff.cashier.group.rotation.y = Math.PI;
    // v5: staff behind the counters walk to the stations and clean up (StaffAgent in people.js)
    this.workers = {
      cafe: new StaffAgent(this, "cafe", { shirt: 0x2a9d8f, pants: 0x22223b, hair: 0xd4a017, skin: 0xffdbac }, { apron: true, cap: 0x264653 }),
      rival: new StaffAgent(this, "rival", { shirt: 0xb83a3a, pants: 0x22223b, hair: 0x5a3825, skin: 0xf1c27d }, { apron: true }),
    };
    // v7: staff for every new shop with a counter (vending machines have none)
    const hairs = [0x111111, 0x8d5524, 0xe8c07d, 0x5a3825, 0xa0522d, 0x2b1d0e, 0xd4a017];
    this.world.newShops.forEach((key, i) => {
      if (P[key].vending && this.config.shops[key].building.interior === "office") {
        // v10: the vending manager: works from the office desk and does his rounds to the machines
        Object.assign(P[key], { staff: P[key].upBoard, homeFace: P[key].frame.at(P[key].frame.depth - 2.0, -(P[key].frame.width / 2 - 1.4)), behind: () => false });
        this.workers[key] = new StaffAgent(this, key, { shirt: 0x37474f, pants: 0x22223b, hair: hairs[i % hairs.length], skin: 0xe0ac69 }, { cap: 0x37474f });
        return;
      }
      if (P[key].vending) return;
      this.workers[key] = new StaffAgent(this, key, { shirt: BUILDINGS[key].trim, pants: 0x22223b, hair: hairs[i % hairs.length], skin: [0xf1c27d, 0xe0ac69, 0xc68642, 0xffdbac][i % 4] }, { apron: true });
    });
    this.eggs = new EasterEggs(this); // v8: Jep and the casino
    this.raycaster = new THREE.Raycaster();
    this.minimap = this.root.querySelector("#minimap-canvas").getContext("2d");
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
    window.__nctP = P;
  }

  focus() { try { this.root.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }

  autoPause() {
    for (const k in this.input) this.input[k] = false;
    if (this.ui.current?.id === "P20") return;
    if (this.ui.dialogOpen) {
      // keep the open pop-up, show the pause menu right after it
      this.clock.paused = true;
      if (!this.ui.queue.some((d) => d.id === "P20")) this.ui.queue.unshift(this.flow.pauseDialog());
      return;
    }
    this.flow.openPause();
  }

  // ---------------------------------------------------------------- big map
  // v8: the big map can be dragged and zoomed (wheel), shows the whole area including the
  // beach, and the people on it move while it is open.
  openBigMap() {
    if (!this.view || this.screen !== "game") return;
    const box = this.root.querySelector("#bigmap");
    box.classList.remove("hidden");
    this.releasePointer();
    this.bigView = { R: this.bigMapR(), C: { ...this.bigMapCenter() } };
    if (!this.bigMapBound) this.bindBigMap();
    this.renderBigMap();
  }
  bindBigMap() {
    this.bigMapBound = true;
    const wrap = this.root.querySelector(".bigmap-wrap");
    let drag = null;
    wrap.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".map-spot")) return;
      drag = { x: e.clientX, y: e.clientY, C: { ...this.bigView.C }, moved: false };
      wrap.setPointerCapture(e.pointerId);
    });
    wrap.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const scale = (2 * this.bigView.R) / wrap.clientWidth;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      this.bigView.C = { x: clamp(drag.C.x - dx * scale, -60, 60), z: clamp(drag.C.z - dy * scale, -45, 110) };
      this.renderBigMap();
    });
    const end = () => { drag = null; };
    wrap.addEventListener("pointerup", end);
    wrap.addEventListener("pointercancel", end);
    wrap.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.bigView.R = clamp(this.bigView.R * (e.deltaY > 0 ? 1.12 : 1 / 1.12), 30, 110);
      this.renderBigMap();
    }, { passive: false });
  }
  renderBigMap(spotsToo = true) {
    const { R, C } = this.bigView;
    this.drawMap(this.root.querySelector("#bigmap-canvas").getContext("2d"), 560, R, false, C);
    if (!spotsToo) return;
    const spots = this.root.querySelector("#bigmap-spots");
    const v = this.view;
    const places = [{ key: "wholesale", label: "🏬 Wholesaler", color: "#2c6fbb", at: { x: 40, z: 12.5 } }];
    for (const [key, spec] of Object.entries(this.config.shops)) {
      const s = v.shops[key], b = BUILDINGS[key];
      if (!b || !this.world.zoneVisible(b.zone)) continue; // closed zones: drawn on the map, no travel
      const mine = s.owner === "player";
      const name = key === "cafe" ? "Your café" : spec.name;
      const tag = mine && key !== "cafe" ? " (yours)" : s.sold ? " (yours tomorrow)" : v.for_sale === key ? " (for sale)" : "";
      // labels below the building; north of the main path and at the beach above it
      const above = b.z1 < -10 || b.zone === "beach";
      const at = { x: (b.x0 + b.x1) / 2, z: above ? b.z0 - 2.8 : b.z1 + 2.8 };
      places.push({ key, label: `${spec.icon || "🏪"} ${name}${tag}`, color: mine ? "#2e8b57" : "#c0392b", at });
    }
    const block = this.teleportBlock();
    // v7: many shops - push labels apart so they never cover each other (pixels of a 560 px map)
    const px = (c, o) => ((c - o + R) / (2 * R)) * 560;
    const boxes = places.map((p) => ({ p, x: px(p.at.x, C.x), y: px(p.at.z, C.z), w: p.label.length * 7.2 + 26 }))
      .filter((b) => b.x > -40 && b.x < 600 && b.y > -20 && b.y < 580);
    boxes.sort((a, b) => a.y - b.y);
    for (let i = 0; i < boxes.length; i++) {
      for (let j = 0; j < i; j++) {
        const a = boxes[j], b = boxes[i];
        if (Math.abs(a.x - b.x) < (a.w + b.w) / 2 && Math.abs(a.y - b.y) < 30) b.y = a.y + 30;
      }
    }
    spots.innerHTML = boxes.map(({ p, x, y }) => `<div class="map-spot ${block ? "off" : ""}" data-go="${p.key}" style="left:${(x / 560) * 100}%;top:${(Math.min(y, 545) / 560) * 100}%;background:${p.color}" title="${block || "Go there"}">${p.label}</div>`).join("");
  }
  // v7: once the beach is open, the big map shows campus and beach together
  bigMapR() { return this.world.zoneVisible("beach") ? 72 : 58; }
  bigMapCenter() { return this.world.zoneVisible("beach") ? { x: 0, z: 34 } : { x: 0, z: 0 }; }
  closeBigMap() { this.root.querySelector("#bigmap").classList.add("hidden"); }
  teleportBlock() {
    if (this.ui.dialogOpen) return "Close the pop-up first";
    if (this.world.buildingAt(this.player.pos) === "wholesale" && Object.keys(this.view.cart).length) return "Pay for your cart first";
    return "";
  }
  teleportTo(key) {
    const block = this.teleportBlock();
    if (block) { this.ui.toast(block, true); return; }
    if (this.world.buildingAt(this.player.pos) === "wholesale") this.flow.leftWholesaleByMap();
    if (this.inCasino) this.eggs.leaveCasino(true);
    if (key === "wholesale") {
      this.player.teleport({ x: 23.6, z: 0 }, Math.PI / 2);
      this.camYaw = -Math.PI / 2;
    } else this.spawnAt(key);
    this.flow.zoneFlags = {};
    this.closeBigMap();
    this.fadeQuick();
  }
  // v8: tell Python the game time (the bridge saves after every batch)
  autosave() {
    if (this.screen !== "game" || !this.view || this.view.status !== "running" || !this.bridge) return;
    this.bridge.send("autosave", {});
  }
  // In front of a shop, looking at its door (the café: looking at the campus, as since v2)
  spawnAt(shop) {
    const sp = P[shop].spawn, door = P[shop].doorOut;
    const facing = shop === "cafe" ? Math.PI / 2 : Math.atan2(door.x - sp.x, door.z - sp.z);
    this.player.teleport(sp, facing);
    this.camYaw = facing - Math.PI;
  }
  fadeQuick() {
    const f = this.root.querySelector("#fade");
    f.classList.add("on");
    setTimeout(() => f.classList.remove("on"), 250);
  }
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
  releasePointer() {
    if (document.pointerLockElement) { try { document.exitPointerLock(); } catch (e) { /* ignore */ } }
  }

  // ------------------------------------------------------------ data from Python
  onData(data) {
    if (!data) return;
    if (!this.renderer) { this.lighting = data.lighting; this.init(data.config); }
    this.lighting = data.lighting;
    this.titleInfo = { hasSave: data.has_save, info: data.save_info };
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
        this.flow.showTitle(data.has_save, data.save_info);
      }
    }
    this.bridge.receive(data);
    if (this.screen === "game" && data.plan && (data.plan.day !== this.planDay || sessionChanged)) {
      const continuing = sessionChanged && data.view.time > 5.001;
      this.planDay = data.plan.day;
      this.startDay(data.plan, data.view, continuing);
    }
    if (prevView !== this.view && this.ui.current && ["P18"].includes(this.ui.current.id)) this.ui.refreshDialog();
    this.ui.updateHud();
  }

  startDay(plan, view, continuing) {
    this.flow.resetDay(plan, view);
    this.clock.t = view.time;
    this.clock.speed = 1;
    this.clock.paused = false;
    this.ui.showHud(true);
    if (this.ui.current && this.ui.current.id === "P00") this.ui.closeDialog();
    this.eggs.reset();
    // v5: the day starts in front of the shop you run yourself
    this.spawnAt(view.work_shop || "cafe");
    for (const w of Object.values(this.workers)) w.reset();
    this.root.querySelector("#fade").classList.remove("on");
    if (continuing) { this.flow.wholesaleAllowed = false; this.bridge.send("resume", {}, () => {}); }
    if (view.status !== "running") return this.flow.openEnd();
    if (view.day_state === "DAY_SUMMARY") return this.flow.openSummary();
    if (view.day_state === "MORNING_PLANNING" && view.time < 5.01) this.flow.openMorning();
    this.focus();
  }

  // ------------------------------------------------------------------- input
  bindInput() {
    const keys = { ArrowUp: "up", KeyW: "up", ArrowDown: "down", KeyS: "down", ArrowLeft: "left", KeyA: "left",
      ArrowRight: "right", KeyD: "right", ShiftLeft: "run", ShiftRight: "run" };
    // v8: browsers allow sound only after a click or a key press
    window.addEventListener("pointerdown", () => this.sound.unlock(), true);
    window.addEventListener("keydown", () => this.sound.unlock(), true);
    window.addEventListener("keydown", (e) => {
      if (!this.view && e.code !== "Enter") return;
      if (keys[e.code]) { this.input[keys[e.code]] = true; if (e.code.startsWith("Arrow")) e.preventDefault(); }
      if (e.code === "Tab") { e.preventDefault(); if (this.view) this.ui.toggleTab(true); }
      if (e.code === "Space" && this.view) e.preventDefault();
      if (e.repeat) return;
      if (e.code === "Enter") { e.preventDefault(); this.ui.pressPrimary(); }
      if (e.code === "Escape") {
        e.preventDefault();
        if (this.pointerLocked) { this.releasePointer(); return; }
        if (this.ui.current && !this.ui.current.noEsc) this.ui.pressSecondary();
      }
      if (e.code === "KeyE" && !this.ui.dialogOpen) this.interact();
      if (e.code === "KeyP") this.flow.openPause();
      if (e.code === "KeyM" && this.view) {
        // v6: M opens and closes the big map
        if (this.root.querySelector("#bigmap").classList.contains("hidden")) { if (!this.ui.dialogOpen) this.openBigMap(); }
        else this.closeBigMap();
      }
    });
    window.addEventListener("keyup", (e) => {
      if (keys[e.code]) this.input[keys[e.code]] = false;
      if (e.code === "Tab") this.ui.toggleTab(false);
    });
    window.addEventListener("blur", () => { for (const k in this.input) this.input[k] = false; });
    // v5: leaving the browser tab pauses the game
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && this.screen === "game" && this.view && this.view.status === "running") {
        this.autoPause();
        this.autosave(); // v8: save right away when the tab is hidden (laptop closed, app switched)
      }
    });
    // v8 safety: save when the page goes away, and every 10 seconds while playing
    window.addEventListener("pagehide", () => this.autosave());
    window.addEventListener("beforeunload", () => this.autosave());
    setInterval(() => { if (!document.hidden) this.autosave(); }, 10000);

    const canvas = this.renderer.domElement;
    let drag = null;
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
    // The game lives in a shadow DOM (Streamlit component). There, document.pointerLockElement
    // points to the shadow host and not to the canvas, so we ask the canvas' own root.
    const lockedOnCanvas = () => {
      const root = canvas.getRootNode();
      return (root && root.pointerLockElement === canvas) || document.pointerLockElement === canvas;
    };
    this.lockFailed = false;
    canvas.addEventListener("pointerdown", (e) => {
      this.focus();
      if (!this.view || this.ui.dialogOpen) return;
      if (e.button === 2) { drag = { x: e.clientX, y: e.clientY, yaw: this.camYaw, pitch: this.camPitch }; return; }
      if (e.button !== 0) return;
      if (this.pointerLocked) return this.clickAt(window.innerWidth / 2, window.innerHeight / 2); // crosshair
      if (!this.clickAt(e.clientX, e.clientY)) {
        // Clicking empty space captures the mouse for looking around (Esc releases it).
        // Until the capture is active (or if the browser refuses it) dragging also turns the camera.
        drag = { x: e.clientX, y: e.clientY, yaw: this.camYaw, pitch: this.camPitch };
        this.captureMouse();
      }
    });
    this.captureMouse = () => {
      try {
        const p = canvas.requestPointerLock();
        if (p && p.catch) p.catch(() => this.onLockError());
      } catch (err) { this.onLockError(); }
    };
    this.onLockError = () => {
      if (this.lockFailed) return;
      this.lockFailed = true;
      this.ui.toast("Mouse capture is blocked here - hold the mouse button and drag to look around.");
    };
    const onLockChange = () => {
      this.pointerLocked = lockedOnCanvas();
      if (this.pointerLocked) { drag = null; this.lockFailed = false; }
      this.root.querySelector("#crosshair").classList.toggle("hidden", !this.pointerLocked);
      this.root.querySelector("#help").innerHTML = this.pointerLocked
        ? "<b>Mouse</b> look · <b>WASD</b> walk · <b>Shift</b> run · <b>Click / E</b> use · <b>M</b> map · <b>Esc</b> free the mouse"
        : "<b>Click the game</b> for mouse look · <b>WASD</b> walk · <b>Shift</b> run · <b>E</b> use · <b>M</b> map · <b>Tab</b> list · <b>P</b> pause";
    };
    document.addEventListener("pointerlockchange", onLockChange);
    document.addEventListener("pointerlockerror", () => this.onLockError());
    window.addEventListener("mousemove", (e) => {
      if (this.pointerLocked) {
        this.camYaw -= e.movementX * 0.0028;
        this.camPitch = clamp(this.camPitch + e.movementY * 0.0022, 0.12, 1.25);
      } else if (drag) {
        this.camYaw = drag.yaw - (e.clientX - drag.x) * 0.006;
        this.camPitch = clamp(drag.pitch + (e.clientY - drag.y) * 0.004, 0.12, 1.25);
      }
    });
    window.addEventListener("pointerup", () => { drag = null; });
    canvas.addEventListener("wheel", (e) => { e.preventDefault(); this.camDist = clamp(this.camDist * (e.deltaY > 0 ? 1.1 : 0.9), 3.5, 22); }, { passive: false });
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

  // Returns true if the click hit something interactive.
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
        if (dist2(this.player.pos, it.pos) > it.radius + 0.8) { this.ui.toast("Get closer"); return true; }
        it.action();
        return true;
      }
      const a = this.flow.agents.get(o.userData.agentId);
      if (a && a.shop && this.flow.queues[a.shop][0] === a.id && this.isManual(a.shop)) {
        if (!this.flow.playerIn(a.shop) || dist2(this.player.pos, a.pos) > 3.2) { this.ui.toast("Get closer"); return true; }
        this.flow.useCounterFront(a.shop);
        return true;
      }
    }
    return false;
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
  // Reliable third-person camera: always behind the player, looking at the upper body.
  // Inside a building it comes closer and looks down more, so the figure is never
  // hidden behind the counter; walls between camera and player fade out.
  updateCamera(dt) {
    const p = this.player.pos;
    let pos, look;
    let k = 1 - Math.exp(-10 * dt);
    if (this.screen !== "game") {
      const a = performance.now() / 14000;
      pos = new THREE.Vector3(Math.sin(a) * 52, 30, Math.cos(a) * 52);
      look = new THREE.Vector3(0, 0, -2);
      k = 1;
    } else {
      const inside = this.world.buildingAt(p);
      // v5: inside a building the camera may go lower and further back (walls fade out),
      // so you see the door and the customers walking up from behind the counter
      const dist = inside ? Math.min(this.camDist, 9.5) : this.camDist;
      const pitch = inside ? Math.max(this.camPitch, 0.3) : this.camPitch;
      const off = new THREE.Vector3(Math.sin(this.camYaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(this.camYaw) * Math.cos(pitch));
      look = new THREE.Vector3(p.x, 1.35, p.z);
      pos = look.clone().addScaledVector(off, dist);
      pos.y = Math.max(pos.y, 1.2);
    }
    this.camPos.lerp(pos, k);
    this.camLook.lerp(look, 1 - Math.exp(-16 * dt));
    this.camera.position.copy(this.camPos);
    this.camera.lookAt(this.camLook);
  }

  // Which buildings stand between the camera and the player (2D segment vs. rectangle)?
  occluders() {
    const out = new Set();
    const a = { x: this.camera.position.x, z: this.camera.position.z }, b = this.player.pos;
    for (const [key, r] of Object.entries(BUILDINGS)) {
      const steps = 24;
      for (let i = 0; i <= steps; i++) {
        const x = lerp(a.x, b.x, i / steps), z = lerp(a.z, b.z, i / steps);
        if (x > r.x0 - 0.3 && x < r.x1 + 0.3 && z > r.z0 - 0.3 && z < r.z1 + 0.3) { out.add(key); break; }
      }
    }
    return out;
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
      const pr = this.flow.progress;
      if (pr) {
        // progress bars run in game minutes; after 21:00 (clock stopped) cleaning still completes
        const add = dtGameMin > 0 ? dtGameMin : (!c.paused && this.ui.current?.id === "P15" && !c.running ? dt : 0);
        pr.done += add;
        const bar = pr.bar(); if (bar) bar.style.width = `${clamp(pr.done / pr.minutes, 0, 1) * 100}%`;
        if (pr.done >= pr.minutes) { this.flow.progress = null; pr.onDone(); }
      }
      // With the mouse captured the figure always faces where you look (Minecraft style);
      // otherwise it turns towards the walking direction (GTA style).
      this.player.update(dt, this.input, this.camYaw, this.ui.dialogOpen, this.pointerLocked);
      this.flow.updateGate();
      this.flow.updateZones();
      this.flow.updateStudents(dt, dtGameMin);
      for (const wk of Object.values(this.workers)) wk.tick(dt * (c.running ? c.speed : 0), dtGameMin);
      this.separatePeople();
      this.updateWorldState(now);
      this.eggs.update(dt);
    }
    this.applyLighting(this.screen === "game" ? this.clock.t : 12.5);
    this.updateCamera(dt);
    this.eggs.afterCamera();
    if (this.screen === "game" && v) this.updateBuildingFade();
    this.updateLabels();
    this.renderer.render(this.scene, this.camera);
    this.hudTimer += dt;
    if (this.hudTimer > 0.1 && this.view) {
      this.hudTimer = 0; this.ui.updateHud(); this.drawMinimap();
      // v8: the people on the open big map move too (canvas only, the labels stay clickable)
      if (this.bigView && !this.root.querySelector("#bigmap").classList.contains("hidden")) this.renderBigMap(false);
    }
  }

  updateBuildingFade() {
    const inside = this.world.buildingAt(this.player.pos);
    const hide = this.occluders();
    if (inside) hide.add(inside);
    for (const [key, parts] of Object.entries(this.world.buildingParts)) {
      const on = hide.has(key);
      for (const m of parts.wallMats) { m.opacity = on ? 0.16 : 1; m.depthWrite = !on; }
      parts.roof.visible = !on;
      if (parts.sign) parts.sign.visible = !on;
    }
  }

  updateWorldState(now) {
    const v = this.view, w = this.world;
    const it = this.nearestInteractable();
    if (this.highlighted !== it) {
      if (this.highlighted) for (const m of this.highlighted.meshes) if (m.material?.emissive) m.material.emissive.setHex(0x000000);
      if (it) for (const m of it.meshes) if (m.material?.emissive) m.material.emissive.setHex(0x664400);
      this.highlighted = it;
    }
    this.currentHint = it && !this.ui.dialogOpen ? it : null;
    w.updateShelves(v);
    w.updateMechanics(v);
    // Roof colour shows the owner: green = yours, otherwise the shop's own colour
    for (const key of Object.keys(this.config.shops)) {
      if (key === "cafe" || !w.buildingParts[key]) continue;
      w.buildingParts[key].roof.material.color.setHex(v.shops[key].owner === "player" ? 0x2e8b57 : BUILDINGS[key].roof);
    }
    w.floorSpot.visible = v.day_state === "CLOSING" && !!v.cleaning.cafe && v.cleaning.cafe.floor === false;
    w.updatePriceBoards(v);
    this.staff.cashier.animate(0);
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
      const now = performance.now();
      for (const a of this.flow.agents.values()) {
        if (!a.figure.visible || dist2(a.pos, this.player.pos) > 40) continue;
        if (a.emote && a.emote.until > now) {
          const e = ui.label("b" + a.id, `<div class="bubble emote" style="position:relative">${a.emote.icon}</div>`);
          ui.placeLabel(e, new THREE.Vector3(a.pos.x, 2.15, a.pos.z), this.camera, W, H);
          continue;
        }
        if (!["to_shop", "queue", "served"].includes(a.mode)) continue;
        const items = a.order || a.wanted || [];
        if (!items.length && !(a.soldOut || []).length) continue;
        const icons = items.map((p) => this.config.products[p].icon).join("") +
          (a.soldOut || []).map((p) => `<span class="gone" title="sold out"><span class="ico">${this.config.products[p].icon}</span><i>sold out</i></span>`).join("");
        let pat = "";
        if (a.mode === "queue" && this.view.open) {
          const f = clamp(a.patience / a.patienceMax, 0, 1);
          pat = `<div class="patience"><div style="width:${f * 100}%;background:${f > 0.5 ? "#2f9e5b" : f > 0.25 ? "#f2c94c" : "#d9534f"}"></div></div>`;
        } else if (a.mode === "served") pat = `<div class="serving">being served</div>`;
        const n = items.length + (a.soldOut || []).length;
        const e = ui.label("b" + a.id, `<div class="stack">${pat}<div class="bubble n${Math.min(3, n)}" style="position:relative">${icons}</div></div>`);
        ui.placeLabel(e, new THREE.Vector3(a.pos.x, 2.15, a.pos.z), this.camera, W, H);
      }
      // v6: what the staff are doing right now (making coffee, pressing juice, cleaning)
      for (const [shop, w] of Object.entries(this.workers)) {
        if (!w.figure.visible || !w.activity || dist2(w.pos, this.player.pos) > 40) continue;
        const pct = Math.round(clamp(w.activity.progress, 0, 1) * 100);
        const e = ui.label("w" + shop, `<div class="stack"><div class="work-tag">${w.activity.icon} ${esc(w.activity.text)}</div>` +
          `<div class="patience"><div style="width:${pct}%;background:#2a9d8f"></div></div></div>`);
        ui.placeLabel(e, new THREE.Vector3(w.pos.x, 2.25, w.pos.z), this.camera, W, H);
      }
    }
    if (this.screen === "game" && this.view) this.eggs.labels(ui, W, H);
    ui.endLabels();
  }

  // Nobody walks through anybody: people push each other apart, the player is pushed out of them.
  separatePeople() {
    const now = performance.now();
    // v6: a walker that hardly moved for a second is stuck in a group: it may pass through
    // the others for 2.5 s (ghost), so groups never block each other for good.
    for (const a of this.flow.agents.values()) {
      if (!a.figure.visible || !a.path.length) { a.stuckSince = null; continue; }
      if (!a.lastCheck || now - a.lastCheck.t > 1000) {
        if (a.lastCheck && dist2(a.pos, a.lastCheck) < 0.04 && this.clock.running) a.ghostUntil = now + 2500;
        a.lastCheck = { x: a.pos.x, z: a.pos.z, t: now };
      }
    }
    const list = [...this.flow.agents.values()].filter((a) => a.figure.visible && !(a.ghostUntil > now));
    for (const wk of Object.values(this.workers)) if (wk.figure.visible) list.push(wk);
    const R = 0.62;
    for (let i = 0; i < list.length; i++) {
      for (let j = i + 1; j < list.length; j++) {
        const a = list[i], b = list[j];
        const dx = b.pos.x - a.pos.x, dz = b.pos.z - a.pos.z;
        const d = Math.hypot(dx, dz);
        if (d >= R || d < 1e-4) continue;
        const push = (R - d) / 2, nx = dx / d, nz = dz / d;
        // somebody standing in the queue or at work stays put; the one walking steps aside
        const aFix = a.anchored && a.anchored(), bFix = b.anchored && b.anchored();
        const wa = aFix ? 0 : bFix ? 1 : 0.5, wb = bFix ? 0 : aFix ? 1 : 0.5;
        a.pos.x -= nx * push * 2 * wa; a.pos.z -= nz * push * 2 * wa;
        b.pos.x += nx * push * 2 * wb; b.pos.z += nz * push * 2 * wb;
        this.world.keepOutOfWalls(a.pos, 0.3); this.world.keepOutOfWalls(b.pos, 0.3);
        a.figure.place(a.pos); b.figure.place(b.pos);
      }
    }
    const p = this.player.pos;
    for (const a of list) {
      const dx = p.x - a.pos.x, dz = p.z - a.pos.z, d = Math.hypot(dx, dz);
      if (d < 0.6 && d > 1e-4) { p.x = a.pos.x + (dx / d) * 0.6; p.z = a.pos.z + (dz / d) * 0.6; }
    }
    this.world.keepOutOfWalls(p, 0.35);
  }

  // ------------------------------------------------------------------ minimap
  drawMinimap() { this.drawMap(this.minimap, 200, 62, true, this.player.pos.z > 72 ? { x: 0, z: 96 } : { x: 0, z: 0 }); }

  // Shared by the minimap (small, centred on the campus) and the big map (clickable places).
  drawMap(ctx, S, R, small, C = { x: 0, z: 0 }) {
    const mx = (x) => (x - C.x + R) / (2 * R) * S, my = (z) => (z - C.z + R) / (2 * R) * S;
    const k = S / 200;
    ctx.clearRect(0, 0, S, S);
    ctx.fillStyle = "#79c25a"; ctx.fillRect(0, 0, S, S);
    const path = (x0, x1, z0, z1) => ctx.fillRect(mx(x0), my(z0), mx(x1) - mx(x0), my(z1) - my(z0));
    // v7: beach and sea (greyed out while the beach is closed)
    ctx.fillStyle = "#f2d9a0"; path(-75, 75, 76, 122);
    ctx.fillStyle = "#2e86c1"; path(-200, 200, 122, 260);
    ctx.fillStyle = "#8d6e63"; path(-66, 66, 73.8, 74.2);
    ctx.fillStyle = "#efe3c8";
    path(-80, 80, -2.2, 2.2); path(-2.2, 2.2, -16, 80); path(-60, 60, 79.8, 83.2);
    ctx.beginPath(); ctx.arc(mx(0), my(6), 8 / (2 * R) * S, 0, Math.PI * 2); ctx.fill();
    const v = this.view;
    for (const [key, b] of Object.entries(BUILDINGS)) {
      const locked = !this.world.zoneVisible(b.zone);
      if (locked && small) continue;
      const shop = this.config.shops[key];
      ctx.fillStyle = locked ? "#9e9e9e" : key === "wholesale" ? "#2c6fbb" : v.shops[key].owner === "player" ? "#2e8b57" : v.for_sale === key ? "#e67e22" : "#c0392b";
      ctx.fillRect(mx(b.x0), my(b.z0), mx(b.x1) - mx(b.x0), my(b.z1) - my(b.z0));
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.5 * k;
      ctx.strokeRect(mx(b.x0), my(b.z0), mx(b.x1) - mx(b.x0), my(b.z1) - my(b.z0));
      ctx.font = `${small ? 16 : 30}px serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(locked ? "🔒" : key === "wholesale" ? "🏬" : shop.icon || "🏪", mx((b.x0 + b.x1) / 2), my((b.z0 + b.z1) / 2));
      if (locked) { // v8: you can look at the beach on the big map before it opens
        ctx.font = "700 13px sans-serif"; ctx.fillStyle = "#3d3d3d";
        ctx.fillText(shop.name, mx((b.x0 + b.x1) / 2), my(b.z0) - 10);
      }
      // v8: SnackBots' machines on the campus
      if (P[key] && P[key].machines) {
        for (const m of Object.values(P[key].machines)) {
          ctx.fillStyle = v.shops[key].owner === "player" ? "#2e8b57" : "#1565c0";
          ctx.fillRect(mx(m.pos.x) - 3 * k, my(m.pos.z) - 3 * k, 6 * k, 6 * k);
        }
      }
    }
    ctx.fillStyle = "#3d3d3d";
    for (const a of this.flow.agents.values()) {
      if (!a.figure.visible) continue;
      ctx.beginPath(); ctx.arc(mx(a.pos.x), my(a.pos.z), 2 * k, 0, Math.PI * 2); ctx.fill();
    }
    const target = this.flow.objectiveTarget();
    if (target) {
      ctx.strokeStyle = "#ffd166"; ctx.lineWidth = 3 * k;
      ctx.beginPath(); ctx.arc(mx(target.x), my(target.z), (6 + Math.sin(performance.now() / 250) * 1.5) * k, 0, Math.PI * 2); ctx.stroke();
    }
    // Player arrow (pointing where the figure looks) and the camera's view direction
    const p = this.inCasino ? this.eggs.entryFront : this.player.pos, f = this.player.facing; // v8: underground = at the hatch
    ctx.save();
    ctx.translate(mx(p.x), my(p.z));
    ctx.scale(k, k);
    ctx.fillStyle = "rgba(255,255,255,0.25)";
    const cy = this.camYaw + Math.PI; // camera looks opposite to its offset
    ctx.beginPath(); ctx.moveTo(0, 0);
    ctx.arc(0, 0, 26, Math.atan2(Math.cos(cy), Math.sin(cy)) - 0.5, Math.atan2(Math.cos(cy), Math.sin(cy)) + 0.5); ctx.fill();
    ctx.rotate(Math.atan2(Math.cos(f), Math.sin(f)) - Math.PI / 2 + Math.PI);
    ctx.fillStyle = "#ffd166"; ctx.strokeStyle = "#2b2118"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(0, -8); ctx.lineTo(6, 6); ctx.lineTo(0, 3); ctx.lineTo(-6, 6); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
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
