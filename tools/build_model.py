#!/usr/bin/env python3
"""Single geometry source for the D5 web viewer, STEP and FreeCAD solid snapshot.
CadQuery 2.8 / Open CASCADE. SI is used by the renderer; design/CAD use millimetres.
Dimensions tagged D/M are explicit design proposals, never measured product data.
"""
from __future__ import annotations
import sys, json, math, time, struct, hashlib, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
import cadquery as cq
from bracket_geometry import build as build_bracket

ROOT=Path(__file__).resolve().parents[1]
P=json.loads((ROOT/'data/parameters.json').read_text())
BP=json.loads((ROOT/'data/bracket-parameters.json').read_text())
H=P['deck']['top']; U=H-P['deck']['thickness']; F=U-P['deck']['frame_height']
R=P['drive']['wheel_diameter']/2
if abs(R-P['drive']['axis_z'])>1e-6: raise ValueError('Update drive.axis_z to wheel_diameter/2 before rebuilding')
if F-6<=R+100: raise ValueError('Deck too low for the original bracket and its proposed adapter')
PARTS=[]; DECALS=[]; PORTS={}; WIRES=[]; OBSTACLES=[]; SHAPES={}; META={}; UID=0
MATS={
 'paint':{'color':'#262e33','metal':.35,'rough':.43,'surface':1},
 'deckmat':{'color':'#272c2e','metal':.08,'rough':.8,'surface':5},
 'rubber':{'color':'#222628','metal':0,'rough':.83,'surface':2},
 'silver':{'color':'#b7c1c9','metal':.88,'rough':.3,'surface':3},
 'steel':{'color':'#929ca6','metal':.84,'rough':.25,'surface':3},
 'black':{'color':'#202a32','metal':.16,'rough':.34,'surface':1},
 'battery':{'color':'#343b40','metal':.02,'rough':.48,'surface':1},
 'pcb':{'color':'#126653','metal':.08,'rough':.58,'surface':4},
 'bluepcb':{'color':'#205c91','metal':.08,'rough':.55,'surface':4},
 'gold':{'color':'#bea365','metal':.72,'rough':.32,'surface':0},
 'red':{'color':'#cc3b37','metal':.03,'rough':.5,'surface':2},
 'wireblack':{'color':'#303b46','metal':0,'rough':.51,'surface':2},
 'blue':{'color':'#3590d4','metal':.03,'rough':.44,'surface':2},
 'yellow':{'color':'#e5b530','metal':.04,'rough':.52,'surface':1},
 'green':{'color':'#34a87b','metal':.02,'rough':.53,'surface':1},
 'white':{'color':'#e1e7e9','metal':.04,'rough':.57,'surface':1},
 'purple':{'color':'#9c7bd5','metal':.03,'rough':.5,'surface':2},
 'clear':{'color':'#a7bdc8','metal':.04,'rough':.13,'surface':0,'alpha':.18},
 'sensorwindow':{'color':'#191d25','metal':.4,'rough':.12,'surface':0},
}
def v(p):return cq.Vector(*map(float,p))
def box(l,w,h,center,r=0):
    s=cq.Workplane('XY').box(l,w,h)
    if r:
        try:s=s.edges().fillet(min(r,min(l,w,h)*.45))
        except Exception:pass
    return s.val().translate(tuple(center))
def cyl(r,h,base,axis=(0,0,1),ri=0):
    s=cq.Solid.makeCylinder(r,h,v(base),v(axis))
    if ri:s=s.cut(cq.Solid.makeCylinder(ri,h+.2,v(np.array(base)-np.array(axis)*.1),v(axis)))
    return s

def ring_plate(l,w,t,center,wall=2):
    return box(l,w,t,center).cut(box(l-2*wall,w-2*wall,t+2,center))

def cut_z(s,points,r,z0,h):
    for x,y in points:s=s.cut(cyl(r,h,(x,y,z0)))
    return s

def add(ref,s,mat='silver',category='frame',name=None,grade='D/M',note='',obstacle=False,role='body'):
    global UID
    if isinstance(s,cq.Workplane):s=s.val()
    if s.Volume()<1e-7:raise ValueError('Empty shape '+ref)
    UID+=1;key=f'D5_{UID:04d}'
    bb=s.BoundingBox()
    PARTS.append({'key':key,'ref':ref,'category':category,'material':mat,'role':role,'name':name or ref,'grade':grade,
                  'note':note,'bbox_mm':[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]})
    SHAPES[key]=s
    if obstacle or role in ['PCB','polymer support','cooling fin']:OBSTACLES.append(key)
    if ref not in META:META[ref]={'id':ref,'name':name or ref,'category':category,'grade':grade,'note':note}
    return s

def decal(ref,title,sub,center,right,up,size,bg='#e8eced',ink='#23313b'):
    DECALS.append({'ref':ref,'title':title,'sub':sub,'center':center,'right':right,'up':up,'size':size,'bg':bg,'ink':ink})

def port(id,point,ref,terminal='',kind='power'):
    PORTS[id]={'id':id,'ref':ref,'point':list(point),'terminal':terminal or id.split('.')[-1],'kind':kind}
    return point

def bolt(ref,p,size=6,axis=(0,0,1),category='hardware',length=10):
    # Visual fastener: genuine hex head, washer and shank; locations on proposed holes.
    pl=cq.Plane(origin=tuple(p),normal=axis)
    sh=cq.Workplane(pl).polygon(6,size*1.72).extrude(size*.65).val()
    add(ref,sh,'steel',category,grade='D',role='fastener')
    add(ref,cyl(size,1.3,p,axis,size*.52),'silver',category,role='fastener')
    add(ref,cyl(size*.48,length,tuple(np.array(p)-np.array(axis)*length),axis),'steel',category,role='fastener')

def pcb(ref,l,w,base,category='controls',color='pcb',grade='B/M',name=None):
    x,y,z=base
    add(ref,box(l,w,1.6,(x,y,z+.8),.3),color,category,name,grade,role='PCB')
    # Shield cans, ICs and passives are geometric visual references, not exact PCB layouts.
    add(ref,box(l*.31,w*.43,2,(x,y,z+2.6),.25),'black',category,role='chip')
    for sign in [-1,1]:
        for j in range(7):
            xx=x-l*.39+j*l*.12
            add(ref,box(2.2,1.4,.9,(xx,y+sign*w*.34,z+2.05)),'silver',category,role='passive')
    return z+1.6

def terminal_block(ref,x,y,z,n=2,step=10,category='power',prefix='T',along='x',mat='green'):
    l=n*step
    add(ref,box(l,12,10,(x,y,z+5),1),mat,category,role='terminal housing')
    for k in range(n):
        px=x+(k-(n-1)/2)*step
        add(ref,cyl(2.5,1,(px,y,z+10)),'steel',category,role='terminal screw')
        # Explicit entry bore with conductive sleeve; wire ends at the mouth.
        add(ref,cyl(2.8,4,(px,y-6,z+4),(0,-1,0),1.5),'gold',category,role='terminal ferrule')
        port(f'{ref}.{prefix}{k}',(px,y-10,z+4),ref,prefix+str(k))

def route_points(points,r):
    """C1 line/true circular fillets. Returns an OCC wire and sampled centreline.
    Requested r is preserved unless segment lengths cannot accommodate it, in which
    case the measured smaller radius is reported (never silently passed by QA).
    """
    ps=[np.array(p,dtype=float) for p in points]
    # Preserve the specified radius where a segment has only one adjacent bend.
    # Shared segments allocate their available tangent length to BOTH bends.
    angles=[0.0]*len(ps);ds=[0.0]*len(ps)
    for i in range(1,len(ps)-1):
        u=(ps[i]-ps[i-1])/np.linalg.norm(ps[i]-ps[i-1]);w=(ps[i+1]-ps[i])/np.linalg.norm(ps[i+1]-ps[i])
        angles[i]=math.acos(float(np.clip(np.dot(u,w),-1,1)))
        if angles[i]>math.pi-.01:raise ValueError('Cable reverses on itself')
        ds[i]=r*math.tan(angles[i]/2)
    for i in range(len(ps)-1):
        avail=np.linalg.norm(ps[i+1]-ps[i])*.96
        total=ds[i]+ds[i+1]
        if total>avail:
            ds[i]*=avail/total;ds[i+1]*=avail/total
    out=[ps[0]];edges=[];cur=ps[0];radii=[]
    for i in range(1,len(ps)-1):
        a,b,c=ps[i-1:i+2];u=(b-a)/np.linalg.norm(b-a);w=(c-b)/np.linalg.norm(c-b)
        angle=math.acos(float(np.clip(np.dot(u,w),-1,1)))
        if angle<1e-4:continue
        if angle>math.pi-.01:raise ValueError('Cable reverses on itself')
        dist=r*math.tan(angle/2)
        d=ds[i]
        actual=d/math.tan(angle/2);radii.append(actual)
        start=b-u*d;end=b+w*d
        if np.linalg.norm(start-cur)>1e-7:
            edges.append(cq.Edge.makeLine(v(cur),v(start)))
            n=max(1,int(np.linalg.norm(start-cur)/3))
            out.extend(cur+(start-cur)*q/n for q in range(1,n+1))
        normal=np.cross(u,w);normal/=np.linalg.norm(normal)
        cent=start+np.cross(normal,u)*actual
        radial=start-cent
        mid=cent+radial*math.cos(angle/2)+np.cross(normal,radial)*math.sin(angle/2)
        edges.append(cq.Edge.makeThreePointArc(v(start),v(mid),v(end)))
        n=max(4,int(angle*actual/2))
        for j in range(1,n+1):
            t=angle*j/n;out.append(cent+radial*math.cos(t)+np.cross(normal,radial)*math.sin(t))
        cur=end
    if np.linalg.norm(ps[-1]-cur)>1e-7:
        edges.append(cq.Edge.makeLine(v(cur),v(ps[-1])))
        n=max(1,int(np.linalg.norm(ps[-1]-cur)/3));out.extend(cur+(ps[-1]-cur)*q/n for q in range(1,n+1))
    return cq.Wire.assembleEdges(edges),out,radii

