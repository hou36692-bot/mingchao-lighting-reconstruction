"""Generic builder: PostProcess material = one Custom node fed by MPC_RestoreControl scalars.

args: <assetPath> <hlslFile> <blendableLocation> <Input=MPCParam>... [--register]
  blendableLocation: after_tonemap | before_bloom | before_tonemap
  'SceneColor' input is always wired from PostProcessInput0 (rgb).
  --register : add the material to APPROX_Daylight_Exposure's blendables (weight 1).
"""
import unreal

MPC = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"
PPV = "APPROX_Daylight_Exposure"
LOC = {"after_tonemap": unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING,
       "before_bloom": unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_BLOOM,
       "before_tonemap": unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_DOF}


def run(*argv):
    path, hlsl, loc = argv[0], argv[1], argv[2]
    register = "--register" in argv
    wires = [a.split("=", 1) for a in argv[3:] if "=" in a]
    lib = unreal.MaterialEditingLibrary
    eal = unreal.EditorAssetLibrary
    pkg, name = path.rsplit("/", 1)
    with open(hlsl, "r", encoding="utf-8") as f:
        code = f.read()
    full = f"{path}.{name}"
    if eal.does_asset_exist(full):
        mat = eal.load_asset(full)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, pkg, unreal.Material, unreal.MaterialFactoryNew())
    for e in list(lib.get_material_expressions(mat)):
        lib.delete_material_expression(mat, e)
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location", LOC[loc])
    coll = eal.load_asset(MPC)

    custom = lib.create_material_expression(mat, unreal.MaterialExpressionCustom, -250, 0)
    custom.set_editor_property("code", code)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", name)
    names = [w[0] for w in wires] + ["SceneColor"]
    items = []
    for n in names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        items.append(ci)
    custom.set_editor_property("inputs", items)

    out = {"wired": []}
    y = -200
    for pin, param in wires:
        n = lib.create_material_expression(mat, unreal.MaterialExpressionCollectionParameter, -800, y)
        n.set_editor_property("collection", coll)
        n.set_editor_property("parameter_name", param)
        out["wired"].append(f"{pin}<-{param}:{lib.connect_material_expressions(n, '', custom, pin)}")
        y += 100
    scene = lib.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -800, y + 50)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    mask = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -550, y + 50)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        mask.set_editor_property(ch, on)
    lib.connect_material_expressions(scene, "Color", mask, "")
    out["wired"].append(f"SceneColor:{lib.connect_material_expressions(mask, '', custom, 'SceneColor')}")
    lib.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat)
    eal.save_loaded_asset(mat)

    if register:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for a in eas.get_all_level_actors():
            if a.get_actor_label() == PPV:
                s = a.get_editor_property("settings")
                wb = s.get_editor_property("weighted_blendables")
                arr = list(wb.get_editor_property("array"))
                if not any(x.get_editor_property("object") == mat for x in arr):
                    b = unreal.WeightedBlendable()
                    b.set_editor_property("weight", 1.0)
                    b.set_editor_property("object", mat)
                    arr.append(b)
                    wb.set_editor_property("array", arr)
                    s.set_editor_property("weighted_blendables", wb)
                    a.set_editor_property("settings", s)
                out["blendables"] = [str(x.get_editor_property("object").get_name()) for x in arr if x.get_editor_property("object")]
    return out
