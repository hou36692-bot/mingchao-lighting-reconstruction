// CSM cascade-split maths: UE's real formula vs the source frame's measured splits.
//
// UE (DirectionalLightComponent.cpp GetSplitDistance / ComputeAccumulatedScale):
//   split(i) = Near + scale(i) * (R - Near)
//   scale(i) = sum_{k<i} e^k / sum_{k<N} e^k          (geometric series, ratio e = CascadeDistributionExponent)
//   R        = WholeSceneDynamicShadowRadius * r.Shadow.DistanceScale   (clamped 0..2)
//   N        = DynamicShadowCascades, capped by r.Shadow.CSM.MaxCascades
//
// Wuthering Waves source (ps1024669 cb0[53..57]) [事实]:
//   cascade far planes 800 / 2000 / 6500 / 15000 / 32500 cm  (5 cascades)
//
// The question: with N <= 4 and a single exponent, how close can UE get, and what
// parameters get there? Search (exponent, R) minimising log-space error.
//   node tools/analysis/csm_fit.mjs

const MC = [800, 2000, 6500, 15000, 32500];
const NEAR = 10;

export function ueSplits(N, exponent, R, near = NEAR) {
  const out = [];
  const total = Array.from({ length: N }, (_, k) => exponent ** k).reduce((a, b) => a + b, 0);
  for (let i = 1; i <= N; i++) {
    let acc = 0;
    for (let k = 0; k < i; k++) acc += exponent ** k;
    out.push(near + (acc / total) * (R - near));
  }
  return out; // far plane of each cascade
}

const logErr = (a, b) => Math.sqrt(a.reduce((s, v, i) => s + (Math.log(v) - Math.log(b[i])) ** 2, 0) / a.length);

// The source frame's own growth between cascades, for reference.
const ratios = MC.slice(1).map((v, i) => v / MC[i]);
console.log("source far planes :", MC.join(" / "), " cm");
console.log("  ratio each step  :", ratios.map((r) => r.toFixed(2)).join(" / "), "  (geometric would be constant)");
console.log();

// What UE does today in this level (sun properties read from the editor).
// Read from the level: DynamicShadowDistanceMovableLight=40000 (this is the property a
// Movable sun uses, see ComputeWholeSceneDynamicShadowRadius), r.Shadow.DistanceScale=0.85.
const cur = { N: 4, e: 3.0, R: 40000 * 0.85 };
console.log(`UE now (N=${cur.N}, exp=${cur.e}, shadow distance 40000 x DistanceScale 0.85 = ${cur.R}):`);
console.log("  far planes       :", ueSplits(cur.N, cur.e, cur.R).map((v) => v.toFixed(0)).join(" / "), " cm");
console.log();

// Fit: for each N in 1..4, find (exponent, R) to best match the first N source
// cascades, OR the last N (a 4-cascade UE can drop either end).
function fit(N, targets) {
  let best = { err: Infinity };
  for (let e = 1.0; e <= 6.0; e += 0.01) {
    for (let R = targets[N - 1] * 0.7; R <= targets[N - 1] * 1.3; R += targets[N - 1] * 0.005) {
      const err = logErr(ueSplits(N, e, R), targets);
      if (err < best.err) best = { err, e: +e.toFixed(2), R: Math.round(R) };
    }
  }
  return best;
}

console.log("Best (exponent, radius) for a 4-cascade UE sun:");
for (const [name, tgt] of [
  ["match source cascades 1-4 (800..15000)  ", MC.slice(0, 4)],
  ["match source cascades 2-5 (2000..32500) ", MC.slice(1, 5)],
]) {
  const b = fit(4, tgt);
  console.log(`  ${name} exp ${b.e}  radius ${b.R}  -> ${ueSplits(4, b.e, b.R).map((v) => v.toFixed(0)).join(" / ")}   rms log-err ${b.err.toFixed(3)}`);
}
console.log();
console.log("Why UE cannot be exact: its splits are one geometric series (1 free exponent + radius),");
console.log("the source step ratios are", ratios.map((r) => r.toFixed(2)).join(" / "), "- they are NOT constant, and there are 5 of them.");

// ---- 5 cascades: N near + F far -------------------------------------------------
// UE's far cascades continue the SAME exponent from R out to FarShadowDistance:
//   split(near i)  = Near + scale(i, N)  * (R - Near)
//   split(far  j)  = R    + scale(j, F)  * (Far - R)
// so with N=4, F=1 there are 5 cascades whose last plane is FarShadowDistance.
export function ueSplits5(N, F, exponent, R, Far, near = NEAR) {
  const near_ = ueSplits(N, exponent, R, near);
  const total = Array.from({ length: F }, (_, k) => exponent ** k).reduce((a, b) => a + b, 0);
  const far_ = [];
  for (let j = 1; j <= F; j++) {
    let acc = 0;
    for (let k = 0; k < j; k++) acc += exponent ** k;
    far_.push(R + (acc / total) * (Far - R));
  }
  return [...near_, ...far_];
}

console.log("\n=== 5 cascades (4 near + 1 far) ===");
let best5 = { err: Infinity };
for (let e = 1.2; e <= 4.0; e += 0.01)
  for (let R = 8000; R <= 22000; R += 100) {
    const s = ueSplits5(4, 1, e, R, 32500);
    const err = logErr(s, MC);
    if (err < best5.err) best5 = { err, e: +e.toFixed(2), R, s };
  }
console.log(`best: exponent ${best5.e}  DynamicShadowDistance ${best5.R}  FarShadowCascadeCount 1  FarShadowDistance 32500`);
console.log("  UE   :", best5.s.map((v) => v.toFixed(0)).join(" / "));
console.log("  MC   :", MC.join(" / "));
console.log("  err% :", best5.s.map((v, i) => (((v - MC[i]) / MC[i]) * 100).toFixed(0) + "%").join(" / "), "  rms log-err", best5.err.toFixed(3));

// the far cascade count can also be >1 (UE allows up to 4 far) - does an alternative do better?
for (const [N, F] of [[3, 2], [2, 3]]) {
  let b = { err: Infinity };
  for (let e = 1.2; e <= 4.0; e += 0.02)
    for (let R = 2000; R <= 22000; R += 200) {
      const s = ueSplits5(N, F, e, R, 32500);
      const err = logErr(s, MC);
      if (err < b.err) b = { err, e: +e.toFixed(2), R, s };
    }
  console.log(`N=${N}+F=${F}: exp ${b.e} R ${b.R}  ${b.s.map((v) => v.toFixed(0)).join(" / ")}  rms ${b.err.toFixed(3)}`);
}
