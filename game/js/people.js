// ---------------------------------------------------------------------------
// People: low-poly figures with a walking animation, player control, students
// ---------------------------------------------------------------------------
class Figure {
  constructor(scene, colors, opts = {}) {
    const mat = (c) => new THREE.MeshLambertMaterial({ color: c });
    const g = new THREE.Group();
    const s = opts.scale || 1;
    const part = (geo, color, x, y, z, parent = g) => {
      const m = new THREE.Mesh(geo, mat(color)); m.position.set(x, y, z); m.castShadow = true; parent.add(m); return m;
    };
    this.legL = new THREE.Group(); this.legR = new THREE.Group();
    this.legL.position.set(-0.13, 0.72, 0); this.legR.position.set(0.13, 0.72, 0);
    part(new THREE.BoxGeometry(0.2, 0.72, 0.22), colors.pants, 0, -0.36, 0, this.legL);
    part(new THREE.BoxGeometry(0.2, 0.72, 0.22), colors.pants, 0, -0.36, 0, this.legR);
    part(new THREE.BoxGeometry(0.22, 0.1, 0.3), 0x222222, 0, -0.72, 0.04, this.legL);
    part(new THREE.BoxGeometry(0.22, 0.1, 0.3), 0x222222, 0, -0.72, 0.04, this.legR);
    g.add(this.legL, this.legR);
    part(new THREE.BoxGeometry(0.52, 0.62, 0.3), colors.shirt, 0, 1.03, 0);
    if (opts.apron) part(new THREE.BoxGeometry(0.44, 0.7, 0.04), 0xffffff, 0, 0.95, 0.17);
    this.armL = new THREE.Group(); this.armR = new THREE.Group();
    this.armL.position.set(-0.34, 1.3, 0); this.armR.position.set(0.34, 1.3, 0);
    part(new THREE.BoxGeometry(0.15, 0.58, 0.17), colors.shirt, 0, -0.27, 0, this.armL);
    part(new THREE.BoxGeometry(0.15, 0.58, 0.17), colors.shirt, 0, -0.27, 0, this.armR);
    part(new THREE.BoxGeometry(0.13, 0.12, 0.13), colors.skin, 0, -0.6, 0, this.armL);
    part(new THREE.BoxGeometry(0.13, 0.12, 0.13), colors.skin, 0, -0.6, 0, this.armR);
    g.add(this.armL, this.armR);
    part(new THREE.SphereGeometry(0.22, 14, 12), colors.skin, 0, 1.57, 0);
    const hair = part(new THREE.SphereGeometry(0.235, 14, 10, 0, Math.PI * 2, 0, Math.PI / 2), colors.hair, 0, 1.6, -0.01);
    if (opts.cap) {
      part(new THREE.CylinderGeometry(0.25, 0.25, 0.1, 14), opts.cap, 0, 1.76, 0);
      part(new THREE.BoxGeometry(0.3, 0.04, 0.2), opts.cap, 0, 1.72, 0.2);
    }
    // eyes
    part(new THREE.BoxGeometry(0.04, 0.05, 0.02), 0x111111, -0.08, 1.6, 0.2);
    part(new THREE.BoxGeometry(0.04, 0.05, 0.02), 0x111111, 0.08, 1.6, 0.2);
    const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.38, 16),
      new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false }));
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
    // stride: distance walked this frame (0 = standing)
    if (stride > 0) this.phase += stride * 3.2;
    else this.phase *= 0.85;
    const a = Math.sin(this.phase) * (stride > 0 ? 0.6 : 0.6 * Math.min(1, Math.abs(Math.sin(this.phase))));
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
    this.pos.x = clamp(this.pos.x, -64, 64); this.pos.z = clamp(this.pos.z, -64, 64);
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
    this.figure.place(this.pos);
    this.figure.animate(stride);
  }
  faceTo(p) { this.figure.face(Math.atan2(p.x - this.pos.x, p.z - this.pos.z)); }
}
