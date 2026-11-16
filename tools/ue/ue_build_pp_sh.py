"""Build M_PP_SH_Ambient: add SH sky irradiance on top of the scene colour.

Post-process material, Blendable Location = Scene Color Before Bloom, so the
ambient term lands in linear HDR and goes through the same tonemap as the rest
of the lighting.

    ambient = SH_Irradiance(N) * BaseColor * (1 - Metallic)
    out     = SceneColor + ambient * Enable_SH_Ambient

BaseColor and Metallic come from the GBuffer via SceneTexture:DiffuseColor, which
is what Substrate=False restores to a predictable layout. AO is left out on
purpose: the custom AO module multiplies it in later, and folding it in here
would count occlusion twice.

The SH evaluation lives in MF_SH_Irradiance (see hlsl/sh_irradiance.hlsl); this
script builds the surrounding graph. The equivalent single-Custom-node form is
hlsl/pp_sh_ambient.hlsl, kept for readability only; this builder intentionally
does not read it, because the shipped material uses the function call plus
Multiply/Add nodes shown below.
"""
import unreal

MAT = "/Game/Reconstruction/Rendering/_Restore/SH/M_PP_SH_Ambient.M_PP_SH_Ambient"
FUNC = "/Game/Reconstruction/Rendering/_Restore/SH/MF_SH_Irradiance.MF_SH_Irradiance"
MPC = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"

out = {}


def run():
    eas = unreal.EditorAssetLibrary
    lib = unreal.MaterialEditingLibrary
    mat = eas.load_asset(MAT)

    for e in list(lib.get_material_expressions(mat)):
        lib.delete_material_expression(mat, e)

    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location",
                            unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_BLOOM)

    collection = eas.load_asset(MPC)
    call = lib.create_material_expression(mat, unreal.MaterialExpressionMaterialFunctionCall, -400, 200)
    call.set_editor_property("material_function", eas.load_asset(FUNC))

    # --- normal from the GBuffer ---
    world_normal = lib.create_material_expression(
        mat, unreal.MaterialExpressionSceneTexture, -1200, -300
    )
    world_normal.set_editor_property("scene_texture_id",
                                     unreal.SceneTextureId.PPI_WORLD_NORMAL)
    # SceneTexture exposes float4; the function wants V3, so mask off alpha.
    mask = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -950, -300)
    mask.set_editor_property("r", True)
    mask.set_editor_property("g", True)
    mask.set_editor_property("b", True)
    mask.set_editor_property("a", False)
    lib.connect_material_expressions(world_normal, "Color", mask, "")
    out["normalWired"] = lib.connect_material_expressions(mask, "", call, "NormalWS (V3)")

    # --- SH coefficients ---
    for i, name in enumerate(["L0"] + [f"SH{j}" for j in range(7)]):
        node = lib.create_material_expression(
            mat, unreal.MaterialExpressionCollectionParameter, -1200, -150 + i * 90
        )
        node.set_editor_property("collection", collection)
        node.set_editor_property("parameter_name", name)
        pin = "L0 (V3)" if name == "L0" else f"{name} (V4)"
        for attempt in (pin, name):
            try:
                if lib.connect_material_expressions(node, "", call, attempt):
                    out.setdefault("shWired", []).append(attempt)
                    break
            except Exception:
                continue

    # --- intensity from the collection ---
    intensity = lib.create_material_expression(
        mat, unreal.MaterialExpressionCollectionParameter, -1200, 700
    )
    intensity.set_editor_property("collection", collection)
    intensity.set_editor_property("parameter_name", "SH_Intensity")
    # Scalar function inputs are pinned as "(S)".
    out["intensityWired"] = lib.connect_material_expressions(
        intensity, "", call, "Intensity (S)"
    )

    # --- enable flag ---
    enable = lib.create_material_expression(
        mat, unreal.MaterialExpressionCollectionParameter, -1200, 800
    )
    enable.set_editor_property("collection", collection)
    enable.set_editor_property("parameter_name", "Enable_SH_Ambient")

    # --- albedo and metallic from the GBuffer ---
    diffuse = lib.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -1200, 900)
    diffuse.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_DIFFUSE_COLOR)

    metallic = lib.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -1200, 1050)
    metallic.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_METALLIC)

    # (1 - metallic) masks the diffuse ambient: metal gets no diffuse irradiance.
    one_minus_metal = lib.create_material_expression(
        mat, unreal.MaterialExpressionOneMinus, -950, 1050
    )
    lib.connect_material_expressions(metallic, "Color", one_minus_metal, "")

    tint = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -750, 900)
    lib.connect_material_expressions(diffuse, "Color", tint, "A")
    lib.connect_material_expressions(one_minus_metal, "", tint, "B")

    # ambient = irradiance * albedo(approx) * (1-metallic)
    ambient = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -450, 600)
    lib.connect_material_expressions(call, "", ambient, "A")
    lib.connect_material_expressions(tint, "", ambient, "B")

    scaled = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 600)
    lib.connect_material_expressions(ambient, "", scaled, "A")
    lib.connect_material_expressions(enable, "", scaled, "B")

    # out = PostProcessInput0 + ambient * Enable
    # PPI_SCENE_COLOR is a Surface-only lookup; in a PostProcess material the
    # incoming image is PostProcessInput0.
    scene_color = lib.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -450, -100)
    scene_color.set_editor_property("scene_texture_id",
                                    unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)

    final = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, 50, 200)
    lib.connect_material_expressions(scene_color, "Color", final, "A")
    lib.connect_material_expressions(scaled, "", final, "B")
    lib.connect_material_property(final, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    lib.recompile_material(mat)
    eas.save_loaded_asset(mat)
    out["expressions"] = [e.get_class().get_name() for e in lib.get_material_expressions(mat)]
    out["done"] = True
    return out
