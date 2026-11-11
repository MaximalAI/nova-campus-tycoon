// ---------------------------------------------------------------------------
// World: campus, buildings, interiors, colliders, interaction points, nav grid
// ---------------------------------------------------------------------------
const BUILDINGS = {
  cafe: { x0: -40, x1: -28, z0: -6, z1: 6, door: { side: "east", a: -1.5, b: 1.5 }, wall: 0xfff1d6, trim: 0x2a9d8f, roof: 0x2e8b57, sign: "YOUR CAFÉ" },
  rival: { x0: -6, x1: 6, z0: -27, z1: -16, door: { side: "south", a: -1.5, b: 1.5 }, wall: 0xe8eef5, trim: 0x8d99ae, roof: 0xb83a3a, sign: "CAFÉ DA ESQUINA" },
  wholesale: { x0: 28, x1: 52, z0: -9, z1: 9, door: { side: "west", a: -1.8, b: 1.8 }, wall: 0xdfe6d8, trim: 0x52796f, roof: 0x3a5a40, sign: "WHOLESALE" },
};
const WALL_H = 2.8;

// v7: the local frame of a shop. "inn" points from the door into the shop, "lat" runs
// along the door wall. Layouts of the new shops are written in this frame (depth, lateral).
function shopFrame(b) {
  const cx = (b.x0 + b.x1) / 2, cz = (b.z0 + b.z1) / 2;
  const f = {
    east: { door: { x: b.x1, z: cz }, inn: { x: -1, z: 0 }, lat: { x: 0, z: 1 }, depth: b.x1 - b.x0, width: b.z1 - b.z0 },
    west: { door: { x: b.x0, z: cz }, inn: { x: 1, z: 0 }, lat: { x: 0, z: -1 }, depth: b.x1 - b.x0, width: b.z1 - b.z0 },
    south: { door: { x: cx, z: b.z1 }, inn: { x: 0, z: -1 }, lat: { x: 1, z: 0 }, depth: b.z1 - b.z0, width: b.x1 - b.x0 },
    north: { door: { x: cx, z: b.z0 }, inn: { x: 0, z: 1 }, lat: { x: -1, z: 0 }, depth: b.z1 - b.z0, width: b.x1 - b.x0 },
  }[b.door.side];
  f.at = (d, l) => ({ x: f.door.x + f.inn.x * d + f.lat.x * l, z: f.door.z + f.inn.z * d + f.lat.z * l });
  f.faceDoor = Math.atan2(-f.inn.x, -f.inn.z); // rotation.y that turns a mesh's front (+z) to the door
  f.faceBack = Math.atan2(f.inn.x, f.inn.z);
  f.faceLat = (sign) => Math.atan2(sign * f.lat.x, sign * f.lat.z);
  f.depthOf = (p) => (p.x - f.door.x) * f.inn.x + (p.z - f.door.z) * f.inn.z;
  f.latOf = (p) => (p.x - f.door.x) * f.lat.x + (p.z - f.door.z) * f.lat.z;
  f.rect = (d0, d1, l0, l1) => {
    const a = f.at(d0, l0), c = f.at(d1, l1);
    return { x0: Math.min(a.x, c.x), x1: Math.max(a.x, c.x), z0: Math.min(a.z, c.z), z1: Math.max(a.z, c.z) };
  };
  return f;
}

// Gameplay points of a new shop, computed from its building and queue size.
function genericPoints(b, spec) {
  const f = shopFrame(b), D = f.depth, W = f.width;
  const vending = b.interior === "vending";
  const cd = vending ? D - 1.2 : b.interior === "market" ? D - 3.5 : D - 5.5; // counter line
  const maxq = spec.max_queue || 4;
  const first = vending ? D - 1.6 : cd - 1.1;
  const step = Math.min(1.1, (first - 0.9) / Math.max(1, maxq - 1));
  const queue = [], outside = [];
  for (let i = 0; i < maxq; i++) {
    queue.push(f.at(first - i * step, i % 2 ? 0.12 : -0.08));
    outside.push(f.at(-1.8 - i * 1.0, i % 2 ? 2.4 : 1.6));
  }
  const cam = f.at(D - 0.6, 0);
  const gapLat = W / 2 - 1.5;
  return {
    frame: f, cd, vending,
    doorOut: f.at(-1.6, 0), doorIn: f.at(1.4, 0), queue, outside,
    counterZone: f.rect(cd + 0.45, D, -W / 2, W / 2),
    cam: { x: cam.x, y: 4.6, z: cam.z, lx: f.door.x, ly: 0.6, lz: f.door.z },
    staff: f.at(cd + 1.4, 0.6), register: vending ? f.at(2.0, -(W / 2 - 2.2)) : f.at(cd + 0.9, 0.6), serve: f.at(cd + 1.4, 0),
    storage: vending ? f.at(D - 2.8, W / 2 - 0.9) : f.at(D - 1.0, W / 2 - 1.8),
    spawn: f.at(-4.5, 2.6),
    exit: [f.at(first - 0.1, -1.2), f.at(1.6, -1.0), f.at(0, -0.8), f.at(-1.8, -0.9)],
    planBoard: f.at(2.4, W / 2 - 1.0), upBoard: f.at(2.4, -(W / 2 - 1.0)),
    gap: [f.at(cd + 1.2, gapLat), f.at(cd - 1.2, gapLat)],
    behind: (p) => f.depthOf(p) > cd + 0.45,
    face: (spot) => f.at(D, f.latOf(spot)),
    homeFace: f.at(cd - 3, 0.6),
    entry: f.at(-2.2, 0),
    priceBoard: f.at(-1.6, 3.6), saleSign: f.at(-1.4, -4.25),
  };
}

// Points used by gameplay (x, z)
const P = {
  spawn: { x: -24.5, z: 0 },
  cafe: {
    doorOut: { x: -26.6, z: 0 }, doorIn: { x: -29.4, z: 0 },
    queue: [{ x: -33.9, z: 0 }, { x: -32.8, z: 0.15 }, { x: -31.7, z: -0.1 }, { x: -30.6, z: 0.1 }],
    outside: [{ x: -26.2, z: 1.6 }, { x: -25.2, z: 2.4 }, { x: -24.2, z: 1.6 }, { x: -23.2, z: 2.4 }],
    counterZone: { x0: -39.8, x1: -35.3, z0: -5.8, z1: 5.8 },
    cam: { x: -39.4, y: 4.6, z: 0, lx: -30, ly: 0.6, lz: 0 },
    staff: { x: -36.4, z: -0.6 },
    register: { x: -35.8, z: -0.6 }, storage: { x: -38.6, z: 3.6 }, serve: { x: -36.4, z: 0 }, spawn: { x: -24.5, z: 0 },
    // customers leave along a side lane, so they do not walk through the queue behind them
    // v6: through the middle of the door (it is 3 m wide), not along the wall
    exit: [{ x: -34.0, z: 1.2 }, { x: -29.6, z: 1.0 }, { x: -28.0, z: 0.8 }, { x: -26.4, z: 0.9 }],
  },
  rival: {
    doorOut: { x: 0, z: -14.4 }, doorIn: { x: 0, z: -17.4 },
    queue: [{ x: 0, z: -19.9 }, { x: 0.15, z: -18.8 }, { x: -0.1, z: -17.8 }, { x: 0.1, z: -16.8 }],
    outside: [{ x: 1.6, z: -14.2 }, { x: 2.4, z: -13.2 }, { x: 1.6, z: -12.2 }, { x: 2.4, z: -11.2 }],
    counterZone: { x0: -5.8, x1: 5.8, z0: -26.8, z1: -21.3 },
    cam: { x: 0, y: 4.6, z: -26.4, lx: 0, ly: 0.6, lz: -16 },
    staff: { x: 0.6, z: -22.4 },
    register: { x: 0.6, z: -21.9 }, storage: { x: 4.2, z: -25.5 }, serve: { x: 0, z: -22.4 }, spawn: { x: 2.6, z: -11.5 },
    exit: [{ x: -1.2, z: -20.0 }, { x: -1.0, z: -17.6 }, { x: -0.8, z: -16.0 }, { x: -0.9, z: -14.2 }],
  },
  wholesale: { doorOut: { x: 25.6, z: 0 }, doorIn: { x: 29.4, z: 0 } },
};
// v7: the same helpers for the two hand-built cafés as for the generated shops
Object.assign(P.cafe, {
  planBoard: { x: -37.4, z: -4.9 }, upBoard: { x: -31.5, z: -4.9 },
  gap: [{ x: -36.2, z: 4.4 }, { x: -33.6, z: 4.4 }], behind: (p) => p.x < -34.9,
  face: (spot) => ({ x: -40, z: spot.z }), homeFace: { x: -31.4, z: -0.6 }, entry: { x: -25.4, z: 0 },
  priceBoard: { x: -25.6, z: -2.9 },
});
Object.assign(P.rival, {
  planBoard: { x: 5.0, z: -18.6 }, upBoard: { x: -5.0, z: -18.6 },
  gap: [{ x: 4.5, z: -22.2 }, { x: 4.5, z: -19.8 }], behind: (p) => p.z < -21.0,
  face: (spot) => ({ x: spot.x, z: -30 }), homeFace: { x: 0.6, z: -17.4 }, entry: { x: 0, z: -13.6 },
  priceBoard: { x: 3.6, z: -14.4 }, saleSign: { x: -4.25, z: -14.6 },
});

