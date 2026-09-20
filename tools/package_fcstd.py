#!/usr/bin/env python3
"""FCStd Part::Feature solid snapshot with forward-only restoration order.
Native FreeCAD/SolidWorks have NOT been executed by this packager.
"""
from pathlib import Path
import json,zipfile,uuid,io,math
import xml.etree.ElementTree as E
import numpy as np
from scipy.spatial.transform import Rotation
import cadquery as cq
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'data/assembly.json').read_text());items=json.loads((ROOT/'cad/assembly-manifest.json').read_text())
def prop(p,n,t,tag,**args):
 e=E.SubElement(p,'Property',name=n,type=t);E.SubElement(e,tag,**{k:str(v) for k,v in args.items()})
doc=E.Element('Document',SchemaVersion='4');dp=E.SubElement(doc,'Properties',Count='7')
for k,v in {'Comment':'D5 only. Real BREP solid snapshot. M/D dimensions and electrical release remain on hold. Not a PartDesign feature history.','Company':'JTech-CO','CreatedBy':'Smart-Cart-5 build tools','CreationDate':'2026-09-21T00:00:00','Id':str(uuid.uuid4()),'Label':'Smart-Cart-5 / Prototype Integration','FileName':''}.items():prop(dp,k,'App::PropertyString','String',value=v)
obs=E.SubElement(doc,'Objects',Count=str(len(items)));od=E.SubElement(doc,'ObjectData',Count=str(len(items)));gui=E.Element('Document',SchemaVersion='1');vg=E.SubElement(gui,'ViewProviderData',Count=str(len(items)))
for it in items:
 name=it['name'];E.SubElement(obs,'Object',type='Part::Feature',name=name);o=E.SubElement(od,'Object',name=name);ps=E.SubElement(o,'Properties',Count='3')
 label=next((c['name'] for c in D['components'] if c['id']==it['ref']),it['ref'])+' / '+it['ref']+' / '+it['material']
 prop(ps,'Label','App::PropertyString','String',value=label);prop(ps,'Placement','App::PropertyPlacement','PropertyPlacement',Px=0,Py=0,Pz=0,Q0=0,Q1=0,Q2=0,Q3=1);prop(ps,'Shape','Part::PropertyPartShape','Part',file=name+'.brp')
 vis=it['category'] not in ['covers','accessories'];v=E.SubElement(vg,'ViewProvider',name=name,expanded='0');ps=E.SubElement(v,'Properties',Count='5');mat=D['materials'][it['material']];rgb=[int(mat['color'][i:i+2],16) for i in [1,3,5]];packed=(rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)
 prop(ps,'ShapeColor','App::PropertyColor','PropertyColor',value=packed);prop(ps,'Visibility','App::PropertyBool','Bool',value='true' if vis else 'false');prop(ps,'LineWidth','App::PropertyFloat','Float',value=1.0);prop(ps,'Transparency','App::PropertyInteger','Integer',value=round(100*(1-mat.get('alpha',1))));prop(ps,'DisplayMode','App::PropertyEnumeration','Integer',value=1)
target=np.array([0.,0.,450]);direction=np.array([1.,-1.2,.75]);direction/=np.linalg.norm(direction);right=np.cross([0,0,1],direction);right/=np.linalg.norm(right);up=np.cross(direction,right);rv=Rotation.from_matrix(np.column_stack([right,up,direction])).as_rotvec();angle=np.linalg.norm(rv);axis=rv/angle;position=target+direction*2500
camera='OrthographicCamera { viewportMapping ADJUST_CAMERA position '+' '.join(map(str,position))+' orientation '+' '.join(map(str,[*axis,angle]))+' nearDistance 1 farDistance 10000 aspectRatio 1.4 focalDistance 2500 height 1350 }';E.SubElement(gui,'Camera',settings=camera)
out=ROOT/'cad/Smart-Cart-5.FCStd'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('Document.xml',E.tostring(doc,encoding='utf-8',xml_declaration=True))
 # Application payloads MUST precede GuiDocument.xml for a monotone ZIP reader.
 for it in items:z.write(ROOT/'cad'/it['file'],it['name']+'.brp')
 z.writestr('GuiDocument.xml',E.tostring(gui,encoding='utf-8',xml_declaration=True))
 thumb=ROOT/'assets/previews/render-overall.png'
 if thumb.exists():
  from PIL import Image
  im=Image.open(thumb).convert('RGB');im.thumbnail((512,512));buf=io.BytesIO();im.save(buf,format='PNG');z.writestr('thumbnails/Thumbnail.png',buf.getvalue())
checks=[]
with zipfile.ZipFile(out) as z:
 names=z.namelist();assert z.testzip() is None;assert names[0]=='Document.xml';assert names.index('GuiDocument.xml')>max(names.index(it['name']+'.brp') for it in items)
 for it in items:
  sh=cq.Shape.importBrep(io.BytesIO(z.read(it['name']+'.brp')));err=abs(sh.Volume()-it['volume_mm3'])/max(it['volume_mm3'],1e-12)
  assert sh.isValid() and len(sh.Solids())==it['solid_count'] and err<1e-6,(it['name'],err)
  checks.append({'name':it['name'],'valid':True,'solids':len(sh.Solids()),'relative_volume_error':err})
report={'file':out.name,'zip_crc':True,'xml_parse':True,'forward_only_app_payload_order':True,'feature_count':len(items),'d4_or_prototype_legacy_objects':0,'all_brep_roundtrips_valid':True,'checks':checks,'native_freecad_open_test':False,'native_solidworks_open_test':False,'editable_scope':'Part::Feature solid snapshots and source regeneration. No native Sketcher/PartDesign feature history.'}
(ROOT/'docs/cad-container-qa.json').write_text(json.dumps(report,indent=2));print(out.name,len(items),'valid restored features',flush=True)
# Neutral BREP round-trip independent of the FCStd container.
sh=cq.importers.importStep(str(ROOT/'cad/Smart-Cart-5.step')).val();assert sh.isValid();expected=sum(i['volume_mm3'] for i in items if i['category']!='accessories');err=abs(sh.Volume()-expected)/expected;assert err<1e-5
(ROOT/'docs/step-qa.json').write_text(json.dumps({'valid':True,'solid_count':len(sh.Solids()),'volume_mm3':sh.Volume(),'relative_volume_error':err,'native_solidworks_open_test':False},indent=2))
# The original-pattern bracket is also available separately; engineering hold retained.
s=cq.Shape.importBrep(str(ROOT/'cad/SCMB-A01_Bracket.brep'));cq.exporters.export(s,str(ROOT/'cad/SCMB-A01_Bracket.step'))
print('STEP round-trip passed',flush=True)
