"""Editor viewport camera helper: get | set x y z pitch yaw | restore.

The saved pose lives in the OS temp directory, not in the repository.
Used by vpshot.sh to move the viewport, take a HighResShot, then restore it.
"""
import json
import os
import tempfile
import unreal

SAVE = os.path.join(tempfile.gettempdir(), "ue_vp_cam_saved.json")


def run(*a):
    sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    loc, rot = sub.get_level_viewport_camera_info()
    if not a or a[0] == "get":
        return {"loc": [loc.x, loc.y, loc.z], "rot": [rot.pitch, rot.yaw, rot.roll]}
    if a[0] == "set":
        if not os.path.exists(SAVE):
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump({"loc": [loc.x, loc.y, loc.z],
                           "rot": [rot.pitch, rot.yaw, rot.roll]}, f)
        x, y, z, p, yw = (float(v) for v in a[1:6])
        sub.set_level_viewport_camera_info(
            unreal.Vector(x, y, z),
            unreal.Rotator(roll=0.0, pitch=p, yaw=yw),
        )
        return {"set": [x, y, z, p, yw]}
    if a[0] == "restore":
        if not os.path.exists(SAVE):
            return {"restore": "nothing saved"}
        with open(SAVE, "r", encoding="utf-8") as f:
            s = json.load(f)
        os.remove(SAVE)
        sub.set_level_viewport_camera_info(
            unreal.Vector(*s["loc"]),
            unreal.Rotator(roll=s["rot"][2], pitch=s["rot"][0], yaw=s["rot"][1]),
        )
        return {"restored": s}
    return {"error": "unknown mode: %s" % (a[0],)}
