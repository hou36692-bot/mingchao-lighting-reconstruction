// 植被步骤 2：把鸣潮 Frame61250 两种地表草网格（VB 12 顶点 / IB 18 索引 / t2 R16G16 UV）原样写成 OBJ
//   node tools/analysis/veg_build_mesh.mjs [outDir]
//
// reference implementation; source data not included
// 源：$MC_WORKSPACE/data/veg_src 下的 RenderDoc buffer 导出（buf_*）；输出默认 $MC_OUT/veg/obj。
//   A = VB1043086/t2 1043083（57 cm，图集右下最底条）
//   B = VB1043066/t2 1043061（37 cm，其上一条）
// t2 每顶点 16 字节，前 4 字节是 UV（VS: (vid+cb3.w)*cb3.y，cb3=(…,4,…,0)）
// Z 向上、cm；UE 的 OBJ 导入会把 Y 取反（右手→左手），所以这里先写 -Y 并反转绕序，导入后与源坐标一致。
// 法线统一 (0,0,1)；OBJ 的 v 取 1-v。
import fs from "node:fs";
import path from "node:path";
const SRC = path.join(process.env.MC_WORKSPACE || ".", "data/veg_src");
const OUT = process.argv[2] || path.join(process.env.MC_OUT || "./out", "veg/obj");
fs.mkdirSync(OUT, { recursive: true });
const half = (u) => { const s = u >> 15, e = (u >> 10) & 31, f = u & 1023; const v = e === 0 ? f / 1024 * 2 ** -14 : (1 + f / 1024) * 2 ** (e - 15); return s ? -v : v; };
const SETS = { A: ["1043086", "1043083", "1043081"], B: ["1043066", "1043061", "1043059"] };
for (const [name, [vb, t2, ib]] of Object.entries(SETS)) {
  const V = fs.readFileSync(`${SRC}/buf_${vb}_vb0.bin`), T = fs.readFileSync(`${SRC}/buf_${t2}_t2.bin`), I = fs.readFileSync(`${SRC}/buf_${ib}_ib.bin`);
  const n = V.length / 12, lines = [`# Wuthering Waves ground grass ${name}: VB ${vb} / UV ${t2} / IB ${ib}`, `o SM_WWGrass_TriCard_${name}`];
  for (let i = 0; i < n; i++) lines.push(`v ${[0, 4, 8].map((o) => (o === 4 ? -1 : 1) * V.readFloatLE(i * 12 + o)).map((x) => x.toFixed(4)).join(" ")}`);
  for (let i = 0; i < n; i++) lines.push(`vt ${half(T.readUInt16LE(i * 16)).toFixed(5)} ${(1 - half(T.readUInt16LE(i * 16 + 2))).toFixed(5)}`);
  lines.push("vn 0 0 1");
  for (let i = 0; i < I.length / 2; i += 3) {
    const f = [0, 1, 2].map((k) => I.readUInt16LE((i + k) * 2) + 1);
    lines.push(`f ${f.reverse().map((x) => `${x}/${x}/1`).join(" ")}`);
  }
  fs.writeFileSync(`${OUT}/SM_WWGrass_TriCard_${name}.obj`, lines.join("\n") + "\n");
  console.log(name, n, "verts", I.length / 6, "tris ->", `${OUT}/SM_WWGrass_TriCard_${name}.obj`);
}
