// Per-pixel diff between two PNGs. Reports share of pixels changed by >2/255,
// mean abs diff, and the signed mean shift per channel (direction of change).
import fs from "node:fs";
import zlib from "node:zlib";
import { stats } from "./img_stats.mjs";

function load(p) {
  const b = fs.readFileSync(p);
  let off = 8, w, h; const idat = [];
  while (off + 12 <= b.length) {
    const len = b.readUInt32BE(off), t = b.slice(off + 4, off + 8).toString();
    const d = b.slice(off + 8, off + 8 + len);
    if (t === "IHDR") { w = d.readUInt32BE(0); h = d.readUInt32BE(4); }
    if (t === "IDAT") idat.push(d);
    if (t === "IEND") break;
    off += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = w * 3, px = Buffer.alloc(w * h * 3);
  let prev = Buffer.alloc(stride), o = 0;
  for (let y = 0; y < h; y++) {
    const f = raw[o++]; const line = Buffer.from(raw.slice(o, o + stride)); o += stride;
    for (let i = 0; i < stride; i++) {
      const a = i >= 3 ? line[i - 3] : 0, up = prev[i], c = i >= 3 ? prev[i - 3] : 0;
      let v = line[i];
      if (f === 1) v += a; else if (f === 2) v += up; else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) { const pa = Math.abs(up - c), pb = Math.abs(a - c), pc = Math.abs(a + up - 2 * c); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : c; }
      line[i] = v & 255;
    }
    line.copy(px, y * stride); prev = line;
  }
  return { w, h, px };
}

const [a, b] = [load(process.argv[2]), load(process.argv[3])];
const n = a.w * a.h; let ch = 0, abs = 0; const sh = [0, 0, 0];
for (let i = 0; i < n; i++) {
  let m = 0;
  for (let c = 0; c < 3; c++) { const d = b.px[i * 3 + c] - a.px[i * 3 + c]; sh[c] += d; m = Math.max(m, Math.abs(d)); abs += Math.abs(d); }
  if (m > 2) ch++;
}
console.log(`${process.argv[2].split("/").pop()} -> ${process.argv[3].split("/").pop()}: changed(>2) ${(ch / n * 100).toFixed(1)}%  meanAbs ${(abs / n / 3).toFixed(2)}  signedShift RGB ${sh.map(v => (v / n).toFixed(2)).join(",")}`);
