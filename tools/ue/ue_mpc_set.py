"""Set scalar parameters on MPC_RestoreControl by name.

args: name=value pairs, e.g. Enable_Custom_AO=1 AO_Radius=150
"""
import unreal

MPC_PATH = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"


def run(*argv):
    pairs = {}
    for a in argv:
        if "=" in a:
            k, v = a.split("=", 1)
            pairs[k] = float(v)

    mpc = unreal.EditorAssetLibrary.load_asset(MPC_PATH)
    scals = list(mpc.get_editor_property("scalar_parameters"))
    applied, missing = {}, []
    for p in scals:
        name = str(p.get_editor_property("parameter_name"))
        if name in pairs:
            p.set_editor_property("default_value", pairs[name])
            applied[name] = pairs[name]

    mpc.set_editor_property("scalar_parameters", scals)
    unreal.EditorAssetLibrary.save_loaded_asset(mpc)
    return {"applied": applied, "requested": list(pairs), "missing": missing}
