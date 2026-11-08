"""Ordu of Almaliq Blender source and deterministic native FBX export.

Run in an isolated background Blender process with -- WORK TEMPLATE DONOR_RGO.
The stock Deer Stones bounds are 10.8 × 10.1 m. The new mobile court keeps
the stock plot, with a broad low felt silhouette and a taller horse standard.
"""
from collections import defaultdict
import inspect
import json
import math
import os
from pathlib import Path
import random
import struct
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

WORK, TEMPLATE, DONOR = map(Path, sys.argv[-3:])
EXT = Path(os.environ["APPDATA"]) / "Blender Foundation/Blender/5.2/extensions/raw_githubusercontent_com/garrison"
sys.path[:0] = [str(EXT), str(EXT.parent)]
from garrison_shared import relic_chunky as rc, unit_model_export as core
sys.path.insert(0, str(Path(__file__).parent))
from lifecycle import graft
import garrison
sys.modules["garrison.garrison_shared"] = sys.modules["garrison_shared"]
from garrison import unit_export

PALETTE = [
    ("Weathered clay", (.34,.22,.13)), ("Felt", (.68,.58,.42)),
    ("Dyed felt", (.57,.38,.24)), ("Oiled larch", (.26,.13,.07)),
    ("Sewn leather", (.27,.19,.13)), ("Iron", (.21,.22,.19)),
    ("Banner cloth", (.51,.32,.21)), ("Bone trim", (.57,.46,.31)),
]
TEAM = {2,6}
STATES = {
    "healthy": ("healthy","preview","targeting"),
    "frame00": tuple(f"construct_{i:02}" for i in range(0,25,5)),
    "frame25": tuple(f"construct_{i:02}" for i in range(25,50,5)),
    "frame50": tuple(f"construct_{i:02}" for i in range(50,75,5)),
    "frame75": tuple(f"construct_{i:02}" for i in range(75,100,5)),
    "wear": ("damage_1","damage_2"), "breach": ("damage_3",),
    "collapse": ("damage_4","damage_5"), "ruins": ("ruins",),
}

class Mesh:
    def __init__(self):
        self.vertices, self.faces, self.tiles = [], [], []

    def part(self, points, faces, tiles):
        start = len(self.vertices)
        self.vertices.extend(points)
        self.faces.extend(tuple(i+start for i in face) for face in faces)
        self.tiles.extend([tiles]*len(faces) if isinstance(tiles,int) else tiles)

    def beam(self, start, end, width, depth, tile):
        a,b = Vector(start),Vector(end)
        direction = (b-a).normalized()
        u = direction.cross(Vector((0,0,1)))
        if u.length < .001:
            u = direction.cross(Vector((1,0,0)))
        u = u.normalized()*width/2
        v = direction.cross(u).normalized()*depth/2
        points = [p+x*u+y*v for p in (a,b) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
        self.part(points,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],tile)

    def shell(self, origin, profile, sides, tile, skip=(), cap=True):
        x,y = origin
        rings = [[(x+rx*math.cos(math.tau*i/sides), y+ry*math.sin(math.tau*i/sides), z)
                  for i in range(sides)] for rx,ry,z in profile]
        faces, tiles = [], []
        for row in range(len(rings)-1):
            for i in range(sides):
                if i in skip:
                    continue
                j = (i+1)%sides
                faces.append((row*sides+i,row*sides+j,(row+1)*sides+j,(row+1)*sides+i))
                tiles.append(tile(row,i) if callable(tile) else tile)
        if cap and not skip:
            faces.extend((tuple(reversed(range(sides))),tuple(range((len(rings)-1)*sides,len(rings)*sides))))
            tiles.extend((0,0))
        self.part([p for ring in rings for p in ring],faces,tiles)
        return rings

