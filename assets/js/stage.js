// Ibom Space 3D stage.
// Every object here is drawn in code: there is no flight hardware yet, so the
// renders are concept visualisations, not photographs.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const TAU = Math.PI * 2;
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const smooth = (a, b, t) => { const x = clamp01((t - a) / (b - a)); return x * x * (3 - 2 * x); };

/* ------------------------------------------------------------------ textures */

function canvasTex(w, h, draw, { srgb = true, repeat } = {}) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
  return t;
}

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

// Crinkled multi-layer insulation: a height field of creases turned into a normal map.
function foilNormal(seed = 7) {
  const N = 256;
  const r = rng(seed);
  const h = new Float32Array(N * N);
  for (let k = 0; k < 70; k++) {
    const x0 = r() * N, y0 = r() * N, a = r() * Math.PI, len = 30 + r() * 120, amp = (r() - 0.5) * 2;
    const dx = Math.cos(a), dy = Math.sin(a);
    for (let s = -len; s < len; s += 0.5) {
      const px = Math.floor(x0 + dx * s + N) % N, py = Math.floor(y0 + dy * s + N) % N;
      for (let o = -3; o <= 3; o++) {
        const qx = (px + Math.round(-dy * o) + N) % N, qy = (py + Math.round(dx * o) + N) % N;
        h[qy * N + qx] += amp * (1 - Math.abs(o) / 4) * 0.25;
      }
    }
  }
  return canvasTex(N, N, (g) => {
    const img = g.createImageData(N, N);
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      const hx = h[y * N + (x + 1) % N] - h[y * N + (x - 1 + N) % N];
      const hy = h[((y + 1) % N) * N + x] - h[((y - 1 + N) % N) * N + x];
      const i = (y * N + x) * 4;
      img.data[i] = 128 + Math.max(-127, Math.min(127, hx * 90));
      img.data[i + 1] = 128 + Math.max(-127, Math.min(127, hy * 90));
      img.data[i + 2] = 255; img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
  }, { srgb: false, repeat: [2, 2] });
}

function solarTex() {
  return canvasTex(512, 512, (g, w, h) => {
    g.fillStyle = '#5d636e'; g.fillRect(0, 0, w, h);
    const cols = 8, rows = 8, gap = 5;
    const cw = (w - gap * (cols + 1)) / cols, ch = (h - gap * (rows + 1)) / rows;
    for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
      const x = gap + i * (cw + gap), y = gap + j * (ch + gap);
      g.fillStyle = (i + j) % 2 ? '#141b33' : '#18213d';
      g.fillRect(x, y, cw, ch);
      g.fillStyle = 'rgba(160,170,200,0.35)';
      for (let k = 1; k < 4; k++) g.fillRect(x, y + (ch * k) / 4, cw, 1);
      g.fillStyle = '#0b1022';
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + 6, y); g.lineTo(x, y + 6); g.fill();
    }
  });
}

function solarRough() {
  return canvasTex(512, 512, (g, w, h) => {
    g.fillStyle = '#9a9a9a'; g.fillRect(0, 0, w, h);
    const cols = 8, gap = 5, cw = (w - gap * 9) / cols;
    g.fillStyle = '#2a2a2a';
    for (let i = 0; i < cols; i++) for (let j = 0; j < cols; j++) g.fillRect(gap + i * (cw + gap), gap + j * (cw + gap), cw, cw);
  }, { srgb: false });
}

function panelTex(base, seams) {
  return canvasTex(256, 256, (g, w, h) => {
    g.fillStyle = base; g.fillRect(0, 0, w, h);
    g.strokeStyle = seams; g.lineWidth = 2;
    g.strokeRect(6, 6, w - 12, h - 12);
    g.fillStyle = seams;
    for (const [x, y] of [[14, 14], [w - 14, 14], [14, h - 14], [w - 14, h - 14]]) { g.beginPath(); g.arc(x, y, 3, 0, TAU); g.fill(); }
  });
}

/* ----------------------------------------------------------------- materials */

function makeMaterials() {
  const crinkle = foilNormal(11);
  const m = {
    gold: new THREE.MeshStandardMaterial({ color: 0xd8a640, metalness: 1, roughness: 0.32, normalMap: crinkle, normalScale: new THREE.Vector2(0.9, 0.9) }),
    silverFoil: new THREE.MeshStandardMaterial({ color: 0xaeb3ba, metalness: 1, roughness: 0.4, normalMap: crinkle, normalScale: new THREE.Vector2(0.7, 0.7) }),
    blackFoil: new THREE.MeshStandardMaterial({ color: 0x1d1f24, metalness: 0.7, roughness: 0.38, normalMap: crinkle, normalScale: new THREE.Vector2(0.6, 0.6) }),
    anod: new THREE.MeshStandardMaterial({ color: 0x3a3f47, metalness: 0.75, roughness: 0.42 }),
    anodDark: new THREE.MeshStandardMaterial({ color: 0x1b1e23, metalness: 0.6, roughness: 0.5 }),
    alu: new THREE.MeshStandardMaterial({ color: 0xb9bec6, metalness: 1, roughness: 0.3 }),
    white: new THREE.MeshStandardMaterial({ map: panelTex('#c9c6be', '#8f8c85'), metalness: 0, roughness: 0.7 }),
    copper: new THREE.MeshStandardMaterial({ color: 0xc27a45, metalness: 1, roughness: 0.3 }),
    black: new THREE.MeshStandardMaterial({ color: 0x08090b, metalness: 0.2, roughness: 0.6 }),
    glass: new THREE.MeshStandardMaterial({ color: 0x0a0d14, metalness: 1, roughness: 0.05 }),
    solar: new THREE.MeshStandardMaterial({ map: solarTex(), roughnessMap: solarRough(), metalness: 0.55, roughness: 1 }),
    solarBack: new THREE.MeshStandardMaterial({ color: 0x8d9097, metalness: 0.2, roughness: 0.6 }),
    channel: new THREE.MeshStandardMaterial({ color: 0x15121c, emissive: 0x9a7bff, emissiveIntensity: 0, roughness: 0.6 }),
    cathode: new THREE.MeshStandardMaterial({ color: 0x777b82, emissive: 0xd6c6ff, emissiveIntensity: 0, metalness: 0.8, roughness: 0.4 }),
    lens: new THREE.MeshStandardMaterial({ color: 0x0b1018, emissive: 0x6fd3ff, emissiveIntensity: 0, metalness: 1, roughness: 0.08 }),
    laserLens: new THREE.MeshStandardMaterial({ color: 0x0b1018, emissive: 0x9fe8ff, emissiveIntensity: 0.6, metalness: 1, roughness: 0.08 }),
  };
  return m;
}

