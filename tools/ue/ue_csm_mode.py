"""Switch the sun between VSM (project default) and CSM aligned to Wuthering Waves.

args: vsm | csm_ue | csm_mc

  vsm    : VSM on, sun + cvars back to the level's original values (baseline).
  csm_ue : VSM off, UE's own CSM with the level's original sun settings
           (4 cascades, exponent 3, 40000cm x DistanceScale 0.85).
  csm_mc : VSM off, CSM aligned to the source frame ps1024669:
           5 cascades, far plane 32500cm, exponent 2.24 (tools/analysis/csm_fit.mjs),
           2048 per cascade (UE SHADOW_BORDER=4 -> 2040 usable, same as the game),
           r.ShadowQuality 5 -> Manual5x5PCF (9 x Gather4, the same kernel).

Cvars are runtime only (lost on editor restart); sun properties are saved with the level.
"""
import unreal

SUN_LABEL = "APPROX_Daylight_Sun"
MPC = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl.MPC_RestoreControl"

ORIGINAL_SUN = {"dynamic_shadow_cascades": 4, "cascade_distribution_exponent": 3.0,
                "dynamic_shadow_distance_movable_light": 40000.0,
                "cascade_transition_fraction": 0.1, "shadow_distance_fadeout_fraction": 0.1}
ORIGINAL_CVARS = {"r.Shadow.Virtual.Enable": 1, "r.Shadow.CSM.MaxCascades": 4,
                  "r.Shadow.DistanceScale": 0.85, "r.Shadow.MaxCSMResolution": 2048,
                  "r.ShadowQuality": 5}

MC_SUN = {"dynamic_shadow_cascades": 5, "cascade_distribution_exponent": 2.24,
          "dynamic_shadow_distance_movable_light": 32500.0,
          "cascade_transition_fraction": 0.1, "shadow_distance_fadeout_fraction": 0.1}
MC_CVARS = {"r.Shadow.Virtual.Enable": 0, "r.Shadow.CSM.MaxCascades": 5,
            "r.Shadow.DistanceScale": 1.0, "r.Shadow.MaxCSMResolution": 2048,
            "r.ShadowQuality": 5}

MODES = {
    "vsm": (ORIGINAL_SUN, ORIGINAL_CVARS),
    "csm_ue": (ORIGINAL_SUN, dict(ORIGINAL_CVARS, **{"r.Shadow.Virtual.Enable": 0})),
    "csm_mc": (MC_SUN, MC_CVARS),
}


def _sun():
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == SUN_LABEL:
            return a, a.get_component_by_class(unreal.DirectionalLightComponent)
    raise RuntimeError("sun not found")


def run(*argv):
    mode = argv[0] if argv else "vsm"
    sun_props, cvars = MODES[mode]
    actor, comp = _sun()
    actor.modify()
    for k, v in sun_props.items():
        comp.set_editor_property(k, v)
    world = unreal.EditorLevelLibrary.get_editor_world()
    for k, v in cvars.items():
        unreal.SystemLibrary.execute_console_command(world, f"{k} {v}")
    g = unreal.SystemLibrary
    # Feed M_PP_RestoreDebugViz mode 2 with the split curve UE is now using.
    eff = {"CSM_UE_Exponent": sun_props["cascade_distribution_exponent"],
           "CSM_UE_Distance": sun_props["dynamic_shadow_distance_movable_light"] * cvars["r.Shadow.DistanceScale"],
           "CSM_UE_Count": min(sun_props["dynamic_shadow_cascades"], cvars["r.Shadow.CSM.MaxCascades"])}
    mpc = unreal.EditorAssetLibrary.load_asset(MPC)
    sc = list(mpc.get_editor_property("scalar_parameters"))
    for p in sc:
        n = str(p.get_editor_property("parameter_name"))
        if n in eff:
            p.set_editor_property("default_value", float(eff[n]))
    mpc.set_editor_property("scalar_parameters", sc)
    unreal.EditorAssetLibrary.save_loaded_asset(mpc)
    return {"mode": mode, "viz": eff,
            "sun": {k: comp.get_editor_property(k) for k in sun_props},
            "cvars": {k: g.get_console_variable_float_value(k) for k in cvars}}
