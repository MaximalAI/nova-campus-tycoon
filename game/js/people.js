// ---------------------------------------------------------------------------
// People: low-poly figures with a walking animation, player control, students
// ---------------------------------------------------------------------------
// v7: up to 60 people on the map - geometries and materials are shared between figures,
// and only the big parts (legs, body, head) cast a shadow.
const FIG_GEO = new Map(), FIG_MAT = new Map();
function figGeo(kind, ...args) {
  const key = kind + args.join(",");
  if (!FIG_GEO.has(key)) FIG_GEO.set(key, new THREE[kind](...args));
  return FIG_GEO.get(key);
}
function figMat(c) {
  if (!FIG_MAT.has(c)) FIG_MAT.set(c, new THREE.MeshLambertMaterial({ color: c }));
  return FIG_MAT.get(c);
}
// v7: each moving body part (body with head, two legs, two arms) becomes one mesh with
// vertex colours: 5 draw calls per person instead of 15. Same looks share the geometry.
function mergeFigureParts(container, key) {
  const parts = container.children.filter((c) => c.isMesh && c.userData.part);
  if (parts.length < 2) return;
  const cacheKey = "M:" + key;
  let geo = FIG_GEO.get(cacheKey);
  if (!geo) {
    const pos = [], nor = [], col = [];
    for (const m of parts) {
      m.updateMatrix();
      const g = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone();
      g.applyMatrix4(m.matrix);
      pos.push(g.attributes.position.array); nor.push(g.attributes.normal.array);
      const c = m.material.color, n = g.attributes.position.count, arr = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) { arr[i * 3] = c.r; arr[i * 3 + 1] = c.g; arr[i * 3 + 2] = c.b; }
      col.push(arr);
      g.dispose();
    }
    const cat = (arrs) => { const out = new Float32Array(arrs.reduce((a, x) => a + x.length, 0)); let o = 0; for (const a of arrs) { out.set(a, o); o += a.length; } return out; };
    geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(cat(pos), 3));
    geo.setAttribute("normal", new THREE.BufferAttribute(cat(nor), 3));
    geo.setAttribute("color", new THREE.BufferAttribute(cat(col), 3));
    FIG_GEO.set(cacheKey, geo);
  }
  if (!FIG_MAT.has("vc")) FIG_MAT.set("vc", new THREE.MeshLambertMaterial({ vertexColors: true }));
  for (const m of parts) container.remove(m);
  const merged = new THREE.Mesh(geo, FIG_MAT.get("vc"));
  merged.castShadow = true;
  container.add(merged);
}
class Figure {
  constructor(scene, colors, opts = {}) {
    const g = new THREE.Group();
    const s = opts.scale || 1;
    const part = (geo, color, x, y, z, parent = g) => {
      const m = new THREE.Mesh(geo, figMat(color)); m.position.set(x, y, z);
      m.userData.part = true;
      parent.add(m); return m;
    };
    const Box = (...a) => figGeo("BoxGeometry", ...a), Sphere = (...a) => figGeo("SphereGeometry", ...a), Cyl = (...a) => figGeo("CylinderGeometry", ...a);
    this.legL = new THREE.Group(); this.legR = new THREE.Group();
    this.legL.position.set(-0.13, 0.72, 0); this.legR.position.set(0.13, 0.72, 0);
    part(Box(0.2, 0.72, 0.22), colors.pants, 0, -0.36, 0, this.legL);
    part(Box(0.2, 0.72, 0.22), colors.pants, 0, -0.36, 0, this.legR);
    part(Box(0.22, 0.1, 0.3), 0x222222, 0, -0.72, 0.04, this.legL);
    part(Box(0.22, 0.1, 0.3), 0x222222, 0, -0.72, 0.04, this.legR);
    g.add(this.legL, this.legR);
    part(Box(0.52, 0.62, 0.3), colors.shirt, 0, 1.03, 0);
    if (opts.apron) part(Box(0.44, 0.7, 0.04), 0xffffff, 0, 0.95, 0.17);
    this.armL = new THREE.Group(); this.armR = new THREE.Group();
    this.armL.position.set(-0.34, 1.3, 0); this.armR.position.set(0.34, 1.3, 0);
    part(Box(0.15, 0.58, 0.17), colors.shirt, 0, -0.27, 0, this.armL);
    part(Box(0.15, 0.58, 0.17), colors.shirt, 0, -0.27, 0, this.armR);
    part(Box(0.13, 0.12, 0.13), colors.skin, 0, -0.6, 0, this.armL);
    part(Box(0.13, 0.12, 0.13), colors.skin, 0, -0.6, 0, this.armR);
    g.add(this.armL, this.armR);
    part(Sphere(0.22, 14, 12), colors.skin, 0, 1.57, 0);
    part(Sphere(0.235, 14, 10, 0, Math.PI * 2, 0, Math.PI / 2), colors.hair, 0, 1.6, -0.01);
    if (opts.cap) {
      part(Cyl(0.25, 0.25, 0.1, 14), opts.cap, 0, 1.76, 0);
      part(Box(0.3, 0.04, 0.2), opts.cap, 0, 1.72, 0.2);
    }
    // eyes
    part(Box(0.04, 0.05, 0.02), 0x111111, -0.08, 1.6, 0.2);
    part(Box(0.04, 0.05, 0.02), 0x111111, 0.08, 1.6, 0.2);
    const look = [colors.shirt, colors.pants, colors.hair, colors.skin, opts.apron ? 1 : 0, opts.cap || 0].join(",");
    mergeFigureParts(g, "body:" + look);
    for (const [k, c] of [["legL", this.legL], ["legR", this.legR], ["armL", this.armL], ["armR", this.armR]]) mergeFigureParts(c, k + ":" + look);
    if (!FIG_MAT.has("blob")) FIG_MAT.set("blob", new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false }));
    const shadow = new THREE.Mesh(figGeo("CircleGeometry", 0.38, 16), FIG_MAT.get("blob"));
    shadow.rotation.x = -Math.PI / 2; shadow.position.y = 0.04; g.add(shadow);
    g.scale.setScalar(s);
    this.group = g;
    this.phase = 0;
    scene.add(g);
  }
  set visible(v) { this.group.visible = v; }
  get visible() { return this.group.visible; }
  place(p) { this.group.position.set(p.x, 0, p.z); }
  face(angle) {
    let d = angle - this.group.rotation.y;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    this.group.rotation.y += d * 0.25;
  }
  animate(stride) {
    // stride: distance walked this frame (0 = standing). v5: when standing, the legs swing
    // out quickly instead of "walking on the spot" for a moment.
    if (this.swing === undefined) this.swing = 0;
    if (stride > 0) { this.phase += stride * 3.2; this.swing = Math.min(1, this.swing + 0.3); }
    else { this.swing *= 0.6; if (this.swing < 0.02) { this.swing = 0; this.phase = 0; } }
    const a = Math.sin(this.phase) * 0.6 * this.swing;
    if (this.work && stride === 0) {
      // v6: working at a station or cleaning: arms move in front of the body
      this.workT = (this.workT || 0) + 0.016;
      const k = this.work === "clean" ? 9 : this.work === "juice" ? 11 : 6;
      const w = Math.sin(this.workT * k);
      this.armL.rotation.x = -1.1 + w * (this.work === "clean" ? 0.15 : 0.35);
      this.armR.rotation.x = -1.1 - w * (this.work === "clean" ? 0.15 : 0.35);
      this.armL.rotation.z = this.work === "clean" ? w * 0.6 : 0;
      this.armR.rotation.z = this.work === "clean" ? w * 0.6 : 0;
      this.legL.rotation.x = 0; this.legR.rotation.x = 0;
      return;
    }
    this.armL.rotation.z = 0; this.armR.rotation.z = 0;
    this.legL.rotation.x = a; this.legR.rotation.x = -a;
    this.armL.rotation.x = -a * 0.8; this.armR.rotation.x = a * 0.8;
  }
}