def cable(id,a,b,via,mat='red',kind='power',od=None,net='',notes='',rating='TBD',bend=None):
    if od is None:od=P['routing']['wire12_od'] if kind=='power' else P['routing']['wire18_od']
    points=[PORTS[a]['point']]+via+[PORTS[b]['point']]
    # Drop redundant equal endpoints.
    points=[p for i,p in enumerate(points) if i==0 or np.linalg.norm(np.array(p)-np.array(points[i-1]))>1e-6]
    rr=bend or od*P['routing']['minimum_bend_od_factor']
    path,samples,radii=route_points(points,rr)
    tang=np.array(samples[1])-np.array(samples[0]);tang=tang/np.linalg.norm(tang)
    profile=cq.Workplane(cq.Plane(origin=points[0],normal=tuple(tang))).circle(od/2)
    shape=profile.sweep(cq.Workplane().newObject([path]),isFrenet=False).val()
    add(id,shape,mat,'wires',id,'D/M',notes,role=kind)
    length=path.Length()
    WIRES.append({'id':id,'from':a,'to':b,'kind':kind,'net':net or id,'od_mm':od,'bend_requested_mm':rr,
        'bend_min_mm':min(radii) if radii else None,'length_mm':round(length,1),
        'cut_length_proposal_mm':math.ceil(length*P['routing']['length_allowance']/10)*10,
        'points_mm':points,'sampled_mm':[list(map(float,p)) for p in samples],'notes':notes,'rating':rating})
    return shape


def rear_service_cut(shape,z0,height):
    for yy in [-150,150]:shape=shape.cut(box(60,30,height,(-220,yy,z0+height/2),5))
    return shape

def structure():
    # Commercial platform envelope, not a new aluminium extrusion chassis.
    service=[(-220,150),(-220,-150)]
    cross_holes=[(x,y) for x in [-160,80] for y in [-280,280]]
    deck=box(900,600,P['deck']['thickness'],(0,0,(H+U)/2),5)
    deck=rear_service_cut(deck,U-1,P['deck']['thickness']+2)
    deck=cut_z(deck,cross_holes,4.25,U-1,H-U+2)
    deck=cut_z(deck,[(360,-244),(360,244),(360,0)],9,U-1,P['deck']['thickness']+2)
    add('CART-DECK',deck,'paint','frame','데스텀 900 × 600 상판','A + D/M','900×600 option confirmed. Thickness/height are proposed; original frame must be measured.',True)
    # Rubber anti-slip surface is real separate geometry; deck holes continued through it.
    mat=box(862,562,2,(0,0,H+1),.7);mat=rear_service_cut(mat,H-.1,3);mat=cut_z(mat,[(360,-244),(360,244),(360,0)],9,H-.1,3)
    mat=cut_z(mat,cross_holes,4.25,H-.1,3)
    add('DECK-MAT',mat,'deckmat','frame','미끄럼 방지 매트','D',obstacle=True)
    for s in [-1,1]:
        add('FRAME-LONG',cut_z(box(840,30,30,(0,s*280,U-15)).cut(box(842,26,26,(0,s*280,U-15))),cross_holes,4.25,F-1,32), 'paint','frame','기존 하부 프레임 대용 단면','D/M',obstacle=True)
    for x in [-420,420]:
        add('FRAME-END',box(30,530,30,(x,0,U-15)).cut(box(26,532,26,(x,0,U-15))), 'paint','frame',grade='D/M',obstacle=True)
    # Load spreading plates sit below, and bear against, the existing frame.
    for x,ref in [(-335,'REAR-SPREADER'),(345,'FRONT-SPREADER')]:
        plate=box(180 if x<0 else 130,590,6,(x,0,F-3),2)
        holes=[(x+dx,s*280) for dx in [-45,45] for s in [-1,1]]
        plate=cut_z(plate,holes,4.25,F-7,8)
        add(ref,plate,'silver','adapters','프레임 하중 분산판','D/M','Bolt/clamp to load-bearing frame; not sheet-only fastening. Hole locations require measurement.',True)
        for pt in holes:bolt(ref,(*pt,F),8,category='adapters',length=8)
    for x,y in service:
        add('GLAND',box(65,35,H-U+8,(x,y,(H+U)/2),3).cut(box(54,24,H-U+10,(x,y,(H+U)/2),3)),'black','hardware','보호 부싱을 갖춘 60 × 30 배선홀','D',role='grommet')
    for yy in [-244,0,244]:
        add('FRONT-GLAND',cyl(11,H-U+8,(360,yy,U-4),ri=7.5),'black','hardware','전면 센서 전용 관통홀','D',role='grommet')
    decal('CART-DECK','SMART CART 05','PROTOTYPE / V8 INTEGRATION',(160,0,H+2.2),(0,1,0),(-1,0,0),(210,38),'#303b42','#c6ced4')
    # Two local flat cross-members carry the hanging batteries, not the thin deck skin.
    # Their tops bear against the underside of both existing longitudinal rails.
    for xx in [-160,80]:
        hangerholes=[(xx,sy*185+dy) for sy in [-1,1] for dy in [-43.5,43.5]]+[(xx,-126),(xx,126)]
        beam=cut_z(box(30,590,10,(xx,0,F-5),1.5),hangerholes,3.3,F-11,12)
        beam=cut_z(beam,cross_holes,4.25,F-11,12)
        add('BATTERY-CROSS',beam,'silver','adapters','배터리·전력부 하중 전달 가로 보강대','D/M','Two 30×590×10 flat members; positive contact with both frame rails. Material, fastening and bending capacity require structural verification.',True)
        for yy in [-280,280]:
            bolt('BATTERY-CROSS',(xx,yy,H+2.5),8,category='adapters',length=H-F+13)
            # Hollow frame needs a crush sleeve. Hole positions and access are M.
            add('BATTERY-CROSS',cyl(6.5,26,(xx,yy,F+2),ri=4.3),'steel','adapters',role='crush sleeve')
    # Height adapter above each retained 110mm caster. Plates, walls and real holes.
    for s in [-1,1]:
        x=345;y=s*230;top=F-6;btm=P['caster']['mount_top']
        for z in [btm+3,top-3]:
            plate=cut_z(box(96,88,6,(x,y,z),2),[(x+a,y+b) for a in [-30,30] for b in [-26,26]],4.25,z-4,8)
            add(f'CASTER-RISER-{s}',plate,'silver','adapters','전륜 높이 보정대','D/M',obstacle=True)
        for dx in [-42,42]:
            leg=box(6,80,top-btm-12,(x+dx,y,(top+btm)/2))
            # Lightening opening leaves material around the vertical load path.
            leg=leg.cut(box(8,44,max(12,top-btm-48),(x+dx,y,(top+btm)/2),4))
            add(f'CASTER-RISER-{s}',leg,'silver','adapters',obstacle=True)
        for dx in [-30,30]:
            for dy in [-26,26]:bolt(f'CASTER-RISER-{s}',(x+dx,y+dy,btm+6),8,category='adapters',length=11)
        add(f'CASTER-{s}',box(90,80,5,(x,y,btm-2.5),2),'steel','drive','110mm TPR 자유회전 캐스터','A + D/M',obstacle=True)
        add(f'CASTER-{s}',cyl(29,13,(x,y,btm-18)),'steel','drive',obstacle=True)
        cx=x-28;cz=55
        # Fork legs connect the swivel head to the axle without crossing the wheel.
        for q in [-1,1]:
            pl=cq.Plane(origin=(0,y+q*22,0),xDir=(1,0,0),normal=(0,-q,0))
            # XZ profile using a fixed plane and translation is less ambiguous.
            shape=cq.Workplane('XZ').polyline([(x-36,52),(x-17,52),(x+18,btm-18),(x-25,btm-18)]).close().extrude(4).val().translate((0,y+q*22,0))
            shape=shape.cut(cyl(4.1,60,(cx,y-30,cz),(0,1,0)))
            add(f'CASTER-{s}',shape,'steel','drive',obstacle=True)
        tire=cyl(55,32,(cx,y-16,cz),(0,1,0),31)
        try:tire=cq.Workplane().newObject([tire]).edges().fillet(3).val()
        except Exception:pass
        add(f'CASTER-{s}',tire,'rubber','drive',obstacle=True)
        add(f'CASTER-{s}',cyl(31,30,(cx,y-15,cz),(0,1,0),5),'yellow','drive')
        bolt(f'CASTER-{s}',(cx,y+25,cz),8,(0,1,0),'drive',52)


