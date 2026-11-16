"""Capture the reflected sky, project real SH, and write the L0 + SH0..SH6 set
into MPC_RestoreControl so MF_SH_Irradiance evaluates the same environment the
SkyLight does.

Basis convention: UE's FSHVectorRGB3 layout. The projection uses the *unscaled*
real SH basis so the band constants (0.282095, 0.488603, 1.092548, ...) stay
explicit and the cosine-lobe factors can be applied per band. The resulting
values are what MF_SH_Irradiance's Custom node expects:

    L0 = L0.rgb
    L1 = SH0.rgb*n.x + SH1.rgb*n.y + SH2.rgb*n.z
    L2 = SH3.rgb*(n.y*n.z) + SH4.rgb*(n.x*n.z)
       + SH5.rgb*(n.x*n.y) + SH6.rgb*(n.x*n.x - n.y*n.y)

L0 is a separate float3, so R/G/B keep independent DC terms. The Wuthering
Waves source frame packs L0 into the float4 .a lanes, which can only carry one
scalar broadcast across rgb; see hlsl/sh_irradiance.hlsl for the rationale.
"""
import math
import unreal

RT_SIZE = 64
CAPTURE_HEIGHT = 60000.0
CAPTURE_XY = (-8285.0, 826.0)

MPC_PATH = "/Game/Reconstruction/Rendering/_Restore/Common/MPC_RestoreControl"


def sh_basis(dx, dy, dz):
    return [
        0.282095,
        0.488603 * dy,
        0.488603 * dz,
        0.488603 * dx,
        1.092548 * dx * dy,
        1.092548 * dy * dz,
        0.315392 * (3.0 * dz * dz - 1.0),
        1.092548 * dx * dz,
        0.546274 * (dx * dx - dy * dy),
    ]


def dir_for_face_pixel(face, u, v):
    if face == 0:
        d = (1.0, -v, -u)
    elif face == 1:
        d = (-1.0, -v, u)
    elif face == 2:
        d = (u, 1.0, v)
    elif face == 3:
        d = (u, -1.0, -v)
    elif face == 4:
        d = (u, -v, 1.0)
    else:
        d = (-u, -v, -1.0)
    l = math.sqrt(sum(c * c for c in d))
    return (d[0] / l, d[1] / l, d[2] / l)


def capture_sh(world, eas):
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == "__TMP_SkyCube":
            eas.destroy_actor(a)

    rt = unreal.RenderingLibrary.create_render_target2d(world, RT_SIZE, RT_SIZE)
    actor = eas.spawn_actor_from_class(
        unreal.SceneCapture2D,
        unreal.Vector(CAPTURE_XY[0], CAPTURE_XY[1], CAPTURE_HEIGHT),
        unreal.Rotator(0, 0, 0),
    )
    actor.set_actor_label("__TMP_SkyCube")
    comp = actor.get_component_by_class(unreal.SceneCaptureComponent2D)
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("fov_angle", 90.0)

    faces = []
    for pitch, yaw in [(0, 0), (0, 180), (0, 90), (0, -90), (90, 0), (-90, 0)]:
        actor.set_actor_rotation(unreal.Rotator(pitch, yaw, 0), False)
        comp.capture_scene()
        faces.append(unreal.RenderingLibrary.read_render_target(world, rt))

    eas.destroy_actor(actor)

    rgb = [[0.0, 0.0, 0.0] for _ in range(9)]
    solid = 0.0
    for face in range(6):
        px = faces[face]
        for y in range(RT_SIZE):
            for x in range(RT_SIZE):
                u = (x + 0.5) / RT_SIZE * 2.0 - 1.0
                v = (y + 0.5) / RT_SIZE * 2.0 - 1.0
                dx, dy, dz = dir_for_face_pixel(face, u, v)
                sa = (4.0 / (RT_SIZE * RT_SIZE)) / ((1 + u * u + v * v) ** 1.5)
                c = px[y * RT_SIZE + x]
                r, g, b = c.r / 255.0, c.g / 255.0, c.b / 255.0
                solid += sa
                for i, yv in enumerate(sh_basis(dx, dy, dz)):
                    w = yv * sa
                    rgb[i][0] += r * w
                    rgb[i][1] += g * w
                    rgb[i][2] += b * w
    return rgb, solid


def pack(raw, scale):
    """9-coefficient projection -> the L0 + SH0..SH6 float4s.

    Order of `raw`: Y00, Y1-1(y), Y10(z), Y11(x), Y2-2(xy), Y2-1(yz),
    Y20(z^2), Y21(xz), Y22(x^2-y^2).
    """
    l0 = raw[0]
    l1y, l1z, l1x = raw[1], raw[2], raw[3]
    l2xy, l2yz, l2z2, l2xz, l2xy2 = raw[4], raw[5], raw[6], raw[7], raw[8]

    def f4(v, a=0.0):
        return [v[0] * scale, v[1] * scale, v[2] * scale, a * scale]

    return {
        # L0 travels as its own float3 so R/G/B keep independent DC terms.
        # The source frame packs it into the float4 .a lanes, which can only
        # carry one scalar broadcast across rgb; see MF_SH_Irradiance's HLSL.
        "L0": [l0[0] * scale, l0[1] * scale, l0[2] * scale, 1.0],
        "SH0": f4(l1y),
        "SH1": f4(l1z),
        "SH2": f4(l1x),
        "SH3": f4(l2xy),
        "SH4": f4(l2yz),
        "SH5": f4(l2xz),
        "SH6": f4(l2xy2),
    }


def write_mpc(values, intensity):
    mpc = unreal.EditorAssetLibrary.load_asset(MPC_PATH)
    params = list(mpc.get_editor_property("vector_parameters"))
    existing = {str(p.get_editor_property("parameter_name")): i for i, p in enumerate(params)}

    written = []
    for name in ("L0", "SH0", "SH1", "SH2", "SH3", "SH4", "SH5", "SH6"):
        r, g, b, a = values[name]
        colour = unreal.LinearColor(r, g, b, a)
        if name in existing:
            params[existing[name]].set_editor_property("default_value", colour)
        else:
            p = unreal.CollectionVectorParameter()
            p.set_editor_property("parameter_name", name)
            p.set_editor_property("default_value", colour)
            params.append(p)
        written.append(name)
    mpc.set_editor_property("vector_parameters", params)

    scals = list(mpc.get_editor_property("scalar_parameters"))
    for p in scals:
        if str(p.get_editor_property("parameter_name")) == "SH_Intensity":
            p.set_editor_property("default_value", intensity)
            written.append("SH_Intensity")

    mpc.set_editor_property("scalar_parameters", scals)
    unreal.EditorAssetLibrary.save_loaded_asset(mpc)
    return written


def run(*argv):
    # The capture reads the LDR screen buffer, so the projected DC term sits
    # near 1.0 while a lit-scene irradiance is two to three orders larger.
    # SH_Intensity carries that conversion so the raw coefficients stay
    # comparable with the numbers the source frame's buffer holds.
    intensity = float(argv[0]) if argv else 1.0

    out = {}
    world = unreal.EditorLevelLibrary.get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    raw, solid = capture_sh(world, eas)
    out["solidAngle"] = round(solid, 4)
    out["raw"] = [[round(v, 6) for v in c] for c in raw]

    values = pack(raw, scale=1.0)
    out["sh"] = {k: [round(v, 5) for v in val] for k, val in values.items()}
    out["written"] = write_mpc(values, intensity)
    out["intensity"] = intensity
    return out
