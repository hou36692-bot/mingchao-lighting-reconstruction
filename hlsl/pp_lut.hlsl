// M_PP_LUT — apply T_LUT_MC_SuiBo as a 32^3 strip lookup.
//
// Custom Node body for a Post Process material at
// Blendable Location = Scene Color After Tonemapping, so the LUT sees
// display-referred values, which is the space lut_bake.mjs indexes by.
// Output goes to Emissive Color.
//
// Inputs (Custom node pin order):
//   SceneColor float3  PostProcessInput0.rgb
//   LUT        Texture 32x1024 strip: tile = blue, row = green, column in tile = red
//   Enable     float   MPC_RestoreControl.Enable_LUT (lerps between original and graded)
//
// The lookup is a manual trilinear fetch on the 1024x32 strip:
//     slice = b * 31, lerp between floor/ceil slice
//     uv.x  = (slice*32 + r*31 + 0.5) / 1024
//     uv.y  = (g*31 + 0.5) / 32

float3 c = saturate(SceneColor);
float size = 32.0;
float maxIdx = size - 1.0;

float bSlice = c.b * maxIdx;
float s0 = floor(bSlice);
float s1 = min(s0 + 1.0, maxIdx);
float t  = bSlice - s0;

float u0 = (s0 * size + c.r * maxIdx + 0.5) / (size * size);
float u1 = (s1 * size + c.r * maxIdx + 0.5) / (size * size);
float v  = (c.g * maxIdx + 0.5) / size;

float3 a = Texture2DSampleLevel(LUT, LUTSampler, float2(u0, v), 0).rgb;
float3 b = Texture2DSampleLevel(LUT, LUTSampler, float2(u1, v), 0).rgb;
float3 graded = lerp(a, b, t);

return lerp(SceneColor, graded, saturate(Enable));