const box = (w, h, d, mat) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
const cyl = (rt, rb, h, mat, seg = 32, open = false) => new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg, 1, open), mat);

/* -------------------------------------------------------------------- models */

function solarWing(M, panels, pw, ph, gap = 0.04) {
  const g = new THREE.Group();
  const yoke = cyl(0.025, 0.025, 0.55, M.alu, 8); yoke.rotation.x = Math.PI / 2; yoke.position.z = 0.275; g.add(yoke);
  for (let i = 0; i < panels; i++) {
    const p = new THREE.Group();
    const front = new THREE.Mesh(new THREE.PlaneGeometry(pw, ph), M.solar);
    front.rotation.x = -Math.PI / 2; front.position.y = 0.012;
    const back = box(pw, 0.02, ph, M.solarBack);
    const rear = new THREE.Mesh(new THREE.PlaneGeometry(pw, ph), M.solar);
    rear.rotation.x = Math.PI / 2; rear.position.y = -0.012; p.add(rear);
    const frame = box(pw + 0.03, 0.026, 0.025, M.alu);
    frame.position.z = ph / 2;
    p.add(front, back, frame);
    p.position.z = 0.55 + ph / 2 + i * (ph + gap);
    g.add(p);
  }
  return g;
}

function helix(M, radius, height, turns, mat) {
  const pts = [];
  for (let i = 0; i <= turns * 40; i++) {
    const a = (i / 40) * TAU;
    pts.push(V(Math.cos(a) * radius, (i / (turns * 40)) * height, Math.sin(a) * radius));
  }
  return new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), turns * 40, 0.012, 6), mat || M.copper);
}

// A customer satellite. Local +Y is its top deck; its launch ring is at local -Y.
function makeClient(M) {
  const g = new THREE.Group();
  const bus = new THREE.Group();
  const core = box(1.5, 1.8, 1.5, M.gold);
  bus.add(core);
  const top = box(1.52, 0.04, 1.52, M.silverFoil); top.position.y = 0.92; bus.add(top);
  const bottom = box(1.52, 0.05, 1.52, M.anod); bottom.position.y = -0.925; bus.add(bottom);
  const rad = box(0.02, 1.2, 1.0, M.white); rad.position.set(0.765, 0.1, 0); bus.add(rad);
  const rad2 = rad.clone(); rad2.position.x = -0.765; bus.add(rad2);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const edge = box(0.05, 1.86, 0.05, M.alu); edge.position.set(sx * 0.75, 0, sz * 0.75); bus.add(edge);
  }
  g.add(bus);
  // dish and star trackers
  const dish = new THREE.Mesh(new THREE.SphereGeometry(0.42, 32, 12, 0, TAU, 0, 0.9), M.white);
  dish.material = M.white.clone(); dish.material.side = THREE.DoubleSide;
  dish.rotation.x = Math.PI; dish.position.set(0.25, 1.48, 0.1);
  const mast = cyl(0.03, 0.03, 0.42, M.alu, 8); mast.position.set(0.25, 1.15, 0.1);
  g.add(dish, mast);
  const st = cyl(0.07, 0.09, 0.2, M.anodDark, 16); st.position.set(-0.5, 1.03, -0.45); st.rotation.z = 0.4; g.add(st);
  // launch adapter and ring (the part the tug grabs)
  const adapter = cyl(0.55, 0.68, 0.24, M.alu, 48); adapter.position.y = -1.07; g.add(adapter);
  const ringBand = cyl(0.72, 0.72, 0.09, M.alu, 64, true); ringBand.material = M.alu.clone(); ringBand.material.side = THREE.DoubleSide;
  ringBand.position.y = -1.22; g.add(ringBand);
  const lip = new THREE.Mesh(new THREE.TorusGeometry(0.725, 0.03, 10, 72), M.alu); lip.rotation.x = Math.PI / 2; lip.position.y = -1.265; g.add(lip);
  // wings along local Z
  const wl = solarWing(M, 3, 1.05, 1.0); wl.position.set(0, 0.2, 0.75); g.add(wl);
  const wr = solarWing(M, 3, 1.05, 1.0); wr.rotation.y = Math.PI; wr.position.set(0, 0.2, -0.75); g.add(wr);
  g.userData.ringY = -1.265;
  return g;
}

