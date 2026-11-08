import bpy,os,sys,json,hashlib,math
from pathlib import Path
from collections import defaultdict
R=Path(os.environ["CK_RUN"])
asset=sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=str(R/f"{asset}-lifecycle.blend"),load_ui=False)
art=R/f"{asset}-textures"
art.mkdir(exist_ok=True)
materials=defaultdict(list)
for c in bpy.context.scene.collection.children:
    if not c.name.startswith(asset+"_"):continue
    for o in c.objects:
        uv=o.data.uv_layers.active.data
        for face in o.data.polygons:
            materials[o.data.materials[face.material_index]].extend(tuple(uv[i].uv) for i in face.loop_indices)
def dump(image):
    assert image.packed_file is not None,image.name
    data=image.packed_file.data
    p=art/(hashlib.sha256(data).hexdigest()[:20]+".png")
    if not p.is_file():p.write_bytes(data)
    return str(p)
res={}
for m,points in materials.items():
    ns=m.node_tree.nodes
    tx=[n for n in ns if n.type=="TEX_IMAGE"]
    base=next((n for n in tx if not any(k in (n.label+n.image.name).lower() for k in ("mask","pattern","normal"))),None)
    mask=next((n for n in tx if any(k in (n.label+n.image.name).lower() for k in ("mask","pattern"))),None)
    if "charred" in m.name or "scorched" in m.name:mask=None
    bs=ns.get("Principled BSDF")
    uv_max=[max(pt[i] for pt in points) for i in (0,1)]
    uv_min=[min(pt[i] for pt in points) for i in (0,1)]
    assert all(a>=-.0001 for a in uv_min) and uv_max[0]<=1.26 and uv_max[1]<=1.0001,(m.name,uv_min,uv_max)
    res[m.name]=dict(base=dump(base.image) if base else None,mask=dump(mask.image) if mask else None,
                    color=list(bs.inputs["Base Color"].default_value),alpha=bs.inputs["Alpha"].is_linked,
                    u_span=1.25 if uv_max[0]>1.0001 else 1,
                    soot=.41 if "charred" in m.name else .66 if "scorched" in m.name else 1,
                    roughness=round(bs.inputs["Roughness"].default_value*255))
(R/f"{asset}-materials.json").write_text(json.dumps(res,indent=2))
