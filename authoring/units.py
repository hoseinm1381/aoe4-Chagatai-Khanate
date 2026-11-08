"""Create rig-matched Chagatai horse and rider meshes from decoded stock binds."""
from collections import defaultdict
import inspect
import json
import math
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import bmesh
import bpy
from mathutils import Matrix
from mathutils.kdtree import KDTree

args=sys.argv[sys.argv.index("--")+1:]
ROOT=Path(__file__).resolve().parent
EXT=Path(os.environ["APPDATA"])/"Blender Foundation/Blender/5.2/extensions/raw_githubusercontent_com/garrison"
sys.path[:0]=[str(ROOT),str(EXT),str(EXT.parent)]
from garrison_shared import unit_model_export as core
import garrison
sys.modules["garrison.garrison_shared"]=sys.modules["garrison_shared"]
from garrison import unit_export
from ordu import Mesh

def armor(group,role,lod,style):
    mesh=Mesh()
    if role=="rider":
        # Keep the grips and seat in their original frame. The new overcoat and
        # laced lamellar bands are rooted to the donor torso surface.
        for side in (-1,1):
            rows = 4 if style=="heavy" else 2 if style in {"archer","crossbow","gunner"} else 3 if style=="light" else 0
            for row in range(max(0,rows-(lod==2))):
                for i in range(6 if lod==0 else 4):
                    x=(i-(2.5 if lod==0 else 1.5))*(.052 if lod==0 else .072)
                    z=1.16+row*.068
                    y=side*(.185-.9*x*x)
                    mesh.beam((x-.025,y,z),(x+.025,y,z),.042,.076,5 if row%2 else 4)
        mesh.shell((0,-.015),[(.113,.127,1.82),(.119,.129,1.90),
                              (.091,.106,1.983),(.043,.061,2.042)],12 if lod==0 else 8,
                   lambda row,i:6 if row==0 and i%3 else 5)
        for side in (-1,1):
            mesh.beam((side*.099,.042,1.852),(side*.118,.069,1.687),.065,.07,6)
        mesh.beam((-.176,-.176,1.167),(.176,-.176,1.167),.04,.056,4)
        if style in {"trader","sufi","worker","gunner","crossbow"}:
            mesh.beam((-.11,.129,1.20),(.12,.156,1.18),.092,.16,4)
            mesh.beam((-.093,.156,1.29),(.101,.173,1.26),.078,.118,6)
        if style in {"sufi","trader","worker","scout"}:
            mesh.shell((0,-.011),[(.122,.137,1.78),(.124,.142,1.85),(.108,.123,1.91)],
                       12 if lod==0 else 8,lambda row,i:6 if i%3 else 1)
    elif role in {"mount","horse"}:
        # Wool saddle pad and halter pieces sit against the reconstructed body.
        y0=-.23 if role=="mount" else .02
        x=.39 if role=="mount" else .245
        z0=1.49 if role=="mount" else 1.22
        for side in (-1,1):
            for j in range(3 if lod==0 else 2):
                yy=y0+(j-1)*.20
                mesh.part([(side*(x-.09),yy-.10,z0+.19),(side*(x-.10),yy+.10,z0+.19),
                           (side*x,yy+.10,z0-.24),(side*x,yy-.10,z0-.26)],
                          [(0,1,2,3)],6 if j%2==0 else 2)
                mesh.beam((side*x,yy-.102,z0-.25),(side*x,yy+.103,z0-.24),.020,.04,4)
        if role=="horse":
            # Rebuild the ears above the new rounded poll after removing antlers.
            for side in (-1,1):
                xx=side*.077
                mesh.part([(xx-.031,-1.43,1.80),(xx+.033,-1.44,1.81),(xx,-1.46,2.01),
                           (xx,-1.49,1.87)],[(0,1,2),(0,3,1),(1,3,2),(0,2,3)],4)
            mesh.beam((0,.73,1.52),(0,.86,1.19),.075,.08,4)
            mesh.beam((0,.85,1.24),(0,.98,.73),.12,.13,4)
    return mesh

def tile_for(role,center,style):
    x,y,z=center
    if role=="rider":
        if z>1.82:return 5 if z>1.91 else 6
        if z>1.64 and abs(x)<.21:return 7
        if z>1.19 and abs(x)<(.33 if style in {"archer","crossbow","gunner"} else .46):return 6 if style in {"sufi","worker"} else 2
        if z>.79 and abs(x)<.25:return 6 if z>1.02 else 4
        return 3 if z<.47 else 1
    if role=="corpse":return 6 if abs(y)<.46 and z>.69 else 0
    if abs(y)<(.51 if role=="horse" else .57) and z>(1.10 if role=="horse" else 1.04):
        return 2 if abs(x)>.17 else 6
    if y<-.96 and z>1.39:return 4
    return 0 if z>.60 else 3

