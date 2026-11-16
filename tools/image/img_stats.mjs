// Per-image colour statistics: mean RGB, luma percentiles, mean saturation.
import fs from "node:fs";
import zlib from "node:zlib";

function readPNG(p) {
  const b = fs.readFileSync(p);
  let off = 8, w, h, ct, bd;
  const idat = [];
  while (off + 12 <= b.length) {
    const len = b.readUInt32BE(off);
    const t = b.slice(off + 4, off + 8).toString();
    const d = b.slice(off + 8, off + 8 + len);
    if (t === "IHDR") { w = d.readUInt32BE(0); h = d.readUInt32BE(4); bd = d[8]; ct = d[9]; }
    if (t === "IDAT") idat.push(d);
    if (t === "IEND") break;
    off += 12 + len;
  }
  const bpp = ct === 6 ? 4 : ct === 2 ? 3 : null;
  if (!bpp || bd !== 8) throw new Error(`unsupported png colorType=${ct} depth=${bd}`);
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = w * bpp;
  const px = Buffer.alloc(w * h * 3);
  let prev = Buffer.alloc(stride);
  let o = 0;
  for (let y = 0; y < h; y++) {
    const f = raw[o++];
    const line = Buffer.from(raw.slice(o, o + stride)); o += stride;
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? line[i - bpp] : 0, up = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
      let v = line[i];
      if (f === 1) v += a;
      else if (f === 2) v += up;
      else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) {
        const pa = Math.abs(up - c), pb = Math.abs(a - c), pc = Math.abs(a + up - 2 * c);
        v += pa <= pb && pa <= pc ? a : pb <= pc ? up : c;
      }
      line[i] = v & 255;
    }
    for (let x = 0; x < w; x++) {
      px[(y * w + x) * 3] = line[x * bpp];
      px[(y * w + x) * 3 + 1] = line[x * bpp + 1];
      px[(y * w + x) * 3 + 2] = line[x * bpp + 2];
    }
    prev = line;
  }
  return { w, h, px };
}

export function stats(p) {
  const { w, h, px } = readPNG(p);
  const n = w * h;
  let r = 0, g = 0, b = 0, sat = 0;
  const lum = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const R = px[i * 3], G = px[i * 3 + 1], B = px[i * 3 + 2];
    r += R; g += G; b += B;
    const mx = Math.max(R, G, B), mn = Math.min(R, G, B);
    sat += mx ? (mx - mn) / mx : 0;
    lum[i] = 0.2126 * R + 0.7152 * G + 0.0722 * B;
  }
  const sorted = Array.from(lum).sort((a, b) => a - b);
  const pct = (q) => sorted[Math.floor(q * (n - 1))].toFixed(0);
  return {
    file: p, size: `${w}x${h}`,
    meanRGB: [r / n, g / n, b / n].map((v) => v.toFixed(1)).join(","),
    meanSat: (sat / n).toFixed(3),
    luma_p05_p50_p95: [pct(0.05), pct(0.5), pct(0.95)].join("/"),
  };
}

if ((process.argv[1] || "").endsWith("img_stats.mjs")) {
  for (const f of process.argv.slice(2)) console.log(JSON.stringify(stats(f)));
}