def layout(state, lod):
    mesh = Mesh()
    rng = random.Random(902)
    n = (32,24,16)[lod]
    ruined = state=="ruins"
    level = {"frame00":0,"frame25":1,"frame50":2,"frame75":3,"ruins":0}.get(state,4)
    breach = {"wear":1,"breach":2,"collapse":4}.get(state,0)
    base = [ (3.62,3.45,-.14),(3.64,3.47,.02),(3.42,3.25,.30),(3.31,3.12,.36) ]
    mesh.shell((0,0),base,n,lambda row,i:3 if row==2 else 0)
    for y,height in [(-3.51,.18),(-3.82,.10),(-4.12,.03)]:
        mesh.beam((-1.06,y,.03),(1.06,y,.03),.32,height*2,3)
    for i in range((10,7,5)[lod]):
        x,y = rng.uniform(-4.75,4.75),rng.uniform(-4.52,4.52)
        if x*x+y*y < 13.0:
            continue
        radius = rng.uniform(.14,.34)
        mesh.shell((x,y),[(radius,radius*.64,-.08),(radius*.83,radius*.48,.16)],5,0)
    points = [(3.02*math.cos(math.tau*i/n),2.82*math.sin(math.tau*i/n)) for i in range(n)]
    door = {i for i in range(n) if abs(points[i][0])<.68 and points[i][1]<0}
    knocked = {((n//8)+i)%n for i in range(breach)}
    if level>=1:
        for i,(x,y) in enumerate(points):
            if i in door or i in knocked or i%2:
                continue
            mesh.beam((x,y,.36),(x,y,2.20),.12,.12,3)
            j = (i+2)%n
            if j not in door and j not in knocked and lod<2:
                a,b = points[j]
                mesh.beam((x,y,.5),(a,b,2.12),.065,.065,4)
                mesh.beam((a,b,.5),(x,y,2.12),.065,.065,4)
        for x in (-.70,.70):
            mesh.beam((x,-2.85,.36),(x,-2.85,2.22),.16,.17,3)
        mesh.beam((-.78,-2.85,2.22),(.78,-2.85,2.22),.16,.16,3)
    if level>=2:
        wall = [(3.04,2.85,.38),(3.08,2.88,.51),(3.10,2.91,1.96),(3.16,2.97,2.16)]
        mesh.shell((0,0),wall,n,lambda row,i:2 if row==2 or (row==1 and i//max(1,n//8) not in (1,5)) else 1,skip=door|knocked,cap=False)
        band = [(3.12,2.92,.78),(3.12,2.92,.88)]
        mesh.shell((0,0),band,n,4,skip=door|knocked,cap=False)
    if level>=3:
        roof = [(3.22,3.01,2.13),(3.23,3.03,2.24),(2.70,2.55,2.77),
                (1.78,1.65,3.38),(.75,.70,3.91),(.53,.51,4.10)]
        missing = (set(range(n//2,n)) if level==3 else set())|knocked
        rings = mesh.shell((0,0),roof,n,lambda row,i:2 if (i//max(1,n//8)) not in (1,3,6) else 1,skip=missing,cap=False)
        for i in range(0,n,max(1,1+lod)):
            if i in missing:
                continue
            for row in range(len(rings)-1):
                a,b=rings[row][i],rings[row+1][i]
                mesh.beam((a[0],a[1],a[2]+.013),(b[0],b[1],b[2]+.013),.038,.033,7 if i%2 else 4)
        if level==4:
            mesh.shell((0,0),[(.57,.55,4.04),(.49,.46,4.23),(.22,.20,4.42)],max(8,n//2),3)
    if level==4 and breach<4:
        for x,y,height in [(-3.75,-3.32,3.4),(3.75,-3.32,3.4),(-3.8,2.7,2.65),(3.8,2.7,2.65)]:
            mesh.beam((x,y,.0),(x,y,height),.13,.13,3)
            mesh.shell((x,y),[(.15,.15,height-.30),(.16,.16,height-.21),(.11,.11,height-.14)],8,5)
            mesh.part([(x,y,height-.35),(x+.55,y+.04,height-.48),(x+.87,y+.05,height-.66),
                       (x+.60,y-.02,height-1.00),(x,y,height-.87)],[(0,1,2),(0,2,3,4)],6)
        mesh.beam((0,3.58,0),(0,3.58,6.34),.14,.14,3)
        mesh.beam((-.53,3.58,5.76),(.53,3.58,5.76),.1,.1,5)
        for i in range(5):
            x=(i-2)*.24
            mesh.beam((x,3.58,5.75),(x+.10,3.65,4.97+abs(i-2)*.15),.10,.065,7)
        mesh.shell((0,3.58),[(.2,.18,6.03),(.24,.2,6.14),(.06,.05,6.48)],9,5)
    if ruined or breach>=2:
        for i in range((18,13,8)[lod]):
            a = rng.uniform(0,math.tau)
            r = rng.uniform(.48,2.78)
            x,y = math.cos(a)*r,math.sin(a)*r
            length = rng.uniform(.42,1.22)
            mesh.beam((x,y,.37),(x+math.cos(a)*length,y+math.sin(a)*length,.47),.12,.12,3)
            if i%3==0:
                mesh.part([(x,y,.41),(x+.53,y+.14,.50),(x+.24,y+.54,.45),(x-.24,y+.43,.42)],
                          [(0,1,2,3)],2 if i%2 else 1)
    return mesh

def add_object(mesh, name, material):
    data=bpy.data.meshes.new(name)
    data.from_pydata(mesh.vertices,[],mesh.faces)
    bm=bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    data.update()
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(material)
    uv=data.uv_layers.new(name="UVMap")
    area=defaultdict(float)
    for poly,tile in zip(data.polygons,mesh.tiles,strict=True):
        area[tile]+=poly.area
        for i,loop in enumerate(poly.loop_indices):
            u,v=((.16,.15),(.84,.15),(.84,.85),(.16,.85))[i%4]
            uv.data[loop].uv=((tile%4+u)/4,(tile//4+v)/2)
    data.uv_layers.new(name="UV2",do_init=True)
    return obj, sum(area[k] for k in TEAM)/sum(area.values())

def native_rgo():
    base=rc.parse((TEMPLATE/"model.rgo").read_bytes())
    def find(doc,tag):
        return next(c for c in rc.walk(doc.roots) if c.tag==tag)
    def pack(chunk,data):
        return rc.pack_chunk(chunk.kind,chunk.tag,data,version=chunk.version,name=chunk.name)
    selectors=find(base,b"MSBP")
    header=next(c for c in selectors.children if c.tag==b"HDR ")
    msa=next(c for c in selectors.children if c.tag==b"MSA ")
    count=next(c for c in selectors.children if c.tag==b"MSD " and len(c.payload)==4)
    shape=next(c for c in selectors.children if c.tag==b"MSD " and len(c.payload)>4)
    condition=next(c for c in selectors.children if c.tag==b"CNBP")
    payload=pack(header,header.payload)+pack(msa,msa.payload)+pack(count,struct.pack("<I",len(STATES)))
    for state,keys in STATES.items():
        model="ordu_"+state
        payload+=pack(shape,rc.lp_string("select_"+state)+struct.pack("<I",1)+rc.lp_string(model))
        tests=b"".join(struct.pack("<IBI",2,0,int(i>0))+rc.lp_string("life_cycle_state")+rc.lp_string(key)
                       for i,key in enumerate(keys))
        payload+=pack(condition,struct.pack("<I",len(keys))+tests)
    defaults=(TEMPLATE/"building-lifecycle-defaults.bin").read_bytes()
    staged=rc.rebuild(base,lambda chunk:payload if chunk.offset==selectors.offset else defaults if chunk.tag==b"DTBP" else None)
    return graft(staged,DONOR.read_bytes(),rc)

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    WORK.mkdir(parents=True,exist_ok=True)
    mat=bpy.data.materials.new("chagatai_ordu_atlas")
    mat.diffuse_color=(.55,.39,.22,1.0)
    atlas=WORK/"albedo.png"
    if atlas.exists():
        mat.use_nodes=True
        nodes=mat.node_tree.nodes
        tex=nodes.new("ShaderNodeTexImage")
        tex.image=bpy.data.images.load(str(atlas))
        tex.image.pack()
        mat.node_tree.links.new(tex.outputs["Color"],nodes.get("Principled BSDF").inputs["Base Color"])
    records=json.loads((TEMPLATE/"static-root-record.json").read_text(encoding="utf-8"))["records"]
    arm=bpy.data.armatures.new("Ordu static rig")
    rig=bpy.data.objects.new("Ordu static rig",arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bone=arm.edit_bones.new(records[0]["name"])
    bone.matrix=Matrix(core.rest_matrix(records[0]))
    bone.length=1.0
    bpy.ops.object.mode_set(mode="OBJECT")
    meshes=[]
    coverage={}
    for state in STATES:
        for lod in range(3):
            name=f"ordu_{state}_lod{lod+1}"
            obj,fraction=add_object(layout(state,lod),name,mat)
            group=obj.vertex_groups.new(name=records[0]["name"])
            group.add(list(range(len(obj.data.vertices))),1.0,"REPLACE")
            obj.modifiers.new("Native static root","ARMATURE").object=rig
            meshes.append(obj)
            coverage[name]=round(fraction,4)
    print("Ordu LOD1 player-color surface",coverage["ordu_healthy_lod1"],flush=True)
    assert .20<=coverage["ordu_healthy_lod1"]<=.40,coverage
    for obj in meshes:
        obj.hide_set(obj.name!="ordu_healthy_lod1")
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/"ordu.blend"))
    for obj in meshes:
        obj.hide_set(False)
    exporter=dict(vars(unit_export))
    code=inspect.getsource(unit_export.export_unit_model)
    assert code.count("filepath=str(output),")==1
    exec(compile(code.replace("filepath=str(output),","filepath=str(output), use_triangles=True,"),"ordu-triangulated-fbx","exec"),exporter)
    exporter["export_unit_model"](rig,meshes,WORK/"model.fbx",records)
    core.write_rig(WORK,core.rig_text(records,partitions=[("Static_LOD1",0,1)]))
    (WORK/"model.rgo").write_bytes(native_rgo())
    (WORK/"model.rgotemplate").write_bytes((TEMPLATE/"model.rgotemplate").read_bytes())
    (WORK/"coverage.json").write_text(json.dumps(coverage,indent=2),encoding="utf-8")

if __name__ == "__main__":
    main()