def horse_body(positions,triangles):
    # The three stock islands are the body and two detachable antlers.
    points=[tuple(p) for p in positions]
    neighbors=defaultdict(set)
    for triangle in triangles:
        vertices=[points[i] for i in triangle]
        for point in vertices:neighbors[point].update(vertices)
    islands=[]
    while neighbors:
        pending=[next(iter(neighbors))]
        island=set()
        while pending:
            point=pending.pop()
            if point in neighbors:
                pending.extend(neighbors.pop(point))
                island.add(point)
        islands.append(island)
    body=max(islands,key=len)
    return [face for face in triangles if points[face[0]] in body]

def editable(doc,group,role,lod,material,rig,label,style):
    positions=group["positions"]
    palette=doc["skeleton"]["skin_palettes"][group["rig_projection"]["palette_index"]]
    names={row["palette_index"]:row["name"] for row in palette["bones"]}
    weights=[]
    for indices,values in zip(group["skin_indices"],group["skin_weights"],strict=True):
        combined=defaultdict(float)
        for index,weight in zip(indices,values):
            if weight>0:combined[names[index]]+=weight
        if not combined:raise ValueError("Vertex without native skin")
        weights.append(combined)
    output=[]
    for x,y,z in positions:
        if role=="rider":
            torso=max(0,1-abs(z-1.38)/.42)
            x*=1+.09*torso
            y*=1+.10*torso
            if z>1.87:z=1.87+(z-1.87)*.45
        else:
            barrel=max(0,1-abs(y+.03)/.83)*max(0,1-abs(z-1.18)/.68)
            x*=1+.19*barrel
            if role=="horse" and y<-.82:
                # Draw the reindeer-based muzzle into the more compact horse head.
                y=-.82+(y+.82)*.88
                if z<1.78:x*=1.10
        output.append((x,y,z))
    faces=[]
    tiles=[]
    triangles=group["triangles"]
    if role=="horse":triangles=horse_body(positions,triangles)
    for tri in triangles:
        center=tuple(sum(output[i][axis] for i in tri)/3 for axis in range(3))
        faces.append(tri)
        tile=tile_for(role,center,style)
        x,y,z=center
        if tile in {2,6} and role=="rider" and len(doc["skeleton"]["bones"])!=127:
            if style in {"scout","heavy","sufi","trader"} and 1.22<z<1.72:
                if abs(x)>(.15 if style=="scout" else .19) and (y>0 or z<1.47):
                    tile=1 if style in {"trader","sufi"} else 4
        tiles.append(tile)

    added=armor(group,role,lod,style)
    nearest=KDTree(len(output))
    for i,v in enumerate(output):nearest.insert(v,i)
    nearest.balance()
    offset=len(output)
    for vertex in added.vertices:
        _,i,_=nearest.find(vertex)
        output.append(tuple(vertex))
        weights.append(weights[i])
    for face,tile in zip(added.faces,added.tiles,strict=True):
        for i in range(1,len(face)-1):
            faces.append(tuple(offset+k for k in (face[0],face[i],face[i+1])))
            tiles.append(tile)
    used=sorted({i for face in faces for i in face})
    remap={old:new for new,old in enumerate(used)}
    mesh=bpy.data.meshes.new(label)
    mesh.from_pydata([output[i] for i in used],[],[tuple(remap[i] for i in face) for face in faces])
    bm=bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj=bpy.data.objects.new(label,mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(material)
    uv=mesh.uv_layers.new(name="UVMap")
    area=[0.0,0.0]
    for face,tile in zip(mesh.polygons,tiles,strict=True):
        area[0]+=face.area
        if tile in {2,6}:area[1]+=face.area
        for loop,(u,v) in zip(face.loop_indices,((.20,.20),(.82,.22),(.54,.79)),strict=True):
            uv.data[loop].uv=((tile%4+u)/4,(tile//4+v)/2)
        face.use_smooth=True
    groups={name:obj.vertex_groups.new(name=name) for name in sorted({k for row in weights for k in row})}
    for j,i in enumerate(used):
        total=sum(weights[i].values())
        for name,weight in weights[i].items():groups[name].add([j],weight/total,"REPLACE")
    modifier=obj.modifiers.new("Preserved native binding","ARMATURE")
    modifier.object=rig
    return obj,area[1]/area[0]

def build(manifest,out,asset,roles,style="light"):
    doc=json.loads(manifest.read_bytes())
    records=doc["skeleton"]["bones"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm=bpy.data.armatures.new(asset+"_native_rig")
    rig=bpy.data.objects.new(arm.name,arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for record in records:
        bone=arm.edit_bones.new(record["name"])
        if record["parent_name"]:bone.parent=arm.edit_bones[record["parent_name"]]
        bone.matrix=Matrix(core.rest_matrix(record))
        bone.length=.16
    bpy.ops.object.mode_set(mode="OBJECT")
    material=bpy.data.materials.new("main")
    material.diffuse_color=(.51,.34,.24,1)
    groups=doc["geometry"]["groups"]
    objects=[]
    coverage={}
    for role,indices in roles:
        for level,group_index in enumerate(indices):
            label=f"{asset}_{role}_lod{level+1}"
            obj,fraction=editable(doc,groups[group_index],role,level,material,rig,label,style)
            objects.append(obj)
            coverage[label]=round(fraction,4)
    out.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(asset+".blend")))
    export_native(rig,objects,out,asset,records)
    (out/"bindings.json").write_text(json.dumps({"donor":str(manifest),"bones":len(records),
        "masks":coverage,"meshes":[x.name for x in objects]},indent=2),encoding="utf-8")

def export_native(rig,objects,out,asset,records):
    export_source=inspect.getsource(unit_export.export_unit_model)
    assert export_source.count("filepath=str(output),")==1
    implementation=dict(vars(unit_export))
    exec(compile(export_source.replace("filepath=str(output),","filepath=str(output), use_triangles=True,"),
                 "triangulated-native-export","exec"),implementation)
    implementation["export_unit_model"](rig,objects,out/(asset+".fbx"),records)
    core.write_rig(out,core.rig_text(records,partitions=[("FullBody_LOD3",0,len(records))]))
    (out/"model.rig").rename(out/(asset+".rig"))

def export_masters(source,output):
    for path in sorted(source.glob("*/*.blend")):
        asset=path.stem
        out=output/asset
        out.mkdir(parents=True)
        records=json.loads(path.with_name("native-bind.json").read_bytes())
        bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False)
        [rig]=[obj for obj in bpy.data.objects if obj.type=="ARMATURE"]
        objects=sorted((obj for obj in bpy.data.objects if obj.type=="MESH"),key=lambda obj:obj.name)
        export_native(rig,objects,out,asset,records)
        (out/"bindings.json").write_text(json.dumps({"bones":len(records),
            "meshes":[obj.name for obj in objects]},indent=2),encoding="utf-8")

def bind_signature(document):
    return {b["name"]:(b["parent_name"], b["global_reference_transform"])
            for b in document["skeleton"]["bones"]}

def same_bind(expected,actual):
    a,b=bind_signature(expected),bind_signature(actual)
    if a.keys()!=b.keys():return False
    for name in a:
        parent,transform=a[name]
        other_parent,other=b[name]
        if parent!=other_parent:return False
        for field in ("translation_xyz","quaternion_xyzw","scale_xyz"):
            left,right=transform[field],other[field]
            if field=="quaternion_xyzw" and sum(x*y for x,y in zip(left,right))<0:
                right=[-v for v in right]
            if max(abs(x-y) for x,y in zip(left,right))>1e-5:return False
    return True

def batch(catalog,out):
    rows=json.loads(catalog.read_bytes())
    lookup={asset:Path(path) for row in rows for asset,path in row["manifests"].items()}
    substitutes={
        "spearman_mounted_3_1":"spearman_mounted_2_1",
        "spearman_mounted_4_1":"spearman_mounted_2_1",
        "nokor_mounted_4_2":"nokor_mounted_3_2",
        "archer_mounted_2_2":"archer_mounted_3_2",
        "religious_mounted_3_1":"spearman_mounted_2_1",
    }
    for row in rows:
        style=row["style"]
        for asset,manifest_path in row["manifests"].items():
            manifest=Path(manifest_path)
            doc=json.loads(manifest.read_bytes())
            if asset in substitutes:
                candidate=lookup[substitutes[asset]]
                substitute=json.loads(candidate.read_bytes())
                if not same_bind(doc,substitute):
                    raise ValueError(f"Incompatible stock palette substitute for {asset}")
                manifest,doc=candidate,substitute
            groups=doc["geometry"]["groups"]
            if style=="corpse":
                indexes=[i for i,g in enumerate(groups) if "resource" in g["name"]]
                if len(indexes)!=1:raise ValueError((asset,indexes))
                roles=[("corpse",indexes*3)]
            elif style=="horse":
                roles=[("horse",[0,1,2])]
            elif len(doc["skeleton"]["bones"])==127:
                def tiers(prefix):
                    return [max((i for i,g in enumerate(groups) if g["material"].startswith(prefix+"_") and g["material"].endswith(f"_lod{level}")),
                                key=lambda i:groups[i]["vertex_count"]) for level in (1,2,3)]
                roles=[("mount",tiers("horse")),("rider",tiers("rider"))]
            else:
                roles=[("rider",[0,1,2])]
            if not (out/asset/"bindings.json").is_file():build(manifest,out/asset,asset,roles,style)

if __name__=="__main__":
    if args[0]=="--export-masters":
        export_masters(Path(args[1]),Path(args[2]))
    elif len(args)==2:
        batch(Path(args[0]),Path(args[1]))
    else:
        asset=args[2]
        roles=[("mount",[0,1,2]),("rider",[3,4,5])] if asset=="light_lancer" else [("horse",[0,1,2])]
        build(Path(args[0]),Path(args[1]),asset,roles)
