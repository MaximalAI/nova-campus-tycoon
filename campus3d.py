"""3D campus view for Nova Campus Tycoon (visual only, no game rules).

Builds a self-contained HTML snippet with Three.js that app.py embeds via
streamlit.components. It only reads the game state; it never changes it.
"""

from __future__ import annotations

import json

import logic

SHOP_POSITIONS = {"player_cafe": (-7.0, 0.0), "competitor": (7.0, 0.0)}
WHOLESALER_POSITION = (0.0, -8.0)
CORNER = (-10.0, 9.0)  # where students wait
STUDENT_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
]


def scene_data(game: logic.Game) -> dict:
    """Positions and colors for the 3D scene, derived from the game state."""
    in_queue: dict[int, tuple[float, float]] = {}
    for shop_id, orders in game.queues.items():
        sx, sz = SHOP_POSITIONS[shop_id]
        for k, order in enumerate(orders):
            if order.student not in in_queue:
                in_queue[order.student] = (sx, sz + 3.2 + 1.1 * k)

    students = []
    for i in range(logic.CONFIG["student_count"]):
        if i in in_queue:
            x, z = in_queue[i]
        else:
            x = CORNER[0] + (i % 5) * 1.0
            z = CORNER[1] + (i // 5) * 1.2
        students.append({"x": x, "z": z, "color": STUDENT_COLORS[i % len(STUDENT_COLORS)]})

    shops = []
    for shop_id, (x, z) in SHOP_POSITIONS.items():
        shop = game.shops[shop_id]
        shops.append({
            "x": x, "z": z,
            "name": logic.CONFIG["shops"][shop_id]["name"],
            "owned": shop.owner == "player",
            "employee": shop.has_employee,
        })

    if game.phase == logic.SELLING and game.manual_shop:
        px, pz = SHOP_POSITIONS[game.manual_shop]
        player = {"x": px + 0.8, "z": pz - 0.3}
    else:
        player = {"x": WHOLESALER_POSITION[0], "z": WHOLESALER_POSITION[1] + 2.4}

    return {
        "shops": shops,
        "wholesaler": {"x": WHOLESALER_POSITION[0], "z": WHOLESALER_POSITION[1]},
        "students": students,
        "player": player,
    }


HTML_TEMPLATE = """
<div id="campus" style="width:100%;height:__HEIGHT__px;border-radius:12px;overflow:hidden;
     background:#bfe3ff;font-family:sans-serif;position:relative">
  <div id="campus-msg" style="position:absolute;top:45%;width:100%;text-align:center;color:#335">
    Loading 3D campus...</div>
</div>
<script type="importmap">
{"imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}}
</script>
<script type="module">
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const DATA = __DATA__;
const H = __HEIGHT__;
const el = document.getElementById("campus");
document.getElementById("campus-msg").remove();

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xbfe3ff);
scene.fog = new THREE.Fog(0xbfe3ff, 40, 90);
const camera = new THREE.PerspectiveCamera(45, el.clientWidth / H, 0.1, 200);
camera.position.set(0, 15, 22);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(el.clientWidth, H);
renderer.shadowMap.enabled = true;
el.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 1);
controls.autoRotate = true;
controls.autoRotateSpeed = 0.5;
controls.maxPolarAngle = Math.PI / 2.2;
controls.minDistance = 10;
controls.maxDistance = 45;

scene.add(new THREE.HemisphereLight(0xffffff, 0x447744, 1.0));
const sun = new THREE.DirectionalLight(0xffffff, 1.3);
sun.position.set(12, 22, 10);
sun.castShadow = true;
sun.shadow.camera.left = -25; sun.shadow.camera.right = 25;
sun.shadow.camera.top = 25; sun.shadow.camera.bottom = -25;
scene.add(sun);

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(400, 400),
  new THREE.MeshLambertMaterial({ color: 0x5fb34a })
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const mat = (c) => new THREE.MeshLambertMaterial({ color: c });

function label(text, bg) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 112;
  const g = c.getContext("2d");
  g.fillStyle = bg; g.beginPath();
  g.roundRect(4, 4, 504, 104, 28); g.fill();
  g.fillStyle = "#fff"; g.font = "bold 46px sans-serif";
  g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, 256, 58);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c) }));
  s.scale.set(6.4, 1.4, 1);
  return s;
}

function person(color, scale = 1) {
  const p = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.28 * scale, 0.6 * scale, 4, 8), mat(color));
  body.position.y = 0.6 * scale; body.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.24 * scale, 16, 12), mat(0xf1c27d));
  head.position.y = 1.25 * scale; head.castShadow = true;
  p.add(body, head);
  return p;
}

function stall(x, z, roofColor, name, labelBg) {
  const s = new THREE.Group();
  const wood = mat(0x9c6b3c), dark = mat(0x6e4826);
  const back = new THREE.Mesh(new THREE.BoxGeometry(4.2, 2.4, 0.25), wood);
  back.position.set(0, 1.2, -1.4);
  const left = new THREE.Mesh(new THREE.BoxGeometry(0.25, 2.4, 3), wood);
  left.position.set(-2, 1.2, 0);
  const right = left.clone(); right.position.x = 2;
  const counter = new THREE.Mesh(new THREE.BoxGeometry(4.2, 1.1, 0.6), dark);
  counter.position.set(0, 0.55, 1.3);
  for (const m of [back, left, right, counter]) { m.castShadow = true; m.receiveShadow = true; s.add(m); }
  for (const px of [-2, 2]) {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.2, 3.2, 0.2), dark);
    post.position.set(px, 1.6, 1.4); s.add(post);
  }
  const roof = new THREE.Mesh(new THREE.BoxGeometry(5, 0.25, 3.8), mat(roofColor));
  roof.position.set(0, 3.25, 0); roof.rotation.x = -0.18; roof.castShadow = true;
  s.add(roof);
  const tag = label(name, labelBg); tag.position.set(0, 4.7, 0); s.add(tag);
  s.position.set(x, 0, z);
  scene.add(s);
  return s;
}

for (const sh of DATA.shops) {
  stall(sh.x, sh.z, sh.owned ? 0x2e8b57 : 0xc0392b, sh.name, sh.owned ? "#2e8b57" : "#c0392b");
  if (sh.employee) {
    const e = person(0x34495e, 0.95); e.position.set(sh.x - 0.8, 0, sh.z - 0.3); scene.add(e);
  }
}
stall(DATA.wholesaler.x, DATA.wholesaler.z, 0x2c6fbb, "Wholesaler", "#2c6fbb");

const you = person(0xf5b400, 1.1);
you.position.set(DATA.player.x, 0, DATA.player.z);
scene.add(you);
const youTag = label("You", "#d49b00"); youTag.scale.set(2.8, 0.62, 1);
youTag.position.set(DATA.player.x, 2.5, DATA.player.z); scene.add(youTag);

const students = DATA.students.map((st) => {
  const p = person(st.color); p.position.set(st.x, 0, st.z); scene.add(p); return p;
});

// a few trees for the campus feeling
for (const [tx, tz] of [[-15, -12], [15, -12], [-16, 2], [16, 4], [12, 12], [-3, 14]]) {
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.3, 1.6), mat(0x7a5230));
  trunk.position.set(tx, 0.8, tz);
  const crown = new THREE.Mesh(new THREE.SphereGeometry(1.3, 12, 10), mat(0x2f7d32));
  crown.position.set(tx, 2.4, tz); crown.castShadow = true;
  scene.add(trunk, crown);
}

const clock = new THREE.Clock();
function animate() {
  const t = clock.getElapsedTime();
  students.forEach((p, i) => { p.position.y = Math.abs(Math.sin(t * 2.5 + i)) * 0.12; });
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();
window.addEventListener("resize", () => {
  camera.aspect = el.clientWidth / H;
  camera.updateProjectionMatrix();
  renderer.setSize(el.clientWidth, H);
});
</script>
"""


def campus_html(game: logic.Game, height: int = 420) -> str:
    return (
        HTML_TEMPLATE.replace("__DATA__", json.dumps(scene_data(game)))
        .replace("__HEIGHT__", str(height))
    )
