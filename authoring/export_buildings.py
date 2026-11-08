"""Export lifecycle meshes and owner-color materials to a native cook project."""
from pathlib import Path
import shutil
import struct
import sys
import xml.etree.ElementTree as ET

import bmesh
import bpy

sys.path.insert(0,str(Path(__file__).parent))
from ordu import rc, graft, STATES

blend, target, template, donor, atlas = map(Path,sys.argv[sys.argv.index("--")+1:][:5])
selected = sys.argv[sys.argv.index("--")+6:]

def authored_rgo(asset):
    base=rc.parse((template/"model.rgo").read_bytes())
    defaults=(template/"building-lifecycle-defaults.bin").read_bytes()
    selectors=next(c for c in rc.walk(base.roots) if c.tag==b"MSBP")
    parts=selectors.children
    def pack(chunk,data):
        return rc.pack_chunk(chunk.kind,chunk.tag,data,version=chunk.version,name=chunk.name)
    header=next(c for c in parts if c.tag==b"HDR ")
    msa=next(c for c in parts if c.tag==b"MSA ")
    count=next(c for c in parts if c.tag==b"MSD " and len(c.payload)==4)
    shape=next(c for c in parts if c.tag==b"MSD " and len(c.payload)>4)
    condition=next(c for c in parts if c.tag==b"CNBP")
    content=pack(header,header.payload)+pack(msa,msa.payload)+pack(count,struct.pack("<I",len(STATES)))
    for name,variants in STATES.items():
        payload=rc.lp_string("sel_"+name)+struct.pack("<I",1)+rc.lp_string(asset+"_"+name)
        content+=pack(shape,payload)
        conditions=b"".join(struct.pack("<IBI",2,0,int(i>0))+rc.lp_string("life_cycle_state")+rc.lp_string(state)
                            for i,state in enumerate(variants))
        content+=pack(condition,struct.pack("<I",len(variants))+conditions)
    raw=rc.rebuild(base,lambda chunk:content if chunk.offset==selectors.offset else
                   defaults if chunk.tag==b"DTBP" else None)
    return graft(raw,donor.read_bytes(),rc)

def export():
    bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False)
    bpy.ops.object.select_all(action="DESELECT")
    for asset in selected:
        collection=bpy.data.collections[asset]
        meshes=list(collection.objects)
        output=target/"art"/"scenario"/"chagatai"/asset
        output.mkdir(parents=True,exist_ok=True)
        for obj in meshes:
            obj.hide_set(False)
            obj.select_set(True)
            data=obj.data
            for uv in list(data.uv_layers)[1:]:data.uv_layers.remove(uv)
            bm=bmesh.new()
            bm.from_mesh(data)
            bmesh.ops.triangulate(bm,faces=list(bm.faces))
            bm.to_mesh(data)
            bm.free()
            for loop in data.uv_layers[0].data:loop.uv.y=1-loop.uv.y
        bpy.context.view_layer.objects.active=meshes[0]
        bpy.ops.export_scene.fbx(filepath=str(output/(asset+".fbx")),use_selection=True,
            object_types={"MESH"},use_mesh_modifiers=True,add_leaf_bones=False,bake_anim=False,
            path_mode="AUTO",axis_forward="-Z",axis_up="Y",apply_unit_scale=True,use_space_transform=True)
        for obj in meshes:
            obj.select_set(False)
        (output/(asset+".rgo")).write_bytes(authored_rgo(asset))
        shutil.copyfile(template/"model.rgotemplate",output/(asset+".rgotemplate"))
        material=ET.Element("materialSet")
        main=ET.SubElement(material,"material",name="main",type="shader",source="unit")
        for role,param in (("albedo","albedoTexture"),("normal","normalMap"),("metalness","metalTex"),
                           ("roughness","roughnessTex"),("pattern","patternTex")):
            image=asset+"_"+role+".png"
            shutil.copyfile(atlas/(role+".png"),output/image)
            path=output.relative_to(target)/image
            ET.SubElement(main,"param",name=param,type="tex2D",value=str(path))
        ET.ElementTree(material).write(output/(asset+".material"),encoding="utf-8",xml_declaration=True)
        print(asset,len(meshes),sum(len(o.data.polygons) for o in meshes),flush=True)

if __name__=="__main__":
    export()
