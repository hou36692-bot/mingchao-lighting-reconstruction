// SH sky irradiance for MF_SH_Irradiance's Custom node.
//
// This is a Custom Node body, not a standalone shader. The material function
// exposes one input pin per symbol below; UE prepends the declarations.
//
// Inputs (Custom node pin order):
//   NormalWS  float3  world-space normal (masked from PPI_WORLD_NORMAL)
//   L0        float3  DC term, per channel
//   SH0..SH6  float4  L1/L2 coefficients packed one band per float4 (.rgb used)
//   Intensity float   SH_Intensity from MPC_RestoreControl
// Output: float3 irradiance
//
// Basis: real SH, L1 + L2, matching the Wuthering Waves source frame ps1037297
// (instr 133-154):
//     L1  = SH0*n.x + SH1*n.y + SH2*n.z
//     L2  = SH3*(n.y*n.z) + SH4*(n.x*n.z) + SH5*(n.x*n.y) + SH6*(n.x*n.x - n.y*n.y)
//     E   = max(0, L0 + L1 + L2)
//
// DELIBERATE DIFFERENCE from the source: the game packs the L0 constant into the
// .a lanes of its float4s, which only works because a scalar broadcasts across
// rgb and therefore cannot carry per-channel colour. We carry L0 as its own
// float3 input so R/G/B keep independent DC terms, and the .a lanes stay unused.
//
// Intensity is folded in by the caller (MPC_RestoreControl.SH_Intensity) rather
// than baked here, so the coefficients stay raw and inspectable.

float3 n = normalize(NormalWS);

float3 L1 = SH0.rgb * n.x + SH1.rgb * n.y + SH2.rgb * n.z;

float3 L2 = SH3.rgb * (n.y * n.z)
          + SH4.rgb * (n.x * n.z)
          + SH5.rgb * (n.x * n.y)
          + SH6.rgb * (n.x * n.x - n.y * n.y);

float3 E = L0 + L1 + L2;

return max(float3(0.0, 0.0, 0.0), E * Intensity);
