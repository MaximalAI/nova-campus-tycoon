// ---------------------------------------------------------------------------
// v8 easter eggs (rules in easter_eggs.py):
//  - Jep stands somewhere on the campus every day. He sells a joint; the player smokes
//    it and is high for 10 game minutes (colours drift, the camera sways, slower walking).
//  - Behind the bowl bar a broken vending machine slides aside: a ladder leads down into
//    an underground casino with a roulette table.
// ---------------------------------------------------------------------------
const CASINO_ROOM = { x: 0, z: -170, w: 22, d: 16, h: 6 }; // far north of the map, nobody sees it from outside
const WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
const RED_NUMBERS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

class EasterEggs {
  constructor(game) {
    this.game = game;
    this.cfg = game.config.easter_eggs;
    this.smoke = [];
    this.smokeT = 0;
    this.smokingUntil = 0; // performance.now() while the first joint is smoked
    this.puffUntil = 0;
    this.history = [];
    this.bet = "red";
    this.chip = this.cfg.casino.chips[0];
    this.lastSpin = null;
    this.spinning = false;
    this.buildJep();
    this.buildEntry();
    this.buildCasino();
    this.buildHighOverlay();
  }

  get v() { return this.game.view; }
  get w() { return this.game.world; }

  // ------------------------------------------------------------------ Jep
  buildJep() {
    const g = this.game;
    // His own look: bucket hat, round sunglasses, a loud flower shirt, a little goatee.
    this.jep = new Figure(g.scene, { shirt: 0x00a7a7, pants: 0x4e342e, hair: 0x6d4c41, skin: 0xe0ac69 });
    const grp = this.jep.group, M = (c) => new THREE.MeshLambertMaterial({ color: c });
    const add = (geo, c, x, y, z) => { const m = new THREE.Mesh(geo, M(c)); m.position.set(x, y, z); grp.add(m); return m; };
    add(new THREE.CylinderGeometry(0.36, 0.36, 0.03, 18), 0x6b8e23, 0, 1.74, 0); // hat brim
    add(new THREE.CylinderGeometry(0.21, 0.25, 0.2, 16), 0x6b8e23, 0, 1.84, 0); // hat crown
    add(new THREE.CylinderGeometry(0.255, 0.255, 0.05, 16), 0xffd54f, 0, 1.77, 0); // hat band
    for (const x of [-0.08, 0.08]) {
      const lens = add(new THREE.CylinderGeometry(0.065, 0.065, 0.02, 14), 0x111111, x, 1.61, 0.215);
      lens.rotation.x = Math.PI / 2;
    }
    add(new THREE.BoxGeometry(0.1, 0.015, 0.02), 0x111111, 0, 1.62, 0.22); // bridge of the glasses
    add(new THREE.BoxGeometry(0.08, 0.07, 0.04), 0x6d4c41, 0, 1.44, 0.2); // goatee
    // flowers on the shirt
    const flowers = [[-0.15, 1.18, 0xffeb3b], [0.12, 0.95, 0xff4081], [0.16, 1.24, 0xffffff], [-0.1, 0.86, 0xff9800]];
    for (const [x, y, c] of flowers) add(new THREE.BoxGeometry(0.09, 0.09, 0.02), c, x, y, 0.16);
    this.jep.visible = false;
    this.jepPos = { x: 999, z: 999 };
    this.jepCollider = this.w.collide(999, 999.6, 999, 999.6);
    this.jepIt = this.w.addInteractable({
      id: "jep", pos: this.jepPos, radius: 2.2, meshes: [], priority: 1,
      label: () => `Talk to ${this.cfg.jep.name}`, enabled: () => this.jep.visible && !this.game.inCasino,
      action: () => this.openJep(),
    });
  }

  placeJep() {
    const s = this.v && this.v.jep;
    if (!s) { this.jep.visible = false; return; }
    if (s.x !== this.jepPos.x || s.z !== this.jepPos.z) {
      this.jepPos.x = s.x; this.jepPos.z = s.z;
      this.jep.place(this.jepPos);
      Object.assign(this.jepCollider, { x0: s.x - 0.3, x1: s.x + 0.3, z0: s.z - 0.3, z1: s.z + 0.3 });
    }
    this.jep.visible = this.game.screen === "game";
  }