const PALETTE = {
  shirt: [0xe63946, 0x457b9d, 0xf4a261, 0x2a9d8f, 0x8338ec, 0xff006e, 0x3a86ff, 0xffbe0b, 0x6a994e, 0xbc4749, 0x1d3557, 0xe76f51],
  pants: [0x264653, 0x3d405b, 0x6d597a, 0x22223b, 0x5e503f, 0x2b2d42],
  hair: [0x2b1d0e, 0x5a3825, 0x8d5524, 0xd4a017, 0x111111, 0xa0522d, 0xe8c07d, 0x7f4f24],
  skin: [0xf1c27d, 0xe0ac69, 0xc68642, 0x8d5524, 0xffdbac],
};

class World {
  constructor(game) {
    this.game = game;
    this.scene = game.scene;
    this.colliders = []; // {x0,x1,z0,z1}
    this.gates = {}; // name -> collider (switchable)
    this.interactables = []; // {id, pos, radius, label(), enabled(), action(), meshes[]}
    this.buildingParts = {}; // building -> {walls:[], roof}
    this.lampLights = [];
    this.lampBulbs = [];
    this.windowMats = [];
    this.markers = {};
    this.registerShops();
    this.build();
    this.buildNav();
  }

  mat(color, opts = {}) { return new THREE.MeshLambertMaterial(Object.assign({ color }, opts)); }

