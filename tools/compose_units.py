"""Read back cooked unit assets and preserve their native default mesh selection."""
from argparse import ArgumentParser
import json
from pathlib import Path
import struct

from compose_buildings import ART, find, pack, rc, stock_game, store

def unit_model(raw):
    doc=rc.parse(raw)
    find(doc,b"SKLN")
    names=[c.decoded_name for c in rc.walk(doc.roots) if c.tag==b"SKMS"]
    if not names or len(names)!=len(set(names)):
        raise ValueError("Cook produced no unique skinned meshes")
    selectors=find(doc,b"MSBP")
    header=next(c for c in selectors.children if c.tag==b"HDR ")
    msa=next(c for c in selectors.children if c.tag==b"MSA ")
    count=next(c for c in selectors.children if c.tag==b"MSD " and len(c.payload)==4)
    data=pack(header)+pack(msa,struct.pack("<I",len(names))+b"".join(rc.lp_string(n) for n in names))
    data+=pack(count,bytes(4))
    for chunk in selectors.children:
        if chunk.tag in (b"MRBP",b"MRD "):data+=pack(chunk)
    return rc.rebuild(doc,lambda c:data if c.offset==selectors.offset else None),names

def main():
    parser=ArgumentParser(description=__doc__)
    for name in ("archive","catalog","output"):parser.add_argument(name,type=Path)
    args=parser.parse_args()
    game=stock_game.current()
    listed=game.archiver.run(["list",str(args.archive),"--verify"])
    if not listed["archive"]["verification"]["verified"]:raise ValueError("Corrupt unit cook")
    rows=json.loads(args.catalog.read_bytes())
    expected={label for row in rows for label in row["models"].values()}
    actual={Path(row["path"]).stem for row in listed["members"] if row["path"].endswith(".rgm")}
    if actual!=expected:raise ValueError(f"Unit cook coverage mismatch: {sorted(expected-actual)}")
    art=args.output/"art"
    art.mkdir(parents=True,exist_ok=True)
    reports=[]
    for member in listed["members"]:
        name=member["path"]
        if not name.startswith(ART):continue
        raw=game.archiver.read(args.archive,name)
        if name.endswith(".rgm"):
            raw,names=unit_model(raw)
            reports.append({"resource":name,"meshes":names})
        elif name.endswith(".rrmaterial") and b"patternTex" not in raw:
            raise ValueError("Owner-colour material missing: "+name)
        store(art,name,raw)
    for row in rows:row.pop("manifests",None)
    (args.output/"units.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    (args.output/"unit-build.json").write_text(json.dumps(reports,indent=2),encoding="utf-8")
    print(f"Verified {len(reports)} skinned models and their cooked material masks")

if __name__=="__main__":
    main()
