import bpy,os,sys,json
from pathlib import Path
R=Path(os.environ["CK_RUN"])
asset=sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=str(R/f"{asset}-lifecycle.blend"),load_ui=False)
root=bpy.context.scene.collection
atlas=R/f"{asset}-atlas"
layout=json.loads((atlas/"uv.json").read_bytes())
native=bpy.data.materials.new("main")
native.use_nodes=True
bs=native.node_tree.nodes.get("Principled BSDF")
N,L=native.node_tree.nodes,native.node_tree.links
albedo=N.new("ShaderNodeTexImage")
albedo.image=bpy.data.images.load(str(atlas/"albedo.png"));albedo.image.pack()
L.new(albedo.outputs["Color"],bs.inputs["Base Color"])
L.new(albedo.outputs["Alpha"],bs.inputs["Alpha"])
pattern=N.new("ShaderNodeTexImage");pattern.label="Native owner-color mask"
pattern.image=bpy.data.images.load(str(atlas/"pattern.png"));pattern.image.colorspace_settings.name="Non-Color";pattern.image.pack()
stage=bpy.data.collections.new("Native staging")
root.children.link(stage)
states=("healthy","frame00","frame25","frame50","frame75","wear","breach","collapse","ruins")
result={}
for state in states:
    name=asset+"_"+state
    src=bpy.data.collections[name]
    verts,faces,coords,smooth=[],[],[],[]
    for o in src.objects:
        data=o.data
        active=data.uv_layers.active
        offset=len(verts)
        verts.extend(o.matrix_world@v.co for v in data.vertices)
        for p in data.polygons:
            x,y,w,h,span,size=layout[data.materials[p.material_index].name]
            faces.append(tuple(offset+i for i in p.vertices))
            smooth.append(p.use_smooth)
            for i in p.loop_indices:
                u,v=active.data[i].uv
                coords.append(((x+u*w/span)/size,(size-y-h+v*h)/size))
    assert all(0<=u<=1 and 0<=v<=1 for u,v in coords)
    mesh=bpy.data.meshes.new(name+"_lod1")
    mesh.from_pydata(verts,[],faces);mesh.update()
    uv=mesh.uv_layers.new(name="UVMap")
    for l,p in zip(uv.data,coords,strict=True):l.uv=p
    mesh.materials.append(native)
    for p,f in zip(mesh.polygons,smooth,strict=True):p.use_smooth=f
    obj=bpy.data.objects.new(name+"_lod1",mesh);stage.objects.link(obj)
    result[state]=[len(mesh.polygons)]
    for lod,ratio in ((2,.64),(3,.36)):
        low=obj.copy();low.data=obj.data.copy()
        low.name=f"{name}_lod{lod}"
        stage.objects.link(low)
        m=low.modifiers.new("LOD reduction","DECIMATE")
        m.ratio=ratio
        m.use_collapse_triangulate=True
        bpy.context.view_layer.objects.active=low
        bpy.ops.object.modifier_apply(modifier=m.name)
        result[state].append(len(low.data.polygons))
    # Every model shares the same atlas. All non-stage objects remain unselected.
    src.hide_viewport=True
    src.hide_render=True
bpy.ops.object.select_all(action="DESELECT")
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(R/f"{asset}-native-stage.blend"))
(R/f"{asset}-lods.json").write_text(json.dumps(result,indent=2)+"\n")

