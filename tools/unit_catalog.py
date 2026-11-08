"""Resolve each redesigned Chagatai body to the exact stock visual attachment donor."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
EXT=Path(os.environ["APPDATA"])/"Blender Foundation/Blender/5.2/extensions/raw_githubusercontent_com/garrison"
sys.path.insert(0,str(EXT))
from garrison_shared import rgd, stock_game

def plan():
    def tiered(key,form,ages,kind,attachment,civ="mon"):
        for age in ages:
            yield (f"ck_{key}_{form}_{age}",f"{key}_{form}_{age}",kind,
                   f"tier{age}_{attachment}_{civ}")
    yield from tiered("spearman","mounted",range(1,5),"light","cavalry_horseman")
    yield from tiered("nokor","mounted",(3,4),"heavy","cavalry_knight")
    yield ("ck_nokor_mounted_2","nokor_mounted_2","heavy","tier2_cavalry_knight_mon")
    yield from tiered("nokor","foot",(3,4),"heavy","manatarms")
    yield ("ck_nokor_foot_2","nokor_foot_2","heavy","tier2_manatarms_eng")
    yield from tiered("archer","foot",(2,3,4),"archer","archer")
    yield from tiered("archer","mounted",(2,3,4),"archer","cavalry_horsearcher")
    yield from tiered("crossbow","mounted",(3,4),"crossbow","cavalry_horsearcher")
    yield ("ck_handcannon_mounted_4","handcannon_mounted_4","gunner","tier4_cavalry_horsearcher_mon")
    yield ("ck_scout_foot_1","scout_foot_1","scout","tier1_militia_rogue_mon")
    yield ("ck_religious_foot_3","religious_foot_3","sufi","tier3_monk_mon")
    yield ("ck_religious_mounted_3","religious_mounted_3","sufi","tier3_cavalry_horseman_mon")
    yield ("ck_trader_foot_2","trader_foot_2","trader","tier3_monk_mon")
    yield ("ck_villager_mounted_1","villager_mounted_1","worker","tier1_cavalry_scout_mon")

def stock_attachment(idx,name):
    paths=[p for p in idx if p.startswith("attachments/attachment_lists/") and p.rsplit("/",1)[-1]==name]
    if len(paths)!=1:raise ValueError(f"{name} resolved to {paths}")
    return paths[0]

def stock_visuals(game,path):
    raw=game.blueprint(path)
    doc=rgd.read(raw)
    models={}
    for field,node in rgd.flatten(doc.nodes):
        if not field.startswith("default/") or node.kind!="CString":continue
        value=node.value.replace("\\","/")
        if ("/animator_merge_mesh_attachment/meshes/" in field or
            "/animator_skin_attachment/animator" in field) and value.startswith("art/"):
            models[value]=field
    if not models:raise ValueError(f"No proven stock body in {path}")
    return sorted(models)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work",type=Path)
    args=parser.parse_args()
    work=args.work
    work.mkdir()
    game=stock_game.current()
    idx=game.blueprint_index(work/"idx")
    entries=[]
    for name,label,style,attach in plan():
        donor=stock_attachment(idx,attach)
        visuals=stock_visuals(game,donor)
        models={}
        for i,visual in enumerate(visuals):
            models[visual]=f"{label}_{i+1}"
        entries.append({"blueprint":name,"style":style,"donor":donor,"models":models})
    loose=stock_attachment(idx,"gaia_huntable_reindeer")
    corpse=stock_attachment(idx,"gaia_food_reindeer_corpse")
    for role,path in (("horse",loose),("corpse",corpse)):
        models={v:f"{role}_{i+1}" for i,v in enumerate(stock_visuals(game,path))}
        entries.append({"blueprint":"ck_"+role,"style":role,"donor":path,"models":models})
    (work/"plan.json").write_text(json.dumps(entries,indent=2),encoding="utf-8")
    kit=Path(os.environ["LOCALAPPDATA"])/"Garrison/Kit"
    roots={model for row in entries for model in row["models"]}
    def decode(pair):
        i,model=pair
        output=work/f"m{i:02d}"
        command=[EXT/"bin/core/garrison-core.exe","convert","decode-static","--logical-path",model+".rgm",
                 "--config",kit/"game-assets.local.json","--index",kit/"game-assets.sqlite3","--output-root",output]
        result=subprocess.run([str(x) for x in command],capture_output=True,text=True)
        if result.returncode:raise ValueError(result.stderr)
        manifest=json.loads(result.stdout)["manifest_path"]
        return model,manifest
    with ThreadPoolExecutor(max_workers=4) as executor:
        decoded=dict(executor.map(decode,enumerate(sorted(roots))))
    for row in entries:
        row["manifests"]={asset:decoded[model] for model,asset in row["models"].items()}
    (work/"plan.json").write_text(json.dumps(entries,indent=2),encoding="utf-8")
    print(f"{len(entries)} receiver families, {len(roots)} decoded official models")

if __name__=="__main__":
    main()
