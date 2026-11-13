"""Read the player ZIP and check its live visual and gameplay graph."""
import argparse
import json
from pathlib import Path
import re
import struct
import zipfile

from build import ROOT, child, locate_inventory, rgd, sha, stock_game, TEMP_ROOT
from compose_buildings import ART, STATES, find, rc
from repair_animators import HORSE, HORSE_IDLE, building_controller
from native_visuals import SCOUT_MODEL, rig_donors, restore_rig, building_boxes, PASSAGE_WIDTH
from native_materials import material_donors, material_name, repair_resource
from garrison_shared import rrtex_decoder
from PIL import Image

ATTACHMENT = "attrib/attachments/attachment_lists/garrison/chagatai/"
ANIMATOR = "/entity_blueprint_ext/animator_attachments/"
MODEL_EXTENSIONS = (".rgm", ".rgo", ".rrgeom", ".rrmaterial")


def leaves(data):
    return {path: (node.kind, node.value) for path, node in rgd.flatten(rgd.read(data).nodes)
            if node.kind not in ("List", "List2")}


def mesh_names(chunk):
    payload = next(c.payload for c in chunk.children if c.tag == b"MSA ")
    count, = struct.unpack_from("<I", payload)
    names, offset = [], 4
    for _ in range(count):
        name, offset = rc.read_lp_string(payload, offset)
        names.append(name)
    if offset != len(payload):
        raise ValueError("Trailing mesh table data")
    return names


def lifecycle_rows(record):
    if "selectors" in record:
        return [(row["mesh"], [tuple(pair) for pair in row["conditions"]], False)
                for row in record["selectors"]]
    keys = [name.removeprefix(record["asset"] + "_") for name in record["states"]]
    groups = dict(STATES)
    groups.update((f"damage_{i}", (f"damage_{i}",)) for i in range(1, 6))
    groups.update(record.get("state_groups", {}))
    return [(name, [("life_cycle_state", value) for value in groups[record.get("stage_aliases", {}).get(key, key)]], len(groups[record.get("stage_aliases", {}).get(key, key)]) > 1)
            for name, key in zip(record["states"], keys, strict=True)]


def verify_model(root, resource, building, dds):
    stage_names = building["states"] if building else None
    def read(extension):
        return (root / (resource + extension)).read_bytes()

    model = rc.parse(read(".rgm"))
    graph = rc.parse(read(".rgo"))
    geometry = rc.parse(read(".rrgeom"))
    material = read(".rrmaterial")
    textures = re.findall(rb"art\\scenario\\chagatai\\[a-z0-9_\\]+\.rrtex", material)
    if not textures or any(not (root / name.decode().replace(chr(92), "/")).is_file() for name in textures):
        raise ValueError(f"Missing cooked material textures for {resource}")
    animator, _ = rc.read_lp_string(find(model, b"BANA").payload, 0)
    if animator.replace(chr(92), "/") != resource:
        raise ValueError(f"Wrong animator in {resource}")

    selector = find(model, b"MSBP")
    rows = mesh_names(selector)
    render_tag = b"SKMS"
    cooked_names = [chunk.decoded_name for chunk in rc.walk(model.roots) if chunk.tag == render_tag]
    if rows != cooked_names or len(set(rows)) != len(rows) or not rows:
        raise ValueError(f"Broken cooked mesh selection for {resource}")

    if stage_names:
        for document in (model, graph):
            info = next(chunk for chunk in find(document, b"MODL").children if chunk.tag == b"INFO")
            if struct.unpack_from("<II", info.payload, 23) != (0, len(stage_names)):
                raise ValueError(f"Incorrect native mesh inventory in {resource}")
        if cooked_names != stage_names:
            raise ValueError(f"Missing building states for {resource}")
        conditions = [c.payload for c in selector.children if c.tag == b"CNBP"]
        records = [c.payload for c in selector.children if c.tag == b"MSD " and len(c.payload) > 4]
        expected = lifecycle_rows(building)
        if len(conditions) != len(expected):
            raise ValueError(f"Unexpected building selector table for {resource}")
        if find(graph, b"BBPC").children or find(graph, b"ACTC").children:
            raise ValueError(f"Unexpected native behavior in the tested controller for {resource}")
        for (mesh, pairs, match_any), payload, record in zip(expected, conditions, records, strict=True):
            _, pos = rc.read_lp_string(record, 0)
            selected, end = rc.read_lp_string(record, pos + 4)
            if selected != mesh or end != len(record) or struct.unpack_from("<I", record, pos)[0] != 1:
                raise ValueError(f"Incorrect selector target for {resource}")
            count, = struct.unpack_from("<I", payload)
            if count != len(pairs):
                raise ValueError(f"Incorrect lifecycle state count in {resource}")
            offset = 4
            for expected_pair in pairs:
                flags = struct.unpack_from("<IBI", payload, offset)
                value, offset = rc.read_lp_string(payload, offset + 9)
                state, offset = rc.read_lp_string(payload, offset)
                if (value, state) != expected_pair or flags != (2, 0, int(match_any)):
                    raise ValueError(f"Wrong lifecycle state {state} for {resource}")
            if offset != len(payload):
                raise ValueError(f"Unexpected lifecycle bytes in {resource}")
        meshes = [c for c in find(geometry, b"RRGO").children if c.tag == b"MESH"]
        if len(meshes) != len(rows) or any(sum(c.tag == b"GOHD" for c in rc.walk([m])) != building["lods"] for m in meshes):
            raise ValueError(f"Missing building geometry in {resource}")
    else:
        find(model, b"SKLN")
        if any(c.tag == b"CNBP" for c in selector.children):
            raise ValueError(f"Unexpected unit selector override for {resource}")

    texture, _ = rc.read_lp_string(material, material.index(b"patternTex") + len(b"patternTex"))
    decoded = rrtex_decoder.decode_rrtex(root / texture.replace(chr(92), "/"), dds, validate_stream=True)
    if not decoded.get("mip_count"):
        raise ValueError(f"No cooked owner-color mask for {resource}")
    with Image.open(dds) as image:
        red = image.convert("RGBA").getchannel("R")
        low, high = red.getextrema()
        fraction = sum(red.histogram()[128:]) / (red.width * red.height)
        meat = "/corpse_1/" in resource and high <= 8
        if not meat and (low > 8 or high < 192 or not 0.005 <= fraction <= 0.85):
            raise ValueError(f"Missing dynamic mask contrast for {resource}")
    return fraction


