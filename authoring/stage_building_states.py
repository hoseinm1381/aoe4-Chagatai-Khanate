"""Stage independently cookable, named Blender state meshes for native assembly."""
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent if Path(__file__).resolve().parent.name == "authoring" else Path(__file__).resolve().parents[1]))
from static_skin import export_static_skin, add_rgb_mask_rule

sys.path.insert(0,str(Path(__file__).parent))
STAGES = ("healthy", "frame00", "frame25", "frame50", "frame75", "wear", "breach", "collapse", "ruins")

args=sys.argv[sys.argv.index("--")+1:]
blend, base_project, destination, atlas = map(Path,args[:4])
assets=args[4:]
if not assets:
    from buildings import BUILDINGS
    assets = list(BUILDINGS)
template=base_project/"source/art/scenario/chagatai/ordu_healthy"
prefix="art\\scenario\\chagatai\\"
needle=prefix+"ordu_healthy\\"

def stage():
    shutil.copytree(base_project,destination,ignore=shutil.ignore_patterns("art","evidence","cache","archives"))
    src=destination/"source"
    burn=src/"_default.burnproj"
    original=burn.read_text(encoding="utf-8-sig")
    scopes=[]
    bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False)
    bpy.ops.object.select_all(action="DESELECT")
    for asset in assets:
        for state in STAGES:
            stem=asset+"_"+state
            output=src/"art/scenario/chagatai"/stem
            output.mkdir(parents=True)
            scopes.append(stem)
            meshes=[bpy.data.objects[f"{stem}_lod{i}"] for i in (1,2,3)]
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
            export_static_skin(meshes, output/(stem+".fbx"))
            for obj in meshes:obj.select_set(False)
            for ext in (".rgo",".rgotemplate"):
                shutil.copyfile(template/("ordu_healthy"+ext),output/(stem+ext))
            material=ET.Element("materialSet")
            main=ET.SubElement(material,"material",name="main",type="shader",source="unit")
            for role,param in (("albedo","albedoTexture"),("normal","normalMap"),("metalness","metalTex"),
                               ("roughness","roughnessTex"),("pattern","patternTex")):
                image=stem+"_"+role+".png"
                shutil.copyfile(atlas/(role+".png"),output/image)
                ET.SubElement(main,"param",name=param,type="tex2D",value=str(output.relative_to(src)/image))
            ET.ElementTree(material).write(output/(stem+".material"),encoding="utf-8",xml_declaration=True)
        print(asset,"exported",len(STAGES),"state geometries",flush=True)
    def expand(match):
        value=match[1]
        if needle not in value:return match[0]
        return "<Includes>"+";".join(value.replace(needle,prefix+scope+"\\") for scope in scopes)+"</Includes>"
    revised=re.sub(r"<Includes>([^<]*)</Includes>",expand,original)
    assert revised!=original and all(prefix+scope+"\\" in revised for scope in scopes)
    burn.write_text(add_rgb_mask_rule(revised),encoding="utf-8")

if __name__=="__main__":
    stage()
