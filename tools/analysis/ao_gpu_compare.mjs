// Compare the GPU render of M_Dbg_AO_Test against ao_ref.mjs, per pixel.
// reference implementation; source data not included
//   node tools/analysis/ao_gpu_compare.mjs <gpu.json>
import fs from "node:fs";
import { aoCore } from "./ao_ref.mjs";

const g = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cam = { fovY: (60 * Math.PI) / 180, width: 160, height: 90 };
const tanHalf = Math.tan(cam.fovY / 2), aspect = cam.width / cam.height;
const ray = (x, y) => [((x + 0.5) / 160 * 2 - 1) * tanHalf * aspect, (1 - (y + 0.5) / 90 * 2) * tanHalf, 1];

const D = new Float32Array(160 * 90), Nn = new Array(160 * 90);
for (let y = 0; y < 90; y++) for (let x = 0; x < 160; x++) {
  const r = ray(x, y); let best = 600, n = [0, 0, -1];
  if (r[1] < -1e-6) { const t = -150 / r[1]; if (t < best) { best = t; n = [0, 1, 0]; } }
  D[y * 160 + x] = best; Nn[y * 160 + x] = n;
}
const scene = { depthAt: (x, y) => D[y * 160 + x], normalAt: (x, y) => Nn[y * 160 + x] };

let maxE = 0, sumE = 0, n = 0, bad = 0, worst = null;
let gpuMin = 1, cpuMin = 1, gpuMean = 0, cpuMean = 0;
for (let y = 0; y < 90; y++) for (let x = 0; x < 160; x++) {
  const cpu = aoCore(scene, cam, x, y, g.radius, g.intensity);
  // The RT readback is sRGB-encoded 8-bit (confirmed by a quantisation check: error
  // 1e-5 when the CPU value is sRGB-encoded + quantised). Decode it back to linear.
  const enc = g.ao[y * 160 + x];
  const gpu = enc <= 0.04045 ? enc / 12.92 : ((enc + 0.055) / 1.055) ** 2.4;
  const e = Math.abs(cpu - gpu);
  sumE += e; n++; gpuMean += gpu; cpuMean += cpu;
  gpuMin = Math.min(gpuMin, gpu); cpuMin = Math.min(cpuMin, cpu);
  if (e > 0.05) bad++;
  if (e > maxE) { maxE = e; worst = { x, y, cpu: +cpu.toFixed(3), gpu: +gpu.toFixed(3) }; }
}
console.log(`radius ${g.radius}  intensity ${g.intensity}`);
console.log(`mean AO   cpu ${(cpuMean / n).toFixed(4)}   gpu ${(gpuMean / n).toFixed(4)}`);
console.log(`min  AO   cpu ${cpuMin.toFixed(3)}   gpu ${gpuMin.toFixed(3)}`);
console.log(`|cpu-gpu| mean ${(sumE / n).toFixed(4)}  max ${maxE.toFixed(3)}  pixels off by >0.05: ${bad} / ${n} (${(bad / n * 100).toFixed(2)}%)`);
console.log("worst:", JSON.stringify(worst));