def drive():
    b,sp=build_bracket(BP)
    b.exportBrep(str(ROOT/'cad/SCMB-A01_Bracket.brep'))
    for s in [-1,1]:
        # Right: local X=forward, Y=inboard; left: rigid 180deg about Z.
        ang=180 if s==1 else 0;origin=(-335,s*280,R)
        def tr(sh):return sh.rotate((0,0,0),(0,0,1),ang).translate(origin)
        def pt(p):return [origin[0]+(-1 if s==1 else 1)*p[0],origin[1]+(-1 if s==1 else 1)*p[1],origin[2]+p[2]]
        ref='MOTOR-L' if s==1 else 'MOTOR-R';br='SCMB-L' if s==1 else 'SCMB-R'
        add(br,tr(b),'silver','drive','SCMB Rev A 모터 브라켓','SOURCE + M','Exact original solid construction: 148×88×130mm; 0.615083kg. No mirrored holes. Frame/boss fit and load capacity unresolved.',True)
        for i,(x,z) in enumerate(BP['motor_holes_xz']):
            add(br,tr(sp.translate((x,0,z))),'steel','drive',role='spacer')
            bolt(br,pt((x,-17.3,z)),6,(0,s,0),'drive',23)
        top=F-6;btm=R+88
        # Welded sheet saddle, separate from the original CNC bracket.
        # Bolt pattern 92×42mm is inherited, chassis attachment is a new proposal.
        for zz in [btm+3,top-3]:
            plate=box(164,104,6,(-335,s*245,zz),2)
            holepts=[(-335+(-1 if s==1 else 1)*x,s*280+(-1 if s==1 else 1)*y) for x,y in BP['frame_holes_xy']]
            plate=cut_z(plate,holepts,4.25,zz-4,8)
            add('DRIVE-RISER-'+str(s),plate,'silver','adapters','후륜 브라켓 높이 연결대','D/M',obstacle=True)
        for dx in [-79,79]:
            leg=box(6,96,top-btm-12,(-335+dx,s*245,(top+btm)/2))
            leg=leg.cut(box(8,54,max(10,top-btm-36),(-335+dx,s*245,(top+btm)/2),4))
            add('DRIVE-RISER-'+str(s),leg,'silver','adapters',obstacle=True)
        for x,y in BP['frame_holes_xy']:
            q=pt((x,y,88+6));bolt('DRIVE-RISER-'+str(s),q,8,(0,0,1),'adapters',15)
        # Gear casing: external shape unknown; holes and output datum retained.
        gp=cq.Plane(origin=(0,0,0),xDir=(1,0,0),normal=(0,1,0))
        # In this plane Y sketch maps to -Z; use an explicit XZ profile instead.
        case=cq.Workplane('XZ').ellipse(42,62).extrude(-26).val()
        for x,z in BP['motor_holes_xz']:
            ear=cyl(9,8,(x,0,z),(0,1,0),3.25);case=case.fuse(ear)
        case=case.fuse(cyl(25,8,(0,-8,0),(0,1,0)))
        add(ref,tr(case),'silver','drive','MY1016Z 24V 250W / 180rpm 옵션','V8 + D/M','V8 Ø72 can used; Ø102 source conflict retained separately. Case contour, ear-to-shoulder distance and key engagement M.',True)
        can=cyl(P['drive']['motor_body_diameter']/2,86,(-28,26,-28),(0,1,0))
        add(ref,tr(can),'black','drive',obstacle=True)
        add(ref,tr(cyl(P['drive']['motor_body_diameter']/2+1,4,(-28,112,-28),(0,1,0))),'steel','drive')
        # Gear cover fasteners are distinct from the mounting-ear fasteners.
        for x,z in [(-39,0),(-30,-35),(0,-58),(33,-34),(40,5),(0,60)]:
            bolt(ref,pt((x,-.8,z)),3,(0,-s,0),'drive',5)
        shaft=cyl(8.5,44,(0,-10,0),(0,-1,0))
        shaft=shaft.cut(box(6,42,4,(0,-32,7)))
        add(ref,tr(shaft),'steel','drive',role='shaft')
        add(ref,tr(box(6,26,3,(0,-35,7))),'gold','drive',role='key')
        # Tyre/hub are unmeasured placeholders and are marked D/M in every export.
        wc=s*P['drive']['wheel_center_y'];wid=P['drive']['wheel_width'];hub=P['drive']['wheel_hub_length']
        wh='WHEEL-L' if s==1 else 'WHEEL-R'
        tire=cyl(R,wid,(-335,wc-wid/2,R),(0,1,0),R*.66)
        try:tire=cq.Workplane().newObject([tire]).edges().fillet(4).val()
        except Exception:pass
        add(wh,tire,'rubber','drive','구동 타이어 / Ø17 보어','A bore + D/M','Ø200×40 and hub 30 are replaceable design values. Not a measured tyre. Axial retention and motor shaft radial load unresolved.',True)
        rim=cyl(R*.66,wid-8,(-335,wc-(wid-8)/2,R),(0,1,0),17)
        for k in range(6):
            t=k*math.tau/6;rim=rim.cut(cyl(14,wid+2,(-335+42*math.cos(t),wc-wid/2-1,R+42*math.sin(t)),(0,1,0)))
        add(wh,rim,'silver','drive')
        add(wh,cyl(17,hub,(-335,wc-hub/2,R),(0,1,0),8.5),'steel','drive')
        bolt(wh,(-335,s*335,R),8,(0,s,0),'drive',8)
        exitp=pt((-28,116,-7))
        add(ref,cyl(5,9,exitp,(0,-s,0),2.4),'black','drive',role='strain relief')
        port(ref+'.A',np.array(exitp)+[0,-s*9,3],ref,'Motor lead A')
        port(ref+'.B',np.array(exitp)+[0,-s*9,-3],ref,'Motor lead B')
        # Contrast plate facing outboard, positioned on can rear cap.
        decal(ref,'MY1016Z','24 V  250 W / V8 Ø72',pt((-28,116.3,-28)),(s,0,0),(0,0,1),(48,25),'#d7dadd','#273238')


