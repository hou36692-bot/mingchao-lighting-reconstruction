"""Dump a texture table and a per-event pipeline table from a capture.

Environment:
  RDC     capture path (required)
  OUTDIR  output directory; textures.csv / events.csv / events.log go here
"""
import os, time, json
import renderdoc as rd
RDC = os.environ["RDC"]; OUTDIR = os.environ["OUTDIR"]
os.makedirs(OUTDIR, exist_ok=True)
log = []
try:
    cap = rd.OpenCaptureFile(); assert cap.OpenFile(RDC, "", None) == rd.ResultCode.Succeeded
    r, ctrl = cap.OpenCapture(rd.ReplayOptions(), None); assert r == rd.ResultCode.Succeeded
    sf = ctrl.GetStructuredFile()
    tex = {}
    for t in ctrl.GetTextures():
        tex[int(t.resourceId)] = t
    names = {int(x.resourceId): x.name for x in ctrl.GetResources()}
    # texture table
    with open(os.path.join(OUTDIR, "textures.csv"), "w", encoding="utf-8-sig") as f:
        f.write("id,name,w,h,d,arr,mips,fmt,msaa,flags\n")
        for i, t in tex.items():
            f.write("%d,%s,%d,%d,%d,%d,%d,%s,%d,%d\n" % (i, names.get(i, "").replace(",", ";"), t.width, t.height, t.depth, t.arraysize, t.mips, t.format.Name(), t.msQual if False else t.msSamp, int(t.creationFlags)))
    rows = []
    def collect(a):
        if a.flags & (rd.ActionFlags.Drawcall | rd.ActionFlags.Dispatch | rd.ActionFlags.Clear | rd.ActionFlags.Copy):
            rows.append(a)
        for c in a.children: collect(c)
    for a in ctrl.GetRootActions(): collect(a)
    t0 = time.time()
    out = open(os.path.join(OUTDIR, "events.csv"), "w", encoding="utf-8-sig")
    out.write("eid,kind,idx,inst,vp,rts,depth,vs,ps,cs,ps_srv,vs_srv,blend0,depthfunc,depthwrite\n")
    for n, a in enumerate(rows):
        f = a.flags
        kind = "D" if f & rd.ActionFlags.Drawcall else "C" if f & rd.ActionFlags.Dispatch else "X" if f & rd.ActionFlags.Clear else "Y"
        ctrl.SetFrameEvent(a.eventId, True)
        s = ctrl.GetPipelineState()
        rts = ""; dep = ""; vs = ps = cs = ""; pss = vss = ""; vp = ""; bl = ""; df = ""; dw = ""
        if kind in "DC":
            if kind == "D":
                rts = ";".join(str(int(d.resource)) for d in s.GetOutputTargets() if int(d.resource) != 0)
                dd = s.GetDepthTarget(); dep = str(int(dd.resource)) if int(dd.resource) else ""
                vs = str(int(s.GetShader(rd.ShaderStage.Vertex))); ps = str(int(s.GetShader(rd.ShaderStage.Pixel)))
                v = s.GetViewport(0); vp = "%dx%d" % (v.width, v.height)
                pss = ";".join(str(int(u.descriptor.resource)) for u in s.GetReadOnlyResources(rd.ShaderStage.Pixel) if int(u.descriptor.resource))
                vss = ";".join(str(int(u.descriptor.resource)) for u in s.GetReadOnlyResources(rd.ShaderStage.Vertex) if int(u.descriptor.resource))
                try:
                    d3 = ctrl.GetD3D11PipelineState()
                    b = d3.outputMerger.blendState.blends[0]
                    bl = "%d:%s/%s" % (int(b.enabled), b.colorBlend.source, b.colorBlend.destination)
                    ds = d3.outputMerger.depthStencilState
                    df = str(ds.depthFunction); dw = str(int(ds.depthWrites))
                except Exception as e:
                    bl = "?"
            else:
                cs = str(int(s.GetShader(rd.ShaderStage.Compute)))
                pss = ";".join(str(int(u.descriptor.resource)) for u in s.GetReadOnlyResources(rd.ShaderStage.Compute) if int(u.descriptor.resource))
                rts = ";".join(str(int(u.descriptor.resource)) for u in s.GetReadWriteResources(rd.ShaderStage.Compute) if int(u.descriptor.resource))
        else:
            try:
                rts = ";".join(str(int(d.resource)) for d in ctrl.GetPipelineState().GetOutputTargets() if int(d.resource) != 0)
            except Exception: pass
        out.write("%d,%s,%d,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (a.eventId, kind, a.numIndices, a.numInstances, vp, rts, dep, vs, ps, cs, pss, vss, bl, df.replace("CompareFunction.",""), dw))
        if n % 300 == 0: log.append("n=%d t=%.0fs" % (n, time.time()-t0))
    out.close()
    log.append("done rows=%d t=%.0fs" % (len(rows), time.time()-t0))
    ctrl.Shutdown(); cap.Shutdown()
except Exception:
    import traceback; log.append("EXC " + traceback.format_exc())
open(os.path.join(OUTDIR, "events.log"), "w").write("\n".join(log))
os._exit(0)
