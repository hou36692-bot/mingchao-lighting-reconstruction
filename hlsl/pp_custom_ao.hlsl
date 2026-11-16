// M_PP_CustomAO — screen-space ambient occlusion, 8 directions x 4 steps.
//
// Custom Node body for a Post Process material at
// Blendable Location = Scene Color Before Bloom (SceneColor is still linear HDR,
// and the AO multiply belongs in the lighting, ahead of bloom/tonemap).
// Output goes to Emissive Color.
//
// Inputs (Custom node pin order):
//   Radius     float  world-space sampling radius (cm), MPC AO_Radius
//   Intensity  float  occlusion falloff exponent, MPC AO_Intensity
//   Enable     float  0..1 blend of the AO multiply, MPC Enable_Custom_AO
//   DebugView  float  >= 0.5 returns AO as greyscale, MPC AO_Debug_View
//   SceneColor float3 PostProcessInput0.rgb
//
// SceneTextureFetch ids used below: 1 = PPI_SceneDepth, 8 = PPI_WorldNormal,
// 23 = PPI_ShadingModelID.

// ---- constants (Wuthering Waves source frame ps1563 unless noted) -------------
const int   DIRS  = 8;
const int   STEPS = 4;
const float FAR_CUTOFF = 700000.0;                       // ps1563: viewZ > 700000 -> 1
const float STEP_FRAC[4] = { 0.1666667, 0.3333333, 0.5, 1.0 };   // 1/36,1/18,1/12,1/6 normalised

// ---- centre pixel ------------------------------------------------------------
float  d0 = SceneTextureFetch(1, float2(0, 0)).r;        // PPI_SceneDepth
float4 smSample = SceneTextureFetch(23, float2(0, 0));   // PPI_ShadingModelID
float  sm = smSample.r;

// Water (sm==10) and the special shading models 12..15 are forced to AO=1 (ps1563 instr 17-23).
// UE's own ids: sky/unlit materials have no GBuffer normal, so they also skip.
bool skip = (d0 <= 0.0) || (d0 > FAR_CUTOFF);
// UE shading model ids: 0 unlit, 1 default lit, ... ; unlit/sky have no valid normal.
skip = skip || (sm < 0.5);

float ao = 1.0;

if (!skip)
{
    // ---- view-space position of this pixel ---------------------------------
    float2 tanHalf = float2(1.0 / ResolvedView.ViewToClip[0][0], 1.0 / ResolvedView.ViewToClip[1][1]);
    float2 vpSize  = View.ViewSizeAndInvSize.xy;

    float2 pixelPos = GetPixelPosition(Parameters);                  // centre of this pixel, in pixels
    float2 ndc0 = float2((pixelPos.x + 0.5) / vpSize.x * 2.0 - 1.0,
                         1.0 - (pixelPos.y + 0.5) / vpSize.y * 2.0);
    float3 P = float3(ndc0 * tanHalf * d0, d0);

    // ---- view-space normal --------------------------------------------------
    // PPI_WorldNormal is the unpacked world-space normal (-1..1). Rotate it into
    // view space with the view matrix's rotation part.
    float3 Nw = normalize(SceneTextureFetch(8, float2(0, 0)).xyz);
    float3 N  = normalize(mul(Nw, (float3x3)ResolvedView.TranslatedWorldToView));

    // ---- per-pixel rotation: interleaved gradient noise ---------------------
    float f   = 0.06711056 * pixelPos.x + 0.00583715 * pixelPos.y;
    float ign = frac(52.9829189 * frac(f));
    float rot = ign * 6.2831853;

    float3 up  = (abs(N.y) < 0.99) ? float3(0, 1, 0) : float3(1, 0, 0);
    float3 t0  = normalize(cross(up, N));
    float3 b0  = cross(N, t0);

    float occl  = 0.0;
    float count = 0.0;

    [loop] for (int i = 0; i < DIRS; i++)
    {
        float a    = rot + (float(i) / float(DIRS)) * 6.2831853;
        float tilt = 0.35 + 0.65 * float(i & 1);
        float3 tdir = t0 * cos(a) + b0 * sin(a);
        float3 dir  = normalize(tdir * (1.0 - tilt * 0.5) + N * (tilt * 0.5));

        [unroll] for (int s = 0; s < STEPS; s++)
        {
            float  dist = Radius * STEP_FRAC[s];
            float3 S    = P + dir * dist;
            count += 1.0;
            if (S.z <= 1e-3) continue;

            // project to a pixel offset from the centre pixel
            float2 ndcS = S.xy / (tanHalf * S.z);
            float2 pS   = float2(ndcS.x * 0.5 + 0.5, 0.5 - ndcS.y * 0.5) * vpSize - 0.5;
            float2 off  = round(pS - (pixelPos));
            float2 pix  = pixelPos + off;
            if (pix.x < 0 || pix.y < 0 || pix.x >= vpSize.x || pix.y >= vpSize.y) continue;

            float sceneZ = SceneTextureFetch(1, off).r;
            if (sceneZ <= 0.0) continue;                                // sky

            float footprint = (S.z * 2.0 * tanHalf.y) / vpSize.y;       // depth one pixel can hide
            float bias = footprint * 1.5 / max(0.5, abs(dot(N, normalize(P))));
            float diff = S.z - sceneZ;
            if (diff > bias)
            {
                float range = max(0.0, 1.0 - abs(P.z - sceneZ) / (Radius * 2.0));
                occl += range * min(1.0, diff / (Radius * 0.25));
            }
        }
    }

    ao = pow(max(0.0, 1.0 - occl / count), Intensity);
}

float3 shaded = SceneColor * lerp(1.0, ao, saturate(Enable));
float3 dbg    = float3(ao, ao, ao);
return lerp(shaded, dbg, step(0.5, DebugView));
