"""Bind six compiled landmark models to the Normal tuning archive."""
import argparse
from collections import defaultdict
from pathlib import Path
import os
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
EXT = Path(os.environ.get("GARRISON_EXTENSION", Path(os.environ["APPDATA"]) /
           "Blender Foundation/Blender/5.2/extensions/raw_githubusercontent_com/garrison"))
sys.path.insert(0, str(EXT))
from garrison_shared import derived_blueprints, mod_content, relic_chunky as rc, rgd, stock_game

MOD_ID = "9fb54312-599d-4721-8eef-70ad08c75e33"
OWNER = MOD_ID.replace("-", "")
ROLES = ("almaliq", "ordu", "qarshi", "court", "ili", "mint")
ART = "art/scenario/chagatai/"
SOURCE = ROOT / "chagatai_khanate/assets"
BOX_DONOR = ("art/civilizations/mongols/layouts/archetypes/"
             "mon_layout_barracks/mon_layout_barracks.simbox")


def node(document, key):
    children = document.nodes if hasattr(document, "nodes") else document.value
    return next(c for c in children if c.key == key or c.hash == rgd.dictionary_hash(key))


def at(document, *keys):
    for key in keys:
        document = node(document, key)
    return document


def variants(document):
    return (item for item in document.nodes if item.kind in ("List", "List2"))


def omit_stamps(group):
    if group.kind in ("List", "List2"):
        group.value[:] = [child for child in group.value if child.key != "stamp_attachment"]
        for child in group.value:
            omit_stamps(child)


def simbox(game, document):
    sizes = set()
    for variant in variants(document):
        site = at(variant, "site_ext", "footprint_scale")
        scale = at(variant, "entity_blueprint_ext", "animator_scale").value / 100
        assert at(variant, "impass_ext", "impass_simboxes", "default_simbox").value
        sizes.add((node(site, "x").value, node(site, "y").value, scale))
    [(width, depth, scale)] = sizes
    assert width > 2 and depth > 2 and scale > 0
    model = rc.parse(game.member("Data.sga", BOX_DONOR))
    [box] = [c for c in rc.walk(model.roots) if c.tag == b"AEGD"]
    old = struct.pack("<3f", 4, 4, 4)
    assert box.version == 3 and box.payload.count(old) == 2
    size = struct.pack("<3f", (width-2)/scale, 4/scale, (depth-2)/scale)
    return rc.rebuild(model, lambda c: box.payload.replace(old, size) if c.offset == box.offset else None)


def attach(base, output, work):
    work.mkdir()
    game = stock_game.current()
    archiver = game.archiver
    def inventory(path):
        info = archiver.run(["list", str(path), "--verify"])
        assert info["archive"]["verification"]["verified"]
        return {row["path"]: row["toc"] for row in info["members"]}

    before = inventory(base)
    stock = defaultdict(list)
    for path in game.blueprint_index(work / "stock-index"):
        if path.startswith("attachments/attachment_lists/"):
            stock[Path(path).name].append(path)

    def derive(name, reference):
        choices = stock[reference]
        if len(choices) > 1:
            choices = [p for p in choices if "/mongol/" in p]
        [donor] = choices
        generated, _ = derived_blueprints.build(
            [{"name": name, "family": "attachments/attachment_lists", "source": donor, "changes": []}],
            {donor: game.blueprint(donor)}, mod_id=MOD_ID, mod_key="chagatai_khanate",
            pbgid=mod_content.pbgid, owner=OWNER)
        [(path, (_, raw))] = generated.items()
        member = f"attrib/{path}.rgd"
        assert member not in before
        return member, rgd.read(raw)

    bindings, art = {}, {}
    filtered = {}
    original = work / "original"
    archiver.run(["extract", str(base), str(original), "--filter", "ck_landmark_"])
    for role in ROLES:
        [member] = [p for p in before if p.startswith("attrib/ebps/") and
                    p.endswith(f"/ck_landmark_{role}.rgd")]
        doc = rgd.read((original / member).read_bytes())
        stem = ART + role + "/model"
        refs = [at(v, "entity_blueprint_ext", "animator_attachments", "$PBGNAME") for v in variants(doc)]
        [donor] = {ref.value for ref in refs}
        name = "ck_visual_" + role
        path, private = derive(name, donor)
        for v in variants(private):
            at(v, "attachment_lists", "parent_animator").value = stem.replace("/", "\\")
        bindings[path] = rgd.write(private)
        for ref in refs:
            ref.value = OWNER + ":" + name
        for v in variants(doc):
            for route, field in rgd.flatten(v.value):
                if route.startswith("tier_ext/") and route.endswith("/attachments/$PBGNAME") and field.value:
                    key = field.value
                    if key not in filtered:
                        filtered[key] = "ck_no_stamps_" + key
                        path, private = derive(filtered[key], key)
                        for part in variants(private):
                            omit_stamps(part)
                        bindings[path] = rgd.write(private)
                    field.value = OWNER + ":" + filtered[key]
        bindings[member] = rgd.write(doc)
        art[stem + ".simbox"] = simbox(game, doc)
        for extension in (".rgo", ".rgm", ".rrgeom", ".rrmaterial"):
            asset = stem + extension
            art[asset] = (SOURCE / asset).read_bytes()
        textures = list((SOURCE / ART / (role+"_healthy")).glob("*.rrtex"))
        assert textures
        for texture in textures:
            art[texture.relative_to(SOURCE).as_posix()] = texture.read_bytes()

    def write_members(source, dest, files, alias):
        paths = []
        for member, payload in sorted(files.items()):
            path = work / alias / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            paths.append(f"{member}={path}")
        manifest = work / (alias + ".txt")
        manifest.write_text("\n".join(paths) + "\n", encoding="utf-8")
        archiver.run(["set-members", str(source), str(manifest), str(dest), "--alias", alias])

    attrs = work / "attributes.sga"
    write_members(base, attrs, bindings, "attrib")
    write_members(attrs, output, art, "data")
    assert inventory(output) == (before | dict.fromkeys(bindings, "attrib") | dict.fromkeys(art, "data"))
    for alias, payloads in (("attrib/attachments/attachment_lists/garrison/chagatai_khanate", bindings),
                            ("ck_landmark_", bindings), (ART, art)):
        dest = work / "readback"
        archiver.run(["extract", str(output), str(dest), "--filter", alias])
        for member, payload in payloads.items():
            if alias in member:
                assert (dest / member).read_bytes() == payload, member
    for filter_ in ("ck_court.rgd", "ck_nokor.rgd", "ui/icons/chagatai/"):
        archiver.run(["extract", str(output), str(dest), "--filter", filter_])
    for name, seconds in (("court", 180), ("nokor", 60)):
        [member] = [p for p in before if p.startswith("attrib/abilities/") and p.endswith(f"/ck_{name}.rgd")]
        assert all(at(v, "ability_bag", "recharge_time").value == seconds
                   for v in variants(rgd.read((dest / member).read_bytes())))
    icons = [p.relative_to(SOURCE).with_suffix(".rrtex")
             for family in ("landmarks", "upgrades")
             for p in (SOURCE / "ui/icons/chagatai" / family).glob("*.png")]
    assert len(icons) == len({(dest / p).read_bytes() for p in icons}) == 27
    print(f"Verified six Normal landmark bindings and {len(art)} model, texture and simulation resources.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "output", "work"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    attach(args.base, args.output, args.work)