// The servicing tug. Local +Y is the capture face, -Y the Hartwigg engine.
function makeTug(M) {
  const g = new THREE.Group();
  const body = cyl(0.78, 0.78, 1.1, M.blackFoil, 8); body.rotation.y = Math.PI / 8; g.add(body);
  // white radiator faces and a silver band
  for (let i = 0; i < 8; i += 2) {
    const a = (i / 8) * TAU;
    const p = box(0.56, 0.82, 0.02, i % 4 === 0 ? M.white : M.silverFoil);
    p.position.set(Math.sin(a) * 0.725, 0, Math.cos(a) * 0.725); p.rotation.y = a; g.add(p);
  }
  const deck = cyl(0.84, 0.84, 0.06, M.anod, 48); deck.position.y = 0.58; g.add(deck);
  const aft = cyl(0.8, 0.8, 0.05, M.anod, 48); aft.position.y = -0.575; g.add(aft);

  // three clamp posts at 120 degrees, fingers swing inward to hook the ring lip
  const fingers = [];
  for (let k = 0; k < 3; k++) {
    const a = (k / 3) * TAU + Math.PI / 6;
    const arm = new THREE.Group(); arm.rotation.y = a; g.add(arm);
    const post = box(0.13, 0.62, 0.15, M.anod); post.position.set(0, 0.92, 0.86); arm.add(post);
    const base = box(0.26, 0.12, 0.26, M.anodDark); base.position.set(0, 0.64, 0.84); arm.add(base);
    const motor = cyl(0.06, 0.06, 0.16, M.alu, 16); motor.rotation.z = Math.PI / 2; motor.position.set(0, 0.74, 0.97); arm.add(motor);
    const pivot = new THREE.Group(); pivot.position.set(0, 1.22, 0.86); arm.add(pivot);
    const finger = box(0.11, 0.07, 0.26, M.alu); finger.position.set(0, 0.0, -0.1); pivot.add(finger);
    const tip = box(0.11, 0.1, 0.05, M.copper); tip.position.set(0, -0.05, -0.22); pivot.add(tip);
    fingers.push(pivot);
  }
  // Kodiak-style lidar on the capture face
  const lidar = new THREE.Group(); lidar.position.set(0.0, 0.75, -0.25); g.add(lidar);
  const lb = box(0.34, 0.24, 0.3, M.white); lidar.add(lb);
  const lens = cyl(0.085, 0.085, 0.06, M.lens, 24); lens.position.y = 0.14; lidar.add(lens);
  const cam = cyl(0.05, 0.05, 0.05, M.glass, 16); cam.position.set(0.25, 0.68, 0.32); g.add(cam);
  // cold-gas pods
  const pods = [];
  for (let k = 0; k < 4; k++) {
    const a = (k / 4) * TAU + Math.PI / 4;
    const pod = new THREE.Group(); pod.position.set(Math.sin(a) * 0.82, 0.15, Math.cos(a) * 0.82); pod.rotation.y = a; g.add(pod);
    pod.add(box(0.16, 0.2, 0.12, M.anodDark));
    for (const [dx, dy, rx, rz] of [[0, 0.13, 0, 0], [0, -0.13, Math.PI, 0], [0.11, 0, 0, -Math.PI / 2]]) {
      const n = cyl(0.015, 0.035, 0.06, M.alu, 10); n.position.set(dx, dy, 0); n.rotation.set(rx, 0, rz); pod.add(n);
    }
    pods.push(pod);
  }
  // iodine tank with heater lines on one side
  const tank = cyl(0.17, 0.17, 0.62, M.alu, 24); tank.position.set(0.0, -0.05, 0.93); g.add(tank);
  for (let i = 0; i < 5; i++) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.175, 0.008, 6, 32), M.copper); r.rotation.x = Math.PI / 2; r.position.set(0, -0.3 + i * 0.12, 0.93); g.add(r); }
  // helical antenna and X-band patch
  const hx = helix(M, 0.05, 0.36, 7); hx.position.set(-0.55, 0.61, 0.25); g.add(hx);
  const patch = box(0.2, 0.2, 0.02, M.copper); patch.position.set(0, 0.05, -0.74); g.add(patch);
  // wings along local Z
  const wl = solarWing(M, 2, 0.8, 0.85); wl.position.set(0, -0.1, 0.6); wl.rotation.z = 0; g.add(wl);
  const wr = solarWing(M, 2, 0.8, 0.85); wr.rotation.y = Math.PI; wr.position.set(0, -0.1, -0.6); g.add(wr);
  wl.children[0].scale.y = 0.6; wr.children[0].scale.y = 0.6;

  // gimballed Hartwigg engine
  const gimbal = new THREE.Group(); gimbal.position.y = -0.62; g.add(gimbal);
  const gring = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.035, 12, 48), M.alu); gring.rotation.x = Math.PI / 2; gimbal.add(gring);
  const engine = makeThruster(M); engine.rotation.x = Math.PI; engine.position.y = -0.05; gimbal.add(engine);

  g.userData = { fingers, pods, gimbal, lidar, captureY: 1.21, nozzleY: -0.98 };
  return g;
}

// Hartwigg Hall thruster: magnet poles around an annular discharge channel.
function makeThruster(M, scale = 1) {
  const g = new THREE.Group();
  const housing = cyl(0.24, 0.26, 0.3, M.anod, 48); housing.position.y = 0.15; g.add(housing);
  const face = cyl(0.245, 0.245, 0.03, M.alu, 48); face.position.y = 0.31; g.add(face);
  const chan = new THREE.Mesh(new THREE.RingGeometry(0.095, 0.17, 64), M.channel); chan.rotation.x = -Math.PI / 2; chan.position.y = 0.327; g.add(chan);
  const pole = cyl(0.09, 0.09, 0.04, M.anodDark, 32); pole.position.y = 0.33; g.add(pole);
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * TAU;
    const coil = cyl(0.03, 0.03, 0.26, M.copper, 12); coil.position.set(Math.cos(a) * 0.26, 0.15, Math.sin(a) * 0.26); g.add(coil);
  }
  const cath = cyl(0.025, 0.025, 0.22, M.cathode, 12); cath.position.set(0.3, 0.3, 0); cath.rotation.z = -0.35; g.add(cath);
  g.scale.setScalar(scale);
  g.userData.exitY = 0.33;
  return g;
}

