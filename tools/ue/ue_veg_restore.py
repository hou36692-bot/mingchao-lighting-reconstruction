"""植被（地表草）还原：鸣潮源草网格 + 源 UV 段，复用 APPROX_GroundGrass_* 撒点。
tools/ue/py.sh tools/ue/ue_veg_restore.py <cmd>
  import        导入 $MC_WORKSPACE/tools/tmp/veg/obj/SM_WWGrass_TriCard_{A,B}.obj（先跑 node tools/analysis/veg_build_mesh.mjs）
  material      复制 M_GroundGrass -> _Restore/Veg/M_WWGrass，建 MI_WWGrass
  apply         HISM 换网格/材质/缩放，Foliage A/E 隐藏（首次会把原状态存到 $MC_WORKSPACE/data/veg_src/veg_orig.json）
  orig          按 veg_orig.json 换回旧网格/材质/缩放/可见性
  state         打印当前状态
  lawn          Frame36153 右侧草坪补撒（新 actor RESTORE_WWGrass_Lawn36153；orig 时隐藏、apply 时显示）
  vis 0|1       临时隐藏/显示全部 BP_GroundGrass 草（差分拍照用）
  color r g b  r g b  r g b [trans]   改 MI_WWGrass 的 RootColor / TipColorA / TipColorB（线性）
只改 L_SuiBo_LightingReverse 关卡里的组件和 _Restore/Veg 资产，不改 Rendering/Grass 原资产。

源数据（草网格 OBJ、鸣潮实例 JSON、原状态 JSON）不在本仓库内，需通过
MC_WORKSPACE 指向的工作区提供；未设置时相关命令会直接报错。
"""
import json, math, os, random, unreal
DIR = "/Game/Reconstruction/Rendering/_Restore/Veg"
SRC_MAT = "/Game/Reconstruction/Rendering/Grass/M_GroundGrass"
MAT, MI = DIR + "/M_WWGrass", DIR + "/MI_WWGrass"
MESH = {"A": DIR + "/SM_WWGrass_TriCard_A", "B": DIR + "/SM_WWGrass_TriCard_B"}
HIDE = ("SM_GroundGrass_A_TallClump", "SM_GroundGrass_E_WideClump")
LEVEL = "L_SuiBo_LightingReverse"
EAL = unreal.EditorAssetLibrary


def _src(*parts):
    """Resolve a path inside the source workspace (MC_WORKSPACE)."""
    root = os.environ.get("MC_WORKSPACE")
    if not root:
        raise RuntimeError(
            "MC_WORKSPACE is not set: vegetation source data (grass OBJ meshes and "
            "instance JSON) is not shipped with this repository"
        )
    return os.path.join(root, *parts)


def _orig_path():
    # 原网格/缩放/高度/旋转，orig 靠它恢复，别删
    return _src("data", "veg_src", "veg_orig.json")


def _xf_path():
    # 鸣潮实例 [水平缩放, 竖直缩放, 倾斜°]（tools/analysis/veg_inst_stats.mjs）
    return _src("data", "veg_src", "ww_inst_xf.json")


def _check_level():
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if w.get_name() != LEVEL:
        raise RuntimeError("current level is %s, expected %s" % (w.get_name(), LEVEL))

def _actors():
    _check_level()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    hism, fol = [], []
    for act in eas.get_all_level_actors():
        cls = act.get_class().get_name()
        if cls.startswith("BP_GroundGrass"):
            for c in act.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
                hism.append((act, c))
        elif cls == "InstancedFoliageActor":
            for c in act.get_components_by_class(unreal.InstancedStaticMeshComponent):
                sm = c.get_editor_property("static_mesh")
                if sm and sm.get_name() in HIDE:
                    fol.append((act, c))
    return hism, fol

def _key(act, c):
    return act.get_actor_label() + "/" + c.get_name()