function lookColors(look) {
  return {
    shirt: PALETTE.shirt[look.shirt % PALETTE.shirt.length],
    pants: PALETTE.pants[look.pants % PALETTE.pants.length],
    hair: PALETTE.hair[look.hair % PALETTE.hair.length],
    skin: PALETTE.skin[look.skin % PALETTE.skin.length],
  };
}

// Push a circle (player) out of all solid boxes.
function resolveCollisions(pos, radius, colliders) {
  for (const c of colliders) {
    if (c.active === false) continue;
    const nx = clamp(pos.x, c.x0, c.x1), nz = clamp(pos.z, c.z0, c.z1);
    const dx = pos.x - nx, dz = pos.z - nz;
    const d = Math.hypot(dx, dz);
    if (d < radius) {
      if (d > 1e-6) { pos.x = nx + (dx / d) * radius; pos.z = nz + (dz / d) * radius; }
      else {
        // centre inside the box: push out along the shortest axis
        const opts = [[c.x0 - radius - pos.x, 0], [c.x1 + radius - pos.x, 0], [0, c.z0 - radius - pos.z], [0, c.z1 + radius - pos.z]];
        opts.sort((a, b) => Math.abs(a[0] + a[1]) - Math.abs(b[0] + b[1]));
        pos.x += opts[0][0]; pos.z += opts[0][1];
      }
    }
  }
}

