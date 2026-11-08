"""Bake a landmark's packed Blender textures and export one native cook project."""
from pathlib import Path
import io,json,math,os,re,shutil,sys,xml.etree.ElementTree as ET
from collections import defaultdict
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent if Path(__file__).resolve().parent.name == "authoring" else Path(__file__).resolve().parents[1]))
from static_skin import export_static_skin, add_rgb_mask_rule
from PIL import Image,ImageFilter
import numpy as np

R=Path(os.environ["CK_RUN"])
P=Path(os.environ["CK_ROOT"])
key=sys.argv[-1]
title={"almaliq":"Almaliq-Market","ordu":"Ordu-of-Almaliq","qarshi":"Qarshi-Palace","court":"Khans-Court","ili":"Ili-Royal-Pastures","mint":"Kebeks-Royal-Mint"}[key]
master=Path(os.environ.get("CK_MASTER",R/f"Chagatai-{title}.blend"))
dst=R/(os.environ.get("CK_STAGE_PREFIX","stage-")+key)
bpy.ops.wm.open_mainfile(filepath=str(master),load_ui=False)
scene=bpy.context.scene
states=tuple(scene["lifecycle_states"].split(", "))
groups={s:bpy.data.collections[f"{key}_{s}"] for s in states}
by_mat=defaultdict(list)
for c in groups.values():
    for obj in c.objects:
        m=obj.data
        uvs=m.uv_layers.active.data
        for p in m.polygons:
            by_mat[m.materials[p.material_index]].extend(tuple(uvs[i].uv) for i in p.loop_indices)

SIZE=2048
GRID=math.ceil(math.sqrt(len(by_mat)))
assert GRID<=8,(key,GRID)
CELL=SIZE//GRID
PAD=6
atlas={name:Image.new("RGBA",(SIZE,SIZE),c) for name,c in {
    "albedo":(60,40,26,255),"pattern":(0,0,0,0),"normal":(128,128,255,255),
    "roughness":(215,215,215,255),"metalness":(0,0,0,255)}.items()}

def image_from_node(node):
    src=node.image
    raw=src.packed_file.data
    return Image.open(io.BytesIO(raw)).convert("RGBA")

def wrapped(image,bounds,span):
    # Bilinear samples from the original UV interval with repeat wrapping.
    u0,v0,u1,v1=bounds
    px=np.asarray(image)
    h,w=px.shape[:2]
    pad=np.pad(px,((1,1),(1,1),(0,0)),mode="wrap")
    u=(u0+(u1-u0)*(np.arange(span)+.5)/span)%1*w+.5
    v=(1-v1+(v1-v0)*(np.arange(span)+.5)/span)%1*h+.5
    ix,iy=u.astype(int),v.astype(int)
    dx=(u-ix)[None,:,None]
    dy=(v-iy)[:,None,None]
    a=pad[iy[:,None],ix[None,:]]*(1-dx)+pad[iy[:,None],ix[None,:]+1]*dx
    b=pad[iy[:,None]+1,ix[None,:]]*(1-dx)+pad[iy[:,None]+1,ix[None,:]+1]*dx
    return Image.fromarray(np.uint8(np.clip(a*(1-dy)+b*dy,0,255)),"RGBA")

def paste(name,img,x,y):
    target=atlas[name]
    im=np.asarray(img)
    border=np.pad(im,((PAD,PAD),(PAD,PAD),(0,0)),mode="edge")
    target.paste(Image.fromarray(border,"RGBA"),(x-PAD,y-PAD))

layout={}
for i,(m,uvs) in enumerate(sorted(by_mat.items(),key=lambda entry:entry[0].name)):
    x=i%GRID*CELL+PAD
    y=i//GRID*CELL+PAD
    span=CELL-PAD*2
    u0,v0=np.min(uvs,axis=0)
    u1,v1=np.max(uvs,axis=0)
    if u1-u0<1e-6:u1=u0+.001
    if v1-v0<1e-6:v1=v0+.001
    bounds=float(u0),float(v0),float(u1),float(v1)
    layout[m.name]=[x,y,span,bounds]
    nodes=m.node_tree.nodes
    tex=[n for n in nodes if n.type=="TEX_IMAGE" and n.image is not None]
    base=next((n for n in tex if n.label=="Albedo source"),None)
    if base is None:base=next((n for n in tex if "albedo" in (n.name+n.label+n.image.name).lower()),None)
    bs=nodes.get("Principled BSDF")
    if base:
        col=wrapped(image_from_node(base),bounds,span)
        if not bs.inputs["Alpha"].is_linked:col.putalpha(255)
    else:
        def srgb(a):return max(0,min(255,round(255*(12.92*a if a<=.0031308 else 1.055*a**(1/2.4)-.055))))
        rgba=tuple(srgb(a) for a in bs.inputs["Base Color"].default_value[:3])+(255,)
        col=Image.new("RGBA",(span,span),rgba)
    paste("albedo",col,x,y)
    owner=next((n for n in tex if n.label=="Owner mask"),None)
    if owner:
        red=wrapped(image_from_node(owner),bounds,span).getchannel("R")
        zero=Image.new("L",(span,span),0)
        paste("pattern",Image.merge("RGBA",(red,zero,zero,zero)),x,y)
    height=np.asarray(col.convert("L").filter(ImageFilter.GaussianBlur(.75)),dtype=np.float32)
    dy,dx=np.gradient(height)
    normal=np.stack((128-dx*.36,128+dy*.36,np.full_like(height,255),np.full_like(height,255)),axis=-1)
    paste("normal",Image.fromarray(np.uint8(np.clip(normal,0,255)),"RGBA"),x,y)
    rough=round(255*bs.inputs["Roughness"].default_value)
    paste("roughness",Image.new("RGBA",(span,span),(rough,rough,rough,255)),x,y)
