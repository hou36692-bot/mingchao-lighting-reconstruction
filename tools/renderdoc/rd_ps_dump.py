"""Disassemble every pixel shader used by draw events between E0 and E1.

Reads $OUTDIR/events.csv (written by rd_events.py) and writes one .txt per
pixel shader plus summary.csv / log.txt under $OUTDIR/ps_E0_E1.

Environment:
  RDC     capture path (required)
  OUTDIR  directory holding events.csv (required)
  E0, E1  inclusive event-id range (required)
"""
import os, csv, re, collections
import renderdoc as rd
RDC=os.environ["RDC"]; D=os.environ["OUTDIR"]; E0=int(os.environ["E0"]); E1=int(os.environ["E1"])
sd=os.path.join(D,"ps_%d_%d"%(E0,E1)); os.makedirs(sd,exist_ok=True); log=[]
try:
    ev=[e for e in csv.DictReader(open(os.path.join(D,"events.csv"),encoding="utf-8-sig")) if e["kind"]=="D" and E0<=int(e["eid"])<=E1]
    g=collections.OrderedDict()
    for e in ev:
        x=g.setdefault(e["ps"],{"n":0,"idx":0,"first":int(e["eid"])}); x["n"]+=1; x["idx"]+=int(e["idx"])
    cap=rd.OpenCaptureFile(); assert cap.OpenFile(RDC,"",None)==rd.ResultCode.Succeeded
    r,ctrl=cap.OpenCapture(rd.ReplayOptions(),None); assert r==rd.ResultCode.Succeeded
    tg=ctrl.GetDisassemblyTargets(True); log.append("targets "+str(tg))
    rows=[]
    for ps,x in g.items():
        ctrl.SetFrameEvent(x["first"],True); s=ctrl.GetPipelineState()
        refl=s.GetShaderReflection(rd.ShaderStage.Pixel)
        txt=ctrl.DisassembleShader(s.GetGraphicsPipelineObject(),refl,tg[0])
        open(os.path.join(sd,"ps%s.txt"%ps),"w",encoding="utf-8").write(txt)
        outs=sorted(set(re.findall(r"dcl_output\s+o(\d+)\.",txt)))
        wr=sorted(set(re.findall(r"^\s*\d*:?\s*\w+(?:_sat)?\s+o(\d+)\.",txt,re.M)))
        rows.append((ps,x["n"],x["idx"],x["first"],",".join(outs),",".join(wr),len(txt.splitlines())))
    with open(os.path.join(sd,"summary.csv"),"w",encoding="utf-8-sig") as f:
        f.write("ps,draws,indices,firstEid,declOutputs,writtenOutputs,lines\n")
        for r_ in rows: f.write(",".join(map(str,r_))+"\n")
    ctrl.Shutdown(); cap.Shutdown()
except Exception:
    import traceback; log.append("EXC "+traceback.format_exc())
open(os.path.join(sd,"log.txt"),"w").write("\n".join(log)); os._exit(0)