def import_mesh():
    obj_dir = _src("tools", "tmp", "veg", "obj")   # node tools/analysis/veg_build_mesh.mjs 的输出
    tasks = []
    for k in ("A", "B"):
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", os.path.join(obj_dir, "SM_WWGrass_TriCard_%s.obj" % k))
        t.set_editor_property("destination_path", DIR)
        t.set_editor_property("destination_name", "SM_WWGrass_TriCard_" + k)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("automated", True)
        t.set_editor_property("save", False)
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    out = {}
    for k, p in MESH.items():
        sm = EAL.load_asset(p)
        if not sm:
            out[k] = "missing"; continue
        ns = sm.get_editor_property("nanite_settings"); ns.enabled = False
        sm.set_editor_property("nanite_settings", ns)
        unreal.EditorStaticMeshLibrary.remove_collisions(sm)
        bs = sm.get_editor_property("body_setup")
        if bs:
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
        EAL.save_loaded_asset(sm)
        b = sm.get_bounding_box()
        out[k] = {"min": [round(b.min.x, 1), round(b.min.y, 1), round(b.min.z, 1)], "max": [round(b.max.x, 1), round(b.max.y, 1), round(b.max.z, 1)],
                  "verts": sm.get_num_vertices(0), "tris": sm.get_num_triangles(0) if hasattr(sm, "get_num_triangles") else None,
                  "uvch": unreal.EditorStaticMeshLibrary.get_num_uv_channels(sm, 0), "mats": [m.material_interface.get_path_name() if m.material_interface else None for m in sm.static_materials]}
    # Interchange 可能给 OBJ 顺手建了材质，删掉
    for a in EAL.list_assets(DIR, recursive=True, include_folder=False):
        n = a.split("/")[-1].split(".")[0]
        if n not in ("SM_WWGrass_TriCard_A", "SM_WWGrass_TriCard_B", "M_WWGrass", "MI_WWGrass"):
            out.setdefault("extra", []).append(a)
    return out

def material():
    if not EAL.does_asset_exist(MAT):
        EAL.duplicate_asset(SRC_MAT, MAT)
    m = EAL.load_asset(MAT)
    unreal.MaterialEditingLibrary.recompile_material(m)
    EAL.save_loaded_asset(m)
    if not EAL.does_asset_exist(MI):
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset("MI_WWGrass", DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", m)
    mi = EAL.load_asset(MI)
    L = unreal.MaterialEditingLibrary
    L.set_material_instance_scalar_parameter_value(mi, "HeightScaleCm", 57.0)
    L.set_material_instance_scalar_parameter_value(mi, "TransmissionStrength", 0.5)
    L.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    for p in MESH.values():
        sm = EAL.load_asset(p)
        if sm:
            sm.set_material(0, mi); EAL.save_loaded_asset(sm)
    return {"mat": m.get_path_name(), "mi": mi.get_path_name()}

def color(*v):
    v = [float(x) for x in v]
    mi = EAL.load_asset(MI); L = unreal.MaterialEditingLibrary
    for i, n in enumerate(("RootColor", "TipColorA", "TipColorB")):
        L.set_material_instance_vector_parameter_value(mi, n, unreal.LinearColor(v[i * 3], v[i * 3 + 1], v[i * 3 + 2], 1.0))
    if len(v) > 9:
        L.set_material_instance_scalar_parameter_value(mi, "TransmissionStrength", v[9])
    L.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return {"set": v}

def _xf_list(c):
    return [c.get_instance_transform(i, world_space=False) for i in range(c.get_instance_count())]

def _set_xf(c, fn):
    """fn(i, transform) 原地改实例变换（本地空间，actor 都在原点）；批量写回。"""
    xs = _xf_list(c)
    for i, t in enumerate(xs):
        fn(i, t)
    c.batch_update_instances_transforms(0, xs, world_space=False, mark_render_state_dirty=True, teleport=True)

COVER_CM = 20.0   # 根部上方 20 cm 内有别的表面（路面/花箱/台阶）→ 视为被埋，缩放置 0
def _ground(world, p):
    """从根部上方 80 cm 向下 160 cm 竖直射线，返回最高表面 z（无命中返回 None）。草/花组件无碰撞，不会自击中。"""
    h = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(p.x, p.y, p.z + 80), unreal.Vector(p.x, p.y, p.z - 80),
                                               unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], unreal.DrawDebugTrace.NONE, True)
    return None if h is None else h.to_tuple()[5].z

