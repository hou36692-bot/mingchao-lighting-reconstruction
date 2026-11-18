# HLSL: UE Custom node bodies

These files are not standalone shaders. Each one is the `Code` string of an Unreal Engine `MaterialExpressionCustom` node. UE wraps the body with its own preamble and declares one variable per entry in the node's `Inputs` list, so symbols such as `SceneTextureFetch`, `ResolvedView`, `View`, `Parameters` and `GetPixelPosition` come from the engine.

That means:

- There is no `#include`, `main` or cbuffer declaration, so the files cannot be compiled with `dxc` or `fxc` directly.
- The `Inputs` list on the Custom node must use the names listed at the top of each file. UE turns each pin name into a variable name, so renaming a pin breaks the body.
- Both materials are post-process materials. Their output goes to Emissive Color, and `SceneColor` is `PostProcessInput0.rgb`.

| File | UE asset | Blendable location | Output |
| --- | --- | --- | --- |
| `pp_custom_ao.hlsl` | `M_PP_CustomAO` | Scene Color Before Bloom | `float3` colour |
| `debug_viz.hlsl` | `M_PP_RestoreDebugViz` | Scene Color After Tonemapping | `float3` colour |

The assets live under `/Game/Reconstruction/Rendering/_Restore/` (`AO/M_PP_CustomAO`, `Common/M_PP_RestoreDebugViz`). The repository does not ship the `.uasset` files; the Python builders in `../tools/ue/` recreate the material graphs.

## pp_custom_ao.hlsl

Screen-space AO with 8 directions and 4 steps per pixel, rotated per pixel by interleaved gradient noise. It reads linear scene depth (`SceneTextureFetch(1, ...)`) and world normals (`SceneTextureFetch(8, ...)`), skips sky and unlit pixels, and has a greyscale debug output. Constants marked `ps1563` come from the source frame's AO shader of that name.

## debug_viz.hlsl

Debug overlay for the shadow and clustered-lighting comparisons. It can draw the source frame's cascade bands, UE's own cascade bands (from `GetSplitDistance`), or the 64 px / 32-slice light grid. Values marked `ps1024669` and `cs1073371` refer to the source frame's shaders.

## Editing

After changing a body here, re-run the matching builder in `../tools/ue/` (`ue_build_pp_ao.py` for AO, `ue_build_pp_generic.py` for the debug overlay) so the Custom node string in the material is refreshed. The builders read these files from disk instead of keeping a second copy.