def batteries():
    bp=P['battery'];base=bp['base'];x=bp['x'];l,w,h=[bp[t] for t in ['length','width','height']]
    for s in [1,-1]:
        y=s*bp['side_y'];ref='BAT1' if s==1 else 'BAT2';tray='TRAY-'+ref
        # Separate 3mm folded tray, 3mm fit clearance per side plus 2mm liner.
        padbase=base-2;bottom=base-5
        add(tray,box(252,w+12,3,(x,y,bottom+1.5),1),'silver','battery','납축전지 독립 트레이','D/M',obstacle=True)
        add(tray,box(l+6,w+6,2,(x,y,base-1),.5),'rubber','battery',role='liner')
        for q in [-1,1]:
            add(tray,box(l+12,3,22,(x,y+q*(w/2+4.5),bottom+14)),'silver','battery',obstacle=True)
            add(tray,box(3,w+6,22,(x+q*(l/2+4.5),y,bottom+14)),'silver','battery',obstacle=True)
        # Hangers attach to actual underside and tray corners, outside the battery volume.
        for dx in [-120,120]:
            for dy in [-w/2-5,w/2+5]:
                leg=cyl(3,F-bottom,(x+dx,y+dy,bottom))
                add(tray,leg,'steel','battery',role='hanger')
                # Rods pass through real cross-member holes; no floating top tabs.
                bolt(tray,(x+dx,y+dy,F),6,category='battery',length=6)
        add(ref,box(l,w,h,(x,y,base+h/2),2),'battery','battery','ROCKET ES18-12 / 12V 18Ah','A/B + M','181×77×167; 5.5kg each nominal. Terminal positions and delivered variant M. Batteries upright.',True)
        add(ref,box(l+1,w+1,7,(x,y,base+h-3.5),1),'black','battery',role='lid')
        for dx,pol in [(-60,'-'),(60,'+')]:
            termx=x+dx;z=base+h
            lug=box(13,12,2,(termx,y,z+1));lug=lug.cut(cyl(2.75,4,(termx,y,z-1)))
            add(ref,lug,'steel','battery',role='F3 terminal')
            port(ref+'.'+('P' if pol=='+' else 'N'),(termx,y,z+4),ref,pol)
            # Terminal insulation leaves a deliberate top cable-entry opening.
            cover=box(22,22,10,(termx,y,z+3),2).cut(box(17,17,12,(termx,y,z+1)))
            add(ref,cover,'red' if pol=='+' else 'black','battery',role='terminal guard')
        decal(ref,'ROCKET  ES18-12','12V / 18Ah  ·  SEALED LEAD ACID',(x,y+s*(w/2+.25),base+90),(-s,0,0),(0,0,1),(145,75),'#ebece5','#263b55')
        # Two metal hold-down straps with insulating cushions, clear of terminals.
        for dx in [-22,22]:
            add(tray,box(14,w+8,2,(x+dx,y,base+h+6)),'paint','battery',role='hold down')
            for q in [-1,1]:
                add(tray,box(14,2,h+7,(x+dx,y+q*(w/2+4),base+(h+7)/2)),'paint','battery',role='hold down')
        # Near-terminal fuse holder supported by a dedicated tab (no floating fuse).
        fr='F-BAT1' if s==1 else 'F-BAT2';fx=140;fz=236
        add(fr,box(64,32,3,(fx,y,fz-15)),'silver','power','배터리 단자 근접 퓨즈','D/M','Fuse current, I²t and DC interrupt rating TBD; housing is a size reservation.',True)
        add(fr,box(58,24,22,(fx,y,fz),3),'black','power',obstacle=True)
        for q in [-1,1]:
            add(fr,cyl(4,4,(fx+q*25,y,fz+11)),'steel','power',role='stud')
            port(fr+('.IN' if q==-1 else '.OUT'),(fx+q*25,y,fz+15),fr,'IN' if q==-1 else 'OUT')
        # Mount to tray and frame via a short formed tab; clear of cable-entry studs.
        add(fr,box(85,24,3,(105,y,fz-15)),'silver','power',role='mount tab')
        add(fr,box(3,24,F-10-(fz-16),(80,y,(F-10+fz-16)/2)),'silver','power',role='mount tab')
        decal(fr,fr,'DC RATING TBD',(fx,y,fz+11.2),(1,0,0),(0,1,0),(36,15),'#dfc44b','#263238')


def power_panel():
    z=180;cat='power'
    plate=box(420,260,4,(-35,0,z+2),2)
    add('POWER-TRAY',plate,'silver',cat,'중앙 전력 트레이','D/M','Battery-free central corridor. Folded tray and splash guard; not an IP-rated enclosure.',True)
    for x in [-160,80]:
        for y in [-126,126]:
            add('POWER-TRAY',cyl(3,F-z-4,(x,y,z+4)),'silver',cat,obstacle=True)
            bolt('POWER-TRAY',(x,y,F),6,category=cat,length=5)
    # Guard hangs below the deck; openings at its perimeter intentionally remain for glands.
    for yy in [-133,133]:
        add('POWER-GUARD',box(300,3,64,(5,yy,216),2),'clear','covers','전력부 탈착식 측면 보호판','D/M','Open top under the deck and open cable ends. Not an IP-rated enclosure.',role='cover')
    for s in [-1,1]:
        ref='DRV-L' if s==1 else 'DRV-R';x=-181;y=s*84;bz=190
        for dx in [-20,20]:
            for dy in [-20,20]:add(ref,cyl(2.5,6,(x+dx,y+dy,z+4)),'gold',cat,role='standoff')
        pcb(ref,52,52,(x,y,bz),cat,'bluepcb',name='BTS7960 / IBT-2')
        add(ref,box(38,34,5,(x+3,y,bz+7)),'silver',cat,role='heatsink base')
        for i in range(9):add(ref,box(2.3,34,32,(x-13+i*4,y,bz+25)),'silver',cat,role='heatsink fin')
        terminal_block(ref,x-13,y-22,bz+1.6,4,8,cat,'P')
        for k in range(8):
            yy=y-9+k*2.54
            add(ref,box(2,2,5,(x+23,yy,bz+4)),'gold',cat,role='signal header')
        port(ref+'.CTRL',(x+24,y,bz+9),ref,'8-pin control harness','signal')
        decal(ref,'IBT-2','43A ≠ CONTINUOUS',(x,y,bz+42),(1,0,0),(0,1,0),(40,14),'#cbd6dd','#24354b')
    # DC contactor and service-disconnect connector are physically modeled, selection pending.
    x=-65;y=-42
    add('K1',box(68,64,48,(x,y,214),3),'black',cat,'K1 DC 주접촉기','D/M','Contactor DC make/break current and coil voltage must be selected; NO power poles, manual seal-in reset.',True)
    for xx,ter in [(x-24,'IN'),(x+24,'OUT')]:
        add('K1',cyl(5,8,(xx,y,238)),'gold',cat,role='stud');port('K1.'+ter,(xx,y,246),'K1',ter)
    for xx,ter in [(x-24,'A1'),(x+24,'A2')]:
        port('K1.'+ter,(xx,y-40,204),'K1',ter,'control')
        add('K1',cyl(2,11,(xx,y-29,204),(0,-1,0)),'steel',cat,role='coil terminal')
    port('K1.AUX1',(x-5,y+34,210),'K1','Aux NO 13','control');port('K1.AUX2',(x+5,y+34,210),'K1','Aux NO 14','control')
    decal('K1','K1  /  DC','NO CONTACTOR',(x,y,238.15),(1,0,0),(0,1,0),(38,24),'#ebe4bf','#28313b')
    # Pull-apart service disconnect, OPEN by default, not hidden by a decorative lead.
    for xx,ter in [(12,'IN'),(-16,'OUT')]:
        add('J-SERVICE',box(20,29,20,(xx,-92,206),2),'red',cat,'직렬 팩 서비스 차단 커넥터','D/M','Shown unplugged. Both batteries and series link must be isolated before two independent 12V chargers are attached.',True)
        port('J-SERVICE.'+ter,(xx,-92,216),'J-SERVICE',ter)
    decal('J-SERVICE','OPEN','ISOLATE BEFORE CHARGE',(-2,-92,216.3),(1,0,0),(0,1,0),(54,12),'#edc14f','#333b42')
    # Insulated DC distribution posts, no chassis return path.
    for ref,yy,mat in [('BUS+',10,'red'),('BUS-',72,'black')]:
        add(ref,box(86,22,14,(17,yy,204),2),mat,cat,'절연 DC 분배 단자','D/M',obstacle=True)
        for i,xx in enumerate([-13,7,27,47]):
            add(ref,cyl(3,8,(xx,yy,211)),'gold',cat,role='bus stud')
            port(ref+'.'+str(i),(xx,yy,219),ref,str(i))
    for ref,xx,yy in [('F-L',-87,101),('F-R',-83,-113),('F-5V',62,-104),('F-COIL',108,-85),('F-SENSE',118,103)]:
        add(ref,box(38,18,19,(xx,yy,205.5),2),'black',cat,'분기 퓨즈 '+ref,'D/M','Fuse value is intentionally TBD, not a selected final rating.',True)
        for q,ter in [(-1,'IN'),(1,'OUT')]:
            port(ref+'.'+ter,(xx+q*11,yy,216),ref,ter)
            add(ref,cyl(2.6,2,(xx+q*11,yy,214)),'steel',cat,role='fuse terminal')
        decal(ref,ref,'TBD',(xx,yy,215.2),(1,0,0),(0,1,0),(26,11),'#e0c34e','#27313a')
    add('DC5',box(80,56,27,(110,14,211.5),2),'silver',cat,'24V → 5.1V DC/DC','D/M','Required separate regulated 5.1V supply. Proposed ≥6A budget; actual model/ripple/thermal/input limits not selected.',True)
    for q in range(10):add('DC5',box(2,52,7,(76+q*7.5,14,228.5)),'silver',cat,role='cooling fin')
    for yy,ter in [(-2,'IN+'),(7,'IN-'),(21,'OUT+'),(30,'OUT-')]:port('DC5.'+ter,(151,yy,207),'DC5',ter)
    decal('DC5','DC / DC','5.1 V  ·  SELECTION HOLD',(110,14,232.2),(1,0,0),(0,1,0),(63,19),'#394752','#e3eaf0')
    # Four-way 5V terminal distribution outside the converter envelope.
    for ref,xx,yy,mat in [('5V+',88,68,'red'),('5V-',129,68,'black')]:
        add(ref,box(30,22,12,(xx,yy,202),2),mat,cat,role='distribution')
        for i,dy in enumerate([-6,0,6]):port(ref+'.'+str(i),(xx,yy+dy,209),ref,str(i),'aux')


