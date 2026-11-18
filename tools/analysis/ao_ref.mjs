// Reference implementation of the screen-space AO, on the CPU.
//
// This is the source of truth for the algorithm. The HLSL in M_PP_CustomAO is a
// transcription of ao_core() below, and tools/analysis/ao_test.mjs checks the maths on
// synthetic scenes with known answers before any of it goes near the GPU.
//
// Wuthering Waves source AO (shader ps1559/1561/1563):
//   * screen-space raymarch in the normal hemisphere, 8 directions x 4 steps  [事实]
//   * a 64x64 rotation-noise texture (R815) scrambles the directions per pixel [事实]
//   * radius cb0[28].x = 15, strength cb0[29].x = 4, step ladder 1/36..1/6     [事实]
//   * result pow(1 - occl, cb0[27].x)                                          [事实]
//   * sm in {12,13,14,15} and sm==10 (water) -> AO = 1                         [事实]
//   * viewZ > 700000 (7km) -> AO = 1                                           [事实]
//   * three passes 540p -> 1080p -> 4K, temporal lerp(prev, new, 0.2)          [事实]
//
// What is NOT reproduced (stated, not hidden):
//   * the 3-level pyramid and the temporal accumulation: a post-process material
//     has no previous-frame buffer and no way to run at 1/4 and 1/2 resolution.
//     The single pass here uses more rotations instead of more passes.
//   * R815 itself: the noise is an interleaved-gradient hash, not their texture.
//
// Conventions: view space, +X right, +Y up, +Z forward (UE: depth grows along +Z).
// A pixel is (x, y, depth) with depth = distance along the camera Z axis.

export const DIRECTIONS = 8;
export const STEPS = 4;

// Interleaved gradient noise (Jimenez). Cheap, no texture, well distributed.
export function ign(px, py) {
  const f = 0.06711056 * px + 0.00583715 * py;
  const g = 52.9829189 * (f - Math.floor(f));
  return g - Math.floor(g);
}

// Step ladder: mirrors the (1/36, 1/18, 1/12, 1/6) the shader steps through,
// i.e. offsets grow roughly quadratically so the near field is sampled densely.
export const STEP_FRACTIONS = [1 / 36, 1 / 18, 1 / 12, 1 / 6].map((v) => v * 6); // normalised so the last step = 1.0

/**
 * Occlusion for one pixel.
 *
 * scene.depthAt(x, y) -> view depth at integer pixel, or Infinity off-screen/sky
 * scene.normalAt(x, y) -> unit view-space normal
 * cam = { fovY, width, height }
 *
 * @returns ao in [0,1], 1 = unoccluded
 */
export function aoCore(scene, cam, x, y, radius, intensity) {
  const d = scene.depthAt(x, y);
  if (!isFinite(d)) return 1;
  if (d > 700000) return 1; // ps1563: 7km far cutoff

  const tanHalf = Math.tan(cam.fovY / 2);
  const aspect = cam.width / cam.height;
  // pixel -> view-space position
  const toView = (px, py, depth) => [
    ((px + 0.5) / cam.width * 2 - 1) * tanHalf * aspect * depth,
    (1 - (py + 0.5) / cam.height * 2) * tanHalf * depth,
    depth,
  ];
  const toPixel = (v) => [
    ((v[0] / (tanHalf * aspect * v[2])) * 0.5 + 0.5) * cam.width - 0.5,
    (0.5 - (v[1] / (tanHalf * v[2])) * 0.5) * cam.height - 0.5,
  ];

  const P = toView(x, y, d);
  const N = scene.normalAt(x, y);

  // Orthonormal basis around N, rotated per pixel by the noise.
  const up = Math.abs(N[1]) < 0.99 ? [0, 1, 0] : [1, 0, 0];
  const t0 = norm(cross(up, N));
  const b0 = cross(N, t0);
  const rot = ign(x, y) * 2 * Math.PI;

  let occl = 0;
  let count = 0;

  for (let i = 0; i < DIRECTIONS; i++) {
    const a = rot + (i / DIRECTIONS) * 2 * Math.PI;
    // direction in the tangent plane, tilted up into the hemisphere
    const tilt = 0.35 + 0.65 * ((i % 2) / 1); // alternate low / high elevation
    const tdir = add(scale(t0, Math.cos(a)), scale(b0, Math.sin(a)));
    const dir = norm(add(scale(tdir, 1 - tilt * 0.5), scale(N, tilt * 0.5 + 0.0)));

    for (let s = 0; s < STEPS; s++) {
      const dist = radius * STEP_FRACTIONS[s];
      const S = add(P, scale(dir, dist));
      if (S[2] <= 1e-3) { count++; continue; }
      const [sx, sy] = toPixel(S);
      const ix = Math.round(sx), iy = Math.round(sy);
      if (ix < 0 || iy < 0 || ix >= cam.width || iy >= cam.height) { count++; continue; }

      const sceneZ = scene.depthAt(ix, iy);
      count++;
      if (!isFinite(sceneZ)) continue;

      // Occluded if the geometry at that pixel is in front of the sample point.
      // The bias must scale with how much depth one pixel can hide at this
      // distance, not with the AO radius: a surface seen at a grazing angle
      // changes depth a lot per pixel, and snapping the sample to the pixel grid
      // (Math.round above) then reads a slightly different depth than the true
      // surface -> a flat floor would occlude itself. Pixel footprint at depth z
      // is z*2*tanHalf/height; grazing surfaces multiply it by ~1/|N.V|.
      const px = (S[2] * 2 * tanHalf) / cam.height;
      const bias = px * 1.5 / Math.max(0.5, Math.abs(dot(N, norm(P))));
      const diff = S[2] - sceneZ;
      if (diff > bias) {
        // fall off to 0 when the occluder is much farther than the radius away
        const range = Math.max(0, 1 - Math.abs(P[2] - sceneZ) / (radius * 2));
        occl += range * Math.min(1, diff / (radius * 0.25));
      }
    }
  }

  const raw = Math.max(0, 1 - occl / count);
  return Math.pow(raw, intensity);
}

// --- tiny vec helpers (arrays) ---
function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
function scale(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
function norm(a) { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