class Player {
  constructor(game) {
    this.game = game;
    this.figure = new Figure(game.scene, { shirt: 0xf2c94c, pants: 0x2b2d42, hair: 0x3d2b1f, skin: 0xe0ac69 }, { apron: true, cap: 0x2a9d8f });
    this.pos = { x: P.spawn.x, z: P.spawn.z };
    this.vel = { x: 0, z: 0 };
    this.walkSpeed = 4.6; // m per real second (not multiplied by game speed)
    this.runSpeed = 8.0;
    this.facing = Math.PI / 2;
    this.figure.place(this.pos);
    this.figure.group.rotation.y = this.facing;
  }
  teleport(p, facing) {
    this.pos = { x: p.x, z: p.z };
    this.vel = { x: 0, z: 0 };
    if (facing !== undefined) { this.facing = facing; this.figure.group.rotation.y = facing; }
    this.figure.place(this.pos);
  }
  // GTA/Minecraft style: WASD relative to the camera, the figure turns smoothly
  // towards where it walks, with acceleration and braking.
  update(dt, input, camYaw, locked, faceCamera = false) {
    let mx = 0, mz = 0;
    if (!locked) {
      if (input.up) mz -= 1;
      if (input.down) mz += 1;
      if (input.left) mx -= 1;
      if (input.right) mx += 1;
    }
    let tx = 0, tz = 0;
    if (mx || mz) {
      const len = Math.hypot(mx, mz); mx /= len; mz /= len;
      const sin = Math.sin(camYaw), cos = Math.cos(camYaw);
      const wx = mx * cos + mz * sin, wz = -mx * sin + mz * cos;
      const speed = input.run ? this.runSpeed : this.walkSpeed;
      tx = wx * speed; tz = wz * speed;
    }
    const k = 1 - Math.exp(-(tx || tz ? 12 : 16) * dt);
    this.vel.x += (tx - this.vel.x) * k;
    this.vel.z += (tz - this.vel.z) * k;
    const before = { x: this.pos.x, z: this.pos.z };
    // Sub-steps of at most 0.2 m, so the figure never tunnels through thin walls at low frame rates
    const travel = Math.hypot(this.vel.x, this.vel.z) * dt;
    const n = Math.max(1, Math.ceil(travel / 0.2));
    for (let i = 0; i < n; i++) {
      this.pos.x += this.vel.x * dt / n; this.pos.z += this.vel.z * dt / n;
      resolveCollisions(this.pos, 0.35, this.game.world.colliders);
    }
    if (!this.game.inCasino) { this.pos.x = clamp(this.pos.x, -64, 64); this.pos.z = clamp(this.pos.z, -64, 120); } // v7: the beach lies south (v8: the casino lies outside)
    const stride = dist2(before, this.pos);
    const moving = Math.hypot(this.vel.x, this.vel.z) > 0.3;
    if (moving || faceCamera) {
      // camera looks along -offset, so "forward" is camYaw + PI
      const target = faceCamera ? camYaw + Math.PI : Math.atan2(this.vel.x, this.vel.z);
      let d = target - this.facing;
      while (d > Math.PI) d -= Math.PI * 2;
      while (d < -Math.PI) d += Math.PI * 2;
      this.facing += d * (1 - Math.exp(-14 * dt));
    }
    this.figure.group.rotation.y = this.facing;
    this.figure.place(this.pos);
    this.figure.animate(stride);
  }
}

