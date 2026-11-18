"""Build M_PP_CustomAO: screen-space AO, after the HLSL in hlsl/pp_custom_ao.hlsl.

Blendable Location = Before Bloom (SceneColor is still linear HDR, and the AO
multiply belongs in the lighting, ahead of bloom/tonemap). Reads its controls
from MPC_RestoreControl, like the other restore modules.

The Custom node body is read from hlsl/pp_custom_ao.hlsl (repository root);
set MC_REPO_ROOT if __file__ is unavailable.
"""
import os
import unreal

MAT_NAME = "M_PP_CustomAO"
PKG = "/Game/Reconstruction/Rendering/_Restore/AO"
MAT = f"{PKG}/{MAT_NAME}.{MAT_NAME}"
MPC = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"
INPUTS = ["Radius", "Intensity", "Enable", "DebugView", "SceneColor"]


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


def run():
    out = {}
    lib = unreal.MaterialEditingLibrary
    eas = unreal.EditorAssetLibrary
    with open(_hlsl("pp_custom_ao.hlsl"), "r", encoding="utf-8") as f:
        code = f.read()

    if eas.does_asset_exist(MAT):
        mat = eas.load_asset(MAT)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MAT_NAME, PKG, unreal.Material, unreal.MaterialFactoryNew())
    for e in list(lib.get_material_expressions(mat)):
        lib.delete_material_expression(mat, e)

    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    mat.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_BLOOM)

    coll = eas.load_asset(MPC)

    def mpc(name, y):
        n = lib.create_material_expression(mat, unreal.MaterialExpressionCollectionParameter, -900, y)
        n.set_editor_property("collection", coll)
        n.set_editor_property("parameter_name", name)
        return n

    radius = mpc("AO_Radius", 0)
    inten = mpc("AO_Intensity", 100)
    enable = mpc("Enable_Custom_AO", 200)
    dbg = mpc("AO_Debug_View", 300)

    scene = lib.create_material_expression(mat, unreal.MaterialExpressionSceneTexture, -900, 420)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    mask = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -650, 420)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        mask.set_editor_property(ch, on)
    lib.connect_material_expressions(scene, "Color", mask, "")

    custom = lib.create_material_expression(mat, unreal.MaterialExpressionCustom, -250, 150)
    custom.set_editor_property("code", code)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", "ScreenSpaceAO")
    items = []
    for n in INPUTS:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        items.append(ci)
    custom.set_editor_property("inputs", items)

    wires = [(radius, "Radius"), (inten, "Intensity"), (enable, "Enable"),
             (dbg, "DebugView"), (mask, "SceneColor")]
    out["wired"] = [f"{p}:{lib.connect_material_expressions(n, '', custom, p)}" for n, p in wires]

    lib.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat)
    eas.save_loaded_asset(mat)
    out["codeChars"] = len(code)
    return out