def controls():
    cat='controls';bz=H+8
    plate=box(224,384,4,(-300,0,bz),2)
    plate=rear_service_cut(plate,bz-3,6)
    add('CONTROL-BASE',plate,'silver',cat,'상부 제어부 탈착 플레이트','D/M','Pi and sensor electronics separated from high-current motor leads.',True)
    for x in [-393,-207]:
        for y in [-174,174]:
            add('CONTROL-BASE',cyl(4,6,(x,y,H)),'gold',cat,role='standoff')
            bolt('CONTROL-BASE',(x,y,bz+2),5,category=cat,length=9)
    # Transparent cover, open bottom, removable screws; pass-throughs are below it.
    zz=H+77
    add('CONTROL-COVER',box(224,384,3,(-300,0,zz),2),'clear','covers','제어부 투명 보호 커버','D',role='cover')
    for x in [-410,-190]:add('CONTROL-COVER',box(3,384,64,(x,0,H+43)),'clear','covers',role='cover')
    for y in [-190,190]:add('CONTROL-COVER',box(218,3,64,(-300,y,H+43)),'clear','covers',role='cover')
    # Pi PCB 85x56 inside the declared 100x75x35 case reservation.
    px=-318;py=-85;pz=H+17
    pcb('PI4',85,56,(px,py,pz),cat,'pcb','A PCB / D case','Raspberry Pi 4 Model B 8GB')
    add('PI4',box(100,75,3,(px,py,pz-2),1),'black',cat,role='case base')
    for q in [-1,1]:
        add('PI4',box(100,3,27,(px,py+q*36,pz+11)),'black',cat,role='case edge')
    # Dual-fan open aluminium case: top perforations are real holes.
    lid=box(100,75,4,(px,py,pz+27),1)
    for dx in [-23,23]:lid=lid.cut(cyl(15,6,(px+dx,py,pz+24)))
    add('PI4',lid,'black',cat,role='case lid')
    for dx in [-23,23]:
        add('PI4',cyl(14.7,4,(px+dx,py,pz+25),ri=12),'black',cat,role='fan ring')
        add('PI4',cyl(4.5,3,(px+dx,py,pz+25)),'black',cat,role='fan motor')
        for j in range(7):
            blade=box(11,4,1,(px+dx+7.5,py,pz+26.5),.5).rotate((px+dx,py,0),(px+dx,py,1),j*360/7+20)
            add('PI4',blade,'black',cat,role='fan blade')
    for yy in [-101,-79,-57]:
        add('PI4',box(17,14,14,(px+43,yy,pz+8),1),'steel',cat,role='USB/Ethernet shell')
        add('PI4',box(2,10,8,(px+52,yy,pz+8)), 'blue' if yy!=-57 else 'black',cat,role='port insert')
    port('PI4.USB',(-265,-101,pz+8),'PI4','USB host','usb')
    port('PI4.5V',(px-21,py-39,pz+6),'PI4','USB-C 5.1V','aux')
    port('PI4.GND',(px-15,py-39,pz+6),'PI4','USB-C return','aux')
    add('PI4',box(9,5,4,(px-18,py-36,pz+6),.7),'steel',cat,role='USB-C shell')
    decal('PI4','Raspberry Pi 4B','8 GB / RBP-002 ENVELOPE',(px,py+25,pz+29.3),(1,0,0),(0,1,0),(89,15),'#1d262b','#d8e5ec')
    # Added powered hub: avoids powering the whole sensor set from an unverified Pi USB budget.
    x=-267;y=51;z=H+22
    add('USB-HUB',box(94,43,18,(x,y,z),2),'black',cat,'외부전원 USB 허브','D/M','Added integration part: host VBUS backfeed must be prevented and sensor peak current verified.',True)
    port('USB-HUB.HOST',(x-48,y,z),'USB-HUB','USB upstream','usb')
    port('USB-HUB.5V',(x-48,y+11,z),'USB-HUB','External 5.1V','aux')
    port('USB-HUB.GND',(x-48,y+17,z),'USB-HUB','Return','aux')
    for i in range(4):
        xx=x-33+i*22
        add('USB-HUB',box(15,5,8,(xx,y-22,z),.5),'steel',cat,role='USB-A shell')
        port('USB-HUB.'+str(i),(xx,y-25,z),'USB-HUB','USB '+str(i),'usb')
    decal('USB-HUB','POWERED USB','NO HOST BACKFEED',(x,y,z+9.2),(1,0,0),(0,1,0),(78,20),'#243947','#e1ecf3')
    # ESP32-32U: conservative 60x35 service envelope, 54.4x27.9 PCB reference.
    ex=-352;ey=79;ez=H+18
    pcb('ESP32',54.4,27.9,(ex,ey,ez),cat,'pcb','A/B + M','ESP32 DevKitC WROOM-32U')
    add('ESP32',box(17,16,3,(ex-12,ey,ez+3.5),.4),'steel',cat,role='RF shield')
    for q in [-1,1]:
        add('ESP32',box(50,2.5,5,(ex,ey+q*12,ez-2.5)),'black',cat,role='header strip')
        for j in range(19):add('ESP32',box(.65,.65,4,(ex-22.86+j*2.54,ey+q*12,ez+3.5)),'gold',cat,role='header pin')
    port('ESP32.USB',(ex+29,ey,ez+3),'ESP32','Micro USB','usb')
    port('ESP32.CTRL',(ex,ey-15,ez+6),'ESP32','PWM/EN harness','signal')
    port('ESP32.I2C',(ex-18,ey+15,ez+6),'ESP32','3.3V/GND/SDA/SCL','signal')
    port('ESP32.STATUS',(ex+16,ey+15,ez+6),'ESP32','E-stop isolated status','signal')
    add('ESP32',cyl(2,8,(ex-25,ey,ez+5)),'gold',cat,role='IPEX reference')
    # INA module included, but not treated as a 20A total-motor shunt.
    pcb('INA226',27,20,(-352,139,H+18),cat,'bluepcb','B/M','INA226 전압 감시 / 전류단자 OPEN')
    port('INA226.I2C',(-335,139,H+23),'INA226','I2C harness','signal')
    port('INA226.VBUS',(-367,135,H+22),'INA226','VBUS pin access must be confirmed','sense')
    port('INA226.GND',(-367,143,H+22),'INA226','GND','sense')
    for y in [133,145]:add('INA226',cyl(2,3,(-361,y,H+19)),'gold',cat,role='OPEN current pad')
    # Added AHCT/buffer carrier, output default-low gating is a circuit requirement.
    pcb('LEVEL-IF',42,24,(-281,125,H+18),cat,'pcb','D/M','3.3V → 5V PWM/EN 인터페이스')
    port('LEVEL-IF.IN',(-302,125,H+23),'LEVEL-IF','MCU input harness','signal')
    port('LEVEL-IF.L',(-274,111,H+23),'LEVEL-IF','Left PWM/EN/GND','signal')
    port('LEVEL-IF.R',(-258,125,H+23),'LEVEL-IF','Right PWM/EN/GND','signal')
    port('LEVEL-IF.5V',(-280,139,H+23),'LEVEL-IF','5V supply','aux')
    port('LEVEL-IF.GND',(-287,139,H+23),'LEVEL-IF','Return','aux')
    # Control and safety terminal strip beside the cable glands.
    terminal_block('CTRL-TB',-250,-162,H+14,5,9,cat,'S')
    for i in range(5):PORTS['CTRL-TB.S'+str(i)]['kind']='control'
    decal('CONTROL-BASE','CONTROL / USB','PI 4B + ESP32',(-382,-12,H+10.2),(0,1,0),(-1,0,0),(140,19),'#c3cdd4','#243442')


