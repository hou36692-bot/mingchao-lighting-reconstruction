"""Module 7 (TOD): drive sun / sky light / height fog from source evidence or the restore curves.

args: ww61250 | orig | hour <h> | measure_flags <diff|spec|sky> <0|1>

  ww61250 [sky] [fog] : Wuthering Waves frame 61250 sun (ps7051 E21908 cb1[6..8]) — direction, colour, illuminance, angle.
            sky: SkyLight intensity (calibrated 1.2 after the real-time sky capture settles).
            fog: also write ps1572 cb1[296].rgb as FogInscatteringLuminance ([推断]; at 1:1 it washes the
            frame out, so it is opt-in and the level currently keeps fog luminance 0).
  orig    : the level's original APPROX_* values (rotation/colour/intensity/fog)
  hour h  : evaluate _Restore/TOD curves at hour h (only the 61250 key is evidence; see curves)

The level shares the game's world basis (UE4-derived engine, Z-up, cm): the
source "direction to sun" (0.530,-0.567,0.630) maps 1:1, actor forward = -dir.
"""
import math
import unreal

SUN = "APPROX_Daylight_Sun"
SKY = "APPROX_Daylight_SkyFill"
FOG = "APPROX_Fog_Height"
TOD = "/Game/Reconstruction/Rendering/_Restore/TOD"

WW_SUN_DIR = (0.530021, -0.567254, 0.630318)      # cb1[7].xyz (also ps1572 cb1[293], water cb0[153])
WW_SUN_COLOR = (4.33657, 3.06767, 1.46663)        # cb1[6].rgb  (ps1572 cb1[288] = same)
WW_SUN_ANGLE_RAD = 0.004675                       # cb1[8].w  angular radius
WW_FOG_COLOR = (0.306668, 0.357438, 0.391376)     # ps1572 cb1[296].rgb
WW_SKY_INTENSITY = None                           # set by calibration (tools/analysis/tod_ratio.mjs), see ORIG/WW below

ORIG = {"rot": (-44.0, 160.0, 180.0), "color_srgb": (216, 255, 253), "intensity": 1.0,
        "sky_intensity": 1.2, "fog_luminance": (0.0, 0.0, 0.0), "source_angle": 0.5357}


def _actor(label):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    raise RuntimeError(label)


def _transmittance():
    atmo = _actor("APPROX_Daylight_Atmosphere").get_component_by_class(unreal.SkyAtmosphereComponent)
    sun = _actor(SUN).get_component_by_class(unreal.DirectionalLightComponent)
    t = atmo.get_atmosphere_transmitance_on_ground_at_planet_top(sun)
    return [t.r, t.g, t.b]


def _rot_from_dir_to_sun(d):
    f = [-v for v in d]
    yaw = math.degrees(math.atan2(f[1], f[0]))
    pitch = math.degrees(math.atan2(f[2], math.hypot(f[0], f[1])))
    return unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)


def apply(sun_dir=None, sun_rot=None, sun_color_lin=None, sun_color_srgb=None, sun_lux=None,
          source_angle=None, sky_intensity=None, fog_lum=None):
    sun = _actor(SUN)
    sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun.modify()
    if sun_dir is not None:
        sun.set_actor_rotation(_rot_from_dir_to_sun(sun_dir), False)
    if sun_rot is not None:
        sun.set_actor_rotation(unreal.Rotator(roll=sun_rot[2], pitch=sun_rot[0], yaw=sun_rot[1]), False)
    if sun_color_lin is not None:
        sc.set_light_color(unreal.LinearColor(*sun_color_lin, 1.0), True)
    if sun_color_srgb is not None:
        sc.set_editor_property("light_color", unreal.Color(r=sun_color_srgb[0], g=sun_color_srgb[1], b=sun_color_srgb[2], a=255))
    if sun_lux is not None:
        sc.set_editor_property("intensity", float(sun_lux))
    if source_angle is not None:
        sc.set_editor_property("light_source_angle", float(source_angle))
    if sky_intensity is not None:
        skc = _actor(SKY).get_component_by_class(unreal.SkyLightComponent)
        skc.set_editor_property("intensity", float(sky_intensity))
    if fog_lum is not None:
        fc = _actor(FOG).get_component_by_class(unreal.ExponentialHeightFogComponent)
        fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(*fog_lum, 1.0))
    return {
        "sun_fwd": str(sun.get_actor_forward_vector()),
        "sun_color": str(sc.get_editor_property("light_color")),
        "sun_lux": sc.get_editor_property("intensity"),
        "source_angle": sc.get_editor_property("light_source_angle"),
        "sky": _actor(SKY).get_component_by_class(unreal.SkyLightComponent).get_editor_property("intensity"),
        "fog": str(_actor(FOG).get_component_by_class(unreal.ExponentialHeightFogComponent).get_editor_property("fog_inscattering_luminance")),
    }


