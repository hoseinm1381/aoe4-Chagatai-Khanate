"""Derive private visual attachment lists without mutating stock or gameplay fields."""
from pathlib import Path
from collections import defaultdict
from copy import deepcopy

from garrison_shared import derived_blueprints, mod_content, rgd
from repair_animators import HORSE_IDLE, HORSE_SELECT

BUILDINGS={
    **{"ck_building_"+name:name for name in ("pasture","steppe_hearth","melee","ranged")},
    **{"ck_landmark_"+name:name for name in ("almaliq","ordu","qarshi","court","ili","mint")},
}

def node(parent,key):
    rows=parent.nodes if hasattr(parent,"nodes") else parent.value
    return next(x for x in rows if x.key==key or x.hash==rgd.dictionary_hash(key))

def attach(variant):
    try:return node(node(variant,"entity_blueprint_ext"),"animator_attachments")
    except StopIteration:return None

def variants(doc):
    return (variant for variant in doc.nodes if variant.kind in ("List", "List2"))


def tier_attachments(variant):
    for route, field in rgd.flatten(variant.value):
        if route.startswith("tier_ext/") and route.endswith("/attachments") and field.kind in ("List", "List2"):
            yield node(field, "$PBGNAME")


def remove_visual_parts(part, remove):
    if part.kind not in ("List", "List2"):
        return
    part.value[:] = [child for child in part.value if not remove(child)]
    for child in part.value:
        remove_visual_parts(child, remove)


def scout_shield(part):
    return part.key == "animator_sim_attachment" and any(
        field.key == "animator" and "/defense/shield" in field.value.replace(chr(92), "/")
        for field in part.value
    )


def private_list(key, donor, game, profile):
    generated, _ = derived_blueprints.build(
        [{"name": key, "family": "attachments/attachment_lists", "source": donor, "changes": []}],
        {donor: game.blueprint(donor)}, mod_id=profile["owner"], mod_key="chagatai",
        pbgid=mod_content.pbgid, owner=profile["owner"].replace("-", ""))
    [(dest, (_, raw))] = generated.items()
    return "attrib/" + dest + ".rgd", rgd.read(raw)


def filtered_tier(stock_name, names, game, profile, tables):
    [donor] = names[stock_name]
    key = "ck_no_stamps_" + stock_name
    path, private = private_list(key, donor, game, profile)
    for variant in variants(private):
        remove_visual_parts(variant, lambda part: part.key == "stamp_attachment")
    tables[path] = private
    return profile["owner"].replace("-", "") + ":" + key


def repair_unit_presentation(tables, game, profile):
    by_name = {(member.split("/")[1], Path(member).stem): doc for member, doc in tables.items()}
    handcannon = by_name["sbps", "ck_handcannon_mounted_4"]
    archer = by_name["sbps", "ck_archer_mounted_4"]
    donor = node(node(node(archer, "default"), "squad_ability_ext"), "abilities")
    formations = [ability for ability in donor.value
                  if node(ability, "$PBGNAME").value.startswith("core_formation_")]
    assert {node(a, "$PBGNAME").value for a in formations} == {
        "core_formation_line", "core_formation_spread", "core_formation_wedge"}
    for variant in variants(handcannon):
        abilities = node(node(variant, "squad_ability_ext"), "abilities")
        present = {node(ability, "$PBGNAME").value for ability in abilities.value}
        abilities.value.extend(deepcopy(a) for a in formations if node(a, "$PBGNAME").value not in present)

    monk = node(rgd.read(game.blueprint("ebps/races/mongol/units/unit_monk_3_mon")), "default")
    stock_trader = rgd.read(game.blueprint("ebps/races/mongol/units/unit_trade_cart_mon"))
    trader = by_name["ebps", "ck_trader_foot_2"]
    # Restore the native trader simulation contract. Animation is deferred by
    # the owner after the monk actor broke trading without fixing playback.
    for variant in variants(trader):
        native = next((v for v in variants(stock_trader) if v.key == variant.key), node(stock_trader, "default"))
        for field in ("statemodel_ext", "action_tree_ext", "action_apply_ext",
                      "animation_action_tree_ext", "hit_react_tree_ext", "holdable_ext"):
            node(variant, field).value = deepcopy(node(native, field).value)

    horseman = node(rgd.read(game.blueprint("ebps/races/mongol/units/unit_horseman_4_mon")), "default")
    for name, donor in (("ck_handcannon_mounted_4", horseman), ("ck_religious_mounted_3", monk)):
        [voice] = [field.value for route, field in rgd.flatten(node(donor, "action_apply_ext").value)
                   if route.endswith("/state_tree") and chr(92) + "audio" + chr(92) + "mon" in field.value]
        for variant in variants(by_name["ebps", name]):
            for route, field in rgd.flatten(node(variant, "action_apply_ext").value):
                if route.endswith("/state_tree") and chr(92) + "audio" + chr(92) in field.value:
                    field.value = voice

    for name in ("ck_horse", "ck_horse_ili", "ck_horse_import"):
        for variant in variants(by_name["ebps", name]):
            node(node(variant, "animation_action_tree_ext"), "default_animation").value = HORSE_IDLE
            node(node(variant, "audio_ext"), "single_select_event").value = HORSE_SELECT


