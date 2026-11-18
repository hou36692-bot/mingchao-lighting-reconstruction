// CPU replica of the light-grid culling for Wuthering Waves source frame 61250,
// written against UE's LightGridInjection.usf (ComputeCellBounds / OverlapsLight /
// IsAabbOutsideInfiniteAcuteConeApprox) and fed with the source frame's own
// view-space light lists:
//   R2315719 = LightViewSpacePositionAndRadius  (xyz, radius)
//   R2315721 = LightViewSpaceDirAndPreprocAngle (dir.xyz, tanConeAngle bits | 0x1 rect | 0x2 tight | 0x4 textured)
// plus the source frame's grid constants (cs1073371 cb2): 60x34x32, 64px,
// Z params (B,O,S)=(0.00432649,0.915633,4.05).
//
// reference implementation; source data not included
// Reads $MC_WORKSPACE/analysis/f61250/light/buf_full.txt (light-buffer text dump)
// and writes under $MC_OUT (default ./out).
//
//   node tools/analysis/cluster_ref.mjs [outPng]
// Output: per-tile max light count over slices 0..30 (UE r.Forward.LightGridDebug 2), drawn the
// way UE draws it (HSV debug colour, MaxThreshold 16) at 960x540 with 16px tiles (= 3840/64 grid).
import fs from "node:fs";
import path from "node:path";
import { writePNG } from "../image/png.mjs";

const OUT = process.env.MC_OUT || "./out";
const W = 3840, H = 2160, TILE = 64, GX = 60, GY = 34, GZ = 32;
// the source frame's own Z params by default; ZFAR=<cm> re-derives them the way UE does
// (GetLightGridZParams, near 10cm)
const S = 4.05;
const [B, O] = process.env.ZFAR ? (() => { const F = +process.env.ZFAR + 10, N = 10 + 9.5; const o = (F - N * 2 ** (31 / S)) / (F - N); return [(1 - o) / N, o]; })() : [0.00432649, 0.915633];
const TAN_X = 0.900404, TAN_Y = 0.506477;              // ps1572 cb1[285]: tan(84deg/2), /aspect
const NUM_LIGHTS = 35;                                 // cs1073371 cb2[0].x

const SRC = path.join(process.env.MC_WORKSPACE || ".", "analysis/f61250/light/buf_full.txt");
const parse = (label) => {
  const txt = fs.readFileSync(SRC, "utf8");
  const blk = txt.split("== ").find((b) => b.startsWith(label));
  const out = [];
  for (const line of blk.split("\n")) {
    const m = line.match(/^\[(\d+)\] f=\(([^)]*)\) u=\(([^)]*)\)/);
    if (m) out[+m[1]] = { f: m[2].split(",").map(Number), u: m[3].split(",").map((x) => Number(x) >>> 0) };
  }
  return out;
};
const pos = parse("R2315719"), dirs = parse("R2315721");
const f32 = (u) => { const b = Buffer.alloc(4); b.writeUInt32LE(u >>> 0); return b.readFloatLE(0); };

const depthFromSlice = (z) => (z === GZ ? 2000000 : z === 0 ? 0 : (2 ** (z / S) - O) / B);

function cellBounds(x, y, z) {
  const ts = [2 * TILE / W, -2 * TILE / H];
  const mn = [x * ts[0] - 1, y * ts[1] + 1], mx = [(x + 1) * ts[0] - 1, (y + 1) * ts[1] + 1];
  const z0 = depthFromSlice(z), z1 = depthFromSlice(z + 1);
  const lo = [Infinity, Infinity, z0], hi = [-Infinity, -Infinity, z1];
  for (const d of [z0, z1]) for (const u of [mn[0], mx[0]]) for (const v of [mn[1], mx[1]]) {
    const vx = u * TAN_X * d, vy = v * TAN_Y * d;
    lo[0] = Math.min(lo[0], vx); hi[0] = Math.max(hi[0], vx);
    lo[1] = Math.min(lo[1], vy); hi[1] = Math.max(hi[1], vy);
  }
  return { c: lo.map((v, i) => (v + hi[i]) / 2), e: lo.map((v, i) => (hi[i] - v) / 2) };
}

