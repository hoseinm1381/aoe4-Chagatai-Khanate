"""Deterministic Blender masters for the Chagatai land-building art set."""
from pathlib import Path
import json
import math
import random
import sys

import bpy

sys.path.insert(0,str(Path(__file__).parent))
from ordu import Mesh, add_object, layout as ordu_layout

OUT=Path(sys.argv[-1])
BUILDINGS={
    "pasture":(4.0,"ck_building_pasture"),
    "steppe_hearth":(4.0,"ck_building_steppe_hearth"),
    "melee":(6.0,"ck_building_melee"),
    "ranged":(6.0,"ck_building_ranged"),
    "almaliq":(8.0,"ck_landmark_almaliq"),
    "ordu":(8.0,"ck_landmark_ordu"),
    "qarshi":(8.0,"ck_landmark_qarshi"),
    "court":(8.0,"ck_landmark_court"),
    "ili":(8.0,"ck_landmark_ili"),
    "mint":(8.0,"ck_landmark_mint"),
    "wonder":(12.0,"ck_building_wonder"),
}
STAGES=("healthy","frame00","frame25","frame50","frame75","wear","breach","collapse","ruins")
TEAM={2,6}

def block(mesh,x,y,z,w,d,h,tile):
    mesh.beam((x-w/2,y,z+h/2),(x+w/2,y,z+h/2),d,h,tile)

def shelter(mesh,x,y,w,d,z,stage,panel):
    legs=[(x+sx*w*.46,y+sy*d*.44) for sx in (-1,1) for sy in (-1,1)]
    for xx,yy in legs:
        mesh.beam((xx,yy,.08),(xx,yy,z),.12,.12,3)
    for yy in (y-d*.44,y+d*.44):
        mesh.beam((x-w*.46,yy,z),(x+w*.46,yy,z),.13,.13,3)
    if stage < 3:return
    profile=[(0,.05),(.24,.29),(.50,.45),(.77,.30),(1,.07)]
    rings=[[(x-w/2+t*w,y+side*d/2,z+h) for t,h in profile] for side in (-1,1)]
    points=rings[0]+rings[1]
    mesh.part(points,[(i,i+1,6+i,5+i) for i in range(4)],
              [panel,1,panel,panel])
    for i in (0,2,4):
        a,b=rings[0][i],rings[1][i]
        mesh.beam((a[0],a[1],a[2]+.018),(b[0],b[1],b[2]+.018),.028,.030,4)
    if stage==4:
        # A dyed felt windbreak hangs from the back stretcher and keeps the
        # open frontage legible as a work shelter or drill enclosure.
        yy=y+d*.445
        mesh.part([(x-w*.45,yy,z),(x+w*.45,yy,z),(x+w*.43,yy,z-.64),
                   (x,yy-.04,z-.71),(x-w*.44,yy,z-.58)],[(0,1,2,3,4)],6)
        for a,b in zip(rings[0],rings[0][1:]):
            mesh.beam(a,b,.05,.12,6)

