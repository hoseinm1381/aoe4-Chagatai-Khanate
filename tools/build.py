"""Assemble a local Chagatai Garrison candidate from two verified native cooks."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
TEMP_ROOT = Path(os.environ.get("CK_SCRATCH", Path(tempfile.gettempdir()) / "chagatai-builds")).resolve()
EXT = Path(os.environ.get("GARRISON_EXTENSION", Path(os.environ["APPDATA"]) /
    "Blender Foundation/Blender/5.2/extensions/raw_githubusercontent_com/garrison"))
sys.path.insert(0, str(EXT))
from garrison_shared import mod_bundle, rgd, stock_game

DISPATCHER = "scar/garrison/chagatai/dispatcher.scar"
VERSION = "0.1.10"
SHARED_SQUADS_MARKER = "local sharedSquads = {} -- Filled by tools/build.py."
ARCHETYPES = {
    "town_center":"town_center", "house":"steppe_hearth", "barracks":"melee",
    "archery_range":"ranged", "monastery":"religious", "siege_workshop":"siege",
    "palisade_wall":"palisade", **{key:key for key in (
        "blacksmith","dock","market","outpost","palisade_gate","university","wonder")},
}
LANDMARK_AGE = {"almaliq":2, "ordu":2, "qarshi":3, "court":3, "ili":4, "mint":4}
BUILDING_AGE = {"blacksmith":2, "market":2, "religious":3, "siege":3, "university":4, "wonder":4}

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def run(*args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True, encoding="utf-8")

def child(parent, key):
    nodes = parent.nodes if hasattr(parent, "nodes") else parent.value
    return next(n for n in nodes if n.key == key or n.hash == rgd.dictionary_hash(key))

def at(parent, *path):
    for key in path:
        parent = child(parent, key)
    return parent

def ref(parent, family, target):
    child(parent, "$PBGMAP").value = family
    child(parent, "$PBGNAME").value = target

def refs(parent):
    for path, node in rgd.flatten(parent.value):
        if node.kind not in ("List","List2"):
            continue
        fields = {item.key: item.value for item in node.value}
        if fields.get("$PBGNAME"):
            yield path, fields.get("$PBGMAP","").replace("\\","/"), fields["$PBGNAME"]

def age_of(name):
    match = re.search(r"_(foot|mounted)_([1-4])$", name)
    if match:
        return int(match[2])
    lowered = name.lower()
    if "imperial" in lowered or "elite" in lowered:
        return 4
    if "castle" in lowered or "veteran" in lowered:
        return 3
    if "feudal" in lowered or "early" in lowered:
        return 2
    return 1

def populate_codex(doc, tables, owner):
    capital = "ck_building_town_center_capital"
    producer_prefix = "attrib/ebps/races/chagatai/buildings/"
    plans = []
    for member, table in sorted(tables.items(), key=lambda pair:(not pair[0].endswith(capital+".rgd"),pair[0])):
        if not member.startswith(producer_prefix):
            continue
        producer = Path(member).stem
        if producer == "ck_building_town_center":
            continue
        landmark = producer.startswith("ck_landmark_")
        slug = producer.removeprefix("ck_landmark_" if landmark else "ck_building_")
        age = LANDMARK_AGE[slug] if landmark else BUILDING_AGE.get(slug, 1)
        products = {
            (family, name) for path, family, name in refs(child(table,"default"))
            if family in {"sbps","upgrade"}
            and (path.startswith("spawner_ext/spawn_items/") or path.startswith("upgrade_ext/standard_upgrades/"))
            and not name.endswith(("_hidden", "_dummy"))
        }
        if producer == capital:
            products.update(("sbps",owner+":"+name) for name in ("ck_unit_villager","ck_scout_foot_1","ck_horse"))
        plans.append((producer, landmark, age, sorted(products)))
    sample = at(doc,"default","codex_bag")
    group_sample = child(sample,"tech_tree").value[0]
    item_sample = child(group_sample,"items").value[0]
    legacy_sample = at(sample,"root_item","children").value[0]
    container_sample = child(legacy_sample,"children").value[0]
    leaf_sample = child(container_sample,"children").value[0]
    for variant in (n for n in doc.nodes if n.kind in ("List","List2")):
        bag = child(variant,"codex_bag")
        tree = child(bag,"tech_tree")
        root = child(bag,"root_item")
        roots = child(root,"children")
        groups, old_groups = [], []
        for producer, landmark, age, products in plans:
            header_age = age - 1 if landmark else age
            group, legacy = deepcopy(group_sample), deepcopy(legacy_sample)
            ref(child(legacy,"pbg"),"ebps",owner+":"+producer)
            at(legacy,"ui_codex_info","ui_position","ui_position_column").value = header_age-1
            entries, leaves = [], []
            rows = Counter()
            for family, name in [("ebps",owner+":"+producer),*products]:
                item = deepcopy(item_sample)
                ref(child(item,"pbg"),family,name)
                ref(child(item,"upgrade_pbg"),"","")
                product_age = max(age, age_of(name))
                y = (header_age-1)*3 + (2 if landmark else 0) if family=="ebps" else (product_age-1)*3+(2 if family=="upgrade" else 1)
                for key, value in (("x_position",rows[y]*2),("y_position",y),
                                   ("left_branch_length",0),("right_branch_length",0),("top_line_length",0)):
                    child(item,key).value = value
                rows[y] += 1
                entries.append(item)
                if family != "ebps":
                    container, leaf = deepcopy(container_sample), deepcopy(leaf_sample)
                    ref(child(leaf,"pbg"),family,name)
                    at(leaf,"ui_codex_info","ui_position","ui_position_column").value = product_age-1
                    child(leaf,"children").value = []
                    child(container,"children").value = [leaf]
                    leaves.append(container)
            child(group,"items").value = entries
            child(group,"background_height").value = 11
            child(group,"background_template").value = "center" if producer == capital else "military"
            child(legacy,"children").value = leaves
            groups.append(group)
            old_groups.append(legacy)
        tree.value = groups
        roots.value = old_groups
        child(bag,"landmark_count").value = len(LANDMARK_AGE)
    return len(plans)

def locate_inventory(game, archive, target):
    listing = game.archiver.run(["list",str(archive),"--verify"])
    if not listing["archive"]["verification"]["verified"]:
        raise ValueError(f"Archive integrity failed: {archive}")
    game.archiver.run(["extract",str(archive),str(target),"--filter",""])
    return listing["archive"]["name"], {m["path"]:m["toc"] for m in listing["members"]}

def ucs(data):
    return dict(line.split("\t",1) for line in data.decode("utf-16").splitlines() if line)

def build(args):
    work = args.work.resolve()
    if not work.is_relative_to(TEMP_ROOT) or work == TEMP_ROOT:
        raise ValueError("Build scratch must be a new directory under Temp_aoe4")
    work.mkdir()
    profile = read_json(SOURCE/"authoring-profile.json")
    owner = profile["owner"].replace("-","")
    game = stock_game.current()
    old_name, tuning_tocs = locate_inventory(game,args.tuning,work/"tuning")
    carrier_name, carrier_tocs = locate_inventory(game,args.carrier,work/"carrier")
    if carrier_name != owner or old_name != owner:
        raise ValueError("Unexpected carrier or tuning archive owner")
    recipe = {"schema":"garrison.civilization-build/v1","owner":profile["owner"],
        "race":"chagatai","dispatcher":DISPATCHER,"shared_entities":[],"attributes":[],"members":[]}
    sources = {}
    tables = {}
    def accept(member,toc,data):
        if member in sources:
            raise ValueError(f"Duplicate recipe input {member}")
        sources[member] = (toc,data)
    def table(member,data):
        if member in tables:
            raise ValueError(f"Duplicate attribute {member}")
        doc = rgd.read(data)
        if rgd.write(doc) != data:
            raise ValueError(f"Typed RGD roundtrip failed for {member}")
        tables[member] = doc
    for member,toc in carrier_tocs.items():
        data = (work/"carrier"/member).read_bytes()
        if toc == "attrib":
            if member.startswith("attrib/racebps/"):
                member = "attrib/racebps/chagatai.rgd"
            table(member,data)
        elif toc == "info" or member.startswith("ui/images/garrison/"):
            accept(member,toc,data)
    carrier_members = set(tables)
    for member,toc in tuning_tocs.items():
        data = (work/"tuning"/member).read_bytes()
        if toc == "attrib" and member.count("/") > 1:
            table(member,data)
        elif toc == "data" and not member.startswith("scar/"):
            accept(member,toc,data)
    root = tables["attrib/chagatai.rgd"]
    additive = child(root,"override_instances")
    if additive.kind != "Boolean" or child(root,"id").value != owner:
        raise ValueError("Unexpected native attribute root")
    additive.value = False

    race = tables["attrib/racebps/chagatai.rgd"]
    for variant in (n for n in race.nodes if n.kind in ("List","List2")):
        arch = at(variant,"race_bag","blueprint_archetypes")
        for field,slug in ARCHETYPES.items():
            ref(child(arch,field),"ebps",owner+":ck_building_"+slug)
        for field,name in {
            "spearman":"ck_spearman_foot_1","horseman":"ck_spearman_mounted_2",
            "manatarms":"ck_nokor_foot_2","knight":"ck_nokor_mounted_2","archer":"ck_archer_foot_2",
            "crossbowman":"ck_crossbow_foot_3","handcannon":"ck_handcannon_foot_4",
            "trader":"ck_trader_foot_2","monk":"ck_religious_foot_3",
        }.items():
            ref(child(arch,field),"ebps",owner+":"+name)
    # Membership is a RaceBP reference. Speech, slot names, and stock donor
    # mechanics retain their exact values.
    membership_fields = ("type_ext/race_type_list/", "squad_type_ext/squad_race_type_list/")
    stock_blueprints = game.blueprint_index(work/"stock-index")
    from bind_art import repair_unit_presentation
    repair_unit_presentation(tables, game, profile)
    visual_receivers={}
    if args.visuals is not None:
        from bind_art import BUILDINGS, building_bindings, unit_bindings
        from repair_animators import building_controller
        from native_visuals import building_boxes, restore_rig, rig_donors
        from native_materials import material_donors, repair_resource
        models=building_bindings(tables,game,stock_blueprints,profile,args.visuals)
        if models.keys()!=BUILDINGS.keys():
            raise ValueError(f"Missing building bindings: {BUILDINGS.keys()-models.keys()}")
        visual_receivers.update(models)
        visual_receivers.update(unit_bindings(tables,game,stock_blueprints,profile,args.visuals))
        controllers = {resource + ".rgo" for resource in models.values()}
        donors = rig_donors(args.visuals)
        materials = material_donors(args.visuals)
        for member, data in building_boxes(tables, game, models).items():
            accept(member, "data", data)
        from building_color import corrected_textures
        color_textures = corrected_textures(args.visuals, work / "building-colors")
        for asset in sorted((args.visuals/"art").rglob("*")):
            if asset.is_file():
                member = asset.relative_to(args.visuals / "art").as_posix()
                data = color_textures.get(member, asset.read_bytes())
                if member in controllers:
                    data = building_controller(data, game)
                if member in donors:
                    stock = game.model_files(donors[member], required=(".rgm",))[".rgm"]
                    data = restore_rig(data, stock)
                data = repair_resource(member, data, materials, game)
                accept(member, "data", data)
    stock_entities = {}
    for path in stock_blueprints:
        if path.startswith(("ebps/","sbps/")):
            stock_entities.setdefault((path.split("/",1)[0],Path(path).name),[]).append(path)
    reviewed_shared = {"ebps": set(), "sbps": set()}
    for member,doc in tables.items():
        if not member.startswith(("attrib/ebps/","attrib/sbps/")):
            continue
        for path,node in rgd.flatten(doc.nodes):
            if node.key=="$PBGNAME" and node.value=="mongol" and any(part in path for part in membership_fields):
                node.value = owner+":chagatai"
        for variant in (n for n in doc.nodes if n.kind in ("List","List2")):
            for path,family,name in refs(variant):
                if ":" in name or family not in {"ebps","sbps"}:
                    continue
                if (path.startswith(("spawner_ext/spawn_items/","squad_loadout_ext/","combat_ext/","projectile_ext/"))
                        and (family,name) in stock_entities):
                    reviewed_shared[family].add(name)
    recipe["shared_entities"] = sorted(reviewed_shared["ebps"])
    shared_squads = sorted(reviewed_shared["sbps"])
    producer_count = populate_codex(next(doc for path,doc in tables.items() if path.startswith("attrib/codex/")),tables,owner)

    locales = {}
    for member,toc in tuning_tocs.items():
        if toc == "locale":
            locales[member] = ucs((work/"tuning"/member).read_bytes())
    moved_ids = {}
    for member,toc in carrier_tocs.items():
        if toc != "locale":
            continue
        rows = locales.setdefault(member,{})
        incoming = ucs((work/"carrier"/member).read_bytes())
        for key,value in incoming.items():
            if key in {"1","2"}:
                rows[key] = profile["name"] if key=="1" else value
                continue
            if key in rows and rows[key] != value:
                new = str(9000+int(key))
                if new in rows or new in incoming:
                    raise ValueError(f"Generated localization ID {new} collides")
                moved_ids[key] = new
                rows[new] = value
            else:
                rows[key] = value
    for member,doc in tables.items():
        if member in carrier_members:
            for _,node in rgd.flatten(doc.nodes):
                if node.kind=="LocString" and isinstance(node.value,str):
                    prefix,separator,local_id = node.value.rpartition(":")
                    if separator and prefix=="$"+owner and local_id in moved_ids:
                        node.value = prefix+":"+moved_ids[local_id]
        accept(member,"attrib",rgd.write(doc))
    for path in sorted((SOURCE/"tuning/assets/scar").rglob("*.scar")):
        member = "scar/"+path.relative_to(SOURCE/"tuning/assets/scar").as_posix()
        data = path.read_bytes()
        if member == DISPATCHER:
            marker = SHARED_SQUADS_MARKER.encode("utf-8")
            if data.count(marker) != 1:
                raise ValueError("Missing unique shared squad inventory declaration")
            inventory = ("local sharedSquads = {" + ", ".join(json.dumps(name) for name in shared_squads) + "}")
            data = data.replace(marker, inventory.encode("utf-8"))
        accept(member,"data",data)
    for member,rows in locales.items():
        raw = "".join(key+"\t"+rows[key]+"\r\n" for key in sorted(rows,key=int)).encode("utf-16")
        accept(member,"locale",raw)
    # The installed assembler indexes hotkey bindings under the hotkeys family.
    # Restore their exact serialized maps after validating the dependency graph.
    subfamilies = {
        "hotkeys/hotkey_binding":"hotkeys",
    }
    subfamily_names = {
        family:{Path(member).stem for member in tables if member.startswith("attrib/"+family+"/")}
        for family in subfamilies
    }
    hotkey_originals = {}
    for member,doc in tables.items():
        changed = False
        for _,node in rgd.flatten(doc.nodes):
            if node.kind not in ("List","List2"):
                continue
            fields = {item.key:item for item in node.value}
            family, name = fields.get("$PBGMAP"), fields.get("$PBGNAME")
            if family is None or name is None:
                continue
            qualified = family.value.replace(chr(92),"/")
            if qualified not in subfamilies or not name.value.startswith(owner+":"):
                continue
            if name.value.split(":",1)[1] not in subfamily_names[qualified]:
                raise ValueError(f"Missing owned {qualified} target in {member}: {name.value}")
            family.value = subfamilies[qualified]
            changed = True
        if changed:
            hotkey_originals[member] = sources[member][1]
            sources[member] = ("attrib",rgd.write(doc))
    for member,(toc,data) in sorted(sources.items()):
        path = work/"recipe-inputs"/member
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        row = {"member":member,"file":str(path),"sha256":sha(data)}
        if toc=="attrib":
            recipe["attributes"].append(row)
        else:
            recipe["members"].append(dict(row,toc=toc))
    recipe_path = work/"recipe.json"
    write_json(recipe_path,recipe)
    core = EXT/"bin/core/garrison-core.exe"
    for step in ("validate","build"):
        try:
            run(core,"civilization",step,recipe_path,*(
                ("--output",work/"assembled") if step=="build" else ()))
        except subprocess.CalledProcessError as exc:
            print(exc.stdout,exc.stderr,file=sys.stderr)
            raise
    report = read_json(work/"assembled/report.json")
    archive = Path(report["archive"])
    if hotkey_originals:
        changes = []
        for member,data in sorted(hotkey_originals.items()):
            path = work/"exact-hotkeys"/member
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            changes.append(f"{member}={path}")
            report["members"][member].update(sha256=sha(data),bytes=len(data))
        listing = work/"restore-hotkey-maps.txt"
        listing.write_text("\n".join(changes)+"\n",encoding="utf-8")
        result = work/"chagatai-exact-hotkeys.sga"
        game.archiver.run(["set-members",str(archive),str(listing),str(result)])
        archive = result
    _, actual = locate_inventory(game,archive,work/"readback")
    if set(actual) != set(report["members"]):
        raise ValueError("Archive readback differs from assembly report")
    for member,toc in actual.items():
        if sha((work/"readback"/member).read_bytes()) != report["members"][member]["sha256"]:
            raise ValueError(f"Member hash differs for {member}")
        if toc != report["members"][member]["toc"]:
            raise ValueError(f"Wrong TOC for {member}")
    if set(("mod.bin","mod.rrtex")) - actual.keys() or any(actual[key]!="info" for key in ("mod.bin","mod.rrtex")):
        raise ValueError("Missing native discovery metadata")
    declaration = read_json(work/"readback/garrison/civilizations.json")
    for entry in [declaration["attribute_root"],*declaration["races"],*declaration["scripts"]]:
        if sha((work/"readback"/entry["member"]).read_bytes()) != entry["sha256"]:
            raise ValueError(f"Broken declaration digest for {entry['member']}")
    dispatcher = (work/"readback"/DISPATCHER).read_bytes()
    if not dispatcher.endswith(sources[DISPATCHER][1]):
        raise ValueError("Generated dispatcher lost its authored body")
    for variable, family, shared in (
        ("entities", "ebps", recipe["shared_entities"]),
        ("squads", "sbps", []),
        ("sharedSquads", None, shared_squads),
    ):
        [inventory] = re.findall(r"^local " + variable + r" = \{([^}]*)\}",
                                 dispatcher.decode("utf-8"), re.MULTILINE)
        actual_names = json.loads("[" + inventory + "]")
        expected_names = set(shared)
        if family:
            expected_names.update(owner + ":" + Path(member).stem for member in tables
                                  if member.startswith(f"attrib/{family}/"))
        if len(actual_names) != len(expected_names) or set(actual_names) != expected_names:
            raise ValueError(f"Incorrect typed prematch inventory: {variable}")
    delivery = work/"delivery"
    delivery.mkdir()
    suffix = "" if visual_receivers else "-development"
    zip_path = delivery/(f"Chagatai-Khanate-Garrison-{VERSION}{suffix}.zip")
    mod_bundle.write_package(delivery/"bundle",zip_path,bundle_key="chagatai",
        details={"id":"chagatai","name":"Chagatai Khanate","version":VERSION if visual_receivers else f"{VERSION}-dev.1",
            "summary":"Independent Chagatai Khanate art and gameplay playtest." if visual_receivers else "Independent Chagatai Khanate development build.",
            "description":profile["description"],"author":"hosein81",
            "min_garrison":"0.1.16","updated":"2026-11-09","content_types":["civilization"],"cover":"cover.png"},
        archives=[("chagatai","civilization",archive)],
        start_here=(ROOT/"START-HERE.md").read_text(encoding="utf-8"),
        cover=SOURCE/"presentation/cover.png")
    with zipfile.ZipFile(zip_path) as bundle:
        if bundle.testzip() or len([n for n in bundle.namelist() if n.endswith(".sga")]) != 1:
            raise ValueError("Invalid player ZIP")
        member = next(n for n in bundle.namelist() if n.endswith(".sga"))
        if sha(bundle.read(member)) != sha(archive.read_bytes()):
            raise ValueError("Player ZIP contains the wrong SGA")
    write_json(work/"verification.json",{"owner":owner,"members":len(actual),"attributes":len(tables),
        "codex_groups":producer_count,"tuning_cook_owner":old_name,"archive_sha256":sha(archive.read_bytes()),
        "zip_sha256":sha(zip_path.read_bytes()),"zip":str(zip_path),"runtime_tested":False,
        "visual_receivers":visual_receivers, "shared_precache_entities":recipe["shared_entities"],
        "shared_precache_squads":shared_squads})
    print(zip_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carrier",required=True,type=Path)
    parser.add_argument("--tuning",required=True,type=Path)
    parser.add_argument("--work",required=True,type=Path)
    parser.add_argument("--visuals",type=Path)
    build(parser.parse_args())
