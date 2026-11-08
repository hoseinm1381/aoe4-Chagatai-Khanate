"""Export approved Blender unit collections with their native bind and packed team-color atlas."""
from collections import defaultdict
from pathlib import Path
from PIL import Image
import bpy,io,json,math,os,shutil,sys
import numpy as np
from mathutils import Matrix, Quaternion, Vector
P=Path(os.environ["CK_ROOT"])
R=Path(os.environ["CK_RUN"])
sys.path.insert(0,str(P/"authoring"))
COOKED_TO_BLENDER=Matrix(((-1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))
BONE_AXES=Matrix(((0,1,0,0),(1,0,0,0),(0,0,1,0),(0,0,0,1)))

def rest_matrix(record):
    bind=record["global_reference_transform"]
    x,y,z,w=bind["quaternion_xyzw"]
    return COOKED_TO_BLENDER@Matrix.LocRotScale(Vector(bind["translation_xyz"]),Quaternion((w,x,y,z)),Vector(bind["scale_xyz"]))@BONE_AXES

def export_native(rig,levels,folder,asset,rig_path):
    rig.data.pose_position="REST"
    roots=[b.head_local.copy() for b in rig.data.bones if b.parent is None]
    assert len(roots)==1
    anchor=roots[0]
    rig.data.transform(Matrix.Translation(anchor)@Matrix.Scale(100,4)@Matrix.Translation(-anchor))
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for ob in levels:
        for uv in ob.data.uv_layers.active.data:uv.uv.y=1-uv.uv.y
        ob.select_set(True)
    bpy.context.view_layer.objects.active=rig
    result=bpy.ops.export_scene.fbx(filepath=str(folder/(asset+".fbx")),use_selection=True,use_triangles=True,
        object_types={"MESH","ARMATURE"},add_leaf_bones=False,bake_anim=False,axis_forward="-Z",axis_up="Y",
        use_mesh_modifiers=False,apply_unit_scale=True,use_space_transform=True,apply_scale_options="FBX_SCALE_UNITS",
        bake_space_transform=False,use_armature_deform_only=False,primary_bone_axis="Y",secondary_bone_axis="X",
        armature_nodetype="NULL",global_scale=1)
    assert result=={"FINISHED"},result
    shutil.copyfile(rig_path,folder/(asset+".rig"))


SOURCE=P/"authoring/review/approval"
DEST=R/"reviewed-unit-fbx"
SIZE=1024
PAD=4
HORSE_COATS = {
    "archer_mounted": (1.20, 0.90, 0.72),      # Warm chestnut
    "crossbow_mounted": (0.58, 0.62, 0.68),  # Dark charcoal
}

def source_maps(m):
    nodes=[n for n in m.node_tree.nodes if n.type=="TEX_IMAGE" and n.image]
    base=next(n.image for n in nodes if n.image.colorspace_settings.name=="sRGB")
    mask=next((n.image for n in nodes if "mask" in n.label.lower() or "pattern" in n.image.name.lower()),None)
    return base,mask

def sampled(image,bounds,cell,fill):
    if image is None:return np.broadcast_to(np.array(fill,dtype=np.uint8),(cell,cell,4)).copy()
    assert image.packed_file,image.name
    with Image.open(io.BytesIO(image.packed_file.data)) as raw:
        pixels=np.asarray(raw.convert("RGBA"))
    u0,v0,u1,v1=bounds
    h,w=pixels.shape[:2]
    x=(((u0+(u1-u0)*(np.arange(cell)+.5)/cell)%1)*w).astype(int)
    y=(((1-v1+(v1-v0)*(np.arange(cell)+.5)/cell)%1)*h).astype(int)
    return pixels[y[:,None],x[None,:],:].copy()

def pack_maps(objects,folder,asset,meat):
    by_pair=defaultdict(list)
    coat = next((rgb for family,rgb in HORSE_COATS.items() if asset.startswith(family+"_")), None)
    for o in objects:
        m=o.data
        for face in m.polygons:
            uv=m.uv_layers.active.data
            material = m.materials[face.material_index]
            dye = coat if "/ horse /" in material.name else None
            by_pair[(*source_maps(material), dye)].extend((uv[i],tuple(uv[i].uv)) for i in face.loop_indices)
    side=math.ceil(math.sqrt(len(by_pair)))
    tile=SIZE//side
    span=tile-2*PAD
    clear={"albedo":(51,38,29,255),"pattern":(0,0,0,0)}
    atlas={k:Image.new("RGBA",(SIZE,SIZE),v) for k,v in clear.items()}
    for i,((base,mask,dye),loops) in enumerate(by_pair.items()):
        x=i%side*tile+PAD
        y=i//side*tile+PAD
        values=np.array([v for _,v in loops])
        u0,v0=np.min(values,axis=0)
        u1,v1=np.maximum(np.max(values,axis=0),(u0+.001,v0+.001))
        bounds=u0,v0,u1,v1
        images=(base,mask)
        for j,role in enumerate(clear):
            img=sampled(images[j] if not(meat and role=="pattern") else None,bounds,span,clear[role])
            if role=="albedo" and dye is not None:
                owner_mask=sampled(mask,bounds,span,clear["pattern"])[:,:,0:1]/255.0
                rgb=img[:,:,:3].astype(float)
                luminance=rgb @ np.array([0.2126,0.7152,0.0722])
                recolored=luminance[:,:,None]*np.array(dye)
                img[:,:,:3]=np.clip(rgb*owner_mask+recolored*(1-owner_mask),0,255).astype(np.uint8)
            if role=="pattern" and images[j] and not meat:
                img[:,:,3]=0
            atlas[role].paste(Image.fromarray(np.pad(img,((PAD,PAD),(PAD,PAD),(0,0)),mode="edge"),"RGBA"),(x-PAD,y-PAD))
        for loop,(u,v) in loops:
            loop.uv=((x+span*(u-u0)/(u1-u0))/SIZE, (SIZE-y-span+span*(v-v0)/(v1-v0))/SIZE)
    for role,im in atlas.items():im.save(folder/f"{asset}_{role}.png")
    for role,fill in (("normal",(128,128,255,255)),("roughness",(183,183,183,255)),("metalness",(0,0,0,255))):
        Image.new("RGBA",(16,16),fill).save(folder/f"{asset}_{role}.png")
    channel=atlas["pattern"].getchannel("R")
    return sum(channel.histogram()[128:])/(SIZE*SIZE)

def clean_skin(o, rig):
    original=o.data
    original.calc_loop_triangles()
    faces=[f for f in original.loop_triangles if f.area>1e-10]
    used=sorted({v for f in faces for v in f.vertices})
    remap={old:new for new,old in enumerate(used)}
    source_uv=original.uv_layers.active.data
    clean=bpy.data.meshes.new(o.name)
    clean.from_pydata([original.vertices[i].co for i in used],[],[[remap[j] for j in f.vertices] for f in faces])
    clean.update()
    clean.materials.append(original.materials[0])
    uv=clean.uv_layers.new(name="UVMap").data
    weights=[]
    groups={g.index:g.name for g in o.vertex_groups}
    for i in used:
        influences=sorted(((g.weight,groups[g.group]) for g in original.vertices[i].groups if g.weight>1e-5),reverse=True)[:4]
        assert influences and all(name in rig.data.bones for _,name in influences),o.name
        total=sum(v for v,_ in influences)
        weights.append([(name,v/total) for v,name in influences])
    for a,b in zip(faces,clean.polygons,strict=True):
        b.use_smooth=True
        xy=[source_uv[i].uv.copy() for i in a.loops]
        if abs((xy[1]-xy[0]).cross(xy[2]-xy[0]))<1e-10:
            xy[1].x+=.00004
            xy[2].y+=.00004
        for j,coord in zip(b.loop_indices,xy,strict=True):uv[j].uv=coord
    o.data=clean
    o.vertex_groups.clear()
    group={n:o.vertex_groups.new(name=n) for n in sorted({n for row in weights for n,v in row})}
    for i,row in enumerate(weights):
        for n,v in row:group[n].add([i],v,"REPLACE")

def remap_skin(mesh, source_rig, target_rig):
    target_names = set(target_rig.data.bones.keys())
    group_names = {}
    for group in mesh.vertex_groups:
        bone = source_rig.data.bones[group.name]
        while bone is not None and bone.name not in target_names:
            bone = bone.parent
        group_names[group.index] = bone.name if bone is not None else "gaia_c_pelvis"
    weights = []
    for vertex in mesh.data.vertices:
        row = defaultdict(float)
        for influence in vertex.groups:
            row[group_names[influence.group]] += influence.weight
        weights.append(row)
    mesh.vertex_groups.clear()
    groups = {name: mesh.vertex_groups.new(name=name) for name in sorted(set(group_names.values()))}
    for index, row in enumerate(weights):
        for name, weight in row.items():
            groups[name].add([index], weight, "REPLACE")


def export(asset,mesh_objs,rig,bind,meat=False):
    gaia_horse = asset == "horse_1" and os.environ.get("CK_HORSE_GAIA") == "1"
    records = json.loads((bind / ("gaia-native-bind.json" if gaia_horse else "native-bind.json")).read_bytes())
    source_rig = rig
    folder=DEST/asset
    if (folder/"bindings.json").is_file():return
    folder.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    col=bpy.data.collections.new("Native export "+asset)
    scene.collection.children.link(col)
    if meat or gaia_horse:
        arm=bpy.data.armatures.new(asset+"_rig")
        rig=bpy.data.objects.new(asset+"_rig",arm)
        col.objects.link(rig)
        bpy.context.view_layer.objects.active=rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        for rec in records:
            b=arm.edit_bones.new(rec["name"])
            if rec["parent_name"]:b.parent=arm.edit_bones[rec["parent_name"]]
            b.matrix=rest_matrix(rec)
            b.length=.15
        bpy.ops.object.mode_set(mode="OBJECT")
    else:
        arm=rig.data
        rig=bpy.data.objects.new(asset+"_rig",arm.copy())
        col.objects.link(rig)
        assert set(rig.data.bones.keys())=={r["name"] for r in records},asset
        for rec in records:
            expected=rest_matrix(rec)
            current=rig.data.bones[rec["name"]].matrix_local
            assert (expected.translation-current.translation).length<.00009 and rig.data.bones[rec["name"]].parent == (rig.data.bones.get(rec["parent_name"]) if rec["parent_name"] else None),(asset,rec["name"],list(expected.translation),list(current.translation))
        # The reviewed masters retained native head positions but their edit
        # bone orientations were reset. Position-only validation missed it.
        # Restore the complete native basis on the temporary export copy.
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        bpy.context.view_layer.objects.active=rig
        bpy.ops.object.mode_set(mode="EDIT")
        for rec in records:
            rig.data.edit_bones[rec["name"]].matrix=rest_matrix(rec)
        bpy.ops.object.mode_set(mode="OBJECT")
    objects=[]
    for src in mesh_objs:
        o=src.copy()
        o.data=src.data.copy()
        col.objects.link(o)
        o.parent=rig
        o.matrix_parent_inverse=Matrix.Identity(4)
        o.matrix_basis=Matrix.Identity(4)
        o.hide_render=False;o.hide_viewport=False;o.hide_set(False)
        o.name=f"{asset}_part{len(objects):02}_lod{src['native_lod']}"
        for mod in list(o.modifiers):
            if mod.type=="ARMATURE":o.modifiers.remove(mod)
        mod=o.modifiers.new("Native skeletal bind","ARMATURE")
        mod.object=rig
        if gaia_horse:
            remap_skin(o, source_rig, rig)
        if meat:
            o.vertex_groups.clear()
            root=next(r["name"] for r in records if not r["parent_name"])
            o.vertex_groups.new(name=root).add(list(range(len(o.data.vertices))),1,"REPLACE")
        objects.append(o)
    fraction=pack_maps(objects,folder,asset,meat)
    if not meat:assert .008<fraction<.85,(asset,fraction)
    mat=bpy.data.materials.get("main") or bpy.data.materials.new("main")
    for o in objects:
        o.data.materials.clear()
        o.data.materials.append(mat)
        for poly in o.data.polygons:poly.material_index=0
    levels=[]
    for lod,group in enumerate([[o for o in objects if o["native_lod"]==n] for n in (1,2,3)],1):
        assert group,(asset,lod)
        bpy.ops.object.select_all(action="DESELECT")
        for o in group:o.select_set(True)
        bpy.context.view_layer.objects.active=group[0]
        if len(group)>1:bpy.ops.object.join()
        lod_obj=bpy.context.view_layer.objects.active
        lod_obj.name=asset+f"_body_lod{lod}"
        clean_skin(lod_obj,rig)
        levels.append(lod_obj)
    export_native(rig, levels, folder, asset, bind / ("gaia-horse.rig" if gaia_horse else asset + ".rig"))
    (folder/"bindings.json").write_text(json.dumps({"bones":len(records),"lods":[len(o.data.polygons) for o in levels],
                                                 "packed_owner_mask":round(fraction,5)},indent=2),encoding="utf-8")
    print("EXPORTED",asset,flush=True)
    for o in list(col.objects):bpy.data.objects.remove(o,do_unlink=True)
    bpy.data.collections.remove(col)

catalog=json.loads((P/"source/visuals/units.json").read_bytes())
expected={a for row in catalog for a in row["models"].values()}
paths=sorted((SOURCE/"unit-batch-01").glob("*.blend"))+sorted((SOURCE/"unit-batch-02").glob("*.blend"))+sorted((SOURCE/"unit-batch-03").glob("*.blend"))
paths=[p for p in paths if p.name not in ("03-mounted-crossbowman.blend","08-mounted-sufi.blend","10-horse-carcass.blend")]
seen=set()
for path in paths:
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    for col in tuple(bpy.context.scene.collection.children):
        if path.name=="03-horse-meat.blend":
            if not col.name.startswith("Gatherable horse"):continue
            asset="corpse_1"
            rig=None
        else:
            if not col.name.endswith("Chagatai edit"):continue
            [rig]=[o for o in col.objects if o.type=="ARMATURE"]
            asset=next(o for o in col.objects if o.type=="MESH" and "native_lod" in o).name.split(" / ")[0]
        assert asset in expected and asset not in seen,(asset,col.name)
        seen.add(asset)
        bind=P/"authoring/units"/asset
        if os.environ.get("CK_UNIT_SAMPLE") and asset not in os.environ["CK_UNIT_SAMPLE"].split(","):continue
        export(asset,[o for o in col.objects if o.type=="MESH" and "native_lod" in o],rig,bind,asset=="corpse_1")
asset="horse_1"
if not os.environ.get("CK_UNIT_SAMPLE") or asset in os.environ["CK_UNIT_SAMPLE"].split(","):
    master=SOURCE/"loose-horse/Chagatai-Loose-Horse-Pilot.blend"
    bpy.ops.wm.open_mainfile(filepath=str(master),load_ui=False,use_scripts=False)
    collection=bpy.data.collections["02 Chagatai Loose Horse pilot"]
    [rig]=[obj for obj in collection.objects if obj.type=="ARMATURE"]
    meshes=[obj for obj in collection.objects if obj.type=="MESH" and "native_lod" in obj]
    export(asset,meshes,rig,P/"authoring/reviewed-units/loose-horse")
seen.add(asset)
assert seen==expected,expected-seen



