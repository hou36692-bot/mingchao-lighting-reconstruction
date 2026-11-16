// Banded colour statistics of one or more images (same framing), for tuning UE against Wuthering Waves.
//   node tools/image/cmp_stats.mjs <ref.png> <a.png> [b.png ...]
// Bands: sky/top (0-30%), mid (30-65%), bottom/water (65-100%). Reports mean sRGB, mean luma,
// luma p10/p50/p90, mean saturation (HSV), and the ratio of each image's band luma to the ref.
import { readPNG } from "./png.mjs";

const bands = [["top", 0, 0.30], ["mid", 0.30, 0.65], ["bot", 0.65, 1.0]];
function stats(img) {
  const out = {};
  for (const [name, y0, y1] of bands) {
    const ls = [], rgb = [0, 0, 0]; let sat = 0, n = 0;
    for (let y = Math.floor(y0 * img.h); y < Math.floor(y1 * img.h); y++) for (let x = 0; x < img.w; x++) {
      const i = (y * img.w + x) * 3, r = img.data[i], g = img.data[i + 1], b = img.data[i + 2];
      rgb[0] += r; rgb[1] += g; rgb[2] += b;
      ls.push(0.2126 * r + 0.7152 * g + 0.0722 * b);
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b); sat += mx ? (mx - mn) / mx : 0; n++;
    }
    ls.sort((a, b) => a - b);
    out[name] = { rgb: rgb.map((v) => Math.round(v / n)), luma: Math.round(ls.reduce((a, b) => a + b, 0) / n),
      p10: Math.round(ls[Math.floor(n * 0.1)]), p50: Math.round(ls[Math.floor(n * 0.5)]), p90: Math.round(ls[Math.floor(n * 0.9)]),
      sat: +(sat / n).toFixed(2) };
  }
  return out;
}
const files = process.argv.slice(2);
const all = files.map((f) => stats(readPNG(f)));
for (const [name] of bands) {
  console.log(`-- ${name}`);
  all.forEach((s, k) => {
    const b = s[name], r = all[0][name];
    console.log(`  ${files[k].split(/[\\/]/).pop().padEnd(28)} rgb ${b.rgb.join(",").padEnd(12)} luma ${String(b.luma).padStart(3)} (x${(b.luma / r.luma).toFixed(2)})  p10/50/90 ${b.p10}/${b.p50}/${b.p90}  sat ${b.sat}`);
  });
}