// A standalone Hartwigg kit: thruster on its gimbal, PPU, iodine tank and feed.
function makeHartwiggKit(M) {
  const g = new THREE.Group();
  const plate = box(1.5, 0.05, 1.1, M.anod); g.add(plate);
  const gimbalBase = cyl(0.3, 0.34, 0.08, M.anodDark, 48); gimbalBase.position.set(-0.25, 0.065, 0); g.add(gimbalBase);
  const gring = new THREE.Mesh(new THREE.TorusGeometry(0.3, 0.035, 12, 48), M.alu); gring.rotation.x = Math.PI / 2; gring.position.set(-0.25, 0.14, 0); g.add(gring);
  const gimbal = new THREE.Group(); gimbal.position.set(-0.25, 0.14, 0); g.add(gimbal);
  const thr = makeThruster(M, 1.15); gimbal.add(thr);
  const ppu = box(0.42, 0.18, 0.5, M.anodDark); ppu.position.set(0.45, 0.115, -0.22); g.add(ppu);
  for (let i = 0; i < 9; i++) { const fin = box(0.42, 0.06, 0.012, M.alu); fin.position.set(0.45, 0.235, -0.44 + i * 0.055); g.add(fin); }
  const conn = cyl(0.03, 0.03, 0.06, M.copper, 12); conn.rotation.z = Math.PI / 2; conn.position.set(0.68, 0.11, -0.12); g.add(conn);
  const tank = cyl(0.16, 0.16, 0.5, M.alu, 32); tank.rotation.x = Math.PI / 2; tank.position.set(0.45, 0.2, 0.3); g.add(tank);
  for (const z of [0.05, 0.55]) { const cap = new THREE.Mesh(new THREE.SphereGeometry(0.16, 24, 12, 0, TAU, 0, Math.PI / 2), M.alu); cap.rotation.x = z < 0.3 ? -Math.PI / 2 : Math.PI / 2; cap.position.set(0.45, 0.2, z); g.add(cap); }
  for (let i = 0; i < 6; i++) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.163, 0.007, 6, 32), M.copper); r.position.set(0.45, 0.2, 0.1 + i * 0.08); g.add(r); }
  const feed = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([V(0.3, 0.2, 0.3), V(0.05, 0.2, 0.3), V(-0.1, 0.18, 0.2), V(-0.18, 0.16, 0.12)]), 32, 0.014, 8), M.copper); g.add(feed);
  const valve = box(0.08, 0.08, 0.08, M.anodDark); valve.position.set(0.05, 0.2, 0.3); g.add(valve);
  g.userData = { gimbal, exitY: 0.33 * 1.15 };
  return g;
}

// The Caelum showcase spacecraft: Hartwigg and Caelum flying together on a bought bus.
function makeCaelum(M) {
  const g = new THREE.Group();
  const core = box(1.7, 2.1, 1.7, M.blackFoil); g.add(core);
  const top = box(1.72, 0.05, 1.72, M.silverFoil); top.position.y = 1.07; g.add(top);
  const band = box(1.73, 0.5, 1.73, M.gold); band.position.y = -0.6; g.add(band);
  const rad = box(0.02, 1.0, 1.2, M.white); rad.position.set(0.86, 0.35, 0); g.add(rad);
  const rad2 = rad.clone(); rad2.position.x = -0.86; g.add(rad2);
  // gimbal-free laser head on the earth face
  const lh = new THREE.Group(); lh.position.set(0.45, -1.05, 0.35); g.add(lh);
  const tube = cyl(0.16, 0.16, 0.34, M.white, 32); tube.position.y = -0.17; lh.add(tube);
  const ring = cyl(0.17, 0.17, 0.04, M.alu, 32); ring.position.y = -0.34; lh.add(ring);
  const lens = cyl(0.13, 0.13, 0.02, M.laserLens, 32); lens.position.y = -0.355; lh.add(lens);
  // multi-band radio dish and deployable helical antennas
  const dish = new THREE.Mesh(new THREE.SphereGeometry(0.55, 40, 12, 0, TAU, 0, 0.85), M.white.clone());
  dish.material.side = THREE.DoubleSide; dish.position.set(-0.35, -1.75, -0.25);
  const mast = cyl(0.035, 0.035, 0.6, M.alu, 8); mast.position.set(-0.35, -1.3, -0.25);
  g.add(dish, mast);
  const feed = cyl(0.03, 0.05, 0.12, M.copper, 12); feed.position.set(-0.35, -1.75, -0.25); g.add(feed);
  for (const [x, z] of [[0.6, -0.6], [-0.6, 0.6]]) { const h = helix(M, 0.07, 0.9, 11); h.position.set(x, 1.1, z); g.add(h); }
  // wings
  const wl = solarWing(M, 4, 1.15, 1.15); wl.position.set(0, 0.35, 0.85); wl.rotation.z = 1.2; g.add(wl);
  const wr = solarWing(M, 4, 1.15, 1.15); wr.rotation.set(0, Math.PI, 1.2); wr.position.set(0, 0.35, -0.85); g.add(wr);
  // Hartwigg on the back face
  const thr = makeThruster(M); thr.rotation.z = Math.PI / 2; thr.position.set(-0.85, -0.1, 0); g.add(thr);
  g.userData = { laserHead: lh };
  return g;
}

/* ------------------------------------------------------------------- effects */

const plumeVert = /* glsl */`
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position,1.0);
    vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }`;
const plumeFrag = /* glsl */`
  uniform float uI; uniform float uT; uniform float uK; uniform vec3 uCore; uniform vec3 uEdge;
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main(){
    float along = 1.0 - vUv.y;                         // 0 at the exit, 1 at the far end
    float facing = abs(dot(vN, vV));
    float body = pow(facing, 1.6);
    float fall = exp(-along * 3.2);
    float flick = 0.92 + 0.08 * sin(uT * 37.0 + along * 30.0) * sin(uT * 23.0 - vUv.x * 40.0);
    vec3 col = mix(uEdge, uCore, exp(-along * 5.0) * body);
    float a = body * fall * uI * flick * smoothstep(0.0, 0.06, along) * uK;
    gl_FragColor = vec4(col * a * 1.6, a);
  }`;

