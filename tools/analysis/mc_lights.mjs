// Decode the 35 local lights of Wuthering Waves source frame 61250 from the forward
// light buffer dump.
//   R2315717: 9 float4 per light (source evidence: forward-light layout)
//   [+0] (worldPos.xyz, 1/radius)
//   [+1] (colorLength/1023, colorDir 10:10:10, LightSceneId, falloffExponent)   <- UE PackLightColor
//   [+2] (direction.xyz, extraDataPacked)        type = (w>>16)&3, valid = bit22
//   [+3] (spotAngles.x, spotAngles.y, ?, ?)        point: (-2, 1) = UE's "not a spot" sentinel
//   [+4] (tangent.xyz, ?) [+5] (rect/barn data)
// reference implementation; source data not included
// Reads $MC_WORKSPACE/analysis/f61250/light/buf_2315717_full.txt,
// writes $MC_OUT/Cluster/mc_lights.json and prints a table.
//   node tools/analysis/mc_lights.mjs
import fs from "node:fs";
import path from "node:path";

const OUT = process.env.MC_OUT || "./out";
const SRC = path.join(process.env.MC_WORKSPACE || ".", "analysis/f61250/light/buf_2315717_full.txt");
const N = 35;
const rows = [];
for (const line of fs.readFileSync(SRC, "utf8").split("\n")) {
  const m = line.match(/^\[(\d+)\] f=\(([^)]*)\) u=\(([^)]*)\)/);
  if (!m) continue;
  rows[+m[1]] = { f: m[2].split(",").map(Number), u: m[3].split(",").map((x) => Number(x) >>> 0) };
}

const lights = [];
for (let i = 0; i < N; i++) {
  const r = (k) => rows[i * 9 + k];
  const p0 = r(0), p1 = r(1), p2 = r(2), p3 = r(3), p4 = r(4), p5 = r(5);
  const packed = p1.u[1];
  const dirInt = [packed & 1023, (packed >> 10) & 1023, (packed >> 20) & 1023];
  const scale = p1.f[0];
  const color = dirInt.map((v) => v * scale);             // = colorLength * unit dir (shader value)
  const len = Math.hypot(...color);
  const flags = p2.u[3];
  const L = {
    index: i,
    pos: p0.f.slice(0, 3),
    radius: 1 / p0.f[3],
    color,                                                   // linear, shader units
    colorLength: len,
    chroma: color.map((c) => c / Math.max(...color)),        // max-normalised, for UE LightColor
    lightSceneId: p1.f[2],
    falloffExponent: p1.f[3],                                // 0 = inverse squared (UE convention)
    dir: p2.f.slice(0, 3),
    flagsHex: "0x" + flags.toString(16),
    type: (flags >>> 16) & 3,
    bit18: (flags >>> 18) & 1,
    valid: (flags >>> 22) & 1,
    spotAngles: p3.f.slice(0, 2),
    p3zw: p3.f.slice(2, 4),
    tangent: p4.f.slice(0, 3),
    p5: p5.f,
  };
  // Shape: UE point lights carry SpotAngles (-2, 1).
  const isSpot = L.spotAngles[0] > -1.5;
  L.shape = isSpot ? "spot" : (Math.abs(L.dir[0] + 1) < 1e-4 && L.dir[1] === 0 ? "point" : "point_with_dir");
  if (isSpot) {
    const cosOuter = L.spotAngles[0], inv = L.spotAngles[1];
    const cosInner = Math.min(1, cosOuter + (inv > 0 ? 1 / inv : 0));
    L.outerDeg = (Math.acos(Math.max(-1, Math.min(1, cosOuter))) * 180) / Math.PI;
    L.innerDeg = (Math.acos(cosInner) * 180) / Math.PI;
  }
  lights.push(L);
}

fs.mkdirSync(path.join(OUT, "Cluster"), { recursive: true });
fs.writeFileSync(path.join(OUT, "Cluster/mc_lights.json"), JSON.stringify(lights, null, 1));

const f = (v, d = 0) => v.map((x) => x.toFixed(d)).join(",");
console.log("idx shape           type b18 valid  radius  |color|  fexp  id   pos                    dir              spot(x,y)        p3zw");
for (const L of lights)
  console.log(
    String(L.index).padStart(3), L.shape.padEnd(15), L.type, " ", L.bit18, "  ", L.valid, " ", L.radius.toFixed(0).padStart(6),
    L.colorLength.toFixed(2).padStart(8), String(L.falloffExponent).padStart(4), String(L.lightSceneId).padStart(4),
    f(L.pos).padEnd(22), f(L.dir, 2).padEnd(16), f(L.spotAngles, 3).padEnd(16), f(L.p3zw, 4),
  );
const count = (k) => lights.reduce((m, L) => ((m[L[k]] = (m[L[k]] || 0) + 1), m), {});
console.log("shape", count("shape"), "type", count("type"), "falloff", count("falloffExponent"));