# 原状态（BP_GroundGrass 默认：Strip=SM_GrassStrip、Tuft=SM_GrassTuft，无覆盖材质→网格自带 MI_GroundGrass；Foliage A/E 可见）
OLD_MESH = {"Strip": "/Game/Reconstruction/Rendering/Grass/Meshes/SM_GrassStrip/StaticMeshes/SM_GrassStrip.SM_GrassStrip",
            "Tuft": "/Game/Reconstruction/Rendering/Grass/Meshes/SM_GrassTuft/StaticMeshes/SM_GrassTuft.SM_GrassTuft"}

def _comp(label, name):
    """按 actor 标签 + 组件名重新取组件（BP 组件改属性会重跑构造脚本，旧引用会失效）。"""
    hism, fol = _actors()
    for act, c in hism + fol:
        if act.get_actor_label() == label and c.get_name() == name:
            return act, c
    return None, None

def _save_orig():
    """首次 apply 前记录原缩放（网格/材质/可见性用上面的已知原值）。已存在就不覆盖。"""
    orig = _orig_path()
    if os.path.exists(orig):
        return json.load(open(orig))
    hism, fol = _actors()
    o = {"hism": {}, "fol": {}}
    for act, c in hism:
        xs = _xf_list(c)
        o["hism"][_key(act, c)] = {"mesh": OLD_MESH.get(c.get_name()), "scales": [[t.scale3d.x, t.scale3d.y, t.scale3d.z] for t in xs],
                                   "z": [t.translation.z for t in xs],
                                   "rot": [[r.pitch, r.yaw, r.roll] for r in (t.rotation.rotator() for t in xs)]}
    for act, c in fol:
        o["fol"][_key(act, c)] = {"visible": True}
    json.dump(o, open(orig, "w"))
    return o

EDGE_R_CM, EDGE_MIN_NB = 90.0, 3   # 半径 90 cm 内邻居少于 3 个的孤立实例（花坛外缘稀疏的一圈）→ 缩放 0

