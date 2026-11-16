# HLSL — UE Custom Node bodies

These files are **not standalone shaders**. Each one is the `Code` string of an
Unreal Engine `MaterialExpressionCustom` node (or, for `sh_irradiance.hlsl`, the
body of a material function's Custom node). UE wraps the body with its own
preamble and the input declarations derived from the node's `Inputs` list, so
symbols such as `SceneTextureFetch`, `ResolvedView`, `View`, `Parameters` and
`GetPixelPosition` are provided by the engine, not by these files.

Consequences:

- No `#include`, no `main`, no cbuffer declarations — do not compile these with
  `dxc`/`fxc` directly.
- Pin order matters: the `Inputs` list on the Custom node must match the input
  order documented at the top of each file. UE appends the input name as the
  variable name, so renaming a pin breaks the body.
- All materials here are Post Process materials. Their output goes to Emissive
  Color; `SceneColor` is `PostProcessInput0.rgb` unless stated otherwise.

| File | Used by (UE asset) | Domain / blendable location | Output |
| --- | --- | --- | --- |
| `sh_irradiance.hlsl` | `MF_SH_Irradiance` (function used by `M_PP_SH_Ambient`) | Material function, no domain | `float3` irradiance |
| `pp_sh_ambient.hlsl` | `M_PP_SH_Ambient` | Post Process, Scene Color Before Bloom | `float3` colour |
| `pp_custom_ao.hlsl` | `M_PP_CustomAO` | Post Process, Scene Color Before Bloom | `float3` colour |
| `pp_lut.hlsl` | `M_PP_LUT` | Post Process, Scene Color After Tonemapping | `float3` colour |
| `debug_viz.hlsl` | `M_PP_RestoreDebugViz` | Post Process (debug overlay) | `float3` colour |

Asset root: `/Game/Reconstruction/Rendering/_Restore/`
(`SH/M_PP_SH_Ambient`, `SH/MF_SH_Irradiance`, `AO/M_PP_CustomAO`, `LUT/M_PP_LUT`,
`Common/M_PP_RestoreDebugViz`). The repository does not ship the `.uasset`
files; the Python builders in `../tools/ue/` recreate the material graphs.

## Files

### `sh_irradiance.hlsl`

L1 + L2 real spherical-harmonic evaluation of sky irradiance. Inputs: world
normal, `L0` (float3 DC term), `SH0..SH6` (one float4 per band, `.rgb`), and a
scalar `Intensity` that is applied outside the raw coefficients. The DC term is
carried as its own float3 instead of being packed into the float4 alpha lanes,
so R/G/B keep independent constant terms; this is a deliberate difference from
the source implementation, documented in the file header.

### `pp_sh_ambient.hlsl`

The whole SH ambient pass as a single Custom node: evaluates the same SH
polynomial, multiplies by albedo and `(1 - metallic)`, scales by
`Enable_SH_Ambient`, and adds the result to `SceneColor`. In the shipped asset
the SH part is a `MaterialFunctionCall` to `MF_SH_Irradiance` plus Multiply/Add
nodes (`tools/ue/ue_build_pp_sh.py`); this file is the equivalent one-node
expression.

### `pp_custom_ao.hlsl`

Screen-space AO, 8 directions x 4 steps per pixel, with interleaved gradient
noise rotation. Reads linear scene depth (`SceneTextureFetch(1, ...)`) and world
normals (`SceneTextureFetch(8, ...)`), skips sky and unlit pixels, and exposes a
greyscale debug output. Constants marked `ps1563` are from the Wuthering Waves
source frame of the same name.

### `pp_lut.hlsl`

Manual trilinear fetch from a 32x1024 LUT strip (blue slice on X, green on Y,
red inside each tile). Lerps between the original and graded colour with
`Enable_LUT`, so the module can be toggled without touching the Post Process
Volume's Color Grading LUT slot.

### `debug_viz.hlsl`

Debug overlay for the cascade and clustered-light comparisons: Wuthering Waves
cascade bands, UE's own `GetSplitDistance` bands, and the 64 px / 32-slice light
grid. Values marked `ps1024669` / `cs1073371` are source frame references.

## Editing

If you change a body here, re-run the matching builder in `../tools/ue/`
(`ue_build_pp_ao.py`, `ue_build_pp_lut.py`, or `ue_build_pp_generic.py`) so the
Custom node string in the material is refreshed; those builders read these files
from disk rather than embedding a second copy. `ue_build_pp_sh.py` instead builds
the SH pass from `MF_SH_Irradiance` plus graph nodes, so `pp_sh_ambient.hlsl` is
the reference single-node form of that graph, not an input to the builder.