function makePlume(len, r0, r1, core = 0xe8e0ff, edge = 0x7a5cff) {
  const geo = new THREE.CylinderGeometry(r1, r0, len, 48, 24, true);
  geo.translate(0, -len / 2, 0);
  const mat = new THREE.ShaderMaterial({
    uniforms: { uI: { value: 0 }, uT: { value: 0 }, uK: { value: 0.8 }, uCore: { value: new THREE.Color(core) }, uEdge: { value: new THREE.Color(edge) } },
    vertexShader: plumeVert, fragmentShader: plumeFrag,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  const g = new THREE.Group();
  const outer = new THREE.Mesh(geo, mat);
  const inner = new THREE.Mesh(new THREE.CylinderGeometry(r1 * 0.35, r0 * 0.75, len * 0.6, 32, 12, true).translate(0, -len * 0.3, 0), mat.clone());
  inner.material.uniforms.uK.value = 1.0;
  inner.material.uniforms.uCore.value = new THREE.Color(0xffffff);
  inner.material.uniforms.uEdge.value = new THREE.Color(0xb7a4ff);
  g.add(outer, inner);
  g.userData.set = (i, t) => { for (const m of [outer.material, inner.material]) { m.uniforms.uI.value = i; m.uniforms.uT.value = t; } };
  return g;
}

function makeBeam(len, r, color) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uI: { value: 0 }, uT: { value: 0 }, uC: { value: new THREE.Color(color) } },
    vertexShader: plumeVert,
    fragmentShader: /* glsl */`
      uniform float uI; uniform float uT; uniform vec3 uC; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){ float f = pow(abs(dot(vN,vV)), 2.0); float a = f * uI * (0.75 + 0.25*sin(vUv.y*80.0 - uT*30.0)); gl_FragColor = vec4(uC * a * 1.5, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 16, 1, true).translate(0, -len / 2, 0), mat);
  m.userData.set = (i, t) => { mat.uniforms.uI.value = i; mat.uniforms.uT.value = t; };
  return m;
}

// Lidar sweep: a faint cone with bands that travel toward the target.
function makeLidar() {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uI: { value: 0 }, uT: { value: 0 } },
    vertexShader: plumeVert,
    fragmentShader: /* glsl */`
      uniform float uI; uniform float uT; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){
        float along = 1.0 - vUv.y;
        float band = smoothstep(0.92, 1.0, fract(along * 6.0 - uT * 1.4));
        float f = pow(1.0 - abs(dot(vN,vV)), 1.5);
        float a = (0.05 + 0.12 * band) * uI * (0.3 + f);
        gl_FragColor = vec4(vec3(0.62,0.92,1.0) * a, a);
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  const geo = new THREE.CylinderGeometry(1, 0.02, 1, 32, 1, true).translate(0, 0.5, 0);
  const m = new THREE.Mesh(geo, mat);
  m.userData.set = (i, t) => { mat.uniforms.uI.value = i; mat.uniforms.uT.value = t; };
  return m;
}

