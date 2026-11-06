// ---------------------------------------------------------------------------
// World: campus, buildings, interiors, colliders, interaction points, nav grid
// ---------------------------------------------------------------------------
const BUILDINGS = {
  cafe: { x0: -40, x1: -28, z0: -6, z1: 6, door: { side: "east", a: -1.5, b: 1.5 }, wall: 0xfff1d6, trim: 0x2a9d8f, roof: 0x2e8b57, sign: "DEIN CAFÉ" },
  rival: { x0: -6, x1: 6, z0: -27, z1: -16, door: { side: "south", a: -1.5, b: 1.5 }, wall: 0xe8eef5, trim: 0x8d99ae, roof: 0xb83a3a, sign: "CAFÉ DA ESQUINA" },
  wholesale: { x0: 28, x1: 46, z0: -9, z1: 9, door: { side: "west", a: -1.8, b: 1.8 }, wall: 0xdfe6d8, trim: 0x52796f, roof: 0x3a5a40, sign: "GROSSHANDEL" },
};
const WALL_H = 2.8;

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
  },
  rival: {
    doorOut: { x: 0, z: -14.4 }, doorIn: { x: 0, z: -17.4 },
    queue: [{ x: 0, z: -19.9 }, { x: 0.15, z: -18.8 }, { x: -0.1, z: -17.8 }, { x: 0.1, z: -16.8 }],
    outside: [{ x: 1.6, z: -14.2 }, { x: 2.4, z: -13.2 }, { x: 1.6, z: -12.2 }, { x: 2.4, z: -11.2 }],
    counterZone: { x0: -5.8, x1: 5.8, z0: -26.8, z1: -21.3 },
    cam: { x: 0, y: 4.6, z: -26.4, lx: 0, ly: 0.6, lz: -16 },
    staff: { x: 0.6, z: -22.4 },
  },
  wholesale: { doorOut: { x: 25.6, z: 0 }, doorIn: { x: 29.4, z: 0 } },
};

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
    const plaza = new THREE.Mesh(new THREE.CircleGeometry(8, 40), pathMat);
    plaza.rotation.x = -Math.PI / 2; plaza.position.set(0, 0.025, 6); plaza.receiveShadow = true; s.add(plaza);
    const fountain = this.box(3, 0.6, 3, 0x9fb7c9, 0, 0.3, 6);
    this.box(2.4, 0.1, 2.4, 0x4ea8de, 0, 0.62, 6, { cast: false });
    this.collide(-1.7, 1.7, 4.3, 7.7);

    for (const [key, b] of Object.entries(BUILDINGS)) this.buildBuilding(key, b);
    this.buildCafeInterior();
    this.buildRivalInterior();
    this.buildWholesaleInterior();

    // Trees, benches and street lamps
    const trees = [[-18, 12], [-12, -12], [12, -12], [16, 13], [-48, 14], [-50, -16], [52, 16], [54, -18],
      [20, 26], [-22, 28], [8, 30], [-8, 22], [32, -20], [-30, -22], [40, 22], [-40, 24], [24, -30], [-16, -32]];
    for (const [x, z] of trees) this.tree(x, z);
    for (const [x, z, r] of [[-8, 3.4, 0], [8, 3.4, 0], [4, 10.5, Math.PI / 2], [-4, 10.5, Math.PI / 2]]) this.bench(x, z, r);
    for (const [x, z] of [[-20, 3.2], [-8, -3.2], [8, -3.2], [20, 3.2], [3.2, -10], [3.2, 18], [-3.2, 30], [34, 11], [-34, 9]]) this.lamp(x, z);

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
    s.add(sign);
    // Awning over the door
    const aw = this.box(door.side === "south" ? 4.4 : 1.4, 0.12, door.side === "south" ? 1.4 : 4.4, b.trim,
      door.side === "east" ? x1 + 0.7 : door.side === "west" ? x0 - 0.7 : cx, 2.35, door.side === "south" ? z1 + 0.7 : cz);
    // Warm window light (glows at night)
    const winMat = new THREE.MeshLambertMaterial({ color: 0x334455, emissive: 0xffc46b, emissiveIntensity: 0 });
    this.windowMats.push(winMat);
    const windows = door.side === "south"
      ? [[x0 - 0.17, cz, Math.PI / 2], [x1 + 0.17, cz, Math.PI / 2]]
      : [[cx - 2.5, z1 + 0.17, 0], [cx + 2.5, z1 + 0.17, 0], [cx - 2.5, z0 - 0.17, 0], [cx + 2.5, z0 - 0.17, 0]];
    for (const [wx, wz, r] of windows) {
      const w = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.1), winMat);
      w.position.set(wx, 1.6, wz); w.rotation.y = r; s.add(w);
      const w2 = w.clone(); w2.rotation.y = r + Math.PI; s.add(w2);
    }
    const light = new THREE.PointLight(0xffc46b, 0, 16, 1.6);
    light.position.set(cx, 2.4, cz); s.add(light);
    this.lampLights.push(light);
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

  station(shop, kind, x, z, rotY) {
    const g = new THREE.Group();
    const meshes = [];
    const add = (geo, color, px, py, pz) => {
      const m = new THREE.Mesh(geo, this.mat(color)); m.position.set(px, py, pz); m.castShadow = true; g.add(m); meshes.push(m); return m;
    };
    add(new THREE.BoxGeometry(1.4, 1.0, 0.8), 0x8d6e63, 0, 0.5, 0); // cabinet
    if (kind === "coffee_machine") {
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
      for (let i = 0; i < 4; i++) add(new THREE.CylinderGeometry(0.12, 0.1, 0.08, 12), 0xf6bd60, -0.4 + i * 0.27, 1.1, 0);
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
    const shelf = this.box(0.6, 1.9, 2.2, 0x6d4c41, -39.5, 0.95, 3.6);
    for (let i = 0; i < 3; i++) this.box(0.5, 0.3, 0.5, [0xa1887f, 0xffb74d, 0x81c784][i], -39.45, 0.55 + i * 0.6, 3.0 + i * 0.5);
    this.collide(-39.85, -39.15, 2.5, 4.7);
    const planBoard = this.board("TAGESPLAN", -37.4, -5.7, 0, "#2a9d8f");
    const upBoard = this.board("AUSBAU", -31.5, -5.7, 0, "#e76f51");
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

    const cafeOpenManual = () => g.isManual("cafe");
    this.addInteractable({ id: "plan_board", pos: { x: -37.4, z: -4.9 }, meshes: [planBoard], label: () => "Tagesplanung",
      enabled: () => g.view && g.view.shops.cafe.owner === "player", action: () => g.flow.openPlanning() });
    this.addInteractable({ id: "upgrade_board", pos: { x: -31.5, z: -4.9 }, meshes: [upBoard], label: () => "Ausbau & Personal",
      action: () => g.flow.openUpgrades() });
    this.addInteractable({ id: "storage_cafe", pos: { x: -38.6, z: 3.6 }, meshes: [shelf], label: () => "Waren einräumen",
      enabled: () => g.flow.bagHasItemsFor("cafe"), action: () => g.flow.openStock("cafe") });
    this.addInteractable({ id: "register_cafe", pos: { x: -35.8, z: -0.6 }, meshes: [register, counter], label: () => g.flow.registerLabel("cafe"),
      action: () => g.flow.useRegister("cafe") });
    this.addInteractable({ id: "door_sign", pos: { x: -27.2, z: 2.1 }, meshes: [doorSign], label: () => "Laden öffnen",
      enabled: () => g.view && !g.view.open && !g.view.closed && g.clock.t >= 7, action: () => g.flow.askOpen() });
    this.addInteractable({ id: "station_cafe_coffee", pos: { x: -38.1, z: -3.6 }, meshes: coffee, label: () => "Kaffee zubereiten",
      enabled: cafeOpenManual, action: () => g.flow.openStation("cafe", "coffee") });
    this.addInteractable({ id: "station_cafe_juice", pos: { x: -38.1, z: -1.6 }, meshes: juicer, label: () => "Orangensaft pressen",
      enabled: cafeOpenManual, action: () => g.flow.openStation("cafe", "orange_juice") });
    this.addInteractable({ id: "station_cafe_nata", pos: { x: -38.1, z: 0.6 }, meshes: display, label: () => "Pastel de Nata nehmen",
      enabled: cafeOpenManual, action: () => g.flow.openStation("cafe", "pastel_de_nata") });
    // Cleaning spots (only after closing)
    const cleaning = { counter: [counter, { x: -34.2, z: -2.5 }], coffee_machine: [coffee[0], { x: -38.1, z: -3.6 }],
      tables: [tables[1], { x: -30.8, z: 2.7 }], floor: [floorSpot, { x: -31.5, z: 1.6 }] };
    for (const [spot, [mesh, pos]] of Object.entries(cleaning)) {
      this.addInteractable({ id: "clean_" + spot, pos, meshes: [mesh], cleaning: spot, priority: 2,
        label: () => g.config.cleaning_spots[spot].name,
        enabled: () => g.view && g.view.day_state === "CLOSING" && !g.view.cleaning[spot],
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
    const shelf = this.box(2.2, 1.9, 0.6, 0x6d4c41, 4.2, 0.95, -26.4);
    this.collide(3.1, 5.3, -26.85, -26.0);
    for (const x of [-3.5, 3.5]) {
      this.box(1.2, 0.08, 1.2, 0xffffff, x, 0.78, -18.2);
      this.box(0.15, 0.75, 0.15, 0x555555, x, 0.38, -18.2);
      this.collide(x - 0.7, x + 0.7, -18.9, -17.5);
    }
    const rivalManual = () => g.isManual("rival");
    const owned = () => g.view && g.view.shops.rival.owner === "player";
    this.addInteractable({ id: "register_rival", pos: { x: 0.6, z: -21.9 }, meshes: [register], label: () => g.flow.registerLabel("rival"),
      enabled: owned, action: () => g.flow.useRegister("rival") });
    this.addInteractable({ id: "storage_rival", pos: { x: 4.2, z: -25.5 }, meshes: [shelf], label: () => "Waren einräumen",
      enabled: () => owned() && g.flow.bagHasItemsFor("rival"), action: () => g.flow.openStock("rival") });
    this.addInteractable({ id: "station_rival_coffee", pos: { x: -3.4, z: -25.1 }, meshes: coffee, label: () => "Kaffee zubereiten",
      enabled: rivalManual, action: () => g.flow.openStation("rival", "coffee") });
    this.addInteractable({ id: "station_rival_tea", pos: { x: -1.4, z: -25.1 }, meshes: kettle, label: () => "Tee aufgießen",
      enabled: rivalManual, action: () => g.flow.openStation("rival", "tea") });
    this.addInteractable({ id: "station_rival_croissant", pos: { x: 0.6, z: -25.1 }, meshes: display, label: () => "Croissant nehmen",
      enabled: rivalManual, action: () => g.flow.openStation("rival", "croissant") });
    this.addInteractable({ id: "counter_front_rival", pos: { x: 0.0, z: -21.9 }, radius: 1.8, meshes: [], priority: 1,
      label: () => g.flow.counterLabel("rival"), enabled: () => g.flow.counterLabel("rival") !== null,
      action: () => g.flow.useCounterFront("rival") });
  }

  buildWholesaleInterior() {
    const g = this.game;
    const stands = { coffee_beans: [32.5, -6.6], oranges: [37, -6.6], nata: [41.5, -6.6], tea_leaves: [35, 6.6], croissant_dough: [40, 6.6] };
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
        label: () => spec.name, enabled: () => g.view && (!spec.needs_rival || g.view.shops.rival.owner === "player"),
        action: () => g.flow.openItem(item) });
    }
    // Checkout with cashier
    const desk = this.box(2.4, 1.0, 0.9, 0x354f52, 32, 0.5, 3.6);
    this.collide(30.8, 33.2, 3.15, 4.05);
    this.addInteractable({ id: "checkout", pos: { x: 32, z: 2.3 }, meshes: [desk], label: () => "Kasse",
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
