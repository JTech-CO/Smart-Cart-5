#!/usr/bin/env python3
"""Exact cable-solid collision inspection, not dynamic/structural verification."""
from pathlib import Path
import sys,json,time,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import build_model as B
T=time.time()
for f in [B.structure,B.drive,B.batteries,B.power_panel,B.controls,B.handle_sensors,B.wiring,B.finalize_covers,B.clamps]:f()
parts={p['key']:p for p in B.PARTS}; wireparts={p['ref']:p for p in B.PARTS if p['category']=='wires'}
coll=[]
for w in B.WIRES:
 p=wireparts[w['id']];lo=np.array(p['bbox_mm'][:3]);hi=np.array(p['bbox_mm'][3:]);ws=B.SHAPES[p['key']]
 for k in B.OBSTACLES:
  o=parts[k];bb=o['bbox_mm']
  if np.any(hi<np.array(bb[:3])) or np.any(lo>np.array(bb[3:])):continue
  q=ws.intersect(B.SHAPES[k]).Volume()
  if q>1e-3:coll.append({'wire':w['id'],'obstacle':o['ref'],'role':o['role'],'volume_mm3':round(q,3),'key':k})
report={'scope':'Exact OCC intersection of swept cable solids with explicitly registered structural and major component-body obstacles. Does not check all decoration/fasteners, cable-cable separation, actual supplier tolerances or moving poses.', 'obstacle_count':len(B.OBSTACLES),'wire_count':len(B.WIRES),'collisions':coll,'bend_failures':[{'wire':w['id'],'min':w['bend_min_mm'],'required':w['bend_requested_mm']} for w in B.WIRES if w['bend_min_mm'] and w['bend_min_mm']+1e-5<w['bend_requested_mm']], 'seconds':time.time()-T}
report['passed']=not(report['collisions'] or report['bend_failures'])
(ROOT/'docs/routing-review.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

raise SystemExit(0 if report['passed'] else 1)
