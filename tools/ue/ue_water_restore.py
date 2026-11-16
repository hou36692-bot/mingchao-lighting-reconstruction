"""Module 6 (water): restore copy of the SLW water with source scattering/absorption switchable by MPC.

args: build | assign | unassign | enable <0|1>

build : duplicate M_WaterMain_SLW / MI_WaterMain_SLW into _Restore/Water and wire
        SLW.Scattering  = lerp(0,                      MC_Scattering_1PerCm, Enable_Water_Absorb)
        SLW.Absorption  = lerp(<original UE approx>,   MC_Absorption_1PerCm, Enable_Water_Absorb)
        SLW.PhaseG      = lerp(0 (pin was unwired),    MC_PhaseG,            Enable_Water_Absorb)
        Source values: ps1072812 (E22261) cb4[27] / cb4[32] / cb4[51].w
enable <0|1>: set the switch (MI scalar + MPC mirror)
assign: put MI_Water_Restore_SLW on the level's SLW water actor (this level only)
unassign: put the original MI back
"""
import unreal

SRC_M = "/Game/Reconstruction/Rendering/Water/Surface/Opaque/SingleLayerWater/M_WaterMain_SLW"
SRC_MI = "/Game/Reconstruction/Rendering/Water/Surface/Opaque/SingleLayerWater/MI_WaterMain_SLW"
DST_M = "/Game/Reconstruction/Rendering/_Restore/Water/M_Water_Restore_SLW"
DST_MI = "/Game/Reconstruction/Rendering/_Restore/Water/MI_Water_Restore_SLW"
MPC = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"
ACTOR = "SRC_Environment_SM_Old_Wat_08AH_3ad68845"

MC_SCATTER = (3.01013e-05, 8.3246e-05, 0.0001)      # cb4[27] (1/cm)
MC_ABSORB = (0.0166667, 0.0166667, 0.0166667)       # cb4[32] (1/cm) = 1/60
MC_PHASE_G = 0.5                                     # cb4[51].w


def _build():
    eal = unreal.EditorAssetLibrary
    lib = unreal.MaterialEditingLibrary
    out = {}
    for d in (DST_M, DST_MI):
        if eal.does_asset_exist(d):
            eal.delete_asset(d)
    mat = eal.duplicate_asset(SRC_M, DST_M)
    mi = eal.duplicate_asset(SRC_MI, DST_MI)
    lib.set_material_instance_parent(mi, mat)

    exprs = lib.get_material_expressions(mat)
    slw = [e for e in exprs if isinstance(e, unreal.MaterialExpressionSingleLayerWaterMaterialOutput)][0]
    ins = lib.get_inputs_for_material_expression(mat, slw)
    names = [str(n) for n in lib.get_material_expression_input_names(slw)]
    out["slw_inputs"] = {n: (i.get_name() if i else None) for n, i in zip(names, ins)}
    absorb_src = ins[names.index("AbsorptionCoefficients")] if "AbsorptionCoefficients" in names else None

    x, y = slw.get_editor_property("material_expression_editor_x") - 700, slw.get_editor_property("material_expression_editor_y") + 500
    # The water already references 2 MPCs (UE's per-material limit), so the switch is an instance
    # parameter; "enable" below mirrors it into MPC_RestoreControl.Enable_Water_Absorb.
    en = lib.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x - 400, y + 300)
    en.set_editor_property("parameter_name", "Enable_Water_Absorb")
    en.set_editor_property("default_value", 0.0)
    en.set_editor_property("group", "WW Restore (Water)")

    def vparam(name, val, yy, desc):
        p = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, x - 400, yy)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", unreal.LinearColor(val[0], val[1], val[2], 0.0))
        p.set_editor_property("group", "WW Restore (Water)")
        p.set_editor_property("desc", desc)
        return p

    sc = vparam("MC_Scattering_1PerCm", MC_SCATTER, y, "[source fact] ps1072812 cb4[27]: scattering coefficient, 1/cm")
    ab = vparam("MC_Absorption_1PerCm", MC_ABSORB, y + 150, "[source fact] ps1072812 cb4[32]: absorption coefficient, 1/cm (=1/60)")
    g = lib.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x - 400, y + 450)
    g.set_editor_property("parameter_name", "MC_PhaseG")
    g.set_editor_property("default_value", MC_PHASE_G)
    g.set_editor_property("group", "WW Restore (Water)")
    g.set_editor_property("desc", "[source fact] ps1072812 cb4[51].w: Schlick phase g")
    zero3 = lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, x - 400, y - 150)
    zero1 = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, x - 400, y + 600)

    def lerp(a, b, yy):
        l = lib.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, x, yy)
        lib.connect_material_expressions(a, "", l, "A")
        lib.connect_material_expressions(b, "", l, "B")
        lib.connect_material_expressions(en, "", l, "Alpha")
        return l

    l_sc = lerp(zero3, sc, y)
    l_ab = lerp(absorb_src if absorb_src else zero3, ab, y + 150)
    l_g = lerp(zero1, g, y + 450)
    out["wire"] = [
        lib.connect_material_expressions(l_sc, "", slw, "ScatteringCoefficients"),
        lib.connect_material_expressions(l_ab, "", slw, "AbsorptionCoefficients"),
        lib.connect_material_expressions(l_g, "", slw, "PhaseG"),
    ]
    lib.recompile_material(mat)
    eal.save_loaded_asset(mat)
    eal.save_loaded_asset(mi)
    after = lib.get_inputs_for_material_expression(mat, slw)
    out["slw_inputs_after"] = {n: (i.get_name() if i else None) for n, i in zip(names, after)}
    return out


def _assign(path):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mi = unreal.EditorAssetLibrary.load_asset(path)
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == ACTOR:
            c = a.get_component_by_class(unreal.StaticMeshComponent)
            n = c.get_num_materials()
            for i in range(n):
                c.set_material(i, mi)
            return {"actor": ACTOR, "slots": n, "material": path}
    return {"error": "actor not found"}


def run(*argv):
    mode = argv[0] if argv else "build"
    if mode == "build":
        return _build()
    if mode == "enable":
        v = float(argv[1])
        mi = unreal.EditorAssetLibrary.load_asset(DST_MI)
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Enable_Water_Absorb", v)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        mpc = unreal.EditorAssetLibrary.load_asset(MPC)
        sc = list(mpc.get_editor_property("scalar_parameters"))
        for p in sc:
            if str(p.get_editor_property("parameter_name")) == "Enable_Water_Absorb":
                p.set_editor_property("default_value", v)
        mpc.set_editor_property("scalar_parameters", sc)
        unreal.EditorAssetLibrary.save_loaded_asset(mpc)
        return {"Enable_Water_Absorb": v}
    if mode == "assign":
        return _assign(DST_MI)
    if mode == "unassign":
        return _assign(SRC_MI)
    return {"error": mode}