def handle_sensors():
    cat='handle';hx=P['handle']['hinge_x'];yy=P['handle']['side_y'];top=H+P['handle']['height_above_deck'];hinge=H+20
    # Bent handle tube with actual smooth bend radii and external harness clips.
    for s in [-1,1]:
        add('HANDLE-HINGE',box(70,44,9,(hx,s*yy,H+5),3),'steel',cat,'원래 손잡이 힌지 / 위치 실측','D/M',obstacle=True)
        add('HANDLE-HINGE',cyl(16,38,(hx,s*yy-19,hinge),(0,1,0),5),'steel',cat)
        bolt('HANDLE-HINGE',(hx,s*yy+23,hinge),10,(0,1,0),cat,45)
    pts=[[hx,yy,hinge],[hx-35,yy,top-40],[hx-35,yy-40,top],[hx-35,-yy+40,top],[hx-35,-yy,top-40],[hx,-yy,hinge]]
    path,smp,rr=route_points(pts,35)
    tang=np.array(smp[1])-np.array(smp[0])
    shape=cq.Workplane(cq.Plane(origin=pts[0],normal=tuple(tang))).circle(12.5).circle(11).sweep(cq.Workplane().newObject([path])).val()
    add('HANDLE',shape,'paint',cat,'접이식 손잡이 / 펼침 자세','D/M','Handle geometry and folding swept envelope require physical verification. External service loop, not a wire through solid tubing.',True)
    add('HANDLE-GRIP',cyl(15,230,(hx-35,-115,top),(0,1,0),12.6),'rubber',cat)
    add('HANDLE-BRACE',box(6,470,50,(hx-15,0,H+360),4),'paint',cat)
    # Clamp-on control enclosure: mushroom behind the bar, accessible from the operator side.
    bx=hx-62;by=159;bz=top-4
    add('E-STOP',box(50,76,58,(bx,by,bz-7),4),'yellow',cat,'손잡이 비상정지 버튼','D/M','Latching mushroom NC contacts; removes K1 coil energy. Does not guarantee braking or a safety performance level.',True)
    add('E-STOP',cyl(14,9,(bx-25,by,bz),( -1,0,0)),'black',cat)
    add('E-STOP',cyl(22,13,(bx-34,by,bz),(-1,0,0)),'red',cat)
    add('E-STOP',cyl(19,3,(bx-47,by,bz),(-1,0,0)),'red',cat)
    for q in [-1,1]:
        add('E-STOP',cyl(17,9,(hx-35,by+q*23-4.5,top),(0,1,0),12.6),'steel',cat,role='handle clamp')
    # Reset button is deliberately separate: releasing E-stop must not restart the cart.
    add('RESET',box(35,36,37,(bx,80,bz-10),3),'black',cat,'수동 재시작 버튼','D/M')
    add('RESET',cyl(9,8,(bx-18,80,bz-7),(-1,0,0)),'green',cat)
    port('E-STOP.1',(bx,by,bz-39),'E-STOP','NC feed','control')
    port('E-STOP.2',(bx+6,by,bz-39),'E-STOP','NC output','control')
    port('RESET.1',(bx,80,bz-30),'RESET','NO feed','control')
    port('RESET.2',(bx+5,80,bz-30),'RESET','NO output','control')
    decal('E-STOP','EMERGENCY','STOP',(bx-25.2,by,bz-21),(0,-1,0),(0,0,1),(65,14),'#ebc035','#28313a')
    # Front sensors on short polymer brackets; no full-width aluminium extrusion cage.
    for s in [-1,1]:
        x=421;y=s*244;zz=H+76;ref='UWB-L' if s==1 else 'UWB-R'
        add(ref,box(60,66,4,(411,y,H+4),2),'black','sensors','BU04 UWB Kit / 안테나 공간','A PCB + D/M','46×52 PCB. Antenna no-metal clearance is a proposal; RF performance must be tested.',True)
        add(ref,box(5,58,55,(x-8,y,H+33),1).cut(box(8,22,41,(x-8,y,H+24),3)),'black','sensors',role='polymer support',obstacle=True)
        # PCB vertical in YZ; dual antenna is the upper 12mm region.
        add(ref,box(1.6,46,52,(x,y,zz),.3),'pcb','sensors',grade='A PCB',role='PCB')
        add(ref,box(2.5,42,11,(x+1.8,y,zz+19.5),.3),'black','sensors',role='antenna substrate')
        for q in [-1,1]:
            for j in range(5):add(ref,box(.3,2.5,5,(x+3.3,y+q*(12+j*1.6),zz+21-j%2*3)),'gold','sensors',role='antenna trace')
        add(ref,box(2.5,21,18,(x+2,y,zz+1),.5),'steel','sensors',role='shield')
        add(ref,box(7,9,4,(x,y,zz-28),.6),'steel','sensors',role='USB-C')
        port(ref+'.USB',(x,y,zz-32),ref,'USB-C','usb')
        decal(ref,'BU04','PDoA UWB',(x+3.5,y,zz+1),(0,1,0),(0,0,1),(23,10),'#59666e','#e5eef4')
    # Front projecting sensor plate leaves the forward scan plane unobstructed.
    add('LIDAR-MOUNT',box(90,78,4,(465,0,H+8),3),'silver','sensors','라이다 전방 돌출 지지판','D',obstacle=True)
    add('LIDAR-MOUNT',box(4,78,28,(425,0,H+20)),'silver','sensors',obstacle=True)
    basez=H+28;cx=482
    for x in [cx-21.5,cx+21.5]:
        for y in [-21.5,21.5]:
            add('LIDAR',cyl(2.5,18,(x,y,H+10)),'black','sensors',role='standoff')
    plate=cut_z(box(55.6,55.6,3,(cx,0,basez+1.5),2),[(cx+x,y) for x in [-21.5,21.5] for y in [-21.5,21.5]],1.25,basez-1,5)
    add('LIDAR',plate,'black','sensors','SLAMTEC RPLIDAR C1','A','55.6×55.6×41.3; scan +29.8; 43×43 M2.5, screw engagement ≤4mm. Cargo can occlude rear sectors.',True)
    add('LIDAR',cyl(25.5,20.1,(cx,0,basez+3)),'black','sensors',obstacle=True)
    add('LIDAR',cyl(24.4,14,(cx,0,basez+23.1)),'sensorwindow','sensors',role='optical window')
    add('LIDAR',cyl(24.7,4.2,(cx,0,basez+37.1)),'black','sensors',role='top cap')
    port('LIDAR.USB',(cx-27,0,basez+10),'LIDAR','C1 USB adapter harness','usb')
    decal('LIDAR','RPLIDAR','C1',(cx,0,basez+41.5),(1,0,0),(0,1,0),(34,18),'#252f38','#d9e4ed')
    # BU03 tag is OFF CART, hidden by default and excluded from chassis dimensions.
    pcb('BU03-TAG',35.56,55,(185,480,90),'accessories','pcb','A PCB + M','BU03 사용자 소지 태그')
    add('BU03-TAG',box(44,67,4,(185,480,86),3),'black','accessories')
    decal('BU03-TAG','BU03 TAG','OFF-CART',(185,480,94.1),(1,0,0),(0,1,0),(30,36),'#263541','#eef4f8')
    for i in range(2):
        add('CHARGER-'+str(i+1),box(115,70,60,(340,470+i*95,34),5),'black','accessories','12V 2A 외장 충전기','B/M','External accessory only. Individually isolated batteries; never assume charger outputs are mutually isolated.')
        decal('CHARGER-'+str(i+1),'12 V / 2 A','EXTERNAL ONLY',(340,470+i*95,64.2),(1,0,0),(0,1,0),(92,44),'#303a44','#d5dfe5')


