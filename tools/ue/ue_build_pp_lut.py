"""Build M_PP_LUT: apply T_LUT_MC_SuiBo as a 32^3 strip lookup.

PostProcess material, Blendable Location = After Tonemapping, so the LUT sees
display-referred values, which is the space lut_bake.mjs indexes by.

Why a material and not the PostProcessVolume's Color Grading LUT slot: that slot
is already holding the project's Fuji LUT, and swapping it would destroy the
comparison baseline. The material also reads Enable_LUT from MPC_RestoreControl,
so on/off is the same switch pattern as the SH module.

The Custom node body is read from hlsl/pp_lut.hlsl (repository root) so there is
a single copy of the lookup maths; set MC_REPO_ROOT if __file__ is unavailable.
"""
import os
import unreal

MAT = "/Game/Reconstruction/Rendering/_Restore/LUT/M_PP_LUT.M_PP_LUT"
TEX = "/Game/Reconstruction/Rendering/_Restore/LUT/T_LUT_MC_SuiBo.T_LUT_MC_SuiBo"
MPC = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"


def _hlsl(name):
    root = os.environ.get("MC_REPO_ROOT")
    if root:
        base = os.path.join(root, "hlsl")
    else:
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            raise RuntimeError("cannot locate hlsl/: set MC_REPO_ROOT to the repository root")
        base = os.path.normpath(os.path.join(here, "..", "..", "hlsl"))
    path = os.path.join(base, name)
    if not os.path.isfile(path):
        raise RuntimeError("HLSL file not found: %s" % path)
    return path


with open(_hlsl("pp_lut.hlsl"), "r", encoding="utf-8") as f:
    CODE = f.read()

out = {}


def run():
    lib = unreal.MaterialEditingLibrary
    eas = unreal.EditorAssetLibrary

    if eas.does_asset_exist(MAT):
        mat = eas.load_asset(MAT)
    else:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mat = tools.create_asset("M_PP_LUT", "/Game/Reconstruction/Rendering/_Restore/LUT",
                                 unreal.Material, unreal.MaterialFactoryNew())
        out["created"] = True

    for e in list(lib.get_material_expressions(mat)):
        lib.delete_material_expression(mat, e)

    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location",
                            unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)

    collection = eas.load_asset(MPC)

    scene = lib.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -900, 0)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    mask = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -650, 0)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        mask.set_editor_property(ch, on)
    lib.connect_material_expressions(scene, "Color", mask, "")

    tex = lib.create_material_expression(mat, unreal.MaterialExpressionTextureObject, -900, 200)
    tex.set_editor_property("texture", eas.load_asset(TEX))
    tex.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)

    enable = lib.create_material_expression(mat, unreal.MaterialExpressionCollectionParameter, -900, 400)
    enable.set_editor_property("collection", collection)
    enable.set_editor_property("parameter_name", "Enable_LUT")

    custom = lib.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 100)
    custom.set_editor_property("code", CODE)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", "LUT_Lookup")
    items = []
    for n in ("SceneColor", "LUT", "Enable"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        items.append(ci)
    custom.set_editor_property("inputs", items)

    out["wired"] = [
        f"SceneColor:{lib.connect_material_expressions(mask, '', custom, 'SceneColor')}",
        f"LUT:{lib.connect_material_expressions(tex, '', custom, 'LUT')}",
        f"Enable:{lib.connect_material_expressions(enable, '', custom, 'Enable')}",
    ]

    lib.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat)
    eas.save_loaded_asset(mat)
    out["done"] = True
    return out
