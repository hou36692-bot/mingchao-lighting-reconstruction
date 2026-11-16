// M_PP_SH_Ambient — combined Custom Node equivalent of the material graph.
//
// The shipped asset builds this from a MaterialFunctionCall to MF_SH_Irradiance
// plus Multiply/Add nodes (see tools/ue/ue_build_pp_sh.py). This file is the
// same arithmetic expressed as one Custom node body, kept for readability:
//
//     ambient = SH_Irradiance(N) * Albedo * (1 - Metallic)
//     out     = SceneColor + ambient * Enable
//
// Material: Post Process, Blendable Location = Scene Color Before Bloom, so the
// ambient term lands in linear HDR and goes through the same tonemap as the
// rest of the lighting. Output goes to Emissive Color.
//
// Inputs (Custom node pin order):
//   SceneColor float3  PostProcessInput0.rgb
//   NormalWS   float3  PPI_WORLD_NORMAL.rgb
//   Albedo     float3  PPI_DIFFUSE_COLOR.rgb (upright GBuffer with Substrate off)
//   Metallic   float   PPI_METALLIC.r
//   L0         float3  DC SH term
//   SH0..SH6   float4  L1/L2 coefficients
//   Intensity  float   MPC_RestoreControl.SH_Intensity
//   Enable     float   MPC_RestoreControl.Enable_SH_Ambient
//
// AO is intentionally not folded in here: M_PP_CustomAO multiplies it in later,
// and applying it twice would double-count occlusion.

float3 n = normalize(NormalWS);

float3 L1 = SH0.rgb * n.x + SH1.rgb * n.y + SH2.rgb * n.z;

float3 L2 = SH3.rgb * (n.y * n.z)
          + SH4.rgb * (n.x * n.z)
          + SH5.rgb * (n.x * n.y)
          + SH6.rgb * (n.x * n.x - n.y * n.y);

float3 E = max(float3(0.0, 0.0, 0.0), (L0 + L1 + L2) * Intensity);

// Metal gets no diffuse irradiance.
float3 ambient = E * Albedo * (1.0 - saturate(Metallic));

return SceneColor + ambient * saturate(Enable);
