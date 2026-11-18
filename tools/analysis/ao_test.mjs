// Synthetic scenes with known answers for tools/analysis/ao_ref.mjs.
//   node tools/analysis/ao_test.mjs
import { aoCore } from "./ao_ref.mjs";

const cam = { fovY: (60 * Math.PI) / 180, width: 160, height: 90 };
const tanHalf = Math.tan(cam.fovY / 2), aspect = cam.width / cam.height;
const ray = (x, y) => [
  ((x + 0.5) / cam.width * 2 - 1) * tanHalf * aspect,
  (1 - (y + 0.5) / cam.height * 2) * tanHalf,
  1,
];

// Build a scene from a list of planes / spheres by ray-casting every pixel.
function makeScene(prims) {
  const depth = new Float32Array(cam.width * cam.height).fill(Infinity);
  const normal = new Array(cam.width * cam.height);
  for (let y = 0; y < cam.height; y++) {
    for (let x = 0; x < cam.width; x++) {
      const r = ray(x, y);
      let best = Infinity, bn = null;
      for (const p of prims) {
        const h = p.hit(r);
        if (h && h.t < best) { best = h.t; bn = h.n; }
      }
      if (isFinite(best)) { depth[y * cam.width + x] = best; normal[y * cam.width + x] = bn; }
    }
  }
  return {
    depthAt: (x, y) => depth[y * cam.width + x],
    normalAt: (x, y) => normal[y * cam.width + x],
  };
}

// plane: n . p = d ; ray origin 0, direction r (r.z = 1 so t == view depth)
const plane = (n, d, accept = () => true) => ({
  hit(r) {
    const den = n[0] * r[0] + n[1] * r[1] + n[2] * r[2];
    if (Math.abs(den) < 1e-6) return null;
    const t = d / den;
    if (t <= 0) return null;
    const p = [r[0] * t, r[1] * t, r[2] * t];
    if (!accept(p)) return null;
    // face the camera
    const s = den > 0 ? -1 : 1;
    return { t, n: [n[0] * s, n[1] * s, n[2] * s] };
  },
});
const sphere = (c, rad) => ({
  hit(r) {
    const a = r[0] ** 2 + r[1] ** 2 + r[2] ** 2;
    const b = -2 * (r[0] * c[0] + r[1] * c[1] + r[2] * c[2]);
    const cc = c[0] ** 2 + c[1] ** 2 + c[2] ** 2 - rad * rad;
    const disc = b * b - 4 * a * cc;
    if (disc < 0) return null;
    const t = (-b - Math.sqrt(disc)) / (2 * a);
    if (t <= 0) return null;
    const p = [r[0] * t, r[1] * t, r[2] * t];
    const n = [(p[0] - c[0]) / rad, (p[1] - c[1]) / rad, (p[2] - c[2]) / rad];
    return { t, n };
  },
});

const RADIUS = 100, INTENSITY = 1;
const ao = (scene, x, y) => aoCore(scene, cam, x, y, RADIUS, INTENSITY);

function meanAO(scene, x0, x1, y0, y1) {
  let s = 0, n = 0;
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const v = ao(scene, x, y); if (isFinite(v)) { s += v; n++; } }
  return s / n;
}

