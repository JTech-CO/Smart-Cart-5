#!/usr/bin/env python3
"""Build, check the modeled cable clearances, and export one matching revision."""
from pathlib import Path
import time,json,numpy as np
import build_model as B
T=time.time();ROOT=B.ROOT
for f in [B.structure,B.drive,B.batteries,B.power_panel,B.controls,B.handle_sensors,B.wiring,B.finalize_covers,B.clamps]:
 print(f.__name__,flush=True);f()
parts={p['key']:p for p in B.PARTS};wireparts={p['ref']:p for p in B.PARTS if p['category']=='wires'};coll=[]
for w in B.WIRES:
 p=wireparts[w['id']];a=p['bbox_mm'];ws=B.SHAPES[p['key']]
 for k in B.OBSTACLES:
  ob=parts[k];b=ob['bbox_mm']
  if any(a[i+3]<b[i] or b[i+3]<a[i] for i in range(3)):continue
  q=ws.intersect(B.SHAPES[k]).Volume()
  if q>1e-3:coll.append({'wire':w['id'],'obstacle':ob['ref'],'role':ob['role'],'volume_mm3':round(q,6),'key':k})
fail=[{'wire':w['id'],'min':w['bend_min_mm'],'required':w['bend_requested_mm']} for w in B.WIRES if w['bend_min_mm'] and w['bend_min_mm']+1e-5<w['bend_requested_mm']]
report={'scope':'Exact OCC intersection of cable sweeps with registered frame, deck, battery, major component, PCB and removable-cover solids. Excludes tolerances, motion, fasteners, every small decorative feature, and cable-cable clearance. Not a manufacturing or electrical approval.','obstacle_count':len(B.OBSTACLES),'wire_count':len(B.WIRES),'collisions':coll,'bend_failures':fail,'provisional_bend_rule':'4 x modeled OD, supplier minimum must be verified','passed':not(coll or fail),'seconds':time.time()-T}
(ROOT/'docs/routing-review.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if coll or fail:raise SystemExit('Review failed; exports intentionally stopped')
B.export_geometry();print('RELEASE BUILD COMPLETE',time.time()-T,flush=True)