// Cold-gas puffs: short-lived sprites from the pod nozzles.
function makePuffs(count = 90) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  geo.setAttribute('alpha', new THREE.BufferAttribute(new Float32Array(count), 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uSize: { value: 70 } },
    vertexShader: /* glsl */`attribute float alpha; varying float vA; uniform float uSize;
      void main(){ vA = alpha; vec4 mv = modelViewMatrix * vec4(position,1.0); gl_PointSize = uSize * (0.4 + (1.0-alpha)) / -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: /* glsl */`varying float vA; void main(){ float d = length(gl_PointCoord-0.5); float a = smoothstep(0.5,0.0,d) * vA * 0.55; gl_FragColor = vec4(vec3(0.85,0.9,1.0)*a, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  return pts;
}

function makeStars(n = 2600) {
  const r = rng(3);
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const u = r() * 2 - 1, a = r() * TAU, s = Math.sqrt(1 - u * u);
    const d = 400;
    pos.set([Math.cos(a) * s * d, u * d, Math.sin(a) * s * d], i * 3);
    const b = 0.35 + Math.pow(r(), 6) * 1.4;
    const warm = r();
    col.set([b * (0.9 + warm * 0.1), b * 0.95, b * (1.0 - warm * 0.12)], i * 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return new THREE.Points(geo, new THREE.PointsMaterial({ size: 1.3, sizeAttenuation: false, vertexColors: true, depthWrite: false }));
}

function makeEarth(loader, urls, sunDir) {
  const R = 70;
  const g = new THREE.Group();
  const day = loader.load(urls.day); day.colorSpace = THREE.SRGBColorSpace; day.anisotropy = 8;
  const mat = new THREE.MeshStandardMaterial({ map: day, roughness: 0.9, metalness: 0, color: 0xb8c2d0 });
  // ocean glint and a soft terminator, done in the standard material through onBeforeCompile
  mat.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
      float ocean = smoothstep(0.08, 0.02, diffuseColor.r - diffuseColor.b * 0.6);
      diffuseColor.rgb *= mix(1.0, 0.85, ocean);`);
  };
  const earth = new THREE.Mesh(new THREE.SphereGeometry(R, 128, 96), mat);
  g.add(earth);
  const clouds = loader.load(urls.clouds);
  const cmat = new THREE.MeshStandardMaterial({ alphaMap: clouds, color: 0xffffff, transparent: true, opacity: 0.45, depthWrite: false, roughness: 1 });
  const cl = new THREE.Mesh(new THREE.SphereGeometry(R * 1.006, 128, 96), cmat);
  g.add(cl);
  const atm = new THREE.Mesh(new THREE.SphereGeometry(R * 1.045, 96, 64), new THREE.ShaderMaterial({
    uniforms: { uSun: { value: sunDir } },
    vertexShader: /* glsl */`varying vec3 vN; varying vec3 vW; void main(){ vN = normalize(mat3(modelMatrix)*normal); vec4 w = modelMatrix*vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: /* glsl */`uniform vec3 uSun; varying vec3 vN; varying vec3 vW;
      void main(){ vec3 v = normalize(cameraPosition - vW); float rim = pow(1.0 - abs(dot(vN, v)), 3.0);
        float lit = smoothstep(-0.25, 0.4, dot(vN, uSun));
        vec3 c = mix(vec3(0.18,0.42,1.0), vec3(0.55,0.78,1.0), rim);
        float a = rim * lit * 1.25; gl_FragColor = vec4(c * a, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.BackSide,
  }));
  g.add(atm);
  const haze = new THREE.Mesh(new THREE.SphereGeometry(R * 1.008, 96, 64), new THREE.ShaderMaterial({
    uniforms: { uSun: { value: sunDir } },
    vertexShader: atm.material.vertexShader,
    fragmentShader: /* glsl */`uniform vec3 uSun; varying vec3 vN; varying vec3 vW;
      void main(){ vec3 v = normalize(cameraPosition - vW); float rim = pow(1.0 - abs(dot(vN, v)), 2.2);
        float lit = smoothstep(-0.2, 0.5, dot(vN, uSun)); float a = rim * lit * 0.9;
        gl_FragColor = vec4(vec3(0.35,0.6,1.0) * a, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  g.add(haze);
  g.userData = { earth, clouds: cl, R };
  return g;
}

/* --------------------------------------------------------------------- shots */
// Each shot returns the full state of the scene at local time t (seconds).
// The client sits at the origin with its ring facing -X; the tug approaches along +X.

const DOCK = -2.5; // tug centre X when docked (client ring at -1.265, tug capture face at +1.21)
const qFromEuler = (x, y, z) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z));
const TUG_Q = qFromEuler(0, 0, -Math.PI / 2);
const CLIENT_Q = qFromEuler(0, 0, -Math.PI / 2);

function orbitCam(target, radius, az, el) {
  return V(target.x + radius * Math.cos(el) * Math.sin(az), target.y + radius * Math.sin(el), target.z + radius * Math.cos(el) * Math.cos(az));
}

const SHOTS = {
  hero: (t) => {
    const tg = V(-1.2, 0.1, 0);
    return {
      cam: orbitCam(tg, 14, -0.62 + Math.sin(t * 0.05) * 0.12, 0.1 + Math.sin(t * 0.037) * 0.03), target: tg, fov: 34,
      tug: V(-4.4 + Math.sin(t * 0.2) * 0.04, 0.0, 0.0), tugQ: TUG_Q.clone().multiply(qFromEuler(0, t * 0.04, 0)),
      client: V(0, 0, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(0, 0.3 + t * 0.02, 0)),
      clamp: 0, plume: 0, lidar: 0, puffs: 0.35, gimbal: 0, earthSpin: t * 0.004,
    };
  },
  find: (t) => {
    const tg = V(-3.2, 0.2, 0);
    return {
      cam: V(-14.2 + Math.sin(t * 0.08) * 0.3, 1.9, 3.6 + t * 0.02), target: tg, fov: 34,
      tug: V(-9.5, 0.4, 0.6), tugQ: TUG_Q.clone().multiply(qFromEuler(0.06, 0, 0)),
      client: V(0, 0, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(0, 0.3, 0)),
      clamp: 0, plume: 0, lidar: 1, puffs: 0, gimbal: 0, earthSpin: t * 0.004,
    };
  },
  inspect: (t) => {
    const tg = V(-2.2, 0, 0);
    return {
      cam: orbitCam(tg, 9, 0.35 + t * 0.015, 0.22), target: tg, fov: 36,
      tug: V(-5.2, 0, 0), tugQ: TUG_Q.clone(),
      client: V(0, 0, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(0, 0.3 + t * 0.01, 0)),
      clamp: 0, plume: 0, lidar: 0.9, puffs: 1, gimbal: 0, earthSpin: t * 0.004,
    };
  },
  capture: (t) => {
    const tg = V(-1.6, 0, 0);
    const k = smooth(0.6, 3.2, t);
    return {
      cam: orbitCam(tg, 8.2, 0.3 + t * 0.01, 0.3), target: tg, fov: 36,
      tug: V(DOCK - 0.6 * (1 - smooth(0, 2.2, t)), 0, 0), tugQ: TUG_Q.clone(),
      client: V(0, 0, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(0, 0.3, 0)),
      clamp: k, plume: 0, lidar: 0.25 * (1 - k), puffs: 1 - k, gimbal: 0, earthSpin: t * 0.004,
    };
  },
  push: (t) => {
    const tg = V(-1.5, 0, 0);
    return {
      cam: orbitCam(tg, 11.5, -0.42 + t * 0.012, 0.14), target: tg, fov: 34,
      tug: V(DOCK, 0, 0), tugQ: TUG_Q.clone(),
      client: V(0, 0, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(0, 0.3, 0)),
      clamp: 1, plume: 1, lidar: 0, puffs: 0, gimbal: Math.sin(t * 0.6) * 0.12, earthSpin: t * 0.02,
    };
  },
  release: (t) => {
    const tg = V(-2.5, -0.4, 0);
    const k = smooth(0, 6, t);
    return {
      cam: orbitCam(tg, 9.5, -0.9 + t * 0.01, 0.2), target: tg, fov: 36,
      tug: V(DOCK - 0.4 - k * 2.6, 0.2 + k * 0.6, 0), tugQ: TUG_Q.clone(),
      client: V(k * 0.6, -k * 1.4, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(k * 0.25, 0.3 + k * 0.4, k * 0.2)),
      clamp: 1 - smooth(0, 0.8, t), plume: 0, lidar: 0, puffs: 1 - smooth(1.5, 4, t), gimbal: 0, earthSpin: t * 0.004,
    };
  },
  next: (t) => {
    const tg = V(-5, 0.6, 0);
    return {
      cam: orbitCam(tg, 11, -2.6 + t * 0.012, 0.18), target: tg, fov: 34,
      tug: V(-6.2, 0.9, 0), tugQ: TUG_Q.clone().multiply(qFromEuler(0, 0, Math.PI)),
      client: V(1.2, -4.5, 0), clientQ: CLIENT_Q.clone().multiply(qFromEuler(0.3, 0.9, 0.3)),
      clamp: 0, plume: 1, lidar: 0, puffs: 0, gimbal: 0, earthSpin: t * 0.004,
    };
  },
};

/* --------------------------------------------------------------------- stage */

export function createStage(canvas, opts = {}) {
  const film = !!opts.film;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: film });
  renderer.setPixelRatio(film ? 1 : Math.min(window.devicePixelRatio || 1, opts.maxDpr || 1.75));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020306);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(36, 1, 0.05, 1200);
  const sunDir = V(-0.55, 0.42, 0.72).normalize();
  const sun = new THREE.DirectionalLight(0xfff4e6, 2.6); sun.position.copy(sunDir).multiplyScalar(50); scene.add(sun);
  const fill = new THREE.DirectionalLight(0x6f8cff, 0.35); fill.position.set(2, -3, -4); scene.add(fill);
  scene.add(new THREE.HemisphereLight(0x8aa6ff, 0x0b0f18, 0.18));

  const M = makeMaterials();
  const stars = makeStars(); scene.add(stars);
  const manager = new THREE.LoadingManager();
  const ready = new Promise((res) => { manager.onLoad = res; manager.onError = res; });
  const loader = new THREE.TextureLoader(manager);
  const earthG = makeEarth(loader, { day: opts.earthDay || 'assets/img/earth_day.jpg', clouds: opts.earthClouds || 'assets/img/earth_clouds.jpg' }, sunDir);
  earthG.position.set(4, -80.5, -40);
  earthG.rotation.set(0.35, 0, 0.18);
  scene.add(earthG);

  const tug = makeTug(M); scene.add(tug);
  const client = makeClient(M); scene.add(client);
  const plume = makePlume(6, 0.17, 0.95); tug.userData.gimbal.add(plume); plume.position.y = -0.38;
  const lidar = makeLidar(); scene.add(lidar);
  const puffs = makePuffs(); scene.add(puffs);
  const puffState = Array.from({ length: 90 }, () => ({ life: 0, p: V(0, 0, 0), v: V(0, 0, 0) }));

  // product-only objects for the film shots
  const kit = makeHartwiggKit(M); kit.visible = false; scene.add(kit);
  const kitPlume = makePlume(5, 0.2, 0.75); kit.userData.gimbal.add(kitPlume); kitPlume.rotation.x = Math.PI; kitPlume.position.y = 0.38;
  const caelum = makeCaelum(M); caelum.visible = false; scene.add(caelum);
  const beam = makeBeam(60, 0.035, 0x9fe8ff); caelum.userData.laserHead.add(beam); beam.position.y = -0.36;
  const caelumPlume = makePlume(6, 0.17, 1.4); caelum.add(caelumPlume); caelumPlume.rotation.z = -Math.PI / 2; caelumPlume.position.set(-1.2, -0.1, 0);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.6, 0.45, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  let shotName = opts.shot || 'hero';
  let shotStart = 0;
  let from = null, blendStart = 0;
  const BLEND = opts.blend ?? 1.8;
  let clock = 0;
  let viewShift = 0, viewShiftTarget = 0, viewShiftY = 0, viewShiftYTarget = 0;
  let frameHook = null;

  function capture() {
    return {
      cam: camera.position.clone(), target: lastTarget.clone(), fov: camera.fov,
      tug: tug.position.clone(), tugQ: tug.quaternion.clone(), client: client.position.clone(), clientQ: client.quaternion.clone(),
      clamp: lastState.clamp, plume: lastState.plume, lidar: lastState.lidar, puffs: lastState.puffs, gimbal: lastState.gimbal, earthSpin: lastState.earthSpin,
    };
  }
  let lastTarget = V(0, 0, 0);
  let lastState = SHOTS.hero(0);

  function mix(a, b, k) {
    const o = {};
    for (const key of Object.keys(b)) {
      const va = a[key], vb = b[key];
      if (vb && vb.isVector3) o[key] = va.clone().lerp(vb, k);
      else if (vb && vb.isQuaternion) o[key] = va.clone().slerp(vb, k);
      else o[key] = va + (vb - va) * k;
    }
    return o;
  }

  function stateAt(time) {
    const fn = SHOTS[shotName] || SHOTS.hero;
    let s = fn(time - shotStart);
    if (from) {
      const k = clamp01((time - blendStart) / BLEND);
      if (k >= 1) from = null; else s = mix(from, s, ease(k));
    }
    return s;
  }

  function apply(s, time, dt) {
    camera.position.copy(s.cam); camera.lookAt(s.target); lastTarget = s.target.clone();
    // Portrait screens see the same scene with a wider lens, so the subject still fits.
    const fov = camera.aspect < 1.25 ? 2 * Math.atan(Math.tan((s.fov * Math.PI) / 360) * Math.min(2.6, 1.25 / camera.aspect)) * 180 / Math.PI : s.fov;
    if (Math.abs(camera.fov - fov) > 1e-3) { camera.fov = fov; camera.updateProjectionMatrix(); }
    tug.position.copy(s.tug); tug.quaternion.copy(s.tugQ);
    client.position.copy(s.client); client.quaternion.copy(s.clientQ);
    for (const f of tug.userData.fingers) f.rotation.x = -0.9 * (1 - s.clamp) + 0.0;
    tug.userData.gimbal.rotation.x = s.gimbal; tug.userData.gimbal.rotation.z = s.gimbal * 0.5;
    plume.userData.set(s.plume, time);
    M.channel.emissiveIntensity = 0.4 + s.plume * 5;
    M.cathode.emissiveIntensity = s.plume * 2;
    M.lens.emissiveIntensity = s.lidar * 1.2;
    earthG.userData.earth.rotation.y = s.earthSpin; earthG.userData.clouds.rotation.y = s.earthSpin * 1.15 + 0.4;
    // lidar cone from the tug's lens to the client
    const lp = tug.userData.lidar.getWorldPosition(V(0, 0, 0));
    const cp = client.position.clone();
    const d = cp.clone().sub(lp); const L = d.length();
    lidar.position.copy(lp); lidar.quaternion.setFromUnitVectors(V(0, 1, 0), d.normalize());
    lidar.scale.set(Math.min(1.5, 0.12 * L + 0.4), L, Math.min(1.5, 0.12 * L + 0.4));
    lidar.userData.set(s.lidar * 0.9, time);
    lidar.visible = s.lidar > 0.01;
    // cold-gas puffs
    const pos = puffs.geometry.attributes.position, al = puffs.geometry.attributes.alpha;
    const pods = tug.userData.pods;
    puffState.forEach((p, i) => {
      if (p.life <= 0 && s.puffs > 0.05 && ((i * 7919 + Math.floor(time * 30)) % 23) === 0) {
        const pod = pods[i % 4]; const w = pod.getWorldPosition(V(0, 0, 0));
        const dir = [V(0, 1, 0), V(0, -1, 0), V(1, 0, 0)][i % 3].applyQuaternion(pod.getWorldQuaternion(new THREE.Quaternion()));
        p.p.copy(w).addScaledVector(dir, 0.15); p.v.copy(dir).multiplyScalar(1.4 + (i % 5) * 0.2); p.life = 0.6 * s.puffs;
      }
      if (p.life > 0) { p.life -= dt; p.p.addScaledVector(p.v, dt); }
      pos.setXYZ(i, p.p.x, p.p.y, p.p.z); al.setX(i, Math.max(0, p.life / 0.6));
    });
    pos.needsUpdate = true; al.needsUpdate = true;
    lastState = s;
  }

  function resize(w, h) {
    w = w || canvas.clientWidth; h = h || canvas.clientHeight;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    bloom.resolution.set(w / 2, h / 2);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    applyShift();
  }
  function applyShift() {
    const w = renderer.domElement.width, h = renderer.domElement.height;
    if (Math.abs(viewShift) < 1e-4 && Math.abs(viewShiftY) < 1e-4) camera.clearViewOffset();
    else camera.setViewOffset(w, h, -viewShift * w, viewShiftY * h, w, h);
  }

  let last = performance.now() / 1000;
  function frame(nowSec) {
    const dt = Math.min(0.25, nowSec - last); last = nowSec; clock += dt;
    viewShift += (viewShiftTarget - viewShift) * Math.min(1, dt * 3);
    viewShiftY += (viewShiftYTarget - viewShiftY) * Math.min(1, dt * 3);
    applyShift();
    const s = stateAt(clock);
    apply(s, clock, dt);
    if (frameHook) frameHook(clock);
    composer.render();
  }

  let running = false, raf = 0;
  function loop() { if (!running) return; frame(performance.now() / 1000); raf = requestAnimationFrame(loop); }

  return {
    renderer, camera, scene, ready,
    resize,
    setShot(name, { instant = false } = {}) {
      if (!SHOTS[name] || name === shotName) return;
      if (!instant) { from = capture(); blendStart = clock; } else from = null;
      shotName = name; shotStart = clock;
    },
    // Shift the subject left (-) or right (+) of centre, as a fraction of the width.
    setShift(x, y = 0, instant = false) { viewShiftTarget = x; viewShiftYTarget = y; if (instant) { viewShift = x; viewShiftY = y; applyShift(); } },
    start() { if (running) return; running = true; last = performance.now() / 1000; loop(); },
    stop() { running = false; cancelAnimationFrame(raf); },
    renderOnce() { frame(last + 1 / 60); },
    // Film mode: render the product shots deterministically, frame by frame.
    filmFrame(name, t) {
      const dt = 1 / 30;
      tug.visible = client.visible = lidar.visible = puffs.visible = false;
      kit.visible = caelum.visible = false;
      if (name === 'hartwigg') {
        kit.visible = true;
        const tg = V(0.05, 0.55, 0);
        const az = 0.7 + Math.sin((t / 10) * TAU) * 0.18;
        camera.position.copy(orbitCam(tg, 3.4, az, 0.22)); camera.lookAt(tg);
        camera.fov = 34; camera.updateProjectionMatrix();
        kit.rotation.set(0, 0.5, 0);
        kit.position.set(0, 0, 0);
        kit.userData.gimbal.rotation.x = Math.sin((t / 10) * TAU) * 0.12;
        kitPlume.userData.set(0.75, t);
        M.channel.emissiveIntensity = 5; M.cathode.emissiveIntensity = 2;
        earthG.userData.earth.rotation.y = 1.2;
      } else if (name === 'caelum') {
        caelum.visible = true;
        const tg = V(0, -0.3, 0);
        const az = -0.45 + Math.sin((t / 12) * TAU) * 0.12;
        camera.position.copy(orbitCam(tg, 10.5, az, 0.05)); camera.lookAt(tg);
        camera.fov = 36; camera.updateProjectionMatrix();
        caelum.position.set(0, 0, 0); caelum.rotation.set(0.1, Math.PI / 2 + 0.25, -0.08);
        beam.userData.set(1, t);
        caelumPlume.userData.set(0.85, t);
        M.channel.emissiveIntensity = 4;
        earthG.userData.earth.rotation.y = 2.1 + Math.sin((t / 12) * TAU) * 0.01;
      } else {
        tug.visible = client.visible = puffs.visible = true;
        shotName = name; shotStart = 0; from = null;
        apply(SHOTS[name](t), t, dt);
      }
      composer.render();
    },
    onFrame(fn) { frameHook = fn; },
    get shot() { return shotName; },
  };
}

export const SHOT_NAMES = Object.keys(SHOTS);
