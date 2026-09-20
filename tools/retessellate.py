#!/usr/bin/env python3
"""Regenerate the web mesh from the shipped exact BREP features.
No CAD dimensions or topology are changed. Requires the CAD build dependencies.
"""
from pathlib import Path
import json
import cadquery as cq
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def main():
    model=json.loads((ROOT/'data/assembly.json').read_text())
    features=json.loads((ROOT/'cad/assembly-manifest.json').read_text())
    chunks=[];offset=0
    assert len(features)==len(model['geometry'])
    for feature,meta in zip(features,model['geometry']):
        assert (feature['ref'],feature['material'])==(meta['ref'],meta['material'])
        shape=cq.Shape.importBrep(str(ROOT/'cad'/feature['file']))
        vertices,faces=shape.tessellate(.5,.3)
        vv=np.array([[v.x,v.y,v.z] for v in vertices],dtype=np.float64)/1000
        ff=np.array(faces,dtype=np.int32);normals=np.zeros_like(vv)
        nn=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]])
        for k in range(3):np.add.at(normals,ff[:,k],nn)
        normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-15)
        flat=ff.reshape(-1);arr=np.concatenate([vv[flat],normals[flat]],axis=1).astype('<f4')
        data=arr.tobytes();chunks.append(data);meta.update(offset=offset,count=len(arr));offset+=len(data)
    (ROOT/'data/geometry.bin').write_bytes(b''.join(chunks))
    model['counts']['triangles']=sum(g['count']//3 for g in model['geometry'])
    (ROOT/'data/assembly.json').write_text(json.dumps(model,ensure_ascii=False,separators=(',',':')))
    q=json.loads((ROOT/'docs/build-summary.json').read_text());q['counts']=model['counts'];q['geometry_bytes']=offset
    (ROOT/'docs/build-summary.json').write_text(json.dumps(q,indent=2))
    print('Web tessellation:',model['counts']['triangles'],'triangles;',offset,'bytes',flush=True)
if __name__=='__main__':main()
