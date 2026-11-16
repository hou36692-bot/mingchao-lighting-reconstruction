// M_PP_RestoreDebugViz — debug overlays for the CSM / light-grid comparison modules.
// Custom Node body, Post Process material, output to Emissive Color.
//
// Inputs: SceneColor (float3), Mode, CsmExp, CsmDist, CsmCount
//   Mode 0 : passthrough
//   Mode 1 : Wuthering Waves cascade bands, far planes 800/2000/6500/15000/32500cm (ps1024669 cb0[53..57])
//   Mode 2 : UE cascade bands, UE's GetSplitDistance with (CsmExp, CsmDist, CsmCount)
//   Mode 3 : light-grid cells: 64px tiles + 32 exponential Z slices,
//            slice = log2(z*B + O)*S, (B,O,S) = (0.00432649, 0.915633, 4.05)  (cs1073371 cb2[4])
float3 c = SceneColor;
if (Mode < 0.5) return c;

float z = SceneTextureFetch(1, float2(0, 0)).r;           // PPI_SceneDepth: linear view depth, cm
float2 px = GetPixelPosition(Parameters);

float3 pal[6] = { float3(1.0, 0.25, 0.25), float3(1.0, 0.85, 0.2), float3(0.25, 1.0, 0.35),
                  float3(0.2, 0.75, 1.0), float3(0.75, 0.35, 1.0), float3(0.15, 0.15, 0.15) };

if (Mode < 2.5)
{
    float split[5];
    if (Mode < 1.5)
    {
        split[0] = 800; split[1] = 2000; split[2] = 6500; split[3] = 15000; split[4] = 32500;
    }
    else
    {
        // UE DirectionalLightComponent GetSplitDistance / ComputeAccumulatedScale:
        // split(i) = near + (sum_{k<i} e^k / sum_{k<N} e^k) * (R - near)
        float n = max(CsmCount, 1.0);
        float nearZ = 10.0;
        float total = (abs(CsmExp - 1.0) < 1e-4) ? n : (pow(CsmExp, n) - 1.0) / (CsmExp - 1.0);
        [unroll] for (int k = 0; k < 5; k++)
        {
            float i = k + 1.0;
            float acc = (abs(CsmExp - 1.0) < 1e-4) ? i : (pow(CsmExp, i) - 1.0) / (CsmExp - 1.0);
            split[k] = (i <= n) ? nearZ + acc / total * (CsmDist - nearZ) : -1.0;
        }
    }
    int idx = 5;
    [unroll] for (int j = 4; j >= 0; j--)
    {
        if (split[j] > 0.0 && z < split[j]) idx = j;
    }
    return lerp(c, pal[idx], 0.45);
}

// Mode 3: light-grid cell
float slice = clamp(floor(log2(z * 0.00432649 + 0.915633) * 4.05), 0.0, 31.0);
float h = slice / 32.0;
float3 hue = saturate(abs(frac(h + float3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0);
float2 t = floor(px / 64.0);
float checker = fmod(t.x + t.y, 2.0);
float3 o = lerp(c, hue * (0.75 + 0.25 * checker), 0.5);
float2 f = fmod(px, 64.0);
if (f.x < 1.0 || f.y < 1.0) o = float3(1, 1, 1);
return o;
