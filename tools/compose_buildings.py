"""Compose state meshes already converted by the native Content Editor."""
from argparse import ArgumentParser
import json
import os
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
EXT=Path(os.environ.get("GARRISON_EXTENSION", Path(os.environ["APPDATA"])/"Blender Foundation/Blender/5.2/extensions/raw_githubusercontent_com/garrison"))
sys.path[:0]=[str(EXT),str(ROOT/"authoring")]
from garrison_shared import relic_chunky as rc, stock_game, model_variants
from lifecycle import graft

STATES={
    "healthy":("healthy","preview","targeting"),
    "frame00":tuple(f"construct_{i:02}" for i in range(0,25,5)),
    "frame25":tuple(f"construct_{i:02}" for i in range(25,50,5)),
    "frame50":tuple(f"construct_{i:02}" for i in range(50,75,5)),
    "frame75":tuple(f"construct_{i:02}" for i in range(75,100,5)),
    "wear":("damage_1","damage_2"),
    "breach":("damage_3",),
    "collapse":("damage_4","damage_5"),
    "ruins":("ruins",),
}
DONOR=("art/civilizations/chinese/structures/wonder_forbidden_palace/"
       "chi_wonder_forbidden_palace_control_age04/chi_wonder_forbidden_palace_control_age04")
ART="art/scenario/chagatai/"

def find(doc,tag):
    matches=[chunk for chunk in rc.walk(doc.roots) if chunk.tag==tag]
    if len(matches)!=1:raise ValueError((tag,len(matches)))
    return matches[0]

def pack(chunk,data=None):
    return rc.pack_chunk(chunk.kind,chunk.tag,chunk.payload if data is None else data,
                         version=chunk.version,name=chunk.name)

def store(root,name,data):
    path=root/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)

def set_mesh_count(document, count, mesh_type):
    info = next(chunk for chunk in find(document, b"MODL").children if chunk.tag == b"INFO")
    if len(info.payload) != 32:
        raise ValueError("Unexpected native model INFO size")
    actual = struct.unpack_from("<II", info.payload, 23)
    initial = (0, 1) if mesh_type == b"SKMS" else (1, 0)
    target = tuple(count * channel for channel in initial)
    if actual not in (initial, target):
        raise ValueError(f"Unexpected native model mesh inventory: {actual}")
    return info, info.payload[:23] + struct.pack("<II", *target) + info.payload[31:]