// One student as the browser sees it: a figure that walks along paths.
class StudentAgent {
  constructor(game, id, info) {
    this.game = game;
    this.id = id;
    this.info = info; // name, traits, look from Python
    this.figure = new Figure(game.scene, lookColors(info.look));
    this.figure.visible = false;
    this.figure.group.userData.agentId = id;
    this.pos = { x: 0, z: 0 };
    this.path = [];
    this.mode = "off"; // off, arriving, wandering, idle, to_shop, entering, queue, exiting, leaving
    this.shop = null;
    this.order = null; // items at the counter
    this.soldOut = [];
    this.patience = 0;
    this.patienceMax = info.traits.patience;
    this.waitUntil = 0;
    this.visit = 0;
    this.offset = { x: (hashRand(id + "x") - 0.5) * 0.6, z: (hashRand(id + "z") - 0.5) * 0.6 };
    this.onArrive = null;
  }
  get speed() { return this.info.traits.walk_speed; }
  walkTo(points, onArrive) {
    this.faceTarget = null;
    this.path = points.map((p) => ({ x: p.x, z: p.z }));
    this.onArrive = onArrive || null;
  }
  update(dtGameScaled) {
    // dtGameScaled: real seconds * speed multiplier (movement scales with game speed)
    let stride = 0;
    let budget = this.speed * dtGameScaled;
    while (budget > 0 && this.path.length) {
      const tgt = this.path[0];
      const d = dist2(this.pos, tgt);
      if (d <= budget) {
        stride += d; budget -= d;
        this.pos.x = tgt.x; this.pos.z = tgt.z;
        this.path.shift();
        if (!this.path.length && this.onArrive) { const cb = this.onArrive; this.onArrive = null; cb(); }
      } else {
        const w = budget / d;
        const nx = lerp(this.pos.x, tgt.x, w), nz = lerp(this.pos.z, tgt.z, w);
        this.figure.face(Math.atan2(tgt.x - this.pos.x, tgt.z - this.pos.z));
        this.pos.x = nx; this.pos.z = nz;
        stride += budget; budget = 0;
      }
    }
    if (!this.path.length && this.faceTarget !== undefined && this.faceTarget !== null) this.figure.face(this.faceTarget);
    this.figure.place(this.pos);
    this.figure.animate(stride);
  }
  faceTo(p) { this.faceTarget = Math.atan2(p.x - this.pos.x, p.z - this.pos.z); }
  // standing in a queue: others walk around me
  anchored() { return !this.path.length && (this.mode === "queue" || this.mode === "served" || this.mode === "machine_queue" || this.mode === "machine_use"); }
}

