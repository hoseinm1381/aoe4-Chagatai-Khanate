"""Compose reviewed Encampment geometry with age-specific lifecycle selectors."""
from pathlib import Path
import json,sys
from compose_buildings import ART,compose_asset,stock_game

AGES=("dark","feudal","castle","imperial")
BUILD_STATES={
    "healthy":("healthy","preview","targeting",*(f"damage_{i}" for i in range(1,6))),
    **{f"frame{j:02}":tuple(f"construct_{i:02}" for i in range(j,j+25,5)) for j in (0,25,50,75)},
    "ruins":("ruins",),
}

def compose(asset, archive, dest):
    game=stock_game.current()
    listed=game.archiver.run(["list",str(archive),"--verify"])
    assert listed["archive"]["verification"]["verified"]
    dest.mkdir()
    read=dest/"read"
    game.archiver.run(["extract",str(archive),str(read),"--filter",""])
    first=1 if asset=="melee" else 2
    states={}
    tiers = {}
    for i in range(first,5):
        prefix=("m" if asset=="melee" else "r")+str(i)
        age=AGES[i-1]
        tiers[str(i)] = {}
        for stage, values in BUILD_STATES.items():
            key="healthy" if i==first and stage=="healthy" else prefix+"_"+stage
            model=asset+"_"+key
            if i == first:
                state_values = values
            else:
                suffix = "construct_"+stage[5:] if stage.startswith("frame") else stage
                state_values = (age+"_"+suffix,)
                tiers[str(i)][stage] = state_values[0]
            states[key] = state_values
    art=dest/"art"
    record=compose_asset(asset,read,art,None,states=states)
    record["state_groups"]={key:list(values) for key,values in states.items()}
    record["age_tiers"]=tiers
    (dest/"buildings.json").write_text(json.dumps([record],indent=2),encoding="utf-8")
    print(asset,len(states),"meshes and",sum(len(row) for row in states.values()),"age/lifecycle selectors")

if __name__=="__main__":
    compose(sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3]))