def compose_asset(asset, source, dest, lifecycle, *, states=None, selections=None):
    states = STATES if states is None else states
    base=ART+asset+"/model"
    rendered=[]
    scene=[]
    names=[]
    mesh_type = None
    for stage in states:
        name=asset+"_"+stage
        prefix=source/(ART+name)/name
        rgm=rc.parse(prefix.with_suffix(".rgm").read_bytes())
        rrgeom=rc.parse(prefix.with_suffix(".rrgeom").read_bytes())
        [render] = [c for c in find(rgm, b"MODL").children if c.tag in (b"STMS", b"SKMS")]
        if mesh_type is not None and render.tag != mesh_type:
            raise ValueError(f"Inconsistent building render type in {asset}")
        mesh_type = render.tag
        if mesh_type == b"SKMS":
            skeleton = find(rgm, b"SKLN")
            skin = find(rgm, b"SKIN")
            if struct.unpack_from("<II", skeleton.payload) != (0, 1) or struct.unpack_from("<I", skin.payload)[0] != 1:
                raise ValueError(f"Building needs one rigid skin bone: {name}")
        if render.decoded_name!=name:
            raise ValueError(f"Unexpected converter mesh name {render.decoded_name!r} for {name}")
        mesh=find(rrgeom,b"MESH")
        for header in (c for c in rc.walk([mesh]) if c.tag==b"GOHD"):
            actual,_=rc.read_lp_string(header.payload,0)
            if actual!=name:raise ValueError((name,actual))
        rendered.append(render)
        scene.append(mesh)
        names.append(name)
    src=source/(ART+asset+"_healthy")/(asset+"_healthy")
    rgm=rc.parse(src.with_suffix(".rgm").read_bytes())
    rrgeom=rc.parse(src.with_suffix(".rrgeom").read_bytes())
    state_template=rc.parse((ROOT/"authoring/templates/model.rgo").read_bytes())
    template=find(state_template,b"MSBP")
    selectors=find(rgm,b"MSBP")
    mapping=next(c for c in selectors.children if c.tag==b"MSA ")
    count=next(c for c in selectors.children if c.tag==b"MSD " and len(c.payload)==4)
    record=next(c for c in selectors.children if c.tag==b"MSD " and len(c.payload)>4)
    cond=next(c for c in template.children if c.tag==b"CNBP")
    header=next(c for c in selectors.children if c.tag==b"HDR ")
    conditions=pack(header)+pack(mapping,struct.pack("<I",len(names))+b"".join(rc.lp_string(n) for n in names))
    if selections is None:
        selections = [
            (stage, name, [("life_cycle_state", state) for state in states[stage]], len(states[stage]) > 1)
            for stage, name in zip(states, names, strict=True)
        ]
    conditions += pack(count, struct.pack("<I", len(selections)))
    for selector, name, checks, match_any in selections:
        if name not in names or not checks:
            raise ValueError((asset, selector, name))
        conditions += pack(record, rc.lp_string("sel_" + selector) + struct.pack("<I", 1) + rc.lp_string(name))
        flags = b"".join(struct.pack("<IBI", 2, 0, int(match_any)) + rc.lp_string(field) + rc.lp_string(value)
                         for field, value in checks)
        conditions += pack(cond, struct.pack("<I", len(checks)) + flags)
    parent=find(rgm,b"MODL")
    assembled=[]
    info, header_payload = set_mesh_count(rgm, len(rendered), mesh_type)
    for chunk in parent.children:
        if chunk.tag==mesh_type:assembled.extend(pack(c) for c in rendered)
        elif chunk.offset==info.offset:assembled.append(pack(chunk,header_payload))
        elif chunk.tag==b"MSBP":assembled.append(pack(chunk,conditions))
        elif chunk.tag==b"BANA":assembled.append(pack(chunk,rc.lp_string(base.replace("/","\\"))))
        else:assembled.append(pack(chunk))
    output=rc.rebuild(rgm,lambda chunk:b"".join(assembled) if chunk.offset==parent.offset else None)
    after=rc.parse(output)
    if [c.decoded_name for c in rc.walk(after.roots) if c.tag==mesh_type]!=names:
        raise ValueError("Selector assembly lost a model")
    store(dest,base+".rgm",output)

    geom_root=find(rrgeom,b"RRGO")
    geom_count=find(rrgeom,b"NBME")
    mesh_payload=pack(geom_count,struct.pack("<I",len(scene)))+b"".join(pack(c) for c in scene)
    geometry=rc.rebuild(rrgeom,lambda chunk:mesh_payload if chunk.offset==geom_root.offset else None)
    assert len([c for c in rc.walk(rc.parse(geometry).roots) if c.tag==b"MESH"])==len(states)
    store(dest,base+".rrgeom",geometry)

    native_rgo=rc.parse(src.with_suffix(".rgo").read_bytes())
    default_source=(ROOT/"authoring/templates/building-lifecycle-defaults.bin").read_bytes()
    info, header_payload = set_mesh_count(native_rgo, len(rendered), mesh_type)
    patches = {find(native_rgo, b"DTBP").offset: default_source, info.offset: header_payload}
    configured=rc.rebuild(native_rgo,lambda c:patches.get(c.offset))
    native_rgo = configured if lifecycle is None else graft(configured, lifecycle, rc)
    store(dest,base+".rgo",native_rgo)
    material=src.with_suffix(".rrmaterial").read_bytes()
    if b"patternTex" not in material:raise ValueError("Missing cooked owner-color channel")
    if mesh_type == b"SKMS":
        pattern = ART + src.parent.name + "/" + src.name + "_pattern.rrtex"
        if not (source / pattern).is_file():
            raise ValueError(f"Missing direct RGB owner-color mask {pattern}")
        material = model_variants.rewrite_material(material, {"patternTex": pattern.replace("/", chr(92))}, {})
    store(dest,base+".rrmaterial",material)
    for path in sorted(src.parent.glob("*.rrtex")):
        store(dest,ART+src.parent.name+"/"+path.name,path.read_bytes())
    return {"asset":asset,"states":names,"resource":base,"lods":3}

def main():
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("scratch",type=Path)
    parser.add_argument("assets",nargs="+")
    args=parser.parse_args()
    game=stock_game.current()
    args.scratch.mkdir()
    listed=game.archiver.run(["list",str(args.archive),"--verify"])
    assert listed["archive"]["verification"]["verified"]
    source=args.scratch/"read"
    game.archiver.run(["extract",str(args.archive),str(source),"--filter",""])
    lifecycle=game.model_files(DONOR,required=(".rgo",))[".rgo"]
    output=args.scratch/"art"
    receipts=[compose_asset(name,source,output,lifecycle) for name in args.assets]
    (args.scratch/"buildings.json").write_text(json.dumps(receipts,indent=2),encoding="utf-8")
    print(f"Composed {len(receipts)} native building assets with {len(STATES)} selector meshes each")

if __name__=="__main__":
    main()
