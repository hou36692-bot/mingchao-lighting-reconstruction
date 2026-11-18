// Per-pixel comparison: Wuthering Waves light-grid replica (tools/analysis/cluster_ref.mjs)
// vs UE's own light grid
// (r.Forward.LightGridDebug 1 = light count of the cell under each pixel's depth).
// reference implementation; source data not included
//   node tools/analysis/cluster_cmp.mjs <ue_depth.bin 960x540> <ue_mode1.png> [outPrefix]
// Both use the same depth (UE capture at the reconstructed pose), so the difference is culling only
// (+ UE's Z slicing, whose far plane depends on its light set).
import fs from "node:fs";
import path from "node:path";
import { readPNG, writePNG } from "../image/png.mjs";

const OUT = process.env.MC_OUT || "./out";
const [depthFile, uePng, prefix = path.join(OUT, "cluster/cmp")] = process.argv.slice(2);
const W = 960, H = 540, SCALE = 4, GX = 60, GY = 34, GZ = 32;
// the source frame's Z params by default; ZFAR=<cm> re-derives them the way UE does (GetLightGridZParams, near 10cm)
const S = 4.05;
const [B, O] = process.env.ZFAR ? (() => { const F = +process.env.ZFAR + 10, N = 10 + 9.5; const o = (F - N * 2 ** (31 / S)) / (F - N); return [(1 - o) / N, o]; })() : [0.00432649, 0.915633];
const counts = fs.readFileSync(path.join(OUT, "Cluster/ref_counts_60x34x32.bin"));
const depth = new Float32Array(fs.readFileSync(depthFile).buffer.slice(0));
const ue = readPNG(uePng);

const rgb2hsv = (r, g, b) => { const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn; let h = 0;
  if (d > 0) { if (mx === r) h = ((g - b) / d) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4; h /= 6; if (h < 0) h += 1; }
  return [h, mx ? d / mx : 0, mx]; };

const ref = new Int16Array(W * H), uev = new Int16Array(W * H).fill(-1);
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const i = y * W + x, z = depth[i];
  const slice = Math.min(GZ - 1, Math.max(0, Math.floor(Math.log2(z * B + O) * S)));
  const tx = Math.floor((x * SCALE) / 64), ty = Math.floor((y * SCALE) / 64);
  ref[i] = z > 1e9 ? 0 : counts[(slice * GY + ty) * GX + tx];
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };   // overlay is written linear, stored sRGB
  const r = lin(ue.data[i * 3]), g = lin(ue.data[i * 3 + 1]), b = lin(ue.data[i * 3 + 2]);
  const [h, s, v] = rgb2hsv(r, g, b);
  if (v < 0.05) uev[i] = 0;                         // no lights
  else if (s > 0.6 && v > 0.6) uev[i] = Math.round((1 - h / 0.6) * 16);   // GetHSVDebugColor, MaxThreshold 16
}
let n = 0, same = 0, off1 = 0, refMore = 0, ueMore = 0;
const hist = {};
for (let i = 0; i < W * H; i++) {
  if (uev[i] < 0) continue;
  n++; const d = ref[i] - uev[i];
  if (d === 0) same++; else if (Math.abs(d) === 1) off1++;
  if (d > 0) refMore++; if (d < 0) ueMore++;
  hist[d] = (hist[d] || 0) + 1;
}
console.log(`decodable pixels ${n}: exact ${(100 * same / n).toFixed(1)}%  |diff|=1 ${(100 * off1 / n).toFixed(1)}%  WW>UE ${(100 * refMore / n).toFixed(1)}%  UE>WW ${(100 * ueMore / n).toFixed(1)}%`);
console.log("diff histogram (WW-UE):", Object.fromEntries(Object.entries(hist).sort((a, b) => +a[0] - +b[0])));
// images: WW replica drawn like UE mode 1, and a signed diff
const hsv2rgb = (h) => { const f = (k) => { k = (k + h * 6) % 6; return 1 - Math.max(0, Math.min(k, 4 - k, 1)); }; return [f(5), f(3), f(1)]; };
const a = Buffer.alloc(W * H * 3), dimg = Buffer.alloc(W * H * 3);
for (let i = 0; i < W * H; i++) {
  const c = ref[i] > 0 ? hsv2rgb((1 - Math.min(ref[i] / 16, 1)) * 0.6) : [0, 0, 0];
  for (let k = 0; k < 3; k++) a[i * 3 + k] = Math.round(c[k] * 255);
  if (uev[i] >= 0) { const d = ref[i] - uev[i]; dimg[i * 3] = d > 0 ? Math.min(255, 80 * d) : 0; dimg[i * 3 + 2] = d < 0 ? Math.min(255, -80 * d) : 0; dimg[i * 3 + 1] = d === 0 && ref[i] > 0 ? 60 : 0; }
}
fs.mkdirSync(path.dirname(prefix), { recursive: true });
writePNG(prefix + "_ww_mode1.png", { w: W, h: H, data: a });
writePNG(prefix + "_diff.png", { w: W, h: H, data: dimg });
