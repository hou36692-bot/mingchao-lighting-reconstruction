"""Save selected textures of one event as PNG.

Environment:
  RDC  capture path (required)
  OUT  output directory, created if missing (required)
  EID  event id to bind before saving
  IDS  comma-separated resource ids to save
"""
import os
import renderdoc as rd
RDC=os.environ["RDC"]; OUT=os.environ["OUT"]; EID=int(os.environ["EID"]); IDS=[int(x) for x in os.environ["IDS"].split(",")]
os.makedirs(OUT, exist_ok=True); log=[]
try:
    cap=rd.OpenCaptureFile(); assert cap.OpenFile(RDC,"",None)==rd.ResultCode.Succeeded
    r,ctrl=cap.OpenCapture(rd.ReplayOptions(),None); assert r==rd.ResultCode.Succeeded
    ctrl.SetFrameEvent(EID, True)
    for i in IDS:
        ts=rd.TextureSave(); ts.resourceId=rd.ResourceId();
        for t in ctrl.GetTextures():
            if int(t.resourceId)==i: ts.resourceId=t.resourceId; break
        ts.mip=0; ts.slice.sliceIndex=0; ts.destType=rd.FileType.PNG; ts.alpha=rd.AlphaMapping.Discard
        p=os.path.join(OUT,"E%d_R%d.png"%(EID,i)); ctrl.SaveTexture(ts,p); log.append("saved "+p)
    ctrl.Shutdown(); cap.Shutdown()
except Exception:
    import traceback; log.append("EXC "+traceback.format_exc())
open(os.path.join(OUT,"save.log"),"w").write("\n".join(log)); os._exit(0)