def enable_imperial_tier(doc, game, asset):
    building = "infantry" if asset == "melee" else "ranged"
    source = f"ebps/races/english/buildings/building_unit_{building}_eng/building_unit_{building}_control_eng"
    official = node(rgd.read(game.blueprint(source)), "default")
    def ages(variant):
        return node(node(node(variant, "tier_ext"), "tier_group_list"), "tier_group").value
    donor = next(row for row in ages(official)
                 if row.key == "tier" and node(row, "tier_attachment_action").value == "act_set_current_age_imperial")
    requirement = node(donor, "statetree_tier_requirements_pbg")
    for variant in doc.nodes:
        if variant.kind not in ("List", "List2"):
            continue
        tiers = ages(variant)
        castle = next(row for row in tiers if row.key == "tier"
                      and node(row, "tier_attachment_action").value == "act_set_current_age_castle")
        imperial = deepcopy(castle)
        node(imperial, "tier_attachment_action").value = "act_set_current_age_imperial"
        node(imperial, "statetree_tier_requirements_pbg").value = deepcopy(requirement.value)
        tiers.append(imperial)


def building_bindings(tables,game,index,profile,source):
    art=source/"art"
    owner=profile["owner"].replace("-","")
    candidates=defaultdict(list)
    for path in index:
        if path.startswith("attachments/attachment_lists/"):
            candidates[path.rsplit("/",1)[-1]].append(path)
    links={}
    filtered_stamps = {}
    for member,doc in list(tables.items()):
        name=Path(member).stem
        asset=BUILDINGS.get(name)
        if not asset or not member.startswith("attrib/ebps/"):continue
        model=f"art/scenario/chagatai/{asset}/model"
        if not (art/(model+".rgm")).is_file():continue
        binding_name="ck_visual_"+asset
        refs=[attach(variant) for variant in doc.nodes if variant.kind in ("List","List2")]
        refs=[ref for ref in refs if ref is not None and node(ref,"$PBGNAME").value]
        if not refs:raise ValueError(f"Missing receiver attachment on {name}")
        stock_name=node(refs[0],"$PBGNAME").value
        available=candidates.get(stock_name,[])
        if len(available)!=1:
            same_race=[path for path in available if "/mongol/" in path]
            if len(same_race)==1:available=same_race
        if len(available)!=1:raise ValueError(f"Ambiguous source attachment on {name}: {available}")
        path=available[0]
        raw=game.blueprint(path)
        generated,_=derived_blueprints.build(
            [{"name":binding_name,"family":"attachments/attachment_lists","source":path,"changes":[]}],
            {path:raw},mod_id=profile["owner"],mod_key="chagatai",pbgid=mod_content.pbgid,owner=owner)
        [(dest,(_,data))]=generated.items()
        private=rgd.read(data)
        count=0
        for variant in (n for n in private.nodes if n.kind in ("List","List2")):
            attachment=node(variant,"attachment_lists")
            parent=node(attachment,"parent_animator")
            parent.value=model.replace("/","\\")
            count+=1
        if not count:raise ValueError("Missing parent animator in derived record")
        tables["attrib/"+dest+".rgd"]=private
        for ref in refs:
            node(ref,"$PBGNAME").value=owner+":"+binding_name
        if asset in ("melee", "ranged") and b"current_age_state" in (art/(model+".rgo")).read_bytes():
            enable_imperial_tier(doc, game, asset)
        for variant in variants(doc):
            for reference in tier_attachments(variant):
                if not reference.value:
                    continue
                if reference.value not in filtered_stamps:
                    filtered_stamps[reference.value] = filtered_tier(
                        reference.value, candidates, game, profile, tables)
                reference.value = filtered_stamps[reference.value]
        links[name]=model
    return links