const boxDistSq = (c, e, p) => [0, 1, 2].reduce((s, i) => s + Math.max(Math.abs(p[i] - c[i]) - e[i], 0) ** 2, 0);
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const norm = (a) => { const l = Math.hypot(...a) || 1; return a.map((v) => v / l); };

function outsideCone(vertex, axis, tanA, c, e) {
  const D = c.map((v, i) => v - vertex[i]);
  const M = norm(cross(cross(D, axis), axis)).map((v) => -v);
  const N = axis.map((v, i) => -tanA * v + M[i]);
  return dot(D, N) > dot(e, N.map(Math.abs));
}

const counts = new Uint8Array(GX * GY * GZ);
const lightCells = new Array(NUM_LIGHTS).fill(0);
for (let z = 0; z < GZ; z++) for (let y = 0; y < GY; y++) for (let x = 0; x < GX; x++) {
  const cb = cellBounds(x, y, z);
  let n = 0;
  for (let i = 0; i < NUM_LIGHTS; i++) {
    const p = pos[i].f, r = p[3];
    if (boxDistSq(cb.c, cb.e, p) >= r * r) continue;
    const tan = f32(dirs[i].u[3] & 0xfffffff8);
    if (tan > 0) {
      const axis = dirs[i].f.slice(0, 3).map((v) => -v);
      if (outsideCone(p.slice(0, 3), axis, tan, cb.c, cb.e)) continue;
    }
    n++; lightCells[i]++;
  }
  counts[(z * GY + y) * GX + x] = Math.min(n, 32);
}

const tileMax = [];
for (let y = 0; y < GY; y++) for (let x = 0; x < GX; x++) {
  let m = 0;
  for (let z = 0; z < GZ - 1; z++) m = Math.max(m, counts[(z * GY + y) * GX + x]);
  tileMax.push(m);
}
fs.mkdirSync(path.join(OUT, "Cluster"), { recursive: true });
fs.writeFileSync(path.join(OUT, "Cluster/ref_tilemax_mode2.json"), JSON.stringify({ GX, GY, tileMax, lightCells }));

// draw like UE's debug pass
const hsv2rgb = (h, s, v) => { const f = (n) => { const k = (n + h * 6) % 6; return v - v * s * Math.max(0, Math.min(k, 4 - k, 1)); }; return [f(5), f(3), f(1)]; };
const OW = 960, OH = 540, OT = 16, TH = 16;
const img = Buffer.alloc(OW * OH * 3);
for (let py = 0; py < OH; py++) for (let px = 0; px < OW; px++) {
  const tx = px >> 4, ty = py >> 4;
  const n = tileMax[ty * GX + tx];
  let rgb = [0, 0, 0];
  if (n > 0) rgb = hsv2rgb((1 - Math.min(n / TH, 1)) * 0.6, 1, 1);
  if (px % OT === 0 || py % OT === 0) rgb = [0.25, 0.25, 0.25];
  const i = (py * OW + px) * 3;
  for (let k = 0; k < 3; k++) img[i + k] = Math.round(Math.min(1, rgb[k]) ** (1 / 2.2) * 255);
}
const out = process.argv[2] || path.join(OUT, "cluster/ref_mode2.png");
fs.mkdirSync(path.dirname(out), { recursive: true });
writePNG(out, { w: OW, h: OH, data: img });

const hist = {};
for (const m of tileMax) hist[m] = (hist[m] || 0) + 1;
console.log("tiles by max-count (slices 0..30):", hist);
console.log("cells touched per light:", lightCells.join(" "));
console.log("non-empty cells", counts.reduce((s, v) => s + (v > 0), 0), "/", counts.length, " max per cell", Math.max(...counts));
fs.writeFileSync(path.join(OUT, "Cluster/ref_counts_60x34x32.bin"), Buffer.from(counts));