def wiring():
    # Main battery circuit. Terminal-stud heights derive from actual modeled geometry.
    cable('W01','BAT1.P','F-BAT1.IN',[[20,185,278],[80,185,278]],net='BAT1+')
    cable('W02','BAT2.P','F-BAT2.IN',[[20,-185,278],[80,-185,278]],net='BAT2+')
    cable('W03','F-BAT1.OUT','BAT2.N',[[130,185,283],[130,-185,283],[-100,-185,283]],net='SERIES-LINK',notes='Fused series jumper; remove and isolate both batteries before individual 12V charging.')
    cable('W04','BAT1.N','BUS-.0',[[-100,185,279],[-13,185,279],[-13,72,279]],'wireblack',net='GND')
    cable('W05','F-BAT2.OUT','J-SERVICE.IN',[[180,-185,282],[225,-185,282],[225,-92,282],[12,-92,282]],net='PACK+')
    cable('W06','J-SERVICE.OUT','K1.IN',[[-16,-92,278],[-89,-92,278],[-89,-42,278]],net='ISOLATED+',notes='Service connector shown open; no electrical continuity across its visible gap.')
    cable('W07','K1.OUT','BUS+.0',[[-41,-42,282],[-13,10,282]],net='DRIVE+')
    cable('W08','BUS+.1','F-L.IN',[[7,10,275],[7,101,275],[-98,101,275]],net='DRIVE+')
    cable('W09','BUS+.2','F-R.IN',[[27,10,271],[27,-113,271],[-94,-113,271]],net='DRIVE+')
    cable('W10','BUS+.3','F-5V.IN',[[47,10,280],[51,-104,280]],net='DRIVE+',notes='D5 intentionally cuts controller power with K1. Re-power requires manual hardware reset.')
    for s,ref,ff in [(1,'DRV-L','F-L'),(-1,'DRV-R','F-R')]:
        # P0=B+, P1=B-, P2=M+, P3=M-; exact purchased screw order is a hold.
        pp=PORTS[ref+'.P0']['point'];nn=PORTS[ref+'.P1']['point']
        f=PORTS[ff+'.OUT']['point']
        cable('W11' if s==1 else 'W12',ff+'.OUT',ref+'.P0',[[f[0],f[1],269],[pp[0],f[1],269],[pp[0],pp[1]-42,269],[pp[0],pp[1]-42,pp[2]]],net=ff+'-OUT')
        bus='BUS-.1' if s==1 else 'BUS-.2';bu=PORTS[bus]['point']
        cable('W13' if s==1 else 'W14',bus,ref+'.P1',[[bu[0],bu[1],281],[nn[0],bu[1],281],[nn[0],nn[1]-40,281],[nn[0],nn[1]-40,nn[2]]],'wireblack',net='GND')
        motor='MOTOR-L' if s==1 else 'MOTOR-R'
        for j,ter,mat in [(2,'A','red'),(3,'B','wireblack')]:
            a=PORTS[ref+'.P'+str(j)]['point'];b=PORTS[motor+'.'+ter]['point'];offset=0 if j==2 else 13
            yy=s*(92-offset)
            cable('WM-'+ter+('-L' if s==1 else '-R'),ref+'.P'+str(j),motor+'.'+ter,
              [[a[0],a[1]-42,a[2]],[-250-offset,a[1]-42,241-offset],[-250-offset,yy,241-offset],[b[0],yy,241-offset],[b[0],yy,b[2]]],mat,net=motor+'-'+ter)
    # Auxiliary converter input/returns, 18AWG proposed; connector pins remain label-based.
    cable('A01','F-5V.OUT','DC5.IN+',[[73,-104,248],[169,-104,248],[169,-2,248],[169,-2,207]],'red','aux',net='24V-AUX')
    cable('A02','BUS-.3','DC5.IN-',[[47,72,245],[182,72,245],[182,7,245],[182,7,207]],'wireblack','aux',net='GND')
    cable('A03','DC5.OUT+','5V+.0',[[178,21,207],[178,62,247],[88,62,247]],'red','aux',net='5V1')
    cable('A04','DC5.OUT-','5V-.0',[[188,30,207],[188,62,239],[129,62,239]],'wireblack','aux',net='5V1-GND')
    # 5V paths cross the deck ONLY through the explicitly cut -220,-150 gland.
    for id,a,b,mat,off in [('A05','5V+.1','PI4.5V','red',-3),('A06','5V-.1','PI4.GND','wireblack',3)]:
        p=PORTS[a]['point'];q=PORTS[b]['point'];gx=-220+off;gy=-150
        cable(id,a,b,[[p[0]+30,p[1],225],[p[0]+30,p[1],270],[191+off,p[1],270],[191+off,gy,270],[gx,gy,270],[gx,gy,H+48],[q[0],gy-32,H+48],[q[0],gy-32,q[2]],[q[0],q[1]-24,q[2]]],mat,'aux',net='5V1' if mat=='red' else 'GND')
    for id,a,b,mat,off in [('A07','5V+.2','USB-HUB.5V','red',-3),('A08','5V-.2','USB-HUB.GND','wireblack',3)]:
        p=PORTS[a]['point'];q=PORTS[b]['point'];gx=-220+off;gy=150
        cable(id,a,b,[[p[0]+32,p[1],224],[p[0]+32,p[1],274],[185+off,p[1],274],[185+off,gy,274],[gx,gy,274],[gx,gy,H+49],[q[0]-22,gy,H+49],[q[0]-22,q[1],H+49],[q[0]-22,q[1],q[2]]],mat,'aux',net='5V1' if mat=='red' else 'GND')
    # Short 5V and return branches for AHCT board. Physical taps at a terminal, not a mystery line.
    for id,a,b,mat,of in [('A09','USB-HUB.5V','LEVEL-IF.5V','red',0),('A10','USB-HUB.GND','LEVEL-IF.GND','wireblack',7)]:
        p=PORTS[a]['point'];q=PORTS[b]['point']
        cable(id,a,b,[[p[0]-30-of,p[1],p[2]],[p[0]-30-of,165,H+49+of],[q[0],165,H+49+of],[q[0],q[1]+14,q[2]]],mat,'aux',net='5V1' if mat=='red' else 'GND')
    # USB host, ESP32 and three remote sensors. Hub is self powered.
    cable('USB-HOST','PI4.USB','USB-HUB.HOST',[[-245,-101,H+25],[-245,-10,H+53],[-343,-10,H+53],[-343,51,H+22]],'wireblack','usb',od=4,notes='Shielded USB upstream; self-powered hub must not backfeed Pi.')
    cable('USB-ESP','USB-HUB.3','ESP32.USB',[[-224,-8,H+22],[-224,-8,H+57],[-315,-8,H+57],[-295,79,H+57]],'wireblack','usb',od=3.6)
    for i,ref,s in [(0,'UWB-L',1),(1,'UWB-R',-1),(2,'LIDAR',0)]:
        p=PORTS['USB-HUB.'+str(i)]['point'];q=PORTS[ref+'.USB']['point'];laneY=150+(i-1)*5;gx=-220+(i-1)*5
        # External underside side rail, forward via a cable saddle on the front edge.
        ty=247 if s==1 else (-247 if s==-1 else 5)
        via=[[p[0],p[1]-26,H+22],[gx,p[1]-26,H+50],[gx,laneY,H+50],[gx,laneY,281],
             [325,laneY,281],[360,ty,281],[360,ty,H+22]]
        if s==0:via[-1]=[360,ty,H+38]
        else:via += [[421,ty,H+22]]
        cable('USB-'+ref,'USB-HUB.'+str(i),ref+'.USB',via,'wireblack','usb',od=3.6,notes='Shielded USB harness. Actual cable exit and strain-relief geometry M.')
    cable('SIG-MCU','ESP32.CTRL','LEVEL-IF.IN',[[-352,43,H+24],[-305,43,H+43],[-319,125,H+43]],'blue','signal',od=3.4,notes='Bundled logic conductors; 18AWG is not assumed for individual GPIO wires.')
    cable('SIG-I2C','ESP32.I2C','INA226.I2C',[[-370,112,H+31],[-324,112,H+38],[-315,139,H+23]],'purple','signal',od=3.2)
    for i,side in enumerate(['L','R']):
        a='LEVEL-IF.'+side;b='DRV-'+side+'.CTRL';p=PORTS[a]['point'];q=PORTS[b]['point'];gx=-226+i*11;gy=146+i*7
        cable('SIG-'+side,a,b,[[p[0],p[1],H+48],[gx,p[1]-12,H+48],[gx,gy,H+48],[gx,gy,271],[q[0]+35,gy,271],[q[0]+35,q[1],271],[q[0]+35,q[1],q[2]]],'blue','signal',od=3.5,notes='PWM/EN/GND harness; actual IBT-2 terminal order, level shifter and default-disabled state require bench verification.')
    # Coil branch is taken BEFORE K1 so the manual seal-in circuit can start without the Pi.
    cable('C01','J-SERVICE.OUT','F-COIL.IN',[[-16,-92,279],[125,-92,279],[125,-85,239],[97,-85,239]],'yellow','control',od=2.6,notes='Hardwired upstream coil feed. Do not depend on booted software to latch K1.')
    cable('C02','F-COIL.OUT','CTRL-TB.S0',[[119,-85,266],[190,-85,266],[190,-153,266],[-216,-153,266],[-216,-153,H+42],[-268,-153,H+42],[-268,-187,H+42]],'yellow','control',od=2.6)
    # External handle wiring follows the outside of the tube and has a real hinge service loop.
    top=H+P['handle']['height_above_deck'];hx=P['handle']['hinge_x'];bx=hx-62
    for idx,end in enumerate(['E-STOP.1','E-STOP.2','RESET.2']):
        start='CTRL-TB.S'+str(idx);p=PORTS[start]['point'];q=PORTS[end]['point'];dy=idx*4
        cable('HANDLE-'+str(idx),start,end,[[p[0],-194,H+22],[-380,-194,H+22],[-461-dy,-194,H+35],[-475-dy,-244,H+65],[-466-dy,-270,H+125],[-428-dy,-270,H+150],[-472-dy,-270,top-85],[-472-dy,q[1],top-85],[q[0],q[1],q[2]-18]],'yellow' if idx<2 else 'blue','control',od=2.6,
              notes='External clamped cable + hinge service loop. Full folding kinematics not validated; only deployed pose supplied.')
    # Button NC output to reset input, and K1 auxiliary seal-in branch.
    q=PORTS['E-STOP.2']['point'];r=PORTS['RESET.1']['point']
    cable('C-HANDLE','E-STOP.2','RESET.1',[[q[0],q[1],q[2]-24],[q[0],r[1],q[2]-24]],'yellow','control',od=2.6)
    for id,fr,to,dy in [('C03','CTRL-TB.S1','K1.AUX1',-2),('C04','CTRL-TB.S2','K1.A1',2)]:
        a=PORTS[fr]['point'];b=PORTS[to]['point'];gx=-218+dy
        approach=22 if id=='C03' else -97
        cable(id,fr,to,[[a[0],-192,H+22],[gx,-192,H+44],[gx,-150+dy,H+44],[gx,-150+dy,269],[-122,-150+dy,269],[-131,approach,269],[-131,approach,b[2]],[b[0],approach,b[2]]],'yellow','control',od=2.6)
    cable('C05','K1.AUX2','K1.A1',[[-37,-8,229],[-131,-8,259],[-131,-97,259],[-131,-97,204],[-89,-97,204]],'yellow','control',od=2.6,notes='NO auxiliary contact in parallel with momentary RESET. Suppressor across coil must be selected for drop-out requirements.')
    cable('C06','K1.A2','BUS-.3',[[-41,-119,204],[-41,-119,247],[62,-119,247],[62,72,247]],'wireblack','control',od=2.6)
    # INA226 uses bus-voltage monitoring only; high-current pads remain visibly open.
    cable('V01','BUS+.3','F-SENSE.IN',[[47,10,263],[107,10,263],[107,103,263]],'purple','sense',od=1.7)
    for id,a,b,mat,gx,gy in [('V02','F-SENSE.OUT','INA226.VBUS','purple',-229,148),('V03','BUS-.3','INA226.GND','wireblack',-228,156)]:
        p=PORTS[a]['point'];q=PORTS[b]['point']
        cable(id,a,b,[[p[0],p[1],277],[163,160,277],[gx,gy,277],[gx,gy,H+60],[q[0]-17,gy,H+60],[q[0]-17,q[1],q[2]]],mat,'sense',od=1.7,notes='VBUS access must be confirmed on the purchased board. R010 current shunt remains OUT of the motor path.')


