from pathlib import Path
import bpy,os,re,sys
P=Path(os.environ["CK_ROOT"])
R=Path(os.environ["CK_RUN"])
key=sys.argv[-1]
kind=key.capitalize()
master=P/f"authoring/review/approval/{key}-encampment/Chagatai-{kind}-Encampment.blend"
bpy.ops.wm.open_mainfile(filepath=str(master),load_ui=False)
scene=bpy.context.scene
states=[]
keys=("m1","m2","m3","m4") if key=="melee" else ("r2","r3","r4")
for age in keys:
    src=bpy.data.collections[age+"_healthy"]
    healthy="healthy" if age==keys[0] else age+"_healthy"
    src.name=key+"_"+healthy
    states.append(healthy)
    for tag,h in zip(("frame00","frame25","frame50","frame75"),(.40,1.13,1.88,20),strict=True):
        state=age+"_"+tag
        states.append(state)
        c=bpy.data.collections.new(key+"_"+state)
        scene.collection.children.link(c)
        for o in src.objects:
            m=o.data
            m.update()
            faces=[f for f in m.polygons if max(m.vertices[i].co.z for i in f.vertices)<=h]
            if not faces:continue
            ids=sorted({i for f in faces for i in f.vertices})
            lut={i:n for n,i in enumerate(ids)}
            out=bpy.data.meshes.new(o.name)
            out.from_pydata([m.vertices[i].co for i in ids],[],[tuple(lut[i] for i in f.vertices) for f in faces])
            out.update()
            for mat in m.materials:out.materials.append(mat)
            uv=out.uv_layers.new(name="UVMap")
            for a,b in zip(faces,out.polygons,strict=True):
                b.material_index=a.material_index
                b.use_smooth=a.use_smooth
                for i,j in zip(a.loop_indices,b.loop_indices,strict=True):uv.data[j].uv=m.uv_layers.active.data[i].uv
            obj=bpy.data.objects.new(o.name,out)
            c.objects.link(obj)
        assert c.objects,state
    bpy.data.collections[age+"_ruins"].name=key+"_"+age+"_ruins"
    states.append(age+"_ruins")
scene["lifecycle_states"]=", ".join(states)
path=R/f"{key}-states.blend"
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(path))
os.environ["CK_MASTER"]=str(path)
recipe=(P/"authoring/reviewed-landmarks/stage_landmark.py").read_text(encoding="utf-8-sig")
recipe=re.sub(r"(?m)^title=.*$","title=key",recipe)
recipe=recipe.replace('n.label=="Owner mask"','n.label in ("Owner mask","Dynamic owner mask")')
recipe=recipe.replace('n.label=="Albedo source"','n.label=="Albedo source" or n.image.colorspace_settings.name=="sRGB"')
recipe=recipe.replace("assert GRID<=8","assert GRID<=14")
exec(compile(recipe,"shared-landmark-stage","exec"))


if os.environ.get("CK_KEEP_DEFAULT_CLOTH") != "1":
    # Match the native owner-color base used by the other Chagatai buildings.
    sys.path.insert(0, str(P/"tools"))
    from building_color import neutral_cloth

    albedo = healthy/f"{key}_healthy_albedo.png"
    pattern = healthy/f"{key}_healthy_pattern.png"
    with Image.open(albedo) as image:
        original = np.array(image.convert("RGBA"))
    with Image.open(pattern) as image:
        mask = np.array(image.convert("RGB"))[:, :, 0]
    Image.fromarray(neutral_cloth(original, mask)).save(albedo)
