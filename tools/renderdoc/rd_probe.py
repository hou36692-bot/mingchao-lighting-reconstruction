"""Smoke test for a RenderDoc capture.

Opens the capture and reports the API, frame number, and the number of root
actions / textures / buffers. Useful to check that a capture replays at all
before running the heavier dump scripts.

Environment:
  RDC  capture path (required)
  OUT  output directory for probe.txt (default: ./out)
"""
import os
import time

OUT = os.environ.get("OUT", "out")
os.makedirs(OUT, exist_ok=True)
out = os.path.join(OUT, "probe.txt")
lines = []
try:
    import renderdoc as rd
    lines.append("renderdoc ok; version=" + str(rd.GetVersionString()))
    path = os.environ["RDC"]
    cap = rd.OpenCaptureFile()
    t = time.time()
    res = cap.OpenFile(path, "", None)
    lines.append("OpenFile: %s (%.1fs)" % (res, time.time() - t))
    if res == rd.ResultCode.Succeeded:
        lines.append("API: %s" % cap.APIProperties().pipelineType)
        t = time.time()
        res, ctrl = cap.OpenCapture(rd.ReplayOptions(), None)
        lines.append("OpenCapture: %s (%.1fs)" % (res, time.time() - t))
        if res == rd.ResultCode.Succeeded:
            fi = ctrl.GetFrameInfo()
            lines.append("frame=%s, root actions=%d, textures=%d, buffers=%d" % (
                fi.frameNumber, len(ctrl.GetRootActions()), len(ctrl.GetTextures()), len(ctrl.GetBuffers())))
            ctrl.Shutdown()
    cap.Shutdown()
except Exception as e:
    import traceback
    lines.append("EXC " + traceback.format_exc())
open(out, "w", encoding="utf-8").write("\n".join(lines))
os._exit(0)
