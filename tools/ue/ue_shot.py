"""Capture the active level viewport to a PNG on disk.

SceneCapture2D renders into a transient RT, then read_render_target_pixel pulls
the pixels back synchronously and we write the PNG ourselves. export_render_target
is deliberately not used: it hands the write to the render thread and returns
before the file exists.

Usage: run(<out.png> [width] [height] [lx ly lz pitch yaw roll [fov]] [showflags])
  - out.png defaults to $MC_OUT/shot.png (MC_OUT defaults to the cwd)
  - showflags example: "TemporalAA=0,AntiAliasing=0,LightingOnlyOverride=1"
"""
import unreal
import os
import struct
import sys
import zlib

LABEL = "__TMP_ViewportShot"


def _write_png(path, width, height, rgb_rows):
    """rgb_rows: list of bytearray, each width*3 bytes, top row first."""
    raw = bytearray()
    for row in rgb_rows:
        raw.append(0)          # filter type 0
        raw.extend(row)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
        f.write(chunk(b"IEND", b""))


def run(*argv):
    if not argv:
        argv = tuple(sys.argv[1:])
    default_out = os.path.join(os.environ.get("MC_OUT", "."), "shot.png")
    out_path = argv[0] if argv else default_out
    width = int(argv[1]) if len(argv) > 1 else 1280
    height = int(argv[2]) if len(argv) > 2 else 720
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    result = {"out": out_path}
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == LABEL:
            eas.destroy_actor(a)

    sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    view_loc, view_rot = sub.get_level_viewport_camera_info()
    result["editorCamera"] = f"{view_loc} / {view_rot}"

    # Optional explicit pose: <out> <w> <h> <lx> <ly> <lz> <pitch> <yaw> <roll>
    # unreal.Rotator's positional order is (roll, pitch, yaw); pass by keyword.
    if len(argv) >= 9:
        view_loc = unreal.Vector(float(argv[3]), float(argv[4]), float(argv[5]))
        view_rot = unreal.Rotator(
            roll=float(argv[8]), pitch=float(argv[6]), yaw=float(argv[7])
        )
        result["overrideCamera"] = f"{view_loc} / {view_rot}"

    world = unreal.EditorLevelLibrary.get_editor_world()
    actor = eas.spawn_actor_from_class(unreal.SceneCapture2D, view_loc, view_rot)
    actor.set_actor_label(LABEL)
    comp = actor.get_component_by_class(unreal.SceneCaptureComponent2D)

    rt = unreal.RenderingLibrary.create_render_target2d(world, width, height)
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    # capture_every_frame must stay True: with it off, PostProcess material blendables are skipped.
    comp.set_editor_property("capture_every_frame", True)
    comp.set_editor_property("fov_angle", float(argv[9]) if len(argv) >= 10 else 90.0)

    # SceneCapture2D does not pick up PostProcess *material* blendables from a
    # volume (native settings like WhiteTemp do come through). Copy them onto
    # the capture component as a freshly built array (assigning the volume's own
    # WeightedBlendables struct silently does nothing).
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == "APPROX_Daylight_Exposure":
            vol_wb = a.get_editor_property("settings").get_editor_property("weighted_blendables")
            items = []
            for src in vol_wb.get_editor_property("array"):
                b = unreal.WeightedBlendable()
                b.set_editor_property("weight", src.get_editor_property("weight"))
                b.set_editor_property("object", src.get_editor_property("object"))
                items.append(b)
            wb = unreal.WeightedBlendables()
            wb.set_editor_property("array", items)
            cps = comp.get_editor_property("post_process_settings")
            cps.set_editor_property("weighted_blendables", wb)
            comp.set_editor_property("post_process_settings", cps)
            comp.set_editor_property("post_process_blend_weight", 1.0)
            result["copiedBlendables"] = len(items)
            break

    # Optional 11th arg: show flag overrides, e.g. "TemporalAA=0,AntiAliasing=0,LightingOnlyOverride=1".
    # Debug props (the SH test sphere) never belong in comparison shots.
    for dbg in eas.get_all_level_actors():
        if dbg.get_actor_label().startswith("__RESTORE_DBG"):
            comp.hide_actor_components(dbg)
    if len(argv) >= 11 and argv[10]:
        flags = []
        for item in argv[10].split(","):
            name, val = item.split("=")
            s = unreal.EngineShowFlagsSetting()
            s.set_editor_property("show_flag_name", name)
            s.set_editor_property("enabled", val == "1")
            flags.append(s)
        comp.set_editor_property("show_flag_settings", flags)
        result["showFlags"] = argv[10]
    comp.capture_scene()

    # One bulk read: a flat FColor array, row-major, top row first.
    pixels = unreal.RenderingLibrary.read_render_target(world, rt)
    if len(pixels) != width * height:
        result["error"] = f"pixel count {len(pixels)} != {width}x{height}"
        eas.destroy_actor(actor)
        return result

    rows = []
    for y in range(height):
        row = bytearray()
        base = y * width
        for x in range(width):
            c = pixels[base + x]
            row.extend((c.r, c.g, c.b))
        rows.append(row)

    _write_png(out_path, width, height, rows)
    result["exists"] = os.path.exists(out_path)
    result["size"] = os.path.getsize(out_path) if os.path.exists(out_path) else 0

    eas.destroy_actor(actor)
    return result