  openJep() {
    const v = this.v, price = this.cfg.jep.price, high = this.isHigh();
    this.game.ui.showDialog({
      id: "P40", icon: "🌿", title: this.cfg.jep.name, unique: true,
      text: high
        ? `"Easy, my friend, you are still flying. Come back later."`
        : `"Hey boss. All that coffee makes you nervous, no? I have something to relax. ` +
          `Only ${euro(price)}, best quality on the whole campus."`,
      rows: [{ label: "Your cash", value: euro(v.money) }],
      secondary: { label: high ? "Later" : "No thanks" },
      primary: high ? undefined : { label: `Buy a joint (${euro(price)})`, disabled: v.money < price, action: () => {
        this.game.flow.send("buy_from_jep", {}, this.game.flow.ok(() => this.startSmoking()));
      } },
    });
  }

  startSmoking() {
    const now = performance.now();
    this.smokingUntil = now + 5500;
    this.nextPuff = now + 400;
    this.game.sound.play("lighter");
    this.game.ui.toast("You light up the joint... everything feels very relaxed.");
    this.showJoint(true);
  }

  showJoint(on) {
    const arm = this.game.player.figure.armR;
    if (!this.joint) {
      const j = new THREE.Group();
      const paper = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.026, 0.16, 8), new THREE.MeshLambertMaterial({ color: 0xf5f5f5 }));
      paper.rotation.x = Math.PI / 2; j.add(paper);
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.03, 8, 6), new THREE.MeshBasicMaterial({ color: 0xff6d00 }));
      tip.position.z = 0.09; j.add(tip);
      j.position.set(0, -0.64, 0.1);
      arm.add(j);
      this.joint = j;
    }
    this.joint.visible = on;
  }

  isHigh() { return !!(this.v && this.game.clock.t < (this.v.high_until || 0)); }

  puff() {
    // a little cloud from the hand
    const hand = new THREE.Vector3(0, -0.64, 0.18);
    this.game.player.figure.armR.localToWorld(hand);
    for (let i = 0; i < 4; i++) this.spawnSmoke(hand, i * 0.08);
    this.game.sound.play("smoke");
    this.puffUntil = performance.now() + 900;
  }

  spawnSmoke(at, delay = 0) {
    if (!this.smokeMat) this.smokeMat = new THREE.MeshBasicMaterial({ color: 0xdedede, transparent: true, opacity: 0.5, depthWrite: false });
    if (!this.smokeGeo) this.smokeGeo = new THREE.SphereGeometry(0.09, 8, 6);
    const m = new THREE.Mesh(this.smokeGeo, this.smokeMat.clone());
    m.position.copy(at);
    this.game.scene.add(m);
    this.smoke.push({ m, age: -delay, life: 2.2, vx: (Math.random() - 0.5) * 0.25, vz: (Math.random() - 0.5) * 0.25 });
  }

  updateSmoke(dt) {
    for (const s of this.smoke) {
      s.age += dt;
      if (s.age < 0) { s.m.visible = false; continue; }
      s.m.visible = true;
      s.m.position.y += dt * 0.45; s.m.position.x += s.vx * dt; s.m.position.z += s.vz * dt;
      s.m.scale.setScalar(1 + s.age * 1.8);
      s.m.material.opacity = Math.max(0, 0.5 * (1 - s.age / s.life));
    }
    const dead = this.smoke.filter((s) => s.age >= s.life);
    for (const s of dead) { this.game.scene.remove(s.m); s.m.material.dispose(); }
    if (dead.length) this.smoke = this.smoke.filter((s) => s.age < s.life);
  }

  buildHighOverlay() {
    const root = this.game.root;
    this.fx = el("div", "", "");
    this.fx.id = "high-fx";
    root.appendChild(this.fx);
    this.badge = el("div", "glass", "");
    this.badge.id = "high-badge";
    this.badge.classList.add("hidden");
    root.querySelector("#hud").appendChild(this.badge);
  }

  updateHigh(dt) {
    const g = this.game, high = this.isHigh() && g.screen === "game";
    const canvas = g.renderer.domElement;
    const now = performance.now();
    if (high) {
      const t = now / 1000;
      if (!this.wasHigh) { this.showJoint(true); g.player.walkSpeed = 3.3; g.player.runSpeed = 5.6; }
      canvas.style.filter = `hue-rotate(${Math.round(Math.sin(t * 0.35) * 70)}deg) saturate(${1.5 + Math.sin(t * 0.9) * 0.3})`;
      this.fx.style.opacity = String(0.35 + Math.sin(t * 1.3) * 0.15);
      const left = Math.max(1, Math.ceil((this.v.high_until - g.clock.t) * 60));
      this.badge.innerHTML = `😵‍💫 High · ${left} min`;
      this.badge.classList.remove("hidden");
      // a puff every few seconds while the effect lasts
      if (now > this.smokingUntil && (!this.nextPuff || now > this.nextPuff)) { this.puff(); this.nextPuff = now + 4200; }
    } else if (this.wasHigh) {
      canvas.style.filter = ""; this.fx.style.opacity = "0";
      this.badge.classList.add("hidden");
      g.player.walkSpeed = 4.6; g.player.runSpeed = 8.0;
      g.camera.fov = 58; g.camera.updateProjectionMatrix();
      this.showJoint(false);
      g.ui.toast("The effect is gone. Back to business.");
    }
    if (now < this.smokingUntil && now > this.nextPuff) { this.puff(); this.nextPuff = now + 1400; }
    this.wasHigh = high;
  }

  // the arm goes to the mouth while puffing (after Figure.animate set the walking pose)
  updateArm() {
    const arm = this.game.player.figure.armR;
    if (performance.now() < this.puffUntil) { arm.rotation.x = -2.5; arm.rotation.z = 0.5; }
  }

  // ------------------------------------------------------------------ casino entrance
  buildEntry() {
    const e = this.cfg.casino.entry, w = this.w;
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.3, 2.1, 0.8), w.mat(0x455a64)); body.position.y = 1.05; body.castShadow = true; g.add(body);
    const glass = new THREE.Mesh(new THREE.BoxGeometry(0.85, 1.3, 0.05), new THREE.MeshLambertMaterial({ color: 0x37474f, transparent: true, opacity: 0.8 }));
    glass.position.set(-0.12, 1.25, 0.42); g.add(glass);
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.3), new THREE.MeshBasicMaterial({ map: w.textTexture("OUT OF ORDER", "#fff59d", "#b71c1c", 512, 128, 64) }));
    sign.position.set(0, 1.3, 0.455); sign.rotation.z = 0.12; g.add(sign);
    const tape = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.08, 0.02), w.mat(0xffeb3b)); tape.position.set(0, 0.7, 0.42); tape.rotation.z = -0.3; g.add(tape);
    g.position.set(e.x, 0, e.z); g.rotation.y = e.rot;
    w.scene.add(g);
    this.entryMachine = g;
    this.entryMeshes = [body, glass];
    const fx = Math.sin(e.rot), fz = Math.cos(e.rot); // front direction
    const lx = Math.cos(e.rot), lz = -Math.sin(e.rot); // to the machine's right
    this.entryFront = { x: e.x + fx * 1.4, z: e.z + fz * 1.4 };
    this.entrySlide = { x: e.x + lx * 1.5, z: e.z + lz * 1.5 };
    this.entryHome = { x: e.x, z: e.z };
    const half = Math.abs(fx) > 0.5 ? [0.45, 0.7] : [0.7, 0.45];
    this.entryCollider = w.collide(e.x - half[0], e.x + half[0], e.z - half[1], e.z + half[1]);
    this.entryHalf = half;
    // the hatch below the machine with the top of the ladder
    const hatch = new THREE.Group();
    const hole = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.8), new THREE.MeshBasicMaterial({ color: 0x050308 }));
    hole.rotation.x = -Math.PI / 2; hole.position.y = 0.03; hatch.add(hole);
    for (const s of [-0.3, 0.3]) { const rail = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.5, 0.05), w.mat(0x8d6e63)); rail.position.set(s, 0.2, 0); hatch.add(rail); }
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.7), new THREE.MeshBasicMaterial({ color: 0x9c27b0, transparent: true, opacity: 0.35 }));
    glow.rotation.x = -Math.PI / 2; glow.position.y = 0.035; hatch.add(glow);
    hatch.position.set(e.x, 0, e.z); hatch.rotation.y = e.rot; hatch.visible = false;
    w.scene.add(hatch);
    this.hatch = hatch;
    w.addInteractable({
      id: "casino_entry", pos: this.entryFront, radius: 1.8, meshes: this.entryMeshes,
      label: () => (this.found() ? "Climb down the ladder" : "Look at the broken machine"),
      enabled: () => !!this.v && !this.game.inCasino,
      action: () => this.openEntry(),
    });
  }

  found() { return !!(this.v && this.v.casino && this.v.casino.found) || this.slidOpen; }

  openEntry() {
    if (this.found()) return this.enterCasino();
    this.game.ui.showDialog({
      id: "P41", icon: "🕳️", title: "A broken machine", unique: true,
      text: "The machine is unplugged and stands a bit crooked. When you lean against it, it slides aside: " +
        "a rusty ladder leads down into the dark. Faint music and the clicking of a roulette ball come from below.",
      secondary: { label: "Leave it" },
      primary: { label: "Climb down", action: () => { this.slideOpen(); setTimeout(() => this.enterCasino(), 600); } },
    });
  }

  slideOpen() {
    if (this.slidOpen) return;
    this.slidOpen = true;
    this.entryMachine.position.set(this.entrySlide.x, 0, this.entrySlide.z);
    const h = this.entryHalf, s = this.entrySlide;
    Object.assign(this.entryCollider, { x0: s.x - h[0], x1: s.x + h[0], z0: s.z - h[1], z1: s.z + h[1] });
    this.hatch.visible = true;
    this.game.sound.play("box");
  }

  // ------------------------------------------------------------------ casino room
  buildCasino() {
    const w = this.w, R = CASINO_ROOM, scene = w.scene;
    const room = new THREE.Group();
    room.position.set(R.x, 0, R.z);
    scene.add(room);
    this.room = room;
    // the room is a box seen from inside (BackSide): from outside the camera looks through it
    const carpet = document.createElement("canvas"); carpet.width = 256; carpet.height = 256;
    const cg = carpet.getContext("2d");
    cg.fillStyle = "#4a0d2e"; cg.fillRect(0, 0, 256, 256);
    cg.strokeStyle = "#c9a227"; cg.lineWidth = 3;
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { cg.beginPath(); cg.arc(32 + i * 64, 32 + j * 64, 18, 0, Math.PI * 2); cg.stroke(); }
    const ctex = new THREE.CanvasTexture(carpet); ctex.wrapS = ctex.wrapT = THREE.RepeatWrapping; ctex.repeat.set(5, 4); ctex.colorSpace = THREE.SRGBColorSpace;
    const wall = new THREE.MeshLambertMaterial({ color: 0x2a1238, side: THREE.BackSide });
    const mats = [wall, wall, new THREE.MeshLambertMaterial({ color: 0x120818, side: THREE.BackSide }),
      new THREE.MeshLambertMaterial({ map: ctex, side: THREE.BackSide }), wall, wall];
    const shell = new THREE.Mesh(new THREE.BoxGeometry(R.w, R.h, R.d), mats);
    shell.position.y = R.h / 2 + 0.03; room.add(shell); // floor just above the campus ground plane
    // gold trim along the walls
    const gold = new THREE.MeshLambertMaterial({ color: 0xc9a227, emissive: 0x3a2a00 });
    for (const [x, z, sx, sz] of [[0, -R.d / 2 + 0.05, R.w, 0.1], [0, R.d / 2 - 0.05, R.w, 0.1], [-R.w / 2 + 0.05, 0, 0.1, R.d], [R.w / 2 - 0.05, 0, 0.1, R.d]]) {
      for (const y of [0.9, 4.6]) { const t = new THREE.Mesh(new THREE.BoxGeometry(sx, 0.08, sz), gold); t.position.set(x, y, z); room.add(t); }
    }
    // neon sign
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(7, 1.1), new THREE.MeshBasicMaterial({ map: w.textTexture("CASINO SUBTERRÂNEO", "#14051f", "#e040fb", 1024, 160, 92) }));
    sign.position.set(0, 4.0, -R.d / 2 + 0.06); room.add(sign);
    // roulette table with the wheel
    const table = new THREE.Mesh(new THREE.BoxGeometry(4.2, 0.9, 2.2), new THREE.MeshLambertMaterial({ color: 0x5d4037 }));
    table.position.set(0, 0.45, -2.5); room.add(table);
    const felt = new THREE.Mesh(new THREE.BoxGeometry(4.0, 0.04, 2.0), new THREE.MeshLambertMaterial({ color: 0x1b5e20 }));
    felt.position.set(0, 0.92, -2.5); room.add(felt);
    const layout = new THREE.Mesh(new THREE.PlaneGeometry(2.3, 1.4), new THREE.MeshBasicMaterial({ map: this.layoutTexture() }));
    layout.rotation.x = -Math.PI / 2; layout.position.set(0.6, 0.945, -2.5); room.add(layout);
    const bowl = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.7, 0.16, 32), new THREE.MeshLambertMaterial({ color: 0x3e2723 }));
    bowl.position.set(-1.35, 1.0, -2.5); room.add(bowl);
    this.wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.05, 37), [
      new THREE.MeshLambertMaterial({ color: 0x3e2723 }), new THREE.MeshBasicMaterial({ map: this.wheelTexture() }), new THREE.MeshLambertMaterial({ color: 0x3e2723 })]);
    this.wheel.position.set(-1.35, 1.1, -2.5); room.add(this.wheel);
    const spindle = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.06, 0.25, 10), gold); spindle.position.set(-1.35, 1.22, -2.5); room.add(spindle);
    this.ball = new THREE.Mesh(new THREE.SphereGeometry(0.035, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    this.ball.position.set(-1.35 + 0.5, 1.15, -2.5); room.add(this.ball);
    this.wheelAngle = 0; this.ballAngle = 0;
    // the croupier behind the table
    this.croupier = new Figure(scene, { shirt: 0x111111, pants: 0x111111, hair: 0xdedede, skin: 0xd7a17a });
    const tie = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.06, 0.03), new THREE.MeshLambertMaterial({ color: 0xb71c1c }));
    tie.position.set(0, 1.3, 0.16); this.croupier.group.add(tie);
    this.croupier.place({ x: R.x, z: R.z - 4.1 });
    // mystic things: candles, floating orbs, a crystal ball on a side table
    this.orbs = [];
    const orbMat = new THREE.MeshBasicMaterial({ color: 0xce93d8, transparent: true, opacity: 0.8 });
    for (let i = 0; i < 7; i++) {
      const o = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 10), orbMat);
      o.position.set(-9 + i * 3, 4.2, (i % 2 ? 1 : -1) * 7.2); room.add(o);
      this.orbs.push({ o, base: 4.2, ph: i * 1.3 });
    }
    for (const [x, z] of [[-9.5, -6.5], [9.5, -6.5], [-9.5, 6.5], [9.5, 6.5]]) {
      const stand = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.18, 1.2, 10), gold); stand.position.set(x, 0.6, z); room.add(stand);
      const flame = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffb300 }));
      flame.position.set(x, 1.32, z); room.add(flame);
    }
    const side = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.8, 16), new THREE.MeshLambertMaterial({ color: 0x311b92 }));
    side.position.set(7.5, 0.4, -3.5); room.add(side);
    this.crystal = new THREE.Mesh(new THREE.SphereGeometry(0.3, 18, 14), new THREE.MeshBasicMaterial({ color: 0x80deea, transparent: true, opacity: 0.7 }));
    this.crystal.position.set(7.5, 1.12, -3.5); room.add(this.crystal);
    // ladder up to the hatch
    for (const s of [-0.35, 0.35]) { const rail = new THREE.Mesh(new THREE.BoxGeometry(0.08, R.h, 0.08), w.mat(0x8d6e63)); rail.position.set(s, R.h / 2, R.d / 2 - 0.4); room.add(rail); }
    for (let y = 0.4; y < R.h; y += 0.45) { const rung = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.05, 0.05), w.mat(0xa1887f)); rung.position.set(0, y, R.d / 2 - 0.4); room.add(rung); }
    const hole = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.9), new THREE.MeshBasicMaterial({ color: 0xfff8e1 }));
    hole.rotation.x = Math.PI / 2; hole.position.set(0, R.h - 0.02, R.d / 2 - 0.5); room.add(hole);
    // light: purple and gold lamps (only on while you are down here)
    this.lights = [new THREE.PointLight(0xe040fb, 0, 26, 1.2), new THREE.PointLight(0xffc46b, 0, 14, 1.4), new THREE.PointLight(0x7c4dff, 0, 26, 1.2)];
    this.lights[0].position.set(-6, 4.5, 0); this.lights[1].position.set(0, 3.2, -2.5); this.lights[2].position.set(6, 4.5, 2);
    for (const l of this.lights) room.add(l);
    // walls for the player
    const X = R.x, Z = R.z;
    w.collide(X - R.w / 2 - 1, X + R.w / 2 + 1, Z - R.d / 2 - 1, Z - R.d / 2 + 0.3);
    w.collide(X - R.w / 2 - 1, X + R.w / 2 + 1, Z + R.d / 2 - 0.3, Z + R.d / 2 + 1);
    w.collide(X - R.w / 2 - 1, X - R.w / 2 + 0.3, Z - R.d / 2, Z + R.d / 2);
    w.collide(X + R.w / 2 - 0.3, X + R.w / 2 + 1, Z - R.d / 2, Z + R.d / 2);
    w.collide(X - 2.1, X + 2.1, Z - 3.6, Z - 1.4); // table
    w.collide(X + 7.0, X + 8.0, Z - 4.0, Z - 3.0); // crystal ball
    this.ladderFoot = { x: X, z: Z + R.d / 2 - 1.3 };
    w.addInteractable({ id: "roulette", pos: { x: X, z: Z - 0.9 }, radius: 2.4, meshes: [], priority: 1,
      label: () => "Play roulette", enabled: () => !!this.game.inCasino, action: () => this.openRoulette() });
    w.addInteractable({ id: "casino_exit", pos: this.ladderFoot, radius: 1.8, meshes: [],
      label: () => "Climb up the ladder", enabled: () => !!this.game.inCasino, action: () => this.leaveCasino() });
    w.addInteractable({ id: "crystal_ball", pos: { x: X + 7.5, z: Z - 2.4 }, radius: 1.6, meshes: [],
      label: () => "Look into the crystal ball", enabled: () => !!this.game.inCasino, action: () => this.crystalBall() });
  }

  wheelTexture() {
    const c = document.createElement("canvas"); c.width = c.height = 512;
    const g = c.getContext("2d"), n = WHEEL_ORDER.length, r = 250;
    g.translate(256, 256);
    WHEEL_ORDER.forEach((num, i) => {
      const a0 = (i / n) * Math.PI * 2, a1 = ((i + 1) / n) * Math.PI * 2;
      g.fillStyle = num === 0 ? "#2e7d32" : RED_NUMBERS.has(num) ? "#c62828" : "#111111";
      g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, r, a0, a1); g.closePath(); g.fill();
      g.save(); g.rotate((a0 + a1) / 2); g.fillStyle = "#ffffff"; g.font = "bold 22px sans-serif"; g.textAlign = "center";
      g.fillText(String(num), r - 26, 8); g.restore();
    });
    g.fillStyle = "#6d4c41"; g.beginPath(); g.arc(0, 0, 120, 0, Math.PI * 2); g.fill();
    g.strokeStyle = "#c9a227"; g.lineWidth = 6; g.stroke();
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }

  layoutTexture() {
    const c = document.createElement("canvas"); c.width = 512; c.height = 320;
    const g = c.getContext("2d");
    g.fillStyle = "#1b5e20"; g.fillRect(0, 0, 512, 320);
    g.strokeStyle = "#ffffff"; g.lineWidth = 3; g.fillStyle = "#ffffff"; g.textAlign = "center"; g.textBaseline = "middle";
    const cell = (x, y, w, h, text, bg) => {
      if (bg) { g.fillStyle = bg; g.fillRect(x, y, w, h); g.fillStyle = "#ffffff"; }
      g.strokeRect(x, y, w, h); g.font = "bold 30px sans-serif"; g.fillText(text, x + w / 2, y + h / 2);
    };
    cell(10, 10, 160, 90, "1-12"); cell(176, 10, 160, 90, "13-24"); cell(342, 10, 160, 90, "25-36");
    cell(10, 115, 118, 90, "EVEN"); cell(133, 115, 118, 90, "", "#c62828"); cell(256, 115, 118, 90, "", "#111111"); cell(379, 115, 123, 90, "ODD");
    g.font = "italic 26px serif"; g.fillText("pays 2:1 · 1:1 · 0 takes all", 256, 260);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }

  enterCasino() {
    const g = this.game;
    g.fade(() => {
      g.inCasino = true;
      g.player.teleport({ x: this.ladderFoot.x, z: this.ladderFoot.z - 4 }, Math.PI);
      g.camYaw = 0; g.camDist = Math.min(g.camDist, 6); g.camPitch = 0.35;
      for (const l of this.lights) l.intensity = 2.2;
      g.sound.setMood("casino");
      g.sound.play("ladder");
      g.flow.send("enter_casino", {}, (r) => {
        if (r.ok && r.result.first_visit) g.ui.toast("You found the secret casino!");
      });
    });
  }

  leaveCasino(quick = false) {
    const g = this.game;
    const out = () => {
      g.inCasino = false;
      for (const l of this.lights) l.intensity = 0;
      g.sound.setMood("campus");
      if (!quick) {
        const e = this.cfg.casino.entry;
        g.player.teleport(this.entryFront, e.rot);
        g.camYaw = e.rot + Math.PI;
        g.sound.play("ladder");
      }
    };
    if (quick) out(); else g.fade(out);
  }

  crystalBall() {
    const v = this.v, c = v.casino || { net: 0, spins: 0 };
    const lines = [
      "The mist swirls... you see a campus full of green roofs.",
      "The mist whispers: the house always wins in the end.",
      `The mist shows a number: ${c.spins} spins, ${c.net >= 0 ? "+" : ""}${euro(c.net)} so far.`,
      "You see a long queue at a café. Is it yours?",
    ];
    this.game.ui.toast(lines[Math.floor(performance.now() / 1000) % lines.length]);
  }

  // ------------------------------------------------------------------ roulette (P42)
  openRoulette() {
    this.game.ui.showDialog({
      id: "P42", icon: "🎰", title: "Roulette", unique: true, wide: true,
      text: "Pick a chip and a field, then spin. Red/Black and Even/Odd pay 1:1, each dozen pays 2:1. On 0 every bet loses.",
      body: (b) => this.rouletteBody(b),
      secondary: { label: "Leave the table" },
      primary: { label: "Spin", disabled: () => this.spinning || !this.v || this.v.money < this.chip, action: () => { this.spin(); return "keep"; } },
    });
  }

  rouletteBody(b) {
    const v = this.v, bets = this.cfg.casino.bets;
    const chips = this.cfg.casino.chips.map((c) => `<button class="chip ${c === this.chip ? "on" : ""}" data-chip="${c}" ${this.spinning ? "disabled" : ""}>${euro(c).replace(".00", "")}</button>`).join("");
    const fields = Object.entries(bets).map(([k, s]) => `<button class="rfield f-${k} ${k === this.bet ? "on" : ""}" data-bet="${k}" ${this.spinning ? "disabled" : ""}>${esc(s.name)}<small>${s.pays}:1</small></button>`).join("");
    const last = this.lastSpin;
    const res = this.spinning ? `<div class="rres spin">The ball is rolling...</div>`
      : last ? `<div class="rres ${last.won ? "win" : "lose"}"><span class="rnum c-${last.color}">${last.number}</span>${last.won ? `You win ${euro(last.change)}!` : `You lose ${euro(-last.change)}.`}</div>` : "";
    const hist = this.history.map((h) => `<span class="rnum small c-${h.color}">${h.number}</span>`).join("");
    const c = v.casino || { net: 0 };
    b.innerHTML = `<div class="roulette">
      <div class="rrow"><b>Chip</b>${chips}</div>
      <div class="rgrid">${fields}</div>
      ${res}
      <div class="rrow small">Cash ${euro(v.money)} · casino total ${c.net >= 0 ? "+" : ""}${euro(c.net)} ${hist ? "· last: " + hist : ""}</div>
    </div>`;
    b.querySelectorAll("[data-chip]").forEach((x) => { x.onclick = () => { this.chip = Number(x.dataset.chip); this.game.sound.play("click"); this.game.ui.refreshDialog(); }; });
    b.querySelectorAll("[data-bet]").forEach((x) => { x.onclick = () => { this.bet = x.dataset.bet; this.game.sound.play("click"); this.game.ui.refreshDialog(); }; });
  }

  spin() {
    if (this.spinning) return;
    const g = this.game, d = g.ui.current;
    this.spinning = true;
    this.lastSpin = null;
    g.ui.refreshDialog();
    g.sound.play("spin");
    const started = performance.now();
    this.wheelSpeed = 9; this.ballSpeed = -13;
    g.flow.send("roulette", { bet: this.bet, amount: this.chip }, (r) => {
      const reveal = () => {
        this.spinning = false;
        this.wheelSpeed = 0; this.ballSpeed = 0;
        if (!r.ok) { g.ui.toast(r.error, true); g.ui.refreshDialog(); return; }
        this.lastSpin = r.result;
        this.landBall(r.result.number);
        this.history = [r.result, ...this.history].slice(0, 8);
        g.sound.play(r.result.won ? "win" : "lose");
        if (g.ui.current === d) g.ui.refreshDialog();
      };
      setTimeout(reveal, Math.max(0, 2700 - (performance.now() - started)));
    });
  }

  // put the ball on the pocket of the number (the texture starts at angle 0 and runs clockwise seen from above)
  landBall(number) {
    const i = WHEEL_ORDER.indexOf(number), n = WHEEL_ORDER.length;
    this.ballAngle = this.wheelAngle - ((i + 0.5) / n) * Math.PI * 2 - Math.PI / 2;
  }

  updateCasino(dt) {
    if (!this.game.inCasino) return;
    const t = performance.now() / 1000;
    if (this.wheelSpeed) this.wheelSpeed *= Math.exp(-dt * 0.7);
    if (this.ballSpeed) this.ballSpeed *= Math.exp(-dt * 0.9);
    this.wheelAngle += (this.wheelSpeed || 0.15) * dt;
    if (this.ballSpeed) this.ballAngle += this.ballSpeed * dt;
    else if (!this.spinning) this.ballAngle += 0.15 * dt; // rests in its pocket and turns with the wheel
    this.wheel.rotation.y = this.wheelAngle;
    const rr = this.spinning ? 0.58 : 0.49;
    this.ball.position.set(-1.35 + Math.cos(this.ballAngle) * rr, 1.15, -2.5 - Math.sin(this.ballAngle) * rr);
    for (const o of this.orbs) o.o.position.y = o.base + Math.sin(t * 1.2 + o.ph) * 0.25;
    this.crystal.material.opacity = 0.55 + Math.sin(t * 2) * 0.2;
    this.croupier.face(Math.atan2(this.game.player.pos.x - CASINO_ROOM.x, this.game.player.pos.z - (CASINO_ROOM.z - 4.1)));
    this.croupier.animate(0);
  }

  // ------------------------------------------------------------------ per frame
  update(dt) {
    const g = this.game;
    if (!this.v) return;
    this.placeJep();
    if (this.jep.visible) {
      const p = g.player.pos, d = dist2(p, this.jepPos);
      if (d < 8) this.jep.face(Math.atan2(p.x - this.jepPos.x, p.z - this.jepPos.z));
      this.jep.animate(0);
      this.jep.group.position.y = Math.abs(Math.sin(performance.now() / 700)) * 0.03; // nods to the music in his head
    }
    this.hatch.visible = this.found();
    if (this.found() && !this.slidOpen) this.slideOpen();
    this.updateArm();
    this.updateHigh(dt);
    this.updateSmoke(dt);
    this.updateCasino(dt);
  }

  // after the camera is placed: the high sway and the dark casino light
  afterCamera() {
    const g = this.game;
    if (g.inCasino) {
      // keep the camera inside the room (the walls are only seen from inside)
      const R = CASINO_ROOM, c = g.camera.position;
      c.x = clamp(c.x, R.x - R.w / 2 + 0.4, R.x + R.w / 2 - 0.4);
      c.z = clamp(c.z, R.z - R.d / 2 + 0.4, R.z + R.d / 2 - 0.4);
      c.y = Math.min(c.y, R.h - 0.4);
      g.camera.lookAt(g.camLook);
    }
    if (this.isHigh() && g.screen === "game") {
      const t = performance.now() / 1000;
      g.camera.rotateZ(Math.sin(t * 0.8) * 0.045);
      g.camera.fov = 58 + Math.sin(t * 0.6) * 5;
      g.camera.updateProjectionMatrix();
    }
    if (g.inCasino) {
      g.sun.intensity = 0.04; g.hemi.intensity = 0.22;
      g.world.markers.ring.visible = false; g.world.markers.arrow.visible = false;
    }
  }

  labels(ui, W, H) {
    const g = this.game;
    if (this.jep.visible && !g.inCasino && dist2(this.jepPos, g.player.pos) < 30) {
      const e = ui.label("jep-name", `<div class="name-tag">${esc(this.cfg.jep.name)}</div>`);
      ui.placeLabel(e, new THREE.Vector3(this.jepPos.x, 2.05, this.jepPos.z), g.camera, W, H);
    }
  }

  // a new day starts outside again
  reset() {
    if (this.game.inCasino) this.leaveCasino(true);
    this.lastSpin = null;
  }
}