def verify_opening(readback, visuals):
    baseline = json.loads((visuals / "opening-baseline.json").read_bytes())
    changed_scout = {SCOUT_MODEL, SCOUT_MODEL.replace('.rgm','.rrgeom'), SCOUT_MODEL.replace('.rgm','.rrmaterial')}
    dispatcher='scar/garrison/chagatai/dispatcher.scar'
    army='attrib/army/garrison/chagatai/chagatai_standard.rgd'
    def original_digest(member):
        raw=(readback/member).read_bytes()
        if member==army:
            doc=rgd.read(raw)
            for variant in (n for n in doc.nodes if n.kind in ('List','List2')):
                bag=child(variant,'army_bag')
                bag.value.remove(child(bag,'ui'))
            if sha(rgd.write(doc)) != baseline['army_gameplay_sha256']:
                raise ValueError('Starting army changed outside presentation fields')
            return baseline['sha256'][army]
        if member.startswith('attrib/ebps/races/chagatai/animals/') and Path(member).stem in {
            'ck_horse', 'ck_horse_ili', 'ck_horse_import'
        }:
            doc = rgd.read(raw)
            for variant in (n for n in doc.nodes if n.kind in ('List', 'List2')):
                if variant.key == 'campaign':
                    continue
                deposit = child(child(variant, 'resource_deposit_ext'), 'initial_amount')
                if deposit.value != 600:
                    raise ValueError(f'Horse deposit does not admit the full Fattened profile: {member}')
                deposit.value = 400.0
            return sha(rgd.write(doc))
        if member==dispatcher:
            statement=b'import("chagatai/building_visuals.scar")'
            eol=b'\r\n' if statement+b'\r\n' in raw else b'\n'
            # Restore only re-applies local selection locks. Pin the rest of
            # the dispatcher, including prematch and starting-army setup.
            restore=b"""        for _,index in ipairs(native.Keys(native.players)) do
            local horses=native.players[index].horses.horses
            for _,id in ipairs(native.Keys(horses)) do
                local horse=horses[id]
                native.LockHorseSelection(horse.nativeID,horse.status=='mount',true)
            end
        end
"""
            import_line=statement+eol
            restore_anchor=b'        pcall(native.RestoreHorseHUD)'+eol
            restore_block=restore_anchor+restore.replace(b'\n',eol)
            if raw.count(import_line)!=1 or raw.count(restore_block)!=1:
                raise ValueError('Missing unique dispatcher addition')
            raw=raw.replace(import_line,b'',1).replace(restore_block,restore_anchor,1)
        return sha(raw)
    mismatches = [member for member, digest in baseline["sha256"].items()
                  if member not in changed_scout and (not (readback / member).is_file() or original_digest(member) != digest)]
    if mismatches:
        raise ValueError(f"The opening differs from {baseline['observed_release']}: {mismatches}")
    stock = stock_game.current().model_files(HORSE, required=(".rgo",))
    if HORSE_IDLE.encode("ascii") not in stock[".rgo"]:
        raise ValueError("The installed Horse animator lacks the opening idle binding")
    return {"matched_release": baseline["observed_release"], "members": len(baseline["sha256"]) - len(changed_scout), "dispatcher_startup_matches_baseline": True, "scout_rig_and_material_verified_separately": True, "army_gameplay_digest_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("zip", "receipt", "visuals", "baseline", "work"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to(ROOT) or not work.is_relative_to(TEMP_ROOT) or work == TEMP_ROOT:
        raise ValueError("Readback scratch must be inside the project scratch folder")
    work.mkdir()
    receipt = json.loads(args.receipt.read_bytes())
    if sha(args.zip.read_bytes()) != receipt["zip_sha256"]:
        raise ValueError("ZIP digest differs from the build receipt")
    with zipfile.ZipFile(args.zip) as bundle:
        if bundle.testzip():
            raise ValueError("Player ZIP failed its CRC check")
        [member] = [name for name in bundle.namelist() if name.endswith(".sga")]
        archive = work / "player.sga"
        archive.write_bytes(bundle.read(member))
    if sha(archive.read_bytes()) != receipt["archive_sha256"]:
        raise ValueError("Player SGA digest differs from the build receipt")
    readback = work / "readback"
    _, members = locate_inventory(stock_game.current(), archive, readback)
    receivers = receipt["visual_receivers"]
    observed = set()
    for path in (p for p in members if p.startswith("attrib/ebps/")):
        name = Path(path).stem
        before = leaves((args.baseline / path).read_bytes())
        after = leaves((readback / path).read_bytes())
        differences = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
        if name not in receivers:
            if differences:
                raise ValueError(f"Out-of-scope EBP change in {name}: {differences}")
            continue
        animator_diffs = {p for p in differences if p.endswith(ANIMATOR + "$PBGNAME")}
        visual_tier_diffs = {p for p in differences if "/tier_ext/" in p and p.endswith("/attachments/$PBGNAME")}
        expected = receivers[name]
        expected = set(expected if isinstance(expected, list) else [expected])
        visual_models = set()
        for p in animator_diffs | visual_tier_diffs:
            binding = after[p][1]
            if not binding and name == "ck_scout_foot_1" and p in visual_tier_diffs:
                continue
            owner, key = binding.split(":", 1)
            if owner != receipt["owner"] or not key.startswith(("ck_no_stamps_", "ck_visual_")):
                raise ValueError(f"Unexpected attachment in {name}: {binding}")
            owned = leaves((readback / (ATTACHMENT + key + ".rgd")).read_bytes())
            if key.startswith("ck_no_stamps_") and any("/stamp_attachment/" in route for route in owned):
                raise ValueError(f"Stock stamp survived in {name}")
            if name == "ck_scout_foot_1" and any(
                "/defense/shield" in value.replace(chr(92), "/") for kind, value in owned.values()
                if kind == "CString"
            ):
                raise ValueError("Foot Scout shield survived in the active attachment")
            references = {value.replace(chr(92), "/") for kind, value in owned.values()
                          if kind == "CString" and value.startswith(ART.replace("/", chr(92)))}
            visual_models.update(references)
        if visual_models != expected:
            raise ValueError(f"Wrong active model in {name}: {visual_models}")
        if isinstance(receivers[name], list) and visual_tier_diffs and name != "ck_scout_foot_1":
            # Every live tier slot, including default/XP3, must stay populated
            # and only the intended art lookup may change in the unit's EBP.
            tier_slots = {p for p, (_, value) in before.items()
                          if "/tier_ext/" in p and p.endswith("/attachments/$PBGNAME") and value}
            if visual_tier_diffs != tier_slots or animator_diffs:
                raise ValueError(f"Missing tier art or changed animation owner in {name}")
        observed.update(visual_models)
        if name.startswith("ck_landmark_") or name == "ck_building_wonder":
            stamps = {p for p in before if p.endswith("/building_presentation_ext/construction_stamp")}
            if not stamps or any(not before[p][1] or before[p] != after.get(p) for p in stamps):
                raise ValueError(f"Missing inherited construction stamp in {name}")
        tier_diffs = differences - animator_diffs - visual_tier_diffs
        if tier_diffs:
            if name not in ("ck_building_melee", "ck_building_ranged"):
                raise ValueError(f"Nonvisual changes in {name}: {tier_diffs}")
            number = 3 if name == "ck_building_melee" else 2
            branch = f"/tier_ext/tier_group_list/tier_group/tier[{number}]/"
            if any(branch not in path or path in before for path in tier_diffs):
                raise ValueError(f"Unexpected age-tier changes in {name}: {tier_diffs}")
            for path in tier_diffs:
                value = after[path][1]
                if path.endswith("/tier_attachment_action") and value != "act_set_current_age_imperial":
                    raise ValueError(f"Wrong Imperial action in {name}")
                if path.endswith("/statetree_tier_requirements_pbg/$PBGNAME") and value != "imperial_age":
                    raise ValueError(f"Wrong Imperial requirement in {name}")
    for path, toc in members.items():
        if path.startswith(("attrib/ebps/", ATTACHMENT, ART)):
            continue
        original = args.baseline / path
        if not original.is_file() or original.read_bytes() != (readback / path).read_bytes():
            raise ValueError(f"Unexpected change to {toc} resource {path}")
    for original in args.baseline.rglob("*"):
        if original.is_file() and original.relative_to(args.baseline).as_posix() not in members:
            raise ValueError(f"Missing original member {original.name}")

    buildings = {row["resource"]: row for row in json.loads((args.visuals / "buildings.json").read_bytes())}
    units = {row["resource"].removesuffix(".rgm") for row in json.loads((args.visuals / "unit-build.json").read_bytes())}
    # These two alternates have no corresponding slot on their original
    # native units. The editable/cooked inputs remain available to future builds.
    alternates = {ART + f"{name}/{name}" for name in
                  ("handcannon_mounted_4_2", "religious_mounted_3_2")}
    inactive = {"art/scenario/chagatai/wonder/model"}
    if observed | alternates != (buildings.keys() - inactive) | units or observed & (alternates | inactive):
        raise ValueError("Unexpected coverage of the custom model inventory")
    opening = verify_opening(readback, args.visuals)
    game = stock_game.current()
    donor_map = rig_donors(args.visuals)
    material_map = material_donors(args.visuals)
    for member, donor in donor_map.items():
        raw = (readback / member).read_bytes()
        stock = game.model_files(donor, required=(".rgm",))[".rgm"]
        if restore_rig(raw, stock) != raw:
            raise ValueError(f"Native rig contract not restored: {member}")
        original = (args.visuals / "art" / member).read_bytes()
        if repair_resource(member, restore_rig(original, stock), material_map, game) != raw:
            raise ValueError(f"Unexpected geometry/skin change: {member}")
    for resource in material_map:
        for extension in ('.rrgeom', '.rrmaterial'):
            member = resource + extension
            original = (args.visuals / 'art' / member).read_bytes()
            if repair_resource(member, original, material_map, game) != (readback / member).read_bytes():
                raise ValueError(f"Incorrect private material contract: {member}")
    from building_color import corrected_textures
    color_textures = corrected_textures(args.visuals, work / 'building-color-readback')
    for member, expected in color_textures.items():
        if (readback / member).read_bytes() != expected:
            raise ValueError(f"Building dye correction absent: {member}")
    tables = {p: rgd.read((readback / p).read_bytes()) for p in members if p.startswith("attrib/ebps/")}
    models = {name: value for name, value in receivers.items() if isinstance(value, str)}
    boxes = building_boxes(tables, game, models)
    for resource in models.values():
        original = (args.visuals/'art'/(resource+'.rgo')).read_bytes()
        if (readback/(resource+'.rgo')).read_bytes() != building_controller(original, buildings[resource]):
            raise ValueError(f"Incorrect native lifecycle controller: {resource}")
        member = resource + '.rgm'
        original = (args.visuals/'art'/member).read_bytes()
        if (readback/member).read_bytes() != repair_resource(member, original, material_map, game):
            raise ValueError(f"Unexpected model changes in {resource}")
    for member, expected in boxes.items():
        if (readback / member).read_bytes() != expected:
            raise ValueError(f"Incorrect footprint blocker: {member}")
    for resource in observed:
        if any(resource + extension not in members for extension in MODEL_EXTENSIONS):
            raise ValueError(f"Incomplete resource set {resource}")
    masks = {resource: verify_model(readback, resource, buildings.get(resource), work / "mask.dds")
             for resource in sorted(observed)}
    summary = {"zip_crc_verified": True, "sga_integrity_verified": True, "active_visual_receivers": len(receivers),
               "skinned_unit_variants": len(observed & units), "buildings": len(buildings),
               "building_state_meshes": sum(len(row['states']) for row in buildings.values()),
               "cooked_player_color_masks_decoded": len(masks),
               "cooked_mask_atlas_texel_range": [round(min(masks.values()), 4), round(max(masks.values()), 4)],
               "original_gameplay_and_presentation_members_verified": True,
               "opening_regression": opening, "stock_rigs_and_skin_binds_verified": len(donor_map), "private_native_materials_verified": len(material_map), "building_blockers_verified": len(boxes), "adjacent_building_passage_world_units": PASSAGE_WIDTH,
               "stable_building_controllers_with_scripted_lifecycle": len(models), "corrected_building_albedo_atlases": len(color_textures)}
    (work / "visual-verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