def run(*argv):
    mode = argv[0] if argv else "ww61250"
    if mode == "orig":
        return apply(sun_rot=ORIG["rot"], sun_color_srgb=ORIG["color_srgb"], sun_lux=ORIG["intensity"],
                     source_angle=ORIG["source_angle"], sky_intensity=ORIG["sky_intensity"], fog_lum=ORIG["fog_luminance"])
    if mode == "ww61250":
        # WW's cb1[6] is what surfaces receive. UE's SkyAtmosphere multiplies the light colour by the
        # ground-level transmittance T(sun dir) before lighting surfaces, so upload WW / T; otherwise
        # the sun is tinted twice and the sky (lit by the un-attenuated colour) turns orange.
        sky = float(argv[1]) if len(argv) > 1 and argv[1] != "-" else None
        apply(sun_dir=WW_SUN_DIR)
        t = _transmittance()
        top = [WW_SUN_COLOR[i] / max(t[i], 1e-4) for i in range(3)]
        peak = max(top)
        r = apply(sun_color_lin=[c / peak for c in top], sun_lux=peak,
                  source_angle=math.degrees(2 * WW_SUN_ANGLE_RAD), sky_intensity=sky,
                  fog_lum=WW_FOG_COLOR if (len(argv) > 2 and argv[2] == "fog") else None)
        r["atmo_T"] = t
        r["ground_sun_check"] = [round(peak * (top[i] / peak) * t[i], 4) for i in range(3)]
        return r
    if mode == "hour":
        # CT_Restore_TOD: only the 14.5h column is source evidence (frame 61250; the clock hour itself is an
        # assumption). 6h / 18.5h are artistic keys for a sunrise / dusk look, not reverse-engineered.
        h = float(argv[1])
        ct = unreal.EditorAssetLibrary.load_asset(f"{TOD}/CT_Restore_TOD")
        ev = lambda row: unreal.DataTableFunctionLibrary.evaluate_curve_table_row(ct, row, h, "tod")[1]
        el, yaw = math.radians(ev("SunElevationDeg")), math.radians(ev("SunForwardYawDeg"))
        fwd = (math.cos(el) * math.cos(yaw), math.cos(el) * math.sin(yaw), -math.sin(el))
        # Rows hold the top-of-atmosphere sun (what UE's light takes); UE's SkyAtmosphere does the
        # reddening. The 14.5 key is the source ground colour / T(39deg) for this level's atmosphere.
        r = apply(sun_dir=[-v for v in fwd],
                  sun_color_lin=(ev("SunTopR"), ev("SunTopG"), ev("SunTopB")), sun_lux=ev("SunTopLux"),
                  source_angle=math.degrees(2 * WW_SUN_ANGLE_RAD),
                  sky_intensity=ev("SkyIntensity"), fog_lum=(ev("FogR"), ev("FogG"), ev("FogB")))
        t = _transmittance()
        r["hour"] = h
        r["ground_sun"] = [round(r["sun_lux"] * c, 3) for c in (ev("SunTopR") * t[0], ev("SunTopG") * t[1], ev("SunTopB") * t[2])]
        return r
    if mode == "measure_flags":
        # Isolate one lighting term for the sun/sky ratio measurement (tools/analysis/tod_ratio.mjs).
        what, on = argv[1], argv[2] == "1"
        if what == "sun":
            sc = _actor(SUN).get_component_by_class(unreal.DirectionalLightComponent)
            sc.set_editor_property("diffuse_scale", 1.0 if on else 0.0)
            sc.set_editor_property("specular_scale", 1.0 if on else 0.0)
        elif what == "sky":
            skc = _actor(SKY).get_component_by_class(unreal.SkyLightComponent)
            skc.set_visibility(on)
        return {what: on}
    return {"error": mode}