def apply(edge_min=None):
    """换网格/材质；缩放按鸣潮实例分布重采样、偏航均匀随机；贴地；剔除被路面盖住的和外缘孤立的实例。"""
    min_nb = EDGE_MIN_NB if edge_min is None else int(edge_min)
    o = _save_orig()
    src = json.load(open(_xf_path()))
    mi = EAL.load_asset(MI)
    meshes = {k: EAL.load_asset(p) for k, p in MESH.items()}
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    out, plan = [], []
    # 第 1 遍：算每个实例的新变换（不写回）
    for k in o["hism"]:
        label, name = k.split("/")
        act, c = _comp(label, name)
        if not c: continue
        rnd = random.Random(sum(ord(ch) * (i + 1) for i, ch in enumerate(k)))
        z0 = o["hism"][k]["z"]
        stat = {"snap": 0, "buried": 0, "nohit": 0, "edge": 0}
        xs = _xf_list(c)
        for i, t in enumerate(xs):
            # 鸣潮 t1 基矩阵：水平缩放 1.00–1.20（中位 1.05）、竖直略大、偏航均匀；倾斜角含义未确认，不用
            sxy, sz, _tilt = src[rnd.randrange(len(src))]
            t.scale3d = unreal.Vector(sxy, sxy, sz)
            t.rotation = unreal.Rotator(roll=0.0, pitch=0.0, yaw=rnd.uniform(-180, 180)).quaternion()
            # 旧撒点根部高度有 ±20 cm 误差（悬空、或埋在路面下只露草尖），按地面重新贴地
            p = unreal.Vector(t.translation.x, t.translation.y, z0[i])
            g = _ground(world, p)
            if g is None:
                stat["nohit"] += 1; t.translation = p
            elif g - p.z > COVER_CM:
                stat["buried"] += 1; t.scale3d = unreal.Vector(0, 0, 0); t.translation = p
            else:
                stat["snap"] += 1; t.translation = unreal.Vector(p.x, p.y, g)
        plan.append((k, name, xs, stat))
    # 第 2 遍：外缘孤立实例。三角围栏卡片下 1/3 很密（图集该条底部覆盖率约 60%），稀疏处俯视会露出一根根"棍子"
    cell = EDGE_R_CM; grid = {}
    for pi, (_, _, xs, _) in enumerate(plan):
        for i, t in enumerate(xs):
            if t.scale3d.x > 0:
                grid.setdefault((int(t.translation.x // cell), int(t.translation.y // cell)), []).append((t.translation.x, t.translation.y, t.translation.z))
    r2 = EDGE_R_CM * EDGE_R_CM
    for _, _, xs, stat in plan:
        for t in xs:
            if t.scale3d.x == 0: continue
            x, y, z = t.translation.x, t.translation.y, t.translation.z
            cx, cy = int(x // cell), int(y // cell); nb = -1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for (px, py, pz) in grid.get((cx + dx, cy + dy), ()):
                        if (px - x) ** 2 + (py - y) ** 2 < r2 and abs(pz - z) < 60: nb += 1
            if nb < min_nb:
                stat["edge"] += 1; t.scale3d = unreal.Vector(0, 0, 0)
    # 写回
    for k, name, xs, stat in plan:
        act, c = _comp(*k.split("/"))
        act.modify()
        # Strip -> A（57 cm），Tuft -> B（37 cm）；鸣潮 A:B 实例比 10374:5633 ≈ 65:35，与现有 Strip:Tuft ≈ 70:30 接近，直接沿用
        sm = meshes["A"] if name == "Strip" else meshes["B"]
        c.set_static_mesh(sm)
        c.set_material(0, mi)
        c.batch_update_instances_transforms(0, xs, world_space=False, mark_render_state_dirty=True, teleport=True)
        out.append([k, sm.get_name(), len(xs), stat])
    out.append([LAWN_LABEL, _lawn_vis(True)])
    for k in o["fol"]:
        label, name = k.split("/")
        act, c = _comp(label, name)
        if not c: continue
        act.modify()
        c.set_visibility(False, False)
        c.set_hidden_in_game(True, False)
        out.append([k, "hidden", c.get_instance_count()])
    return out

def orig():
    orig_path = _orig_path()
    if not os.path.exists(orig_path):
        return "no veg_orig.json in MC_WORKSPACE — nothing to restore"
    o = json.load(open(orig_path))
    out = []
    for k, s in o["hism"].items():
        label, name = k.split("/")
        act, c = _comp(label, name)
        if not c: continue
        act.modify()
        c.set_static_mesh(EAL.load_asset(s["mesh"]))
        c.set_material(0, None)
        sc, zs, rs = s["scales"], s.get("z"), s.get("rot")
        def back(i, t):
            if rs and i < len(rs): t.rotation = unreal.Rotator(roll=rs[i][2], pitch=rs[i][0], yaw=rs[i][1]).quaternion()
            if i < len(sc): t.scale3d = unreal.Vector(*sc[i])
            if zs and i < len(zs): t.translation = unreal.Vector(t.translation.x, t.translation.y, zs[i])
        _set_xf(c, back)
        out.append([k, "restored"])
    for k, s in o["fol"].items():
        label, name = k.split("/")
        act, c = _comp(label, name)
        if not c: continue
        act.modify()
        c.set_visibility(s["visible"], False)
        c.set_hidden_in_game(not s["visible"], False)
        out.append([k, "visible=%s" % s["visible"]])
    out.append([LAWN_LABEL, _lawn_vis(False)])
    return out

def state():
    hism, fol = _actors()
    r = []
    for act, c in hism + fol:
        t = c.get_instance_transform(0, world_space=False) if c.get_instance_count() else None
        r.append([_key(act, c), c.get_editor_property("static_mesh").get_name(), [m.get_name() if m else None for m in c.get_editor_property("override_materials")],
                  c.get_editor_property("visible"), c.get_instance_count(), round(t.scale3d.z, 3) if t else None])
    return r

LAWN_LABEL = "RESTORE_WWGrass_Lawn36153"
LAWN_BOX = (-18300.0, 700.0, -15000.0, 2600.0)   # Frame36153 右侧草坪（UE 世界 XY）：旧程序化撒点没覆盖到这里
LAWN_STEP = 55.0                                   # 抖动网格 55 cm ≈ 3.3 株/m²（鸣潮 Frame61250 实例密度约 2.2/m²，旧撒点 4–6/m²，取中间）
BP_GRASS = "/Game/Reconstruction/Rendering/Grass/BP_GroundGrass"

def _lawn_actor():
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for act in eas.get_all_level_actors():
        if act.get_actor_label() == LAWN_LABEL:
            return act
    return None

def lawn():
    """在 Frame36153 右侧草坪补撒（新 BP_GroundGrass actor，只在本关卡）。只撒在 SRC_Ground_* 地表上、坡度 < 37°。"""
    _check_level()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    old = _lawn_actor()
    if old: eas.destroy_actor(old)
    src = json.load(open(_xf_path())); rnd = random.Random(36153)
    pts = {"Strip": [], "Tuft": []}
    x0, y0, x1, y1 = LAWN_BOX
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            px, py = x + rnd.uniform(-0.45, 0.45) * LAWN_STEP, y + rnd.uniform(-0.45, 0.45) * LAWN_STEP
            h = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(px, py, 1500), unreal.Vector(px, py, -1500),
                                                       unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], unreal.DrawDebugTrace.NONE, True)
            if h is not None:
                tp = h.to_tuple(); a = tp[9]
                if a and a.get_actor_label().startswith("SRC_Ground") and tp[7].z > 0.8:
                    sxy, sz, _ = src[rnd.randrange(len(src))]
                    t = unreal.Transform(location=unreal.Vector(px, py, tp[5].z), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=rnd.uniform(-180, 180)), scale=unreal.Vector(sxy, sxy, sz))
                    pts["Strip" if rnd.random() < 0.65 else "Tuft"].append(t)   # 鸣潮 A:B ≈ 65:35
            y += LAWN_STEP
        x += LAWN_STEP
    act = eas.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(BP_GRASS), unreal.Vector(0, 0, 0))
    act.set_actor_label(LAWN_LABEL); act.set_folder_path("_Restore/Veg")
    mi = EAL.load_asset(MI); out = {}
    for c in act.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
        nm = c.get_name()
        c.set_static_mesh(EAL.load_asset(MESH["A"] if nm == "Strip" else MESH["B"]))
        c.set_material(0, mi)
        c.add_instances(pts.get(nm, []), False, True)
        out[nm] = c.get_instance_count()
    return out

def _lawn_vis(on):
    act = _lawn_actor()
    if not act: return None
    act.modify()
    for c in act.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
        c.set_visibility(on, False)
    return on

def vis(on="1"):
    """临时显隐所有 BP_GroundGrass HISM（拍"有草/无草"差分用，不进 orig）。"""
    hism, _ = _actors()
    for _, c in hism:
        c.set_visibility(on == "1", False)
    return {"visible": on == "1", "n": len(hism)}

def run(*a):
    cmd = a[0] if a else "state"
    if cmd == "import": return import_mesh()
    if cmd == "material": return material()
    if cmd == "apply": return apply(*a[1:])
    if cmd == "orig": return orig()
    if cmd == "vis": return vis(*a[1:])
    if cmd == "lawn": return lawn()
    if cmd == "color": return color(*a[1:])
    return state()
