"""Compose reviewed Encampment geometry with the stock age-tier and landmark lifecycle contracts."""
from pathlib import Path
import json,os,struct,sys
from compose_buildings import ART,DONOR,compose_asset,find,pack,rc,stock_game

AGE_FIELD="current_age_state"
AGES=("dark","feudal","castle","imperial")
BUILD_STATES={
    "healthy":("healthy","preview","targeting",*(f"damage_{i}" for i in range(1,6))),
    **{f"frame{j:02}":tuple(f"construct_{i:02}" for i in range(j,j+25,5)) for j in (0,25,50,75)},
    "ruins":("ruins",),
}

def age_graph(asset, path, game):
    raw=path.read_bytes()
    doc=rc.parse(raw)
    label="barracks" if asset=="melee" else "archery"
    model=f"art/civilizations/mongols/layouts/archetypes/mon_layout_{label}/mon_layout_{label}"
    donor=rc.parse(game.model_files(model,required=(".rgo",))[".rgo"])
    source=find(donor,b"DTBP").payload
    prefix=rc.lp_string(AGE_FIELD)
    start=source.index(prefix)
    cursor=start+len(prefix)
    count,=struct.unpack_from("<I",source,cursor)
    cursor+=4
    observed=[]
    for _ in range(count):
        name,cursor=rc.read_lp_string(source,cursor)
        observed.append(name)
    assert observed==[*AGES,"null"]
    _,end=rc.read_lp_string(source,cursor)
    default=AGES[0 if asset=="melee" else 1]
    field=source[start:cursor]+rc.lp_string(default)
    definitions=find(doc,b"DTBP")
    assert definitions.payload[:4]==bytes(4)
    enums,=struct.unpack_from("<I",definitions.payload,4)
    updated=definitions.payload[:4]+struct.pack("<I",enums+1)+field+definitions.payload[8:]
    actions=find(doc,b"ACTC")
    example=next(c for c in actions.children if c.decoded_name=="set_lifecycle_construct_00")
    additions=[]
    for age in AGES[1:]:
        action=struct.pack("<I",1)+rc.lp_string("setstate")+struct.pack("<I",2)
        action+=rc.lp_string("StateMachine")+rc.lp_string(AGE_FIELD)+rc.lp_string("State")+rc.lp_string(age)+bytes(4)
        additions.append(rc.pack_chunk(example.kind,example.tag,action,version=example.version,name=f"act_set_current_age_{age}".encode("ascii")))
    patched=rc.rebuild(doc,lambda c:updated if c.offset==definitions.offset else
                       actions.payload+b"".join(additions) if c.offset==actions.offset else None)
    check=rc.parse(patched)
    assert len(find(check,b"BBPC").children)==29 and len(find(check,b"ACTC").children)==32
    path.write_bytes(patched)

def compose(asset, archive, dest):
    game=stock_game.current()
    listed=game.archiver.run(["list",str(archive),"--verify"])
    assert listed["archive"]["verification"]["verified"]
    dest.mkdir()
    read=dest/"read"
    game.archiver.run(["extract",str(archive),str(read),"--filter",""])
    lifecycle=game.model_files(DONOR,required=(".rgo",))[".rgo"]
    first=1 if asset=="melee" else 2
    states={}
    selections=[]
    for i in range(first,5):
        prefix=("m" if asset=="melee" else "r")+str(i)
        for stage,values in BUILD_STATES.items():
            key="healthy" if i==first and stage=="healthy" else prefix+"_"+stage
            states[key]=values
            for value in values:
                selections.append((key+"_"+value,asset+"_"+key,
                    [(AGE_FIELD,AGES[i-1]),("life_cycle_state",value)],False))
                if asset=="ranged" and i==first:
                    selections.append((key+"_"+value+"_preview",asset+"_"+key,
                        [(AGE_FIELD,"dark"),("life_cycle_state",value)],False))
    art=dest/"art"
    record=compose_asset(asset,read,art,lifecycle,states=states,selections=selections)
    path=art/(ART+asset+"/model.rgo")
    age_graph(asset,path,game)
    record["selectors"]=[{"mesh":model,"conditions":conditions} for _,model,conditions,_ in selections]
    (dest/"buildings.json").write_text(json.dumps([record],indent=2),encoding="utf-8")
    print(asset,len(states),"meshes and",len(selections),"age/lifecycle selectors")

if __name__=="__main__":
    compose(sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3]))
