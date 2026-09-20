"""Geometric construction transcribed from JTech-CO/Motor-Bracket/src/build_cadquery.py.
SCMB Rev A. Upstream design retained; helpers condensed, no interface alteration.
No manufacturing, radial-load or 18 kg capacity approval is inherited.
"""
import cadquery as cq
from cadquery.selectors import ParallelDirSelector

def poly(points, plane, length, radius=0):
    s=cq.Workplane(plane).polyline(points).close().extrude(length)
    return s.edges(ParallelDirSelector(plane.zDir)).fillet(radius) if radius else s

def rect(plane,x,y,w,h,l,r):
    return cq.Workplane(plane).center(x,y).rect(w,h).extrude(l).edges(ParallelDirSelector(plane.zDir)).fillet(r)

def block(x0,x1,y0,y1,z0,z1):
    return cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0,centered=(False,False,False)).translate((x0,y0,z0))

def build(p):
    w,t,g=p['width'],p['plate_thickness'],p['motor_face_gap'];top=p['top_underside_z'];tt=p['top_thickness'];rib=p['gusset_thickness'];yi=-p['inboard_extent_y']
    fp=cq.Plane(origin=(0,g+t,0),xDir=(1,0,0),normal=(0,-1,0))
    outline=[(-46,-42),(62,-42),(w/2,-30),(w/2,top),(-w/2,top),(-w/2,10),(-50,-18)]
    body=poly(outline,fp,t,4).union(rect(cq.Plane(origin=(0,0,top)),0,(yi+g+t)/2,w,g+t-yi,tt,4))
    for x in [-w/2,w/2-rib]:
        body=body.union(poly([(g,0),(g,top),(yi,top)],cq.Plane(origin=(x,0,0),xDir=(0,1,0),normal=(1,0,0)),rib))
    r=p['root_radius'];inner=w/2-rib
    body=body.union(block(-inner,inner,g-r,g,top-r,top))
    for a,b in [(-inner,-inner+r),(inner-r,inner)]:
        body=body.union(block(a,b,g-r,g,0,top)).union(block(a,b,yi,g,top-r,top))
    cavity=block(-inner,inner,yi-100,g,-100,top);edges=[]
    for e in cavity.val().Edges():
        c=e.Center();bb=e.BoundingBox()
        if abs(c.y-g)<1e-5 and abs(c.z-top)<1e-5 and bb.xlen>1:edges.append(e)
        elif abs(abs(c.x)-inner)<1e-5 and ((abs(c.y-g)<1e-5 and bb.zlen>1) or (abs(c.z-top)<1e-5 and bb.ylen>1)):edges.append(e)
    assert len(edges)==5
    body=body.cut(cavity.newObject(edges).fillet(r)).clean()
    for x,z in p['motor_holes_xz']:
        body=body.cut(cq.Solid.makeCylinder(p['motor_seat_relief_diameter']/2,200,cq.Vector(x,g-200,z),cq.Vector(0,1,0)))
    cutters=cq.Workplane(fp).circle(p['central_clearance_diameter']/2).extrude(t+1)
    for x,z in p['motor_holes_xz']:
        cutters=cutters.union(cq.Workplane(fp).center(x,z).circle(p['bracket_hole_diameter']/2).extrude(t+1))
    body=body.cut(cutters)
    for x,y in p['frame_holes_xy']:
        body=body.cut(cq.Workplane('XY',origin=(0,0,top-1)).center(x,-y).circle(p['frame_hole_diameter']/2).extrude(tt+2))
    if p['lightening_windows']:
        body=body.cut(rect(fp,-57,44,16,42,t+1,6)).cut(rect(fp,40,49,34,34,t+1,6))
        body=body.cut(rect(cq.Plane(origin=(0,0,top-1)),0,-34,70,46,tt+2,6))
        for x in [-w/2-1,w/2-rib-1]:
            body=body.cut(poly([(-6,34),(-6,66),(-38,66)],cq.Plane(origin=(x,0,0),xDir=(0,1,0),normal=(1,0,0)),rib+2,4))
    body=body.clean().val().mirror('XZ')
    spacer=cq.Workplane('XZ').circle(p['spacer_od']/2).circle(p['spacer_id']/2).extrude(-g).val().mirror('XZ')
    assert body.isValid() and len(body.Solids())==1
    return body,spacer