def finalize_covers():
    cutouts=[]
    wires=[p for p in PARTS if p['category']=='wires']
    for p in [p for p in PARTS if p['category']=='covers']:
        shape=SHAPES[p['key']];bb=shape.BoundingBox();dims=[bb.xlen,bb.ylen,bb.zlen];axis=int(np.argmin(dims))
        for wire in wires:
            other=SHAPES[wire['key']]
            if not shape.BoundingBox().isInside(other.BoundingBox()) and not other.BoundingBox().isInside(shape.BoundingBox()):
                a=p['bbox_mm'];b=wire['bbox_mm']
                if any(a[i+3]<b[i] or b[i+3]<a[i] for i in range(3)):continue
            common=shape.intersect(other)
            if common.Volume()<1e-4:continue
            q=common.BoundingBox();lo=[q.xmin,q.ymin,q.zmin];hi=[q.xmax,q.ymax,q.zmax]
            size=[max(8,hi[i]-lo[i]+6) for i in range(3)];size[axis]=dims[axis]+4
            center=[(lo[i]+hi[i])/2 for i in range(3)]
            cutter=box(*size,center,r=1.5);shape=shape.cut(cutter)
            cutouts.append({'cover':p['ref'],'wire':wire['ref'],'center_mm':center,'size_mm':size,'status':'D: proposed deburred clearance opening'})
        SHAPES[p['key']]=shape
        if p['key'] not in OBSTACLES:OBSTACLES.append(p['key'])
    (ROOT/'data/cover-cutouts.json').write_text(json.dumps(cutouts,indent=2))


def clamps():
    # Adhesive cable saddles carry horizontal harnesses below the solid deck.
    for xx in [-100,100,250]:
        clip=cyl(11,4,(xx-2,150,281),(1,0,0),9).fuse(box(14,10,2,(xx,164,291),.5))
        add('CABLE-CLIPS',clip,'black','hardware','상판 하부 접착식 케이블 새들','D/M',role='wire saddle')
    # Deployed-pose tie envelopes enclose the handle tube and actual harness.
    hx=P['handle']['hinge_x'];top=H+P['handle']['height_above_deck'];hinge=H+28
    hw=[w for w in WIRES if w['id'] in ['HANDLE-0','HANDLE-1','HANDLE-2']]
    for zz in [H+185,H+350,H+515]:
        pts=[]
        for w in hw:
            ps=np.asarray(w['sampled_mm']);i=int(np.argmin(abs(ps[:,2]-zz)));pts.append(ps[i])
        tx=hx-35*(zz-hinge)/(top-40-hinge);loX=min(tx-13,min(p[0] for p in pts)-2);hiX=max(tx+13,max(p[0] for p in pts)+2)
        loY=min(-258,min(p[1] for p in pts)-2);hiY=-231
        cen=((loX+hiX)/2,(loY+hiY)/2,zz)
        sh=box(hiX-loX+3,hiY-loY+3,3,cen,1).cut(box(hiX-loX,hiY-loY,5,cen,1))
        add('HANDLE-CLIPS',sh,'black','hardware','손잡이 외부 하네스 고정 밴드','D/M',role='wire saddle')


def export_geometry():
    ROOT.joinpath('cad','brep').mkdir(exist_ok=True)
    # Per-reference CAD features retain solids, named in the same manner as web selection.
    groups=defaultdict(list)
    for part in PARTS:groups[(part['ref'],part['material'],part['category'])].append(SHAPES[part['key']])
    geometry=[];data=[];byte_offset=0;brepmeta=[];assembly=cq.Assembly(name='Smart_Cart_5_Prototype')
    for index,((ref,mat,cat),shapes) in enumerate(groups.items()):
        shape=cq.Compound.makeCompound(shapes);verts,faces=shape.tessellate(.5,.3)
        vv=np.array([[p.x,p.y,p.z] for p in verts],dtype=np.float64)/1000
        ff=np.array(faces,dtype=np.int32)
        norms=np.zeros_like(vv)
        n=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]])
        for k in range(3):np.add.at(norms,ff[:,k],n)
        ln=np.linalg.norm(norms,axis=1);norms/=np.maximum(ln[:,None],1e-15)
        arr=np.concatenate([vv[ff.reshape(-1)],norms[ff.reshape(-1)]],axis=1).astype('<f4')
        blob=arr.tobytes();data.append(blob)
        bb=shape.BoundingBox();rec={'ref':ref,'category':cat,'material':mat,'offset':byte_offset,'count':int(arr.shape[0]),'bbox_mm':[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]};geometry.append(rec);byte_offset+=len(blob)
        name=f'D5_{index:03d}_{ref.replace("+","POS").replace("-","_")}_{mat}'
        path=ROOT/'cad/brep'/f'{name}.brp';shape.exportBrep(str(path))
        brepmeta.append({'name':name,'file':f'brep/{name}.brp','ref':ref,'material':mat,'category':cat,'volume_mm3':shape.Volume(),'solid_count':len(shape.Solids()),'valid':shape.isValid()})
        if cat!='accessories':
            h=MATS[mat]['color'];col=[int(h[q:q+2],16)/255 for q in [1,3,5]]
            assembly.add(shape,name=name,color=cq.Color(*col,MATS[mat].get('alpha',1)))
    ROOT.joinpath('data/geometry.bin').write_bytes(b''.join(data))
    manifest={'project':'Smart-Cart-5','version':'1.0.0','units':'mm','rendererUnits':'metres','status':P['status'],'parameters':P,'materials':MATS,
              'geometry':geometry,'parts':PARTS,'components':list(META.values()),'ports':PORTS,'decals':DECALS,'connections':WIRES,'obstacles':OBSTACLES,
              'counts':{'solid_parts':len(PARTS),'components':len(META),'connections':len(WIRES),'render_batches':len(groups),'triangles':sum(x['count']//3 for x in geometry)}}
    ROOT.joinpath('data/assembly.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
    ROOT.joinpath('cad/assembly-manifest.json').write_text(json.dumps(brepmeta,indent=2))
    # Remove obsolete batches from earlier rebuilds; only this manifest is shipped.
    current_breps={x['name']+'.brp' for x in brepmeta}
    for stale in (ROOT/'cad/brep').glob('D5_*.brp'):
        if stale.name not in current_breps:stale.unlink()
    print('Exporting STEP',len(groups),'batches',len(PARTS),'parts',flush=True)
    assembly.export(str(ROOT/'cad/Smart-Cart-5.step'))
    # Compact CSVs are plain text export tables, not Excel files.
    import csv
    with (ROOT/'data/connections.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=['id','from','to','kind','net','od_mm','bend_min_mm','length_mm','cut_length_proposal_mm','rating','notes'];wr=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');wr.writeheader();wr.writerows(WIRES)
    # Store all raw shapes in a single validation-oriented BREP as well as per-component files.
    ROOT.joinpath('docs/build-summary.json').write_text(json.dumps({'engine':'CadQuery '+cq.__version__,'counts':manifest['counts'],
       'brep_features_valid':all(x['valid'] for x in brepmeta),'geometry_bytes':byte_offset,'bracket_mass_kg':build_bracket(BP)[0].Volume()*2.7e-6,
       'native_freecad_run':False,'native_solidworks_run':False,'physical_fit_test':False,'structural_fea':False,'electrical_energization':False},indent=2))
    return manifest,brepmeta

if __name__=='__main__':
    ts=time.time()
    for f in [structure,drive,batteries,power_panel,controls,handle_sensors,wiring,finalize_covers,clamps]:
        print(f.__name__,flush=True);f()
    export_geometry();print('Build seconds',round(time.time()-ts,2),flush=True)