let fails = 0;
function check(name, ok, detail) {
  if (!ok) fails++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}   ${detail}`);
}

// 1. Open flat floor: nothing near it, AO must stay ~1.
{
  const floor = plane([0, 1, 0], -150); // y = -150
  const s = makeScene([floor]);
  const m = meanAO(s, 20, 140, 60, 88);
  check("flat floor is unoccluded", m > 0.95, `mean AO ${m.toFixed(3)} (want > 0.95)`);
}

// 2. Concave corner: floor + back wall meeting at a right angle.
//    Pixels at the crease must be much darker than pixels far from it.
{
  const floor = plane([0, 1, 0], -150);
  const wall = plane([0, 0, 1], 600);
  const s = makeScene([floor, wall]);
  // find the crease row: where depth hits 600 on the floor
  let creaseY = -1;
  for (let y = 89; y > 0; y--) { if (Math.abs(s.depthAt(80, y) - 600) < 3) { creaseY = y; break; } }
  // AO is confined to ~radius/pixelSize rows around the crease (~10 rows here), so
  // measure the crease row itself and the open floor well away from it.
  const nearCrease = meanAO(s, 60, 100, creaseY, creaseY + 1);
  const farFloor = meanAO(s, 60, 100, 80, 88);
  check("crease darker than open floor", nearCrease < farFloor - 0.08, `crease ${nearCrease.toFixed(3)} vs open ${farFloor.toFixed(3)} (want crease < open - 0.08)  creaseRow ${creaseY}`);
}

// 3. Sphere resting just above a floor: floor right under it is occluded,
//    floor far from it is not.
{
  const floor = plane([0, 1, 0], -150);
  const ball = sphere([0, -100, 450], 60);
  const s = makeScene([floor, ball]);
  // The floor point below the ball projects near the ball's lower silhouette.
  const under = (() => {
    const p = [0, -150, 450];
    return [Math.round((p[0] / (tanHalf * aspect * p[2]) * 0.5 + 0.5) * cam.width - 0.5),
            Math.round((0.5 - p[1] / (tanHalf * p[2]) * 0.5) * cam.height - 0.5)];
  })();
  const near = meanAO(s, under[0] - 4, under[0] + 5, under[1] + 1, under[1] + 5);
  const far = meanAO(s, 10, 30, 70, 85);
  check("floor under a ball is darker than open floor", near < far - 0.05, `under ${near.toFixed(3)} vs open ${far.toFixed(3)}  (px ${under})`);
}

// 4. Sky (no geometry) and the 7 km cutoff return exactly 1.
{
  const s = makeScene([]);
  check("sky pixel returns 1", ao(s, 80, 45) === 1, `${ao(s, 80, 45)}`);
  const far = plane([0, 1, 0], -150000);
  const sf = makeScene([plane([0, 0, 1], 800000)]);
  check("viewZ > 700000 returns 1", ao(sf, 80, 45) === 1, `${ao(sf, 80, 45)}`);
}

// 5. Intensity: AO^k, so k>1 must not brighten and must darken the crease.
{
  const floor = plane([0, 1, 0], -150);
  const wall = plane([0, 0, 1], 600);
  const s = makeScene([floor, wall]);
  let creaseY = -1;
  for (let y = 89; y > 0; y--) { if (Math.abs(s.depthAt(80, y) - 600) < 3) { creaseY = y; break; } }
  const a1 = aoCore(s, cam, 80, creaseY + 2, RADIUS, 1);
  const a4 = aoCore(s, cam, 80, creaseY + 2, RADIUS, 4);
  check("intensity exponent darkens", a4 < a1 && a4 >= 0, `k=1 ${a1.toFixed(3)}  k=4 ${a4.toFixed(3)}`);
}

// 6. Radius: a larger radius must reach farther -> a floor point a bit away from
//    the wall gets darker with a big radius than with a small one.
{
  const floor = plane([0, 1, 0], -150);
  const wall = plane([0, 0, 1], 600);
  const s = makeScene([floor, wall]);
  let creaseY = -1;
  for (let y = 89; y > 0; y--) { if (Math.abs(s.depthAt(80, y) - 600) < 3) { creaseY = y; break; } }
  const y = creaseY + 8;
  const small = aoCore(s, cam, 80, y, 30, 1);
  const big = aoCore(s, cam, 80, y, 300, 1);
  check("larger radius reaches farther", big < small, `r=30 ${small.toFixed(3)}  r=300 ${big.toFixed(3)}  (row ${y})`);
}

console.log(fails ? `\n${fails} FAILED` : "\nall passed");
process.exit(fails ? 1 : 0);