def body_fields(variant):
    for route, field in rgd.flatten(node(variant, "attachment_lists").value):
        if field.kind == "CString" and field.value and (
            "/animator_merge_mesh_attachment/meshes/" in route
            or route.endswith("/animator_skin_attachment/animator")
        ):
            yield field


def unit_bindings(tables, game, index, profile, source):
    import json
    catalog = json.loads((source / "units.json").read_bytes())
    owner = profile["owner"].replace("-", "")
    names = defaultdict(list)
    for path in index:
        if path.startswith("attachments/attachment_lists/"):
            names[Path(path).name].append(path)
    receivers = {Path(path).stem: doc for path, doc in tables.items() if path.startswith("attrib/ebps/")}
    links = {}
    for row in catalog:
        name = row["blueprint"]
        if name == "ck_corpse":
            targets = sorted(n for n in receivers if n.startswith("ck_horse_corpse_"))
        elif name == "ck_horse":
            targets = ["ck_horse", "ck_horse_ili", "ck_horse_import"]
        elif name == "ck_villager_mounted_1":
            targets = [name] + sorted(n for n in receivers if n.startswith(name + "_livestock_"))
        else:
            targets = [name]
        if not targets:
            raise ValueError(f"No visual receivers for {name}")
        mapping = {old: f"art/scenario/chagatai/{asset}/{asset}" for old, asset in row["models"].items()}
        by_gender = {("female" in old): new for old, new in mapping.items()}
        bindings = {}
        for target in targets:
            observed = set()
            for variant in variants(receivers[target]):
                tiers = [ref for ref in tier_attachments(variant) if ref.value]
                scout = name == "ck_scout_foot_1"
                if scout:
                    # Keep the shieldless opening Scout on the root attachment
                    # and stock animation owner that already reached gameplay.
                    for tier in tiers:
                        tier.value = ""
                base = scout or not tiers
                if base:
                    tiers = [node(attach(variant), "$PBGNAME")]
                for ref in tiers:
                    original = ref.value
                    binding_key = "" if base else original
                    if binding_key not in bindings:
                        key = name.replace("ck_", "ck_visual_", 1)
                        if not base:
                            key += "_" + original
                        # The original tier owns the live slots, equipment, and animation
                        # overlays. Change the body in those slots, including every age.
                        donor = row["donor"] if base or name=="ck_trader_foot_2" else names[original][0]
                        path, private = private_list(key, donor, game, profile)
                        models = set()
                        for part in variants(private):
                            if base and "animation_owner" in row:
                                node(node(part, "attachment_lists"), "parent_animator").value = row[
                                    "animation_owner"].replace("/", chr(92))
                            if scout:
                                stock = node(rgd.read(game.blueprint(names[original][0])), "default")
                                parent = node(node(stock, "attachment_lists"), "parent_animator")
                                node(node(part, "attachment_lists"), "parent_animator").value = parent.value
                                remove_visual_parts(part, scout_shield)
                            for field in body_fields(part):
                                previous = field.value.replace(chr(92), "/")
                                gender = "female" in previous
                                resource = mapping.get(previous, by_gender.get(gender) or by_gender[False])
                                field.value = resource.replace("/", chr(92))
                                models.add(resource)
                        if not models:
                            raise ValueError(f"No native body slots in {donor}")
                        tables[path] = private
                        bindings[binding_key] = (owner + ":" + key, models)
                    ref.value, models = bindings[binding_key]
                    observed.update(models)
            links[target] = sorted(observed)
    return links