  box(w, h, d, color, x, y, z, opts = {}) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), opts.material || this.mat(color));
    m.position.set(x, y, z);
    m.castShadow = opts.cast !== false;
    m.receiveShadow = true;
    (opts.parent || this.scene).add(m);
    return m;
  }

  collide(x0, x1, z0, z1) { const c = { x0, x1, z0, z1 }; this.colliders.push(c); return c; }

  textTexture(text, bg, fg, w = 512, h = 128, font = 64) {
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    const g = c.getContext("2d");
    g.fillStyle = bg; g.fillRect(0, 0, w, h);
    g.fillStyle = fg; g.font = `900 ${font}px sans-serif`; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(text, w / 2, h / 2 + 4);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }

  emojiTexture(emoji, size = 128) {
    const c = document.createElement("canvas"); c.width = size; c.height = size;
    const g = c.getContext("2d");
    g.font = `${size * 0.8}px serif`; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(emoji, size / 2, size / 2 + size * 0.05);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }

  // v7: the new shops come from the config (building, door, colours); their gameplay
  // points are computed from the layout.
  registerShops() {
    const shops = this.game.config.shops;
    this.newShops = [];
    for (const [key, spec] of Object.entries(shops)) {
      const b = spec.building;
      if (!b) continue;
      BUILDINGS[key] = { x0: b.x0, x1: b.x1, z0: b.z0, z1: b.z1, door: { side: b.door, a: -1.5, b: 1.5 },
        wall: b.wall, trim: b.trim, roof: b.roof, sign: b.sign, interior: b.interior, zone: spec.zone };
      P[key] = genericPoints(BUILDINGS[key], spec);
      this.newShops.push(key);
    }
  }

  build() {
    const s = this.scene;
    // Ground and paths
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), this.mat(0x6cbf4a));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; s.add(ground);
    const pathMat = this.mat(0xe9dcc0);
    const path = (x0, x1, z0, z1) => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, z1 - z0), pathMat);
      m.rotation.x = -Math.PI / 2; m.position.set((x0 + x1) / 2, 0.02, (z0 + z1) / 2); m.receiveShadow = true; s.add(m);
    };
    path(-70, 70, -2.2, 2.2);
    path(-2.2, 2.2, -16, 70);
    path(-70, -40, -8, -6.5);
    // v7: a path from the main paths to every new shop's door
    for (const key of this.newShops) {
      const pt = P[key], d = pt.frame;
      const a = pt.doorOut;
      if (d.inn.x !== 0) { // door in an east/west wall: walk sideways to the north-south path
        path(Math.min(a.x, 0), Math.max(a.x, 0), a.z - 1.2, a.z + 1.2);
      } else { // door in a north/south wall: walk to the east-west path
        path(a.x - 1.2, a.x + 1.2, Math.min(a.z, 0), Math.max(a.z, 0));
      }
    }
    const plaza = new THREE.Mesh(new THREE.CircleGeometry(8, 40), pathMat);
    plaza.rotation.x = -Math.PI / 2; plaza.position.set(0, 0.025, 6); plaza.receiveShadow = true; s.add(plaza);
    const fountain = this.box(3, 0.6, 3, 0x9fb7c9, 0, 0.3, 6);
    this.box(2.4, 0.1, 2.4, 0x4ea8de, 0, 0.62, 6, { cast: false });
    this.collide(-1.7, 1.7, 4.3, 7.7);

    for (const [key, b] of Object.entries(BUILDINGS)) this.buildBuilding(key, b);
    this.buildCafeInterior();
    this.buildRivalInterior();
    for (const key of this.newShops) this.buildGenericShop(key);
    this.buildWholesaleInterior();
    this.buildPriceBoards();

    // Trees, benches and street lamps
    // v7: trees moved out of the new shops (bowl bar, market, mensa)
    const trees = [[-18, 7.5], [-12, -12], [12, -12], [16.5, 12], [-48, 14], [-50, -16], [52, 16], [54, -18],
      [20, 26], [-22, 28], [8, 30], [-8, 24], [32, -20], [-30, -22], [40, 22], [-40, 24], [27, -32], [-16, -39]];
    for (const [x, z] of trees) this.tree(x, z);
    for (const [x, z, r] of [[-8, 3.4, 0], [8, 3.4, 0], [4, 10.5, Math.PI / 2], [-4, 10.5, Math.PI / 2]]) this.bench(x, z, r);
    for (const [x, z] of [[-20, 3.2], [-8, -3.2], [8, -3.2], [20, 3.2], [3.2, -10], [3.2, 24], [-3.2, 30], [34, 11], [-34, 9]]) this.lamp(x, z);

    // Objective marker (ring on the ground)
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.7, 0.95, 40),
      new THREE.MeshBasicMaterial({ color: 0xffd166, transparent: true, opacity: 0.9, side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.06; s.add(ring);
    this.markers.ring = ring;
    // Flat chevron on the ground next to the player, pointing to the objective
    const shape = new THREE.Shape();
    shape.moveTo(0, 0.55); shape.lineTo(0.42, -0.25); shape.lineTo(0, -0.05); shape.lineTo(-0.42, -0.25); shape.lineTo(0, 0.55);
    const arrow = new THREE.Mesh(new THREE.ShapeGeometry(shape),
      new THREE.MeshBasicMaterial({ color: 0xffd166, side: THREE.DoubleSide, transparent: true, opacity: 0.95 }));
    s.add(arrow);
    this.markers.arrow = arrow;
  }

  buildBuilding(key, b) {
    const s = this.scene;
    const parts = { walls: [], roof: null, wallMats: [] };
    const wallMat = this.mat(b.wall, { transparent: true });
    parts.wallMats.push(wallMat);
    const t = 0.3;
    const segs = [];
    const { x0, x1, z0, z1, door } = b;
    const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
    const horiz = (z, side) => {
      if (door.side === side) {
        segs.push([x0, cx + door.a, z - t / 2, z + t / 2], [cx + door.b, x1, z - t / 2, z + t / 2]);
      } else segs.push([x0, x1, z - t / 2, z + t / 2]);
    };
    const vert = (x, side) => {
      if (door.side === side) {
        segs.push([x - t / 2, x + t / 2, z0, cz + door.a], [x - t / 2, x + t / 2, cz + door.b, z1]);
      } else segs.push([x - t / 2, x + t / 2, z0, z1]);
    };
    horiz(z0, "north"); horiz(z1, "south"); vert(x0, "west"); vert(x1, "east");
    for (const [a0, a1, b0, b1] of segs) {
      const m = this.box(a1 - a0, WALL_H, b1 - b0, 0, (a0 + a1) / 2, WALL_H / 2, (b0 + b1) / 2, { material: wallMat });
      parts.walls.push(m);
      this.collide(a0, a1, b0, b1);
    }
    // Trim stripe and floor
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, z1 - z0), this.mat(key === "wholesale" ? 0xc9c3b6 : 0xc89f73));
    floor.rotation.x = -Math.PI / 2; floor.position.set(cx, 0.03, cz); floor.receiveShadow = true; s.add(floor);
    // Roof (hidden when the player is inside)
    const roof = new THREE.Mesh(new THREE.BoxGeometry(x1 - x0 + 1.2, 0.35, z1 - z0 + 1.2), this.mat(b.roof, { transparent: true }));
    roof.position.set(cx, WALL_H + 0.2, cz); roof.castShadow = true; s.add(roof);
    parts.roof = roof;
    // Sign above the door
    const signTex = this.textTexture(b.sign, "#" + b.trim.toString(16).padStart(6, "0"), "#ffffff", 1024, 160, 92);
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(6, 0.95), new THREE.MeshBasicMaterial({ map: signTex }));
    const off = 0.25;
    if (door.side === "east") { sign.position.set(x1 + off, WALL_H + 0.9, cz); sign.rotation.y = Math.PI / 2; }
    if (door.side === "west") { sign.position.set(x0 - off, WALL_H + 0.9, cz); sign.rotation.y = -Math.PI / 2; }
    if (door.side === "south") { sign.position.set(cx, WALL_H + 0.9, z1 + off); }
    if (door.side === "north") { sign.position.set(cx, WALL_H + 0.9, z0 - off); sign.rotation.y = Math.PI; }
    s.add(sign);
    parts.sign = sign; // hidden together with the roof, so it never blocks the view from inside
    // Awning over the door
    const ns = door.side === "south" || door.side === "north";
    this.box(ns ? 4.4 : 1.4, 0.12, ns ? 1.4 : 4.4, b.trim,
      door.side === "east" ? x1 + 0.7 : door.side === "west" ? x0 - 0.7 : cx, 2.35,
      door.side === "south" ? z1 + 0.7 : door.side === "north" ? z0 - 0.7 : cz);
    // Warm window light (glows at night)
    const winMat = new THREE.MeshLambertMaterial({ color: 0x334455, emissive: 0xffc46b, emissiveIntensity: 0 });
    this.windowMats.push(winMat);
    const windows = ns
      ? [[x0 - 0.17, cz, Math.PI / 2], [x1 + 0.17, cz, Math.PI / 2]]
      : [[cx - 2.5, z1 + 0.17, 0], [cx + 2.5, z1 + 0.17, 0], [cx - 2.5, z0 - 0.17, 0], [cx + 2.5, z0 - 0.17, 0]];
    for (const [wx, wz, r] of windows) {
      const w = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.1), winMat);
      w.position.set(wx, 1.6, wz); w.rotation.y = r; s.add(w);
      const w2 = w.clone(); w2.rotation.y = r + Math.PI; s.add(w2);
    }
    if (!b.interior) { // v7: the new shops only glow through the windows (point lights are expensive)
      const light = new THREE.PointLight(0xffc46b, 0, 16, 1.6);
      light.position.set(cx, 2.4, cz); s.add(light);
      this.lampLights.push(light);
    }
    this.buildingParts[key] = parts;
  }

  addInteractable(spec) {
    const it = Object.assign({ radius: 2.1, enabled: () => true, meshes: [] }, spec);
    for (const m of it.meshes) {
      m.userData.interactable = it;
      if (m.material && m.material.emissive) m.material = m.material.clone();
    }
    this.interactables.push(it);
    return it;
  }

  station(shop, kind, x, z, rotY, opts = {}) {
    const g = new THREE.Group();
    const meshes = [];
    const add = (geo, color, px, py, pz) => {
      const m = new THREE.Mesh(geo, this.mat(color)); m.position.set(px, py, pz); m.castShadow = true; g.add(m); meshes.push(m); return m;
    };
    if (kind === "machine") {
      // v7: a vending machine: body, glass front with rows of products, a status light
      const body = add(new THREE.BoxGeometry(1.3, 2.1, 0.8), opts.color || 0x1565c0, 0, 1.05, 0);
      void body;
      const glass = new THREE.Mesh(new THREE.BoxGeometry(0.85, 1.3, 0.05), new THREE.MeshLambertMaterial({ color: 0xbde0fe, transparent: true, opacity: 0.55 }));
      glass.position.set(-0.12, 1.25, 0.42); g.add(glass); meshes.push(glass);
      const icon = this.emojiTexture(this.game.config.products[opts.product].icon, 128);
      const pic = new THREE.Mesh(new THREE.PlaneGeometry(0.55, 0.55), new THREE.MeshBasicMaterial({ map: icon, transparent: true }));
      pic.position.set(-0.12, 1.3, 0.46); g.add(pic);
      add(new THREE.BoxGeometry(0.25, 0.5, 0.05), 0x263238, 0.45, 1.25, 0.42);
      const lightMat = new THREE.MeshBasicMaterial({ color: 0x2ecc71 });
      const led = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), lightMat);
      led.position.set(0.45, 1.7, 0.45); g.add(led);
      this.machineLights = this.machineLights || {};
      this.machineLights[`${shop}:${opts.product}`] = lightMat;
      g.position.set(x, 0, z); g.rotation.y = rotY || 0;
      this.scene.add(g);
      return meshes;
    }
    add(new THREE.BoxGeometry(1.4, 1.0, 0.8), 0x8d6e63, 0, 0.5, 0); // cabinet
    if (kind === "assembly") {
      // v7: bowl station: ingredient trays and two bowls
      for (let i = 0; i < 4; i++) add(new THREE.BoxGeometry(0.28, 0.08, 0.4), [0xffffff, 0xff8a65, 0x7b1fa2, 0xe53935][i], -0.45 + i * 0.3, 1.04, -0.1);
      for (const bx of [-0.3, 0.3]) add(new THREE.CylinderGeometry(0.2, 0.12, 0.14, 14), 0xffffff, bx, 1.08, 0.22);
    } else if (kind === "grill") {
      add(new THREE.BoxGeometry(1.2, 0.08, 0.6), 0x212121, 0, 1.04, 0);
      for (let i = 0; i < 3; i++) add(new THREE.CylinderGeometry(0.12, 0.12, 0.06, 10), 0xc68642, -0.35 + i * 0.35, 1.1, 0);
    } else if (kind === "oven") {
      add(new THREE.BoxGeometry(1.2, 0.7, 0.7), 0x9e9e9e, 0, 1.35, 0);
      add(new THREE.BoxGeometry(0.9, 0.35, 0.05), 0xff7043, 0, 1.35, 0.36);
    } else if (kind === "fridge") {
      add(new THREE.BoxGeometry(1.2, 1.1, 0.7), 0xeceff1, 0, 1.55, 0);
      for (let i = 0; i < 3; i++) add(new THREE.CylinderGeometry(0.09, 0.08, 0.12, 10), 0xf6bd60, -0.3 + i * 0.3, 1.12, 0.3);
    } else if (kind === "coffee_machine") {
      add(new THREE.BoxGeometry(0.8, 0.7, 0.55), 0x37474f, 0, 1.35, 0);
      add(new THREE.CylinderGeometry(0.12, 0.12, 0.25, 12), 0xb0bec5, 0.2, 1.85, 0);
      add(new THREE.CylinderGeometry(0.08, 0.07, 0.12, 12), 0xffffff, 0, 1.06, 0.18);
    } else if (kind === "juicer") {
      add(new THREE.CylinderGeometry(0.28, 0.32, 0.6, 16), 0xff9f1c, 0, 1.3, 0);
      add(new THREE.SphereGeometry(0.16, 12, 10), 0xffa62b, 0.45, 1.12, 0.1);
      add(new THREE.SphereGeometry(0.16, 12, 10), 0xffa62b, -0.45, 1.12, -0.1);
    } else if (kind === "display_case") {
      const glass = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.55, 0.65),
        new THREE.MeshLambertMaterial({ color: 0xbde0fe, transparent: true, opacity: 0.45 }));
      glass.position.set(0, 1.3, 0); g.add(glass); meshes.push(glass);
      if (shop === "rival") {
        // v6: croissants (half rings) instead of pastéis de nata
        for (let i = 0; i < 3; i++) {
          const c = add(new THREE.TorusGeometry(0.11, 0.05, 8, 14, Math.PI * 1.25), 0xd9963b, -0.36 + i * 0.36, 1.1, 0);
          c.rotation.x = -Math.PI / 2; c.rotation.z = Math.PI * 0.12;
        }
      } else {
        for (let i = 0; i < 4; i++) add(new THREE.CylinderGeometry(0.12, 0.1, 0.08, 12), 0xf6bd60, -0.4 + i * 0.27, 1.1, 0);
      }
    } else if (kind === "kettle") {
      add(new THREE.CylinderGeometry(0.22, 0.26, 0.45, 14), 0xc0c0c0, 0, 1.25, 0);
      add(new THREE.CylinderGeometry(0.05, 0.05, 0.3, 8), 0x555555, 0.25, 1.35, 0).rotation.z = -0.8;
    }
    g.position.set(x, 0, z); g.rotation.y = rotY || 0;
    this.scene.add(g);
    return meshes;
  }

  board(text, x, z, rotY, color) {
    const tex = this.textTexture(text, color, "#ffffff", 512, 256, 54);
    const m = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.2, 0.08), [
      this.mat(0x5d4037), this.mat(0x5d4037), this.mat(0x5d4037), this.mat(0x5d4037),
      new THREE.MeshLambertMaterial({ map: tex, emissive: 0x000000 }), this.mat(0x5d4037)]);
    m.position.set(x, 1.6, z); m.rotation.y = rotY; m.castShadow = true;
    this.scene.add(m);
    return m;
  }

  // Open storage shelf with one board per item. The crates on it show the real stock
  // (updated every frame from the view), instead of boxes stuck inside a solid block.
  storageShelf(shop, x, z, rotY, items) {
    const group = new THREE.Group();
    group.position.set(x, 0, z); group.rotation.y = rotY;
    this.scene.add(group);
    const wood = 0x6d4c41, parent = { parent: group };
    const parts = [
      this.box(2.2, 1.9, 0.06, wood, 0, 0.95, -0.27, parent),
      this.box(0.06, 1.9, 0.6, wood, -1.07, 0.95, 0, parent),
      this.box(0.06, 1.9, 0.6, wood, 1.07, 0.95, 0, parent),
    ];
    // v7: shops with four ingredients get four boards
    const levels = items.length > 3 ? [0.06, 0.52, 0.98, 1.44] : [0.06, 0.69, 1.32];
    for (const y of [...levels, 1.9]) parts.push(this.box(2.2, 0.05, 0.6, 0x8d6e63, 0, y, 0, parent));
    const colors = { coffee_beans: 0x6f4e37, oranges: 0xff9f1c, nata: 0xf4c95d, tea_leaves: 0x6a994e, croissant_dough: 0xe9b872,
      water: 0x81d4fa, coke_zero: 0x212121, protein_bars: 0x8d6e63, bread: 0xd7a86e, cheese: 0xffd54f, iced_tea: 0xffb74d,
      apples: 0xe53935, rice: 0xfafafa, salmon: 0xff8a65, acai: 0x6a1b9a, fruit_mix: 0xef5350, chicken: 0xc68642,
      fries: 0xffca28, frozen_pizza: 0xff7043, pudding_cups: 0xffe082 };
    this.shelfCrates = this.shelfCrates || {};
    this.shelfCrates[shop] = {};
    items.forEach((item, k) => {
      const crates = [];
      for (const cx of [-0.68, 0, 0.68]) {
        const crate = new THREE.Group();
        crate.position.set(cx, levels[k] + 0.03, 0.02);
        if (items.length > 3) crate.scale.y = 0.75;
        this.box(0.56, 0.3, 0.46, 0xa1887f, 0, 0.15, 0, { parent: crate });
        this.box(0.5, 0.06, 0.4, colors[item] || 0xcccccc, 0, 0.31, 0, { parent: crate, cast: false });
        group.add(crate);
        crate.visible = false;
        crates.push(crate);
      }
      this.shelfCrates[shop][item] = crates;
    });
    return parts;
  }
  updateShelves(view) {
    for (const [shop, items] of Object.entries(this.shelfCrates || {})) {
      const stock = view.shops[shop].owner === "player" ? view.shops[shop].stock : null;
      for (const [item, crates] of Object.entries(items)) {
        const units = stock && stock[item] ? stock[item].units : 0;
        const packs = Math.ceil(units / this.game.config.wholesale_items[item].base_units);
        const show = view.shops[shop].owner === "bot" ? 3 : Math.min(3, packs);
        crates.forEach((c, i) => { c.visible = i < show; });
      }
    }
  }

  buildCafeInterior() {
    const g = this.game;
    // Counter with a gap at the south end so the player can get behind it
    const counter = this.box(0.9, 1.05, 8.6, 0x8b5e3c, -34.9, 0.52, -1.5);
    this.box(1.1, 0.08, 8.8, 0xf4e1c1, -34.9, 1.08, -1.5);
    this.collide(-35.35, -34.45, -5.8, 2.8);
    const register = this.box(0.5, 0.35, 0.45, 0x264653, -35.0, 1.3, -0.6);
    // Stations against the west wall
    const coffee = this.station("cafe", "coffee_machine", -39.1, -3.6, Math.PI / 2);
    const juicer = this.station("cafe", "juicer", -39.1, -1.6, Math.PI / 2);
    const display = this.station("cafe", "display_case", -39.1, 0.6, Math.PI / 2);
    this.collide(-39.85, -38.6, -4.4, 1.4);
    const shelf = this.storageShelf("cafe", -39.5, 3.6, Math.PI / 2, ["coffee_beans", "oranges", "nata"]);
    this.collide(-39.85, -39.15, 2.5, 4.7);
    const planBoard = this.board("DAY PLAN", -37.4, -5.7, 0, "#2a9d8f");
    const upBoard = this.board("UPGRADES", -31.5, -5.7, 0, "#e76f51");
    // Customer area: two tables with chairs
    const tables = [];
    for (const z of [-3.9, 3.9]) {
      tables.push(this.box(1.3, 0.08, 1.3, 0xffffff, -30.8, 0.78, z));
      this.box(0.15, 0.75, 0.15, 0x555555, -30.8, 0.38, z);
      this.box(0.6, 0.45, 0.6, 0x2a9d8f, -32.1, 0.23, z);
      this.box(0.6, 0.45, 0.6, 0x2a9d8f, -29.5, 0.23, z);
      this.collide(-32.4, -29.2, z - 0.7, z + 0.7);
    }
    const doorSign = this.box(0.08, 0.6, 0.9, 0xffffff, -27.75, 1.6, 2.1);
    const floorSpot = new THREE.Mesh(new THREE.CircleGeometry(0.6, 24), new THREE.MeshLambertMaterial({ color: 0xb08968, emissive: 0x000000 }));
    floorSpot.rotation.x = -Math.PI / 2; floorSpot.position.set(-31.5, 0.05, 1.6); this.scene.add(floorSpot);
    floorSpot.visible = false; // only dirty after closing (see updateWorldState)
    this.floorSpot = floorSpot;

    const cafeOpenManual = () => g.isManual("cafe");
    this.addInteractable({ id: "plan_board", pos: { x: -37.4, z: -4.9 }, radius: 2.7, meshes: [planBoard], label: () => g.flow.planBoardLabel("cafe"),
      enabled: () => g.flow.planBoardLabel("cafe") !== null, action: () => g.flow.usePlanBoard("cafe") });
    this.addInteractable({ id: "upgrade_board", pos: { x: -31.5, z: -4.9 }, radius: 2.7, meshes: [upBoard], label: () => "Upgrades & staff",
      action: () => g.flow.openUpgrades() });
    this.addInteractable({ id: "storage_cafe", pos: { x: -38.6, z: 3.6 }, meshes: shelf, label: () => "Stock the goods",
      enabled: () => g.flow.bagHasItemsFor("cafe"), action: () => g.flow.openStock("cafe") });
    // v5: only before opening (prices cannot change during the day)
    this.addInteractable({ id: "register_cafe", pos: { x: -35.8, z: -0.6 }, meshes: [register, counter], label: () => g.flow.registerLabel(),
      enabled: () => g.flow.canSetPrices("cafe"), action: () => g.flow.useRegister("cafe") });
    this.addInteractable({ id: "door_sign", pos: { x: -27.2, z: 2.1 }, meshes: [doorSign], label: () => "Open the café",
      enabled: () => g.view && !g.view.open && !g.view.closed && g.clock.t >= 7, action: () => g.flow.askOpen() });
    this.addInteractable({ id: "station_cafe_coffee", pos: { x: -38.1, z: -3.6 }, meshes: coffee, label: () => "Make a coffee",
      enabled: cafeOpenManual, action: () => g.flow.openStation("cafe", "coffee") });
    this.addInteractable({ id: "station_cafe_juice", pos: { x: -38.1, z: -1.6 }, meshes: juicer, label: () => "Squeeze orange juice",
      enabled: cafeOpenManual, action: () => g.flow.openStation("cafe", "orange_juice") });
    this.addInteractable({ id: "station_cafe_nata", pos: { x: -38.1, z: 0.6 }, meshes: display, label: () => "Take a pastel de nata",
      enabled: cafeOpenManual, action: () => g.flow.openStation("cafe", "pastel_de_nata") });
    // Cleaning spots (only after closing)
    const cleaning = { counter: [counter, { x: -34.2, z: -2.5 }], coffee_machine: [coffee[0], { x: -38.1, z: -3.6 }],
      tables: [tables[1], { x: -30.8, z: 2.7 }], floor: [floorSpot, { x: -31.5, z: 1.6 }] };
    for (const [spot, [mesh, pos]] of Object.entries(cleaning)) {
      this.addInteractable({ id: "clean_" + spot, pos, meshes: [mesh], cleaning: spot, priority: 2,
        label: () => g.config.cleaning_spots[spot].name,
        // v6: with a manager the player cannot clean - the manager does it
        enabled: () => g.view && g.view.day_state === "CLOSING" && !g.view.cleaning[spot] && !g.view.shops.cafe.manager_hired,
        action: () => g.flow.openCleaning(spot) });
    }
    this.addInteractable({ id: "counter_front_cafe", pos: { x: -35.6, z: 0.2 }, radius: 1.8, meshes: [], priority: 1,
      label: () => g.flow.counterLabel("cafe"), enabled: () => g.flow.counterLabel("cafe") !== null,
      action: () => g.flow.useCounterFront("cafe") });
  }

  buildRivalInterior() {
    const g = this.game;
    const counter = this.box(8.4, 1.05, 0.9, 0x6d597a, -1.2, 0.52, -21.0);
    this.box(8.6, 0.08, 1.1, 0xf8f9fa, -1.2, 1.08, -21.0);
    this.collide(-5.8, 3.0, -21.45, -20.55);
    const register = this.box(0.45, 0.35, 0.5, 0x264653, 0.6, 1.3, -21.1);
    const coffee = this.station("rival", "coffee_machine", -3.4, -26.1, 0);
    const kettle = this.station("rival", "kettle", -1.4, -26.1, 0);
    const display = this.station("rival", "display_case", 0.6, -26.1, 0);
    this.collide(-4.2, 1.4, -26.85, -25.6);
    const shelf = this.storageShelf("rival", 4.2, -26.4, 0, ["coffee_beans", "tea_leaves", "croissant_dough"]);
    this.collide(3.1, 5.3, -26.85, -26.0);
    for (const x of [-3.5, 3.5]) {
      this.box(1.2, 0.08, 1.2, 0xffffff, x, 0.78, -18.2);
      this.box(0.15, 0.75, 0.15, 0x555555, x, 0.38, -18.2);
      this.collide(x - 0.7, x + 0.7, -18.9, -17.5);
    }
    const rivalManual = () => g.isManual("rival");
    const owned = () => g.view && g.view.shops.rival.owner === "player";
    this.addInteractable({ id: "register_rival", pos: { x: 0.6, z: -21.9 }, meshes: [register], label: () => g.flow.registerLabel(),
      enabled: () => g.flow.canSetPrices("rival"), action: () => g.flow.useRegister("rival") });
    // v5: boards for planning and upgrades also in the second café
    const rPlan = this.board("DAY PLAN", 5.92, -18.6, -Math.PI / 2, "#2a9d8f");
    const rUp = this.board("UPGRADES", -5.92, -18.6, Math.PI / 2, "#e76f51");
    this.addInteractable({ id: "plan_board_rival", pos: { x: 5.0, z: -18.6 }, radius: 2.4, meshes: [rPlan], label: () => g.flow.planBoardLabel("rival"),
      enabled: () => owned() && g.flow.planBoardLabel("rival") !== null, action: () => g.flow.usePlanBoard("rival") });
    this.addInteractable({ id: "upgrade_board_rival", pos: { x: -5.0, z: -18.6 }, radius: 2.4, meshes: [rUp], label: () => "Upgrades & staff",
      enabled: owned, action: () => g.flow.openUpgrades() });
    this.addInteractable({ id: "storage_rival", pos: { x: 4.2, z: -25.5 }, meshes: shelf, label: () => "Stock the goods",
      enabled: () => owned() && g.flow.bagHasItemsFor("rival"), action: () => g.flow.openStock("rival") });
    this.addInteractable({ id: "station_rival_coffee", pos: { x: -3.4, z: -25.1 }, meshes: coffee, label: () => "Make a coffee",
      enabled: rivalManual, action: () => g.flow.openStation("rival", "coffee") });
    this.addInteractable({ id: "station_rival_tea", pos: { x: -1.4, z: -25.1 }, meshes: kettle, label: () => "Make a tea",
      enabled: rivalManual, action: () => g.flow.openStation("rival", "tea") });
    this.addInteractable({ id: "station_rival_croissant", pos: { x: 0.6, z: -25.1 }, meshes: display, label: () => "Take a croissant",
      enabled: rivalManual, action: () => g.flow.openStation("rival", "croissant") });
    this.addInteractable({ id: "counter_front_rival", pos: { x: 0.0, z: -21.9 }, radius: 1.8, meshes: [], priority: 1,
      label: () => g.flow.counterLabel("rival"), enabled: () => g.flow.counterLabel("rival") !== null,
      action: () => g.flow.useCounterFront("rival") });
  }

  // v7: interiors of the new shops, built from the frame of the building.
  //   counter: counter with a gap, stations along the back wall (one per station kind)
  //   market:  checkout counter near the back, product shelves along the side walls
  //   vending: one machine per product along the back wall, an office desk near the door
  buildGenericShop(key) {
    const g = this.game, b = BUILDINGS[key], pt = P[key], f = pt.frame, spec = g.config.shops[key];
    const D = f.depth, W = f.width, cd = pt.cd;
    const owned = () => g.view && g.view.shops[key].owner === "player";
    const manual = () => g.isManual(key);
    const at = (d, l) => f.at(d, l);
    const place = (mesh, d, l, rotY) => { const p = at(d, l); mesh.position.x = p.x; mesh.position.z = p.z; if (rotY !== undefined) mesh.rotation.y = rotY; return mesh; };
    const boxAt = (w, h, dep, color, d, l, y, rot) => { // w along lat, dep along inn
      const along = f.inn.x !== 0; // inn along x: the box's x size is the depth
      const m = this.box(along ? dep : w, h, along ? w : dep, color, 0, y, 0);
      place(m, d, l, rot);
      return m;
    };
    const items = [...new Set(spec.products.flatMap((p) => Object.keys(g.config.products[p].uses)))];
    const kinds = [...new Set(spec.products.map((p) => g.config.products[p].station).filter(Boolean))];
    const stationAt = {};
    if (b.interior === "vending") {
      spec.products.forEach((p, i) => {
        const lat = (i - (spec.products.length - 1) / 2) * 2.2;
        const pos = at(D - 0.55, lat);
        const meshes = this.station(key, "machine", pos.x, pos.z, f.faceDoor, { product: p, color: b.trim });
        const r = f.rect(D - 1.0, D, lat - 0.75, lat + 0.75); this.collide(r.x0, r.x1, r.z0, r.z1);
        const front = at(D - 1.5, lat);
        stationAt[p] = front;
        this.addInteractable({ id: `station_${key}_${p}`, pos: front, meshes, radius: 1.6,
          label: () => g.flow.machineLabel(key, p), enabled: () => g.flow.machineLabel(key, p) !== null,
          action: () => g.flow.useMachine(key, p) });
      });
      const desk = boxAt(1.6, 0.9, 0.8, 0x5d4037, 2.0, -(W / 2 - 1.0), 0.45);
      boxAt(0.5, 0.35, 0.4, 0x263238, 2.0, -(W / 2 - 1.0), 1.1);
      const r = f.rect(1.6, 2.4, -(W / 2), -(W / 2 - 1.8)); this.collide(r.x0, r.x1, r.z0, r.z1);
      pt.upBoard = at(2.0, -(W / 2 - 2.2));
      this.addInteractable({ id: `office_${key}`, pos: pt.upBoard, meshes: [desk], radius: 2.0,
        label: () => "Vending company office", enabled: () => !!g.view, action: () => g.flow.openOffice(key) });
    } else {
      // counter across the shop with a gap at the "lat +" end
      const counterLen = W - 3.2;
      const cLat = -W / 2 + counterLen / 2;
      const counter = boxAt(counterLen, 1.05, 0.9, b.trim, cd, cLat, 0.52);
      boxAt(counterLen + 0.2, 0.08, 1.1, 0xf8f9fa, cd, cLat, 1.08);
      const r = f.rect(cd - 0.45, cd + 0.45, -W / 2, -W / 2 + counterLen); this.collide(r.x0, r.x1, r.z0, r.z1);
      const register = boxAt(0.45, 0.35, 0.5, 0x264653, cd, 0.6, 1.3);
      this.addInteractable({ id: `register_${key}`, pos: pt.register, meshes: [register, counter], label: () => g.flow.registerLabel(),
        enabled: () => g.flow.canSetPrices(key), action: () => g.flow.useRegister(key) });
      this.addInteractable({ id: `counter_front_${key}`, pos: at(cd + 0.9, 0), radius: 1.8, meshes: [], priority: 1,
        label: () => g.flow.counterLabel(key), enabled: () => g.flow.counterLabel(key) !== null,
        action: () => g.flow.useCounterFront(key) });
      kinds.forEach((kind, i) => {
        const lat = -W / 2 + 2.6 + i * 2.0;
        const pos = at(D - 0.9, lat);
        const meshes = this.station(key, kind, pos.x, pos.z, f.faceDoor, { color: b.trim });
        const rr = f.rect(D - 1.3, D, lat - 0.75, lat + 0.75); this.collide(rr.x0, rr.x1, rr.z0, rr.z1);
        const front = at(D - 1.9, lat);
        stationAt[kind] = front;
        this.addInteractable({ id: `station_${key}_${kind}`, pos: front, meshes,
          label: () => g.flow.stationLabel(key, kind), enabled: manual, action: () => g.flow.useStation(key, kind) });
      });
      if (b.interior === "market") {
        // product shelves along the side walls (customer side), filled from the storage
        this.marketShelves = this.marketShelves || {};
        this.marketShelves[key] = [];
        spec.products.forEach((p, i) => {
          const side = i % 2 ? 1 : -1, d = i < 2 ? 3.8 : 5.9;
          const shelf = boxAt(0.6, 1.6, 1.6, 0x8d6e63, d, side * (W / 2 - 0.45), 0.8);
          const rr = f.rect(d - 0.8, d + 0.8, side * (W / 2), side * (W / 2 - 0.8)); this.collide(rr.x0, rr.x1, rr.z0, rr.z1);
          const goods = [];
          for (let k = 0; k < 4; k++) {
            const m = boxAt(0.36, 0.26, 0.36, 0xffffff, d - 0.4 + (k % 2) * 0.8, side * (W / 2 - 0.85), 0.55 + Math.floor(k / 2) * 0.5);
            m.material = this.mat([0xffd166, 0x4ea8de, 0xe63946][i % 3]);
            goods.push(m);
          }
          this.marketShelves[key].push({ product: p, goods });
          const front = at(d, side * (W / 2 - 1.5));
          stationAt["shelf_" + p] = front;
          this.addInteractable({ id: `shelf_${key}_${p}`, pos: front, meshes: [shelf], radius: 1.7,
            label: () => g.flow.shelfLabel(key), enabled: () => g.flow.shelfLabel(key) !== null, action: () => g.flow.openShelves(key) });
        });
      } else {
        for (const lat of [-(W / 2 - 2.5), W / 2 - 2.5]) {
          boxAt(1.2, 0.08, 1.2, 0xffffff, 2.2, lat, 0.78);
          boxAt(0.15, 0.75, 0.15, 0x555555, 2.2, lat, 0.38);
          const rr = f.rect(1.5, 2.9, lat - 0.7, lat + 0.7); this.collide(rr.x0, rr.x1, rr.z0, rr.z1);
        }
      }
      const up = this.board("UPGRADES", 0, 0, 0, "#e76f51");
      place(up, 2.4, -(W / 2 - 0.08), f.faceLat(1));
      this.addInteractable({ id: `upgrade_board_${key}`, pos: pt.upBoard, radius: 2.4, meshes: [up], label: () => "Upgrades & staff",
        enabled: owned, action: () => g.flow.openUpgrades() });
    }
    const plan = this.board("DAY PLAN", 0, 0, 0, "#2a9d8f");
    place(plan, 2.4, W / 2 - 0.08, f.faceLat(-1));
    this.addInteractable({ id: `plan_board_${key}`, pos: pt.planBoard, radius: 2.4, meshes: [plan], label: () => g.flow.planBoardLabel(key),
      enabled: () => owned() && g.flow.planBoardLabel(key) !== null, action: () => g.flow.usePlanBoard(key) });
    const sp = pt.storage;
    const vend = b.interior === "vending";
    const shelf = this.storageShelf(key, sp.x, sp.z, vend ? f.faceLat(-1) : f.faceDoor, items);
    const sr = vend ? f.rect(D - 3.9, D - 1.7, W / 2 - 0.6, W / 2) : f.rect(D - 1.3, D, W / 2 - 2.9, W / 2 - 0.7);
    this.collide(sr.x0, sr.x1, sr.z0, sr.z1);
    this.addInteractable({ id: `storage_${key}`, pos: b.interior === "vending" ? at(D - 2.8, W / 2 - 2.0) : at(D - 1.9, W / 2 - 1.8), meshes: shelf,
      label: () => "Stock the goods", enabled: () => owned() && g.flow.bagHasItemsFor(key), action: () => g.flow.openStock(key) });
    pt.stationAt = stationAt;
  }

  // v5: a price board in front of each café ("-" until today's prices are set),
  // and a "FOR SALE" sign at the competitor once you could buy it.
  buildPriceBoards() {
    this.priceBoards = {};
    const make = (shop, x, z, rotY) => {
      const c = document.createElement("canvas"); c.width = 512; c.height = 640;
      const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
      const group = new THREE.Group(); group.position.set(x, 0, z); group.rotation.y = rotY;
      const face = new THREE.Mesh(new THREE.BoxGeometry(1.0, 1.25, 0.06), [
        this.mat(0x3e2723), this.mat(0x3e2723), this.mat(0x3e2723), this.mat(0x3e2723),
        new THREE.MeshLambertMaterial({ map: tex, emissive: 0x000000 }), this.mat(0x3e2723)]);
      face.position.set(0, 1.05, 0); face.rotation.x = -0.12; face.castShadow = true;
      group.add(face);
      for (const sx of [-0.42, 0.42]) this.box(0.06, 0.5, 0.06, 0x3e2723, sx, 0.25, -0.05, { parent: group });
      this.scene.add(group);
      this.collide(x - 0.55, x + 0.55, z - 0.4, z + 0.4);
      this.priceBoards[shop] = { canvas: c, tex, key: "" };
    };
    make("cafe", -25.6, -2.9, Math.PI / 2);
    make("rival", 3.6, -14.4, 0);
    for (const key of this.newShops) { const p = P[key].priceBoard; make(key, p.x, p.z, P[key].frame.faceDoor); }
    // FOR SALE sign next to the door of the shop you can buy next (v7: it moves from shop to shop)
    const sale = new THREE.Group(); sale.position.set(-4.25, 0, -14.6);
    // v6: two posts behind the plate, so nothing covers the letters
    for (const px of [-0.6, 0.6]) this.box(0.08, 1.85, 0.08, 0x5d4037, px, 0.925, -0.08, { parent: sale });
    const tex = this.textTexture("FOR SALE", "#c0392b", "#ffffff", 512, 200, 96);
    const plate = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.55, 0.05), [
      this.mat(0xffffff), this.mat(0xffffff), this.mat(0xffffff), this.mat(0xffffff),
      new THREE.MeshLambertMaterial({ map: tex, emissive: 0x000000 }), new THREE.MeshLambertMaterial({ map: tex, emissive: 0x000000 })]);
    plate.position.set(0, 1.55, 0); plate.castShadow = true; sale.add(plate);
    sale.visible = false;
    this.scene.add(sale);
    this.forSale = sale;
  }
  updatePriceBoards(view) {
    const cfg = this.game.config;
    for (const [shop, b] of Object.entries(this.priceBoards || {})) {
      const s = view.shops[shop];
      const known = s.prices_set || s.owner === "bot";
      const sold = s.sold;
      const key = JSON.stringify([s.prices, known, s.operating, s.owner, sold]);
      if (key === b.key) continue;
      b.key = key;
      const g = b.canvas.getContext("2d"), W = b.canvas.width, H = b.canvas.height;
      g.fillStyle = "#26302b"; g.fillRect(0, 0, W, H);
      g.strokeStyle = "#c9a227"; g.lineWidth = 14; g.strokeRect(10, 10, W - 20, H - 20);
      g.fillStyle = "#f4e9c9"; g.textAlign = "center"; g.textBaseline = "middle";
      g.font = "900 54px sans-serif"; g.fillText(cfg.shops[shop].name.toUpperCase(), W / 2, 74);
      const prods = cfg.shops[shop].products;
      prods.forEach((p, i) => {
        const y = 190 + i * 130;
        g.textAlign = "left"; g.font = "60px serif"; g.fillText(cfg.products[p].icon, 44, y);
        g.font = "800 38px sans-serif"; g.fillText(cfg.products[p].name.split(" (")[0], 118, y, W - 118 - 190);
        g.textAlign = "right"; g.font = "900 52px sans-serif"; g.fillStyle = known ? "#ffd166" : "#9aa59f";
        g.fillText(known ? euro(s.prices[p]) : "-", W - 36, y, 160);
        g.fillStyle = "#f4e9c9";
      });
      const hours = cfg.shops[shop].open_hours;
      if (!s.operating) { g.textAlign = "center"; g.font = "900 46px sans-serif"; g.fillStyle = "#ff8a80"; g.fillText("CLOSED TODAY", W / 2, H - 50); }
      else if (hours && !sold) { g.textAlign = "center"; g.font = "800 40px sans-serif"; g.fillStyle = "#9ad0f5"; g.fillText(`OPEN ${fmtTime(hours[0])} - ${fmtTime(hours[1])}`, W / 2, H - 50, W - 40); }
      if (sold) { g.textAlign = "center"; g.font = "900 46px sans-serif"; g.fillStyle = "#7ee2a8"; g.fillText("SOLD - NEW OWNER TOMORROW", W / 2, H - 50, W - 40); }
      b.tex.needsUpdate = true;
    }
    if (this.forSale) {
      const shop = view.for_sale;
      this.forSale.visible = !!shop;
      if (shop && this.forSaleAt !== shop) {
        this.forSaleAt = shop;
        const p = P[shop].saleSign || P[shop].frame.at(-1.4, -4.25);
        this.forSale.position.set(p.x, 0, p.z);
        this.forSale.rotation.y = P[shop].frame ? P[shop].frame.faceDoor : 0;
      }
    }
  }

  // v7: status lights of the vending machines and goods on the market shelves
  updateMechanics(view) {
    for (const [k, mat] of Object.entries(this.machineLights || {})) {
      const [shop, product] = k.split(":"), s = view.shops[shop];
      const mine = s.owner === "player";
      const color = mine && s.mech.broken && s.mech.broken[product] ? 0xe74c3c : mine && !(s.front[product] > 0) ? 0xf1c40f : 0x2ecc71;
      if (mat.color.getHex() !== color) mat.color.setHex(color);
    }
    for (const [shop, shelves] of Object.entries(this.marketShelves || {})) {
      const s = view.shops[shop];
      for (const { product, goods } of shelves) {
        const n = s.owner === "bot" ? goods.length : Math.min(goods.length, Math.ceil((s.front[product] || 0) / 5));
        goods.forEach((m, i) => { m.visible = i < n; });
      }
    }
  }
  keepOutOfWalls(pos, radius) { resolveCollisions(pos, radius, this.colliders); }
  // v7: zones that are not open yet are hidden on the maps (beach)
  zoneVisible(zone) { return !zone || zone === "campus" || !!(this.game.view && this.game.view.zones_open.includes(zone)); }

  buildWholesaleInterior() {
    const g = this.game;
    const stands = { coffee_beans: [32.5, -6.6], oranges: [37, -6.6], nata: [41.5, -6.6], tea_leaves: [35, 6.6], croissant_dough: [40, 6.6] };
    // v7: one aisle per new shop (its items are sold once you own the shop)
    const aisleSpots = [[46, -6.6], [50.5, -6.6], [44.5, 6.6], [49, 6.6], [37.5, 0], [42, 0], [46.5, 0]];
    this.newShops.forEach((shop, k) => {
      const [x, z] = aisleSpots[k];
      const spec = g.config.shops[shop];
      const face = z > 0 ? -1 : 1; // the side customers stand on
      const table = this.box(2.6, 0.9, 1.2, 0x8d99ae, x, 0.45, z);
      const crates = [];
      for (let i = 0; i < 3; i++) crates.push(this.box(0.7, 0.45, 0.7, 0xd4a373, x - 0.8 + i * 0.8, 1.13, z));
      const pic = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.1), new THREE.MeshBasicMaterial({ map: this.emojiTexture(spec.icon, 128), transparent: true }));
      pic.position.set(x, 2.1, z + face * 0.65); if (face < 0) pic.rotation.y = Math.PI; this.scene.add(pic);
      const label = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.42),
        new THREE.MeshBasicMaterial({ map: this.textTexture(spec.name, "#3d5a80", "#fff", 512, 96, 50) }));
      label.position.set(x, 1.45, z + face * 0.62); if (face < 0) label.rotation.y = Math.PI; this.scene.add(label);
      this.collide(x - 1.3, x + 1.3, z - 0.6, z + 0.6);
      this.addInteractable({ id: "aisle_" + shop, pos: { x, z: z + face * 1.5 }, meshes: [table, ...crates],
        label: () => `${spec.name} supplies`, enabled: () => g.view && g.view.shops[shop].owner === "player",
        action: () => g.flow.openAisle(shop) });
    });
    for (const [item, [x, z]] of Object.entries(stands)) {
      const spec = g.config.wholesale_items[item];
      const table = this.box(2.6, 0.9, 1.2, 0xa98467, x, 0.45, z);
      const crates = [];
      for (let i = 0; i < 3; i++) crates.push(this.box(0.7, 0.45, 0.7, 0xd4a373, x - 0.8 + i * 0.8, 1.13, z));
      const tex = this.emojiTexture(spec.icon, 128);
      const pic = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.1), new THREE.MeshBasicMaterial({ map: tex, transparent: true }));
      pic.position.set(x, 2.1, z + (z < 0 ? 0.65 : -0.65)); if (z > 0) pic.rotation.y = Math.PI; this.scene.add(pic);
      const label = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 0.42),
        new THREE.MeshBasicMaterial({ map: this.textTexture(spec.name, "#52796f", "#fff", 512, 96, 54) }));
      label.position.set(x, 1.45, z + (z < 0 ? 0.62 : -0.62)); if (z > 0) label.rotation.y = Math.PI; this.scene.add(label);
      this.collide(x - 1.3, x + 1.3, z - 0.6, z + 0.6);
      this.addInteractable({ id: "stand_" + item, pos: { x, z: z + (z < 0 ? 1.5 : -1.5) }, meshes: [table, ...crates],
        label: () => spec.name, enabled: () => g.view && g.view.items_available.includes(item),
        action: () => g.flow.openItem(item) });
    }
    // Checkout with cashier
    const desk = this.box(2.4, 1.0, 0.9, 0x354f52, 32, 0.5, 3.6);
    this.collide(30.8, 33.2, 3.15, 4.05);
    this.addInteractable({ id: "checkout", pos: { x: 32, z: 2.3 }, meshes: [desk], label: () => "Checkout",
      action: () => g.flow.openCheckout() });
    this.cashierPos = { x: 32, z: 4.8 };
    // Gate in the door: closed until the player enters via P03, and while unpaid goods are in the cart
    this.gates.wholesale = { x0: 27.75, x1: 28.25, z0: -1.8, z1: 1.8, active: true };
    this.colliders.push(this.gates.wholesale);
  }

  tree(x, z) {
    this.box(0.4, 1.6, 0.4, 0x7a5230, x, 0.8, z);
    const crown = new THREE.Mesh(new THREE.IcosahedronGeometry(1.6, 0), this.mat(0x2f7d32, { flatShading: true }));
    crown.position.set(x, 2.6, z); crown.castShadow = true; this.scene.add(crown);
    this.collide(x - 0.4, x + 0.4, z - 0.4, z + 0.4);
  }

  bench(x, z, r) {
    const g = new THREE.Group();
    const seat = new THREE.Mesh(new THREE.BoxGeometry(2, 0.12, 0.5), this.mat(0x9c6644)); seat.position.y = 0.45; seat.castShadow = true;
    const back = new THREE.Mesh(new THREE.BoxGeometry(2, 0.45, 0.1), this.mat(0x9c6644)); back.position.set(0, 0.75, -0.22); back.castShadow = true;
    g.add(seat, back); g.position.set(x, 0, z); g.rotation.y = r; this.scene.add(g);
  }

  lamp(x, z) {
    this.box(0.15, 3.4, 0.15, 0x333d29, x, 1.7, z);
    const bulbMat = new THREE.MeshBasicMaterial({ color: 0x555555 });
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.25, 12, 10), bulbMat);
    bulb.position.set(x, 3.5, z); this.scene.add(bulb);
    this.lampBulbs.push(bulbMat);
    if (this.lampLights.length < 7) { // 3 building lights + 4 street lamps; other lamps only glow
      const light = new THREE.PointLight(0xffd59e, 0, 13, 1.5);
      light.position.set(x, 3.3, z); this.scene.add(light);
      this.lampLights.push(light);
    }
    this.collide(x - 0.15, x + 0.15, z - 0.15, z + 0.15);
  }

  // Which building contains the point (inside the walls)?
  buildingAt(p) {
    for (const [key, b] of Object.entries(BUILDINGS)) {
      if (p.x > b.x0 + 0.15 && p.x < b.x1 - 0.15 && p.z > b.z0 + 0.15 && p.z < b.z1 - 0.15) return key;
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // Navigation grid for students (outdoor), with line-of-sight smoothing
  // ---------------------------------------------------------------------
  blockedRect(x, z, pad) {
    for (const b of Object.values(BUILDINGS)) {
      if (x > b.x0 - pad && x < b.x1 + pad && z > b.z0 - pad && z < b.z1 + pad) return true;
    }
    for (const c of this.colliders) {
      if (c.x1 - c.x0 < 2 && c.z1 - c.z0 < 2 && x > c.x0 - pad && x < c.x1 + pad && z > c.z0 - pad && z < c.z1 + pad) return true;
    }
    return x > -1.7 - pad && x < 1.7 + pad && z > 4.3 - pad && z < 7.7 + pad; // fountain
  }

  lineFree(a, b, pad = 0.7) {
    const steps = Math.ceil(dist2(a, b) / 0.5);
    for (let i = 1; i < steps; i++) {
      const w = i / steps;
      if (this.blockedRect(lerp(a.x, b.x, w), lerp(a.z, b.z, w), pad)) return false;
    }
    return true;
  }

  buildNav() {
    this.navStep = 3;
    this.navMin = -66;
    this.navN = 45;
    this.navFree = new Uint8Array(this.navN * this.navN);
    for (let i = 0; i < this.navN; i++) for (let j = 0; j < this.navN; j++) {
      const x = this.navMin + i * this.navStep, z = this.navMin + j * this.navStep;
      this.navFree[i * this.navN + j] = this.blockedRect(x, z, 1.0) ? 0 : 1;
    }
    this.wanderPoints = [];
    for (let i = 0; i < this.navN; i++) for (let j = 0; j < this.navN; j++) {
      const x = this.navMin + i * this.navStep, z = this.navMin + j * this.navStep;
      if (this.navFree[i * this.navN + j] && Math.abs(x) < 48 && Math.abs(z) < 40) this.wanderPoints.push({ x, z });
    }
    // Students enter and leave over the map edges (spread over all sides)
    this.edgePoints = [
      { x: -56, z: 0 }, { x: 56, z: 0 }, { x: 0, z: 54 }, { x: -56, z: -30 }, { x: 56, z: 30 },
      { x: -30, z: 54 }, { x: 36, z: 54 }, { x: 56, z: -36 }, { x: -56, z: 34 }, { x: 20, z: -54 },
    ];
  }

  navCell(p) {
    let i = clamp(Math.round((p.x - this.navMin) / this.navStep), 0, this.navN - 1);
    let j = clamp(Math.round((p.z - this.navMin) / this.navStep), 0, this.navN - 1);
    if (this.navFree[i * this.navN + j]) return [i, j];
    let best = null, bd = 1e9;
    for (let di = -3; di <= 3; di++) for (let dj = -3; dj <= 3; dj++) {
      const a = i + di, b = j + dj;
      if (a < 0 || b < 0 || a >= this.navN || b >= this.navN || !this.navFree[a * this.navN + b]) continue;
      const d = di * di + dj * dj;
      if (d < bd) { bd = d; best = [a, b]; }
    }
    return best || [i, j];
  }

  findPath(from, to) {
    if (this.lineFree(from, to)) return [to];
    const N = this.navN;
    const [si, sj] = this.navCell(from), [ti, tj] = this.navCell(to);
    const start = si * N + sj, goal = ti * N + tj;
    const prev = new Int32Array(N * N).fill(-1);
    const queue = [start];
    prev[start] = start;
    while (queue.length) {
      const c = queue.shift();
      if (c === goal) break;
      const ci = Math.floor(c / N), cj = c % N;
      for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
        const a = ci + di, b = cj + dj;
        if (a < 0 || b < 0 || a >= N || b >= N) continue;
        const n = a * N + b;
        if (prev[n] !== -1 || !this.navFree[n]) continue;
        if (di && dj && (!this.navFree[ci * N + b] || !this.navFree[a * N + cj])) continue;
        prev[n] = c;
        queue.push(n);
      }
    }
    if (prev[goal] === -1) return [to];
    const cells = [];
    for (let c = goal; c !== start; c = prev[c]) cells.push(c);
    cells.reverse();
    const pts = cells.map((c) => ({ x: this.navMin + Math.floor(c / N) * this.navStep, z: this.navMin + (c % N) * this.navStep }));
    pts.push(to);
    // String pulling: skip points we can see past
    const out = [];
    let cur = from;
    let k = 0;
    while (k < pts.length) {
      let far = k;
      for (let m = pts.length - 1; m > k; m--) if (this.lineFree(cur, pts[m])) { far = m; break; }
      out.push(pts[far]);
      cur = pts[far];
      k = far + 1;
    }
    return out;
  }
}