def ger(mesh,x,y,r,stage,lod,court=False):
    n=(26,20,14)[lod]
    sides=[(r*math.cos(math.tau*i/n),r*math.sin(math.tau*i/n)) for i in range(n)]
    door={i for i,(xx,yy) in enumerate(sides) if abs(xx)<r*.26 and yy<0}
    mesh.shell((x,y),[(r*1.08,r*1.08,0),(r*1.05,r*1.05,r*.12)],n,0)
    for i,(xx,yy) in enumerate(sides):
        if i%2 or i in door:continue
        mesh.beam((x+xx,y+yy,r*.10),(x+xx,y+yy,r*.69),.06,.07,3)
    for side in (-1,1):
        xx=x+side*r*.22
        mesh.beam((xx,y-r*.98,r*.12),(xx,y-r*.98,r*.74),r*.07,r*.08,3)
    mesh.beam((x-r*.24,y-r*.98,r*.74),(x+r*.24,y-r*.98,r*.74),.09,.08,3)
    if stage>=2:
        mesh.shell((x,y),[(r*1.02,r*1.02,r*.11),(r,r,r*.71)],n,
                   lambda _,i:2 if (i//3)%3!=0 else 1,skip=door,cap=False)
    if stage>=3:
        roof=[(r*1.04,r*1.04,r*.70),(r*.88,r*.88,r*.88),(r*.48,r*.48,r*1.17),
              (r*.19,r*.19,r*1.35),(r*.15,r*.15,r*1.41)]
        skip=set(range(n//2,n)) if stage==3 else set()
        rings=mesh.shell((x,y),roof,n,lambda _,i:2 if (i//3)%2==0 else 1,skip=skip,cap=False)
        for i in range(0,n,2+lod):
            if i in skip:continue
            for a,b in zip(rings,rings[1:]):
                p,q=a[i],b[i]
                mesh.beam((p[0],p[1],p[2]+.015),(q[0],q[1],q[2]+.015),.025,.022,4)
        mesh.shell((x,y),[(r*.19,r*.19,r*1.38),(r*.15,r*.15,r*1.46)],12,3)
    if stage==4 and court:
        for i in range(6):
            xx=x+(i-2.5)*.23
            mesh.beam((xx,y-r*.94,r*.64),(xx,y-r*1.0,r*.34),.13,.06,6)

def fence(mesh,x,y,w,d,stage,lod):
    for axis,sign in ((0,-1),(0,1),(1,-1),(1,1)):
        length=(w,d)[axis]
        count=max(3,int(length/.65))
        side=(d,w)[axis]*sign/2
        points=[]
        for i in range(count+1):
            along=(i/count-.5)*length
            points.append((x+along,y+side) if axis==0 else (x+side,y+along))
        for i,(xx,yy) in enumerate(points):
            if axis==0 and sign==-1 and 0<i<count and abs(xx-x)<.45:
                continue
            height=.86 if stage>1 else .35
            mesh.beam((xx,yy,0),(xx,yy,height),.10,.10,3)
            if stage>=2 and i:
                a,b=points[i-1],points[i]
                if axis==0 and sign==-1 and min(abs(a[0]-x),abs(b[0]-x))<.43:continue
                for z in (.36,.64):
                    mesh.beam((*a,z),(*b,z),.07,.08,4 if z<.5 else 6)
            if stage==4 and lod==0:
                block(mesh,xx,yy,.62,.14,.14,.10,6)

def portal(mesh,x,y,w,h,d,stage,lod):
    radius=w*.31
    spring=h*.56
    for side in (-1,1):
        xx=x+side*(w/2-radius*.39)
        block(mesh,xx,y,.10,w*.23,d,spring-.10,0)
        block(mesh,xx,y,spring*.66,w*.24,d*1.04,.14,2)
        block(mesh,xx,y,spring-.12,w*.25,d*1.08,.12,7)
    if stage<2:return
    count=(11,9,7)[lod]
    for i in range(count):
        a,b=math.pi*i/count+.008,math.pi*(i+1)/count-.008
        if stage==2 and count//3<i<2*count//3:continue
        rr=radius+w*.14
        cross=[(x+math.cos(t)*r,spring+math.sin(t)*r)
               for t,r in ((a,radius),(b,radius),(b,rr),(a,rr))]
        coords=[(xx,y+side*d/2,zz) for side in (-1,1) for xx,zz in cross]
        mesh.part(coords,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],2 if i%3 else 7)
    if stage>=3:
        block(mesh,x,y,spring+radius+w*.16,w*1.09,d*1.12,.18,6)

def flag(mesh,x,y,height,width):
    mesh.beam((x,y,0),(x,y,height),.085,.085,3)
    mesh.part([(x,y,height-.12),(x+width,y+.07,height-.18),
               (x+width*.84,y+.10,height-.54),(x,y,height-.63)],[(0,1,2,3)],6)

def circular_target(mesh,x,y,lod):
    mesh.beam((x-.3,y,.02),(x,y,1.53),.09,.09,3)
    mesh.beam((x+.3,y,.02),(x,y,1.53),.09,.09,3)
    n=(18,12,8)[lod]
    for j,r in enumerate((.54,.42,.29,.14)):
        yy=y-.055-j*.012
        coords=[(x+r*math.cos(math.tau*i/n),yy,1.42+r*math.sin(math.tau*i/n)) for i in range(n)]
        mesh.part(coords,[tuple(range(n))],(4,2,1,6)[j])
        back=[(xx,y+.055+j*.012,zz) for xx,_,zz in coords]
        mesh.part(back,[tuple(reversed(range(n)))],(4,2,1,6)[j])

def broken(mesh,extent,seed,lod):
    rng=random.Random(seed)
    for _ in range((22,14,9)[lod]):
        x,y=(rng.uniform(-extent*.4,extent*.4) for _ in range(2))
        r=rng.uniform(.08,.25)
        block(mesh,x,y,.04,2.4*r,1.5*r,r,rng.choice((0,3,4,7)))
    for i in range(5-lod):
        x,y=(rng.uniform(-extent*.29,extent*.29) for _ in range(2))
        mesh.beam((x,y,.07),(x+.43,y+.61,.19),.12,.13,3)

def authored_model(name,state,lod):
    if name=="ordu":
        return ordu_layout(state,lod)
    extent=BUILDINGS[name][0]
    m=Mesh()
    e=extent*.5
    f=.32 if extent>6 else .20
    block(m,0,0,-.12,extent*.96,extent*.92,.21,0)
    level={"frame00":0,"frame25":1,"frame50":2,"frame75":3,"collapse":2,"ruins":0}.get(state,4)
    if level==0 or state in ("breach","collapse"):
        broken(m,extent,sum(map(ord,name)),lod)
    if level==0:return m
    if name=="steppe_hearth":
        ger(m,0,.12,e*.81,level,lod)
        if level==4:
            for x in (-1.42,1.34):block(m,x,-1.12,.11,.37,.33,.29,4)
            flag(m,1.52,.65,1.71,.36)
    elif name in ("pasture","ili"):
        fence(m,0,0,extent*.88,extent*.88,level,lod)
        shelter(m,0,e*.45,extent*.72,extent*.44,1.38 if name=="pasture" else 2.1,level,2)
        if level>=2:
            block(m,-e*.55,-e*.52,.09,e*.54,e*.24,.25,3)
            block(m,-e*.55,-e*.52,.34,e*.44,e*.17,.05,4)
        if name=="ili" and level==4:
            ger(m,e*.42,e*.39,e*.36,4,lod,True)
            flag(m,-e*.75,-e*.5,3.35,.64)
            flag(m,e*.73,-e*.54,3.35,.64)
    elif name in ("melee","ranged"):
        if name=="ranged":
            shelter(m,-e*.37,e*.48,extent*.50,extent*.33,1.61,level,2)
            if level>=2:
                for x in (.38,1.45):circular_target(m,x,e*.50,lod)
                block(m,e*.48,-e*.50,.12,.52,.32,.27,4)
            if level>=3:
                for x in (-e*.78,e*.78):
                    m.beam((x,-e*.41,0),(x,-e*.41,1.48),.10,.12,3)
                    m.beam((x,e*.27,0),(x,e*.27,1.48),.10,.12,3)
                    m.beam((x,-e*.41,1.43),(x,e*.27,1.43),.10,.10,3)
                    m.part([(x,-e*.41,1.38),(x,e*.27,1.38),(x,e*.24,.63),
                            (x,-e*.39,.69)],[(0,1,2,3)],6)
        else:
            shelter(m,0,e*.43,extent*.8,extent*.40,1.81,level,2)
        fence(m,0,-e*.15,extent*.86,extent*.63,level,lod)
        if level>=2:
            for i in range(3):
                x=(i-1)*1.05
                if name=="ranged":
                    if i!=1:circular_target(m,x,-.82+.15*i,lod)
                else:
                    m.beam((x,-.88,.05),(x,-.88,1.18),.10,.10,3)
                    m.beam((x-.26,-.88,1.01),(x+.26,-.88,1.01),.08,.08,4)
                    m.shell((x,-.88),[(.13,.11,.99),(.13,.11,1.18),(.09,.08,1.32)],10,1)
        if level==4:flag(m,-e*.67,-e*.8,2.45,.59)
    elif name=="almaliq":
        for side in (-1,1):
            shelter(m,side*e*.63,0,extent*.23,extent*.70,1.99,level,2)
            if level>=2:
                for i in range(3):
                    y=(i-1)*1.37
                    block(m,side*e*.64,y,.11,.79,.63,.35,3)
                    block(m,side*e*.64,y,.46,.62,.54,.12,4 if i%2 else 7)
        portal(m,0,e*.64,extent*.37,3.8,.61,level,lod)
        if level==4:
            for side in (-1,1):flag(m,side*1.55,-e*.75,2.92,.73)
    elif name=="court":
        ger(m,0,e*.13,e*.70,level,lod,True)
        if level>=2:
            for side in (-1,1):
                shelter(m,side*e*.69,-e*.50,extent*.27,extent*.24,1.9,level,2)
                if level==4:flag(m,side*e*.71,e*.70,3.84,.87)
    else:
        center={"qarshi":.53,"mint":.44,"wonder":.54}[name]
        width=extent*center
        back=e*.23
        wall=2.45 if name!="wonder" else 3.25
        if level>=1:
            block(m,0,back,.08,width,width*.82,.32,0)
            for side in (-1,1):
                block(m,side*width*.44,back,.39,width*.16,width*.72,wall-.39,0)
                block(m,side*width*.44,back,wall*.58,width*.17,width*.73,.19,2)
                block(m,side*width*.44,back,wall-.14,width*.18,width*.75,.15,6)
        if level>=2:
            block(m,0,back+width*.35,.40,width*.75,.24,wall-.40,0)
            portal(m,0,back-width*.35,width*.87,wall+1.18,.51,level,lod)
        if level>=3:
            block(m,0,back,wall,width,width*.82,.15,2)
            if name=="qarshi":
                for side in (-1,1):
                    xx=side*(width*.51+.18)
                    m.shell((xx,back-.35),[(.48,.48,.14),(.42,.42,2.52),(.51,.51,2.60),(.43,.43,2.89)],12,lambda i,_:2 if i==1 else 0)
                    flag(m,xx,back-.35,3.78,.5)
            else:
                radius=width*(.40 if name=="wonder" else .36)
                dome=[(radius,radius,wall+.11),(radius*.98,radius*.98,wall+.45),
                      (radius*.86,radius*.86,wall+.83),(radius*.60,radius*.60,wall+1.23),
                      (radius*.27,radius*.27,wall+1.53),(.09,.09,wall+1.70)]
                m.shell((0,back),dome,(32,24,16)[lod],lambda _,i:2 if i%4!=0 else 7)
        if level==4:
            if name=="mint":
                shelter(m,-e*.60,-e*.53,extent*.28,extent*.28,1.69,level,2)
                for i in range(3):
                    block(m,-e*.61+i*.31,-e*.54,.10,.25,.31,.27,4)
                m.shell((e*.51,-e*.56),[(.36,.36,.08),(.37,.37,.32),(.25,.25,.55)],12,5)
            if name=="wonder":
                for side in (-1,1):
                    xx=side*extent*.33
                    m.shell((xx,e*.06),[(.50,.50,.09),(.45,.45,3.4),(.52,.52,3.60),(.27,.27,4.0),(.08,.08,4.32)],
                            (15,12,9)[lod],lambda row,_:2 if row in (1,2) else 0)
            for side in (-1,1):flag(m,side*e*.70,-e*.65,2.86 if name!="wonder" else 3.48,.66)
    return m

def generate():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    OUT.mkdir(parents=True,exist_ok=True)
    material=bpy.data.materials.new("main")
    material.diffuse_color=(.50,.34,.20,1)
    table={}
    for name,(extent,blueprint) in BUILDINGS.items():
        collection=bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
        coverage={}
        for state in STAGES:
            for lod in range(3):
                label=f"{name}_{state}_lod{lod+1}"
                obj,ratio=add_object(authored_model(name,state,lod),label,material)
                for link in list(obj.users_collection):link.objects.unlink(obj)
                collection.objects.link(obj)
                obj["native_stage"]=state
                obj["lod"]=lod+1
                obj.hide_set(state!="healthy" or lod!=0 or name!="ordu")
                coverage[label]=round(ratio,4)
        table[name]={"blueprint":blueprint,"footprint":extent,"mask_coverage":coverage}
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"Chagatai-buildings.blend"))
    (OUT/"coverage.json").write_text(json.dumps(table,indent=2),encoding="utf-8")

if __name__=="__main__":
    generate()
