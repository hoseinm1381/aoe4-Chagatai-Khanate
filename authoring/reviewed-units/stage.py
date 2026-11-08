"""Stage rigged masters in a short-path copy of the qualified native model project."""
from argparse import ArgumentParser
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

PREFIX="art\\scenario\\chagatai\\"
EXAMPLE=PREFIX+"ordu_healthy\\"

def stage(source, template, destination):
    shutil.copytree(template,destination,ignore=shutil.ignore_patterns("art","evidence","cache","archives"))
    inputs=destination/"source"
    carrier=template/"source/art/scenario/chagatai/ordu_healthy"
    folders=[]
    for path in sorted(source.glob("*/bindings.json")):
        directory=path.parent
        asset=directory.name
        output=inputs/"art/scenario/chagatai"/asset
        output.mkdir(parents=True)
        folders.append(asset)
        for ext in (".fbx",".rig"):
            shutil.copyfile(directory/(asset+ext),output/(asset+ext))
        for ext in (".rgo",".rgotemplate"):
            shutil.copyfile(carrier/("ordu_healthy"+ext),output/(asset+ext))
        material=ET.Element("materialSet")
        node=ET.SubElement(material,"material",name="main",type="shader",source="unit")
        for role,param in (("albedo","albedoTexture"),("normal","normalMap"),("metalness","metalTex"),
                           ("roughness","roughnessTex"),("pattern","patternTex")):
            image=asset+"_"+role+".png"
            shutil.copyfile(directory/(asset+"_"+role+".png"),output/image)
            ET.SubElement(node,"param",name=param,type="tex2D",value=str(output.relative_to(inputs)/image))
        ET.ElementTree(material).write(output/(asset+".material"),encoding="utf-8",xml_declaration=True)
    if not folders:raise ValueError("No completed rigged masters")
    burn=inputs/"_default.burnproj"
    before=burn.read_text(encoding="utf-8-sig")
    def expand(match):
        value=match[1]
        if EXAMPLE not in value:return match[0]
        return "<Includes>"+";".join(value.replace(EXAMPLE,PREFIX+asset+"\\") for asset in folders)+"</Includes>"
    updated=re.sub(r"<Includes>([^<]*)</Includes>",expand,before)
    if updated==before:raise ValueError("Missing qualified burn rules")
    burn.write_text(updated,encoding="utf-8")
    print(f"Staged {len(folders)} rigged models")

if __name__=="__main__":
    parser=ArgumentParser(description=__doc__)
    for name in ("source","template","destination"):parser.add_argument(name,type=Path)
    args=parser.parse_args()
    stage(args.source,args.template,args.destination)