hist=atlas["pattern"].getchannel("R").histogram()
assert sum(hist[128:])>0
print(key,len(by_mat),"atlas slots; texture coverage",sum(hist[128:])/(SIZE*SIZE),flush=True)
base_project=P/"authoring/cook-template"
shutil.copytree(base_project,dst,ignore=shutil.ignore_patterns("art","evidence","cache","archives"))
src=dst/"source"
art=src/"art/scenario/chagatai"
healthy=art/f"{key}_healthy"
healthy.mkdir(parents=True)
for role,img in atlas.items():
    img.save(healthy/f"{key}_healthy_{role}.png")
template=base_project/"source/art/scenario/chagatai/ordu_healthy"
pack=bpy.data.collections.new("Cook-only meshes")
scene.collection.children.link(pack)
mat=bpy.data.materials.new("main")
stats={}
for state,col in groups.items():
    col.hide_viewport=True
    name=f"{key}_{state}"
    path=art/name
    path.mkdir(exist_ok=True)
    verts,faces,coords,soft=[],[],[],[]
    for o in col.objects:
        d=o.data
        start=len(verts)
        verts.extend(o.matrix_world@v.co for v in d.vertices)
        d.calc_loop_triangles()
        for tri in d.loop_triangles:
            if tri.area<=1e-9:continue
            x,y,n,(u0,v0,u1,v1)=layout[d.materials[tri.material_index].name]
            faces.append(tuple(start+v for v in tri.vertices))
            soft.append(d.polygons[tri.polygon_index].use_smooth)
            for l in tri.loops:
                u,v=d.uv_layers.active.data[l].uv
                coords.append(((x+n*(u-u0)/(u1-u0))/SIZE,(SIZE-y-n+n*(v-v0)/(v1-v0))/SIZE))
    d=bpy.data.meshes.new(name+"_lod1")
    d.from_pydata(verts,[],faces);d.update();d.materials.append(mat)
    uv=d.uv_layers.new(name="UVMap")
    for l,uvv in zip(uv.data,coords,strict=True):l.uv=uvv
    for p,s in zip(d.polygons,soft,strict=True):p.use_smooth=s
    ob=bpy.data.objects.new(name+"_lod1",d);pack.objects.link(ob)
    cap=5900
    if len(d.polygons)>cap:
        bpy.context.view_layer.objects.active=ob
        decimate=ob.modifiers.new("Cooked LOD1 vertex budget","DECIMATE")
        decimate.ratio=cap/len(d.polygons)
        decimate.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier=decimate.name)
        d=ob.data
    levels=[ob]
    for lod,ratio in ((2,.56),(3,.29)):
        low=ob.copy()
        low.data=d.copy()
        low.name=f"{name}_lod{lod}"
        pack.objects.link(low)
        bpy.context.view_layer.objects.active=low
        mod=low.modifiers.new("Retain silhouette and reduce faces","DECIMATE")
        mod.ratio=ratio;mod.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        levels.append(low)
    bpy.ops.object.select_all(action="DESELECT")
    for o in levels:
        o.select_set(True)
        for l in o.data.uv_layers.active.data:l.uv.y=1-l.uv.y
    bpy.context.view_layer.objects.active=ob
    export_static_skin(levels, path/(name+".fbx"))
    for ext in (".rgo",".rgotemplate"):
        shutil.copyfile(template/("ordu_healthy"+ext),path/(name+ext))
    doc=ET.Element("materialSet")
    params=ET.SubElement(doc,"material",name="main",type="shader",source="unit")
    for role,param in (("albedo","albedoTexture"),("normal","normalMap"),("metalness","metalTex"),("roughness","roughnessTex"),("pattern","patternTex")):
        ET.SubElement(params,"param",name=param,type="tex2D",value=str(healthy.relative_to(src)/(f"{key}_healthy_{role}.png")))
    ET.ElementTree(doc).write(path/(name+".material"),encoding="utf-8",xml_declaration=True)
    stats[state]=[len(o.data.polygons) for o in levels]
    assert all(count>0 for count in stats[state]) and stats[state][0]<=8600,stats[state]
    for o in levels:bpy.data.objects.remove(o,do_unlink=True)
burn=src/"_default.burnproj"
text=burn.read_text(encoding="utf-8-sig")
needle="art\\scenario\\chagatai\\ordu_healthy\\"
def scopes(match):
    payload=match[1]
    if needle not in payload:return match[0]
    names=[payload.replace(needle,f"art\\scenario\\chagatai\\{key}_{s}\\") for s in states]
    return "<Includes>"+";".join(names)+"</Includes>"
new=re.sub(r"<Includes>([^<]*)</Includes>",scopes,text)
assert new!=text
burn.write_text(add_rgb_mask_rule(new),encoding="utf-8")
(R/f"{key}-native-stage.json").write_text(json.dumps({"lod_triangles":stats,"atlas_materials":len(layout),"texture_mask_pixels":sum(hist[128:])},indent=2))