// v5: staff (manager or the competitor's barista) walk to the stations for each product,
// back to the counter, and clean the café after closing.
class StaffAgent extends StudentAgent {
  constructor(game, shop, colors, opts) {
    super(game, "staff_" + shop, { name: "Staff", traits: { walk_speed: 2.6, patience: 60, fickleness: 1 },
      look: { shirt: 0, pants: 0, hair: 0, skin: 0 } });
    game.scene.remove(this.figure.group);
    this.figure = new Figure(game.scene, colors, opts);
    this.shop = shop;
    this.home = P[shop].staff;
    this.steps = [];
    this.reset();
  }
  get speed() { return 3.6; }
  reset() {
    this.steps = []; this.path = []; this.waitLeft = 0; this.job = null;
    this.activity = null; if (this.figure) this.figure.work = null;
    this.pos = { x: this.home.x, z: this.home.z };
    this.figure.place(this.pos);
    const hf = P[this.shop].homeFace;
    this.faceTarget = Math.atan2(hf.x - this.home.x, hf.z - this.home.z);
  }
  anchored() { return true; }
  // Behind the counter or in front of it? Crossing sides goes through the gap at the end of the counter.
  behind(p) { return P[this.shop].behind(p); }
  route(from, to) {
    if (this.behind(from) === this.behind(to)) return [to];
    const gap = P[this.shop].gap;
    return this.behind(from) ? [gap[0], gap[1], to] : [gap[1], gap[0], to];
  }
  get busy() { return this.steps.length > 0 || this.path.length > 0; }
  // steps: {walk: point} | {wait: game minutes} | {face: point} | {call: fn}
  run(steps, job) { this.steps = steps.slice(); this.job = job || null; this.path = []; this.waitLeft = 0; }
  stop() { this.activity = null; this.figure.work = null; this.steps = [{ walk: this.home }, { face: P[this.shop].homeFace }]; this.job = null; this.path = []; }
  tick(dtScaled, dtGameMin) {
    const v = this.game.view;
    // v6: a newly hired manager already comes in for the cleaning on his first evening
    this.figure.visible = !!(v && this.game.screen === "game" && (this.shop === "snackbots" ? v.shops.snackbots.manager
      : (v.shops[this.shop].auto || (this.shop === "cafe" && v.shops.cafe.manager)))); // v10: the vending manager only once hired
    if (!this.figure.visible) return;
    while (this.steps.length && !this.path.length) {
      const s = this.steps[0];
      if (s.walk) {
        if (dist2(this.pos, s.walk) < 0.05) { this.steps.shift(); continue; }
        this.walkTo(s.direct ? [s.walk] : this.route(this.pos, s.walk)); // v9: direct legs outside the shop
        this.steps[0] = { arrived: true };
        break;
      }
      if (s.arrived) { this.steps.shift(); continue; }
      if (s.face) { this.faceTo(s.face); this.steps.shift(); continue; }
      if (s.wait !== undefined) {
        if (this.waitLeft <= 0 && !s.started) { this.waitLeft = s.wait; s.started = true; }
        this.waitLeft -= dtGameMin;
        dtGameMin = 0;
        // v6: show what the staff member is doing (arms move, icon + progress above the head)
        this.figure.work = s.work || null;
        // v9: the cleaning sound goes with the animation (a swish every 1.8 s), only heard nearby
        // v10: only heard when the player is in that shop
        if (s.work === "clean" && (!this.nextSwish || performance.now() > this.nextSwish)) {
          if (this.game.flow.playerIn(this.shop)) this.game.sound.play("clean");
          this.nextSwish = performance.now() + 1800;
        }
        const dyn = (s.dyn && s.dyn()) || {}; // v11: e.g. "Repairing" instead of "Refilling" at a broken machine
        this.activity = s.work ? { icon: dyn.icon || s.icon || "⚙️", text: dyn.text || s.text || "", progress: 1 - Math.max(0, this.waitLeft) / s.wait } : null;
        if (this.waitLeft > 0) break;
        this.figure.work = null; this.activity = null;
        this.steps.shift();
        continue;
      }
      if (s.call) { this.steps.shift(); s.call(); continue; }
      if (s.until) { if (s.until()) { this.steps.shift(); this.activity = null; continue; } this.activity = s.waiting || null; break; } // v9: wait for a free checkout
      this.steps.shift();
    }
    this.update(dtScaled);
  }
}
