// Minimal PNG read/write + box downscale + side-by-side, no dependencies.
//   node tools/image/png.mjs resize <in> <out> <width>
//   node tools/image/png.mjs sbs <out> <height> <in1> <in2> [in3...]     (side by side, each scaled to height)
import fs from "node:fs";
import zlib from "node:zlib";

export function readPNG(p) {
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
  const out = Buffer.alloc(w * h * 3);
  const prev = Buffer.alloc(stride), cur = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)];
    raw.copy(cur, 0, y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? cur[i - bpp] : 0, up = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
      let v = cur[i];
      if (f === 1) v += a;
      else if (f === 2) v += up;
      else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) { const p = a + up - c, pa = Math.abs(p - a), pb = Math.abs(p - up), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : c; }
      cur[i] = v & 255;
    }
    for (let x = 0; x < w; x++) for (let k = 0; k < 3; k++) out[(y * w + x) * 3 + k] = cur[x * bpp + k];
    cur.copy(prev);
  }
  return { w, h, data: out };
}

export function writePNG(p, img) {
  const { w, h, data } = img;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 3 + 1)] = 0; data.copy(raw, y * (w * 3 + 1) + 1, y * w * 3, (y + 1) * w * 3); }
  const crcT = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; crcT[n] = c >>> 0; }
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (t, d) => { const len = Buffer.alloc(4); len.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  fs.writeFileSync(p, Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw, { level: 6 })), chunk("IEND", Buffer.alloc(0))]));
}

export function resize(img, nw, nh) {
  nh = nh || Math.round(img.h * nw / img.w);
  const out = Buffer.alloc(nw * nh * 3);
  const sx = img.w / nw, sy = img.h / nh;
  for (let y = 0; y < nh; y++) for (let x = 0; x < nw; x++) {
    const x0 = Math.floor(x * sx), x1 = Math.max(x0 + 1, Math.floor((x + 1) * sx));
    const y0 = Math.floor(y * sy), y1 = Math.max(y0 + 1, Math.floor((y + 1) * sy));
    const s = [0, 0, 0]; let n = 0;
    for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) { const i = (yy * img.w + xx) * 3; s[0] += img.data[i]; s[1] += img.data[i + 1]; s[2] += img.data[i + 2]; n++; }
    for (let k = 0; k < 3; k++) out[(y * nw + x) * 3 + k] = Math.round(s[k] / n);
  }
  return { w: nw, h: nh, data: out };
}

export function sideBySide(imgs, h, gap = 4) {
  const rs = imgs.map((im) => resize(im, Math.round(im.w * h / im.h), h));
  const W = rs.reduce((a, r) => a + r.w, 0) + gap * (rs.length - 1);
  const out = Buffer.alloc(W * h * 3, 255);
  let ox = 0;
  for (const r of rs) { for (let y = 0; y < h; y++) r.data.copy(out, (y * W + ox) * 3, y * r.w * 3, (y + 1) * r.w * 3); ox += r.w + gap; }
  return { w: W, h, data: out };
}

const [cmd, ...a] = process.argv.slice(2);
if (cmd === "resize") writePNG(a[1], resize(readPNG(a[0]), +a[2]));
else if (cmd === "sbs") writePNG(a[0], sideBySide(a.slice(2).map(readPNG), +a[1]));
// node tools/image/png.mjs diff <a> <b> <out> [gain=4]   -> |a-b| luma * gain, grey heatmap
if (cmd === "diff") {
  const A = readPNG(a[0]), B = readPNG(a[1]); const g = +(a[3] || 4);
  const o = Buffer.alloc(A.w * A.h * 3);
  for (let i = 0; i < A.w * A.h; i++) {
    const la = 0.299 * A.data[i * 3] + 0.587 * A.data[i * 3 + 1] + 0.114 * A.data[i * 3 + 2];
    const lb = 0.299 * B.data[i * 3] + 0.587 * B.data[i * 3 + 1] + 0.114 * B.data[i * 3 + 2];
    const d = (lb - la) * g; // red = b brighter, blue = b darker
    o[i * 3] = Math.min(255, Math.max(0, d)); o[i * 3 + 2] = Math.min(255, Math.max(0, -d)); o[i * 3 + 1] = 0;
  }
  writePNG(a[2], { w: A.w, h: A.h, data: o });
}
// node tools/image/png.mjs crop <in> <out> <x> <y> <w> <h> [scale=1]
if (cmd === "crop") {
  const I = readPNG(a[0]); const [x, y, w, h] = a.slice(2, 6).map(Number); const s = +(a[6] || 1);
  const o = Buffer.alloc(w * s * h * s * 3);
  for (let yy = 0; yy < h * s; yy++) for (let xx = 0; xx < w * s; xx++) {
    const si = ((y + Math.floor(yy / s)) * I.w + x + Math.floor(xx / s)) * 3, di = (yy * w * s + xx) * 3;
    o[di] = I.data[si]; o[di + 1] = I.data[si + 1]; o[di + 2] = I.data[si + 2];
  }
  writePNG(a[1], { w: w * s, h: h * s, data: o });
}
