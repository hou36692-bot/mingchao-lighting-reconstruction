// 植被：解鸣潮草实例基矩阵 t1（R16G16B16A16_FLOAT，每实例 3 行 xyz；Frame61250 e1850 绑定的 5653 个实例）
//   node tools/analysis/veg_inst_stats.mjs
//   -> $MC_OUT/veg/ww_inst_xf.json：每实例 [水平缩放, 竖直缩放, 倾斜角°]（偏航在源里是均匀分布，不存）
//
// reference implementation; source data not included
// 源：$MC_WORKSPACE/data/veg_src/e1850_t1_basis.bin
import fs from "node:fs";
import path from "node:path";
const SRC = path.join(process.env.MC_WORKSPACE || ".", "data/veg_src");
const OUT = process.env.MC_OUT || "./out";
const b = fs.readFileSync(path.join(SRC, "e1850_t1_basis.bin"));
const h = (u) => { const s = u >> 15, e = (u >> 10) & 31, f = u & 1023; const v = e === 0 ? f / 1024 * 2 ** -14 : e === 31 ? NaN : (1 + f / 1024) * 2 ** (e - 15); return s ? -v : v; };
const out = [];
for (let i = 0; i < b.length / 24; i++) {
  const R = [0, 1, 2].map((k) => [0, 1, 2].map((c) => h(b.readUInt16LE(i * 24 + k * 8 + c * 2))));
  const sx = Math.hypot(...R[0]), sz = Math.hypot(...R[2]);
  if (!(sx > 0.01)) continue;
  out.push([+sx.toFixed(3), +sz.toFixed(3), +(Math.acos(Math.min(1, R[2][2] / sz)) * 180 / Math.PI).toFixed(2)]);
}
const dest = path.join(OUT, "veg/ww_inst_xf.json");
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, JSON.stringify(out));
console.log(out.length, "instances ->", dest);
