"""Assemble cooked landmark states and verify native repair and all LOD groups."""
import json, os, struct, sys
from PIL import Image
from pathlib import Path

R=Path(os.environ["CK_RUN"])
P=Path(os.environ["CK_ROOT"])
sys.path.insert(0,str(P/"tools"))
import compose_buildings as base
from compose_buildings import rc,stock_game,find,DONOR,ART
from garrison_shared import rrtex_decoder

asset=sys.argv[1]
archive=Path(sys.argv[2])
work=R/(os.environ.get("CK_ASSEMBLY_PREFIX","assembled-")+asset)
work.mkdir()
stock=stock_game.current()
checked=stock.archiver.run(["list",str(archive),"--verify"])
assert checked["archive"]["verification"]["verified"]
read=work/"read"
stock.archiver.run(["extract",str(archive),str(read),"--filter",""])
source=stock.model_files(DONOR,required=(".rgo",))[".rgo"]
states={
 "healthy":("healthy","preview","targeting"),
 **{f"frame{j:02}":tuple(f"construct_{i:02}" for i in range(j,j+25,5)) for j in (0,25,50,75)},
 **{f"damage_{i}":(f"damage_{i}",) for i in range(1,6)},
 "ruins":("ruins",),
}
base.STATES=states
record=base.compose_asset(asset,read,work/"art",source)
stem=work/"art"/(ART+asset+"/model")
docs={ext:rc.parse(stem.with_suffix(ext).read_bytes()) for ext in (".rgm",".rgo",".rrgeom")}
geom=find(docs[".rrgeom"],b"RRGO")
meshes=[m for m in geom.children if m.tag==b"MESH"]
assert len(meshes)==len(states)
geo={name:len([c for c in rc.walk([m]) if c.tag==b"GOHD"]) for name,m in zip(states,meshes,strict=True)}
assert set(geo.values())=={3},geo
selectors=find(docs[".rgm"],b"MSBP")
matches={}
for c in selectors.children:
    if c.tag!=b"CNBP":continue
    n,=struct.unpack_from("<I",c.payload)
    names=[]
    pos=4
    for _ in range(n):
        pos+=9
        field,pos=rc.read_lp_string(c.payload,pos)
        assert field=="life_cycle_state"
        name,pos=rc.read_lp_string(c.payload,pos)
        names.append(name)
    assert pos==len(c.payload)
    matches[tuple(names)]=True
assert set(matches)==set(states.values())
act=find(docs[".rgo"],b"ACTC")
conditions=find(docs[".rgo"],b"BBPC")
official=rc.parse(source)
official_actions={a.decoded_name:a.payload for a in find(official,b"ACTC").children}
official_triggers={rc.read_lp_string(x.children[1].payload,0)[0]:x.children[0].payload for x in find(official,b"BBPC").children}
actual_actions={a.decoded_name:a.payload for a in act.children}
actual_triggers={rc.read_lp_string(x.children[1].payload,0)[0]:x.children[0].payload for x in conditions.children}
assert len(actual_actions)==29 and actual_actions.keys()==actual_triggers.keys()
assert all(data==official_actions[k] for k,data in actual_actions.items())
assert all(data==official_triggers[k] for k,data in actual_triggers.items())
for target in ("healthy","damage_1","damage_2","damage_3","damage_4","damage_5","ruins"):
    name="set_lifecycle_"+target.replace("_","")
    assert name in actual_actions
    assert target.encode() in actual_actions[name]
    assert b"health" in actual_triggers[name]
material=stem.with_suffix(".rrmaterial").read_bytes()
assert b"patternTex" in material
mask,_=rc.read_lp_string(material,material.index(b"patternTex")+len(b"patternTex"))
dds=work/"owner-mask.dds"
decoded=rrtex_decoder.decode_rrtex(work/"art"/mask.replace(chr(92),"/"),dds,validate_stream=True)
assert decoded.get("mip_count")
with Image.open(dds) as img:
    red=img.convert("RGBA").getchannel("R")
    lo,hi=red.getextrema()
    assert lo<=8 and hi>=192
    atlas_mask_fraction=sum(red.histogram()[128:])/(red.width*red.height)
    assert .01<=atlas_mask_fraction<=.60
texture_dir=work/"art"/ART/(asset+"_healthy")
textures=sorted(texture_dir.glob("*.rrtex"))
assert len(textures)>=2
record.update({
    "lod_groups":geo, "native_lifecycle_actions":len(actual_actions),
    "stock_lifecycle_byte_match":True,"cook_archive_verified":True,
    "packed_owner_mask_red_fraction":round(atlas_mask_fraction,4),
    "native_repair_confirmation":"Stock health-conditioned geometry selection verified in cooked data. Runtime repair pending.",
    "textures":[p.name for p in textures]
})
(work/"verification.json").write_text(json.dumps(record,indent=2))
print(json.dumps(record))


