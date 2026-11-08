"""Give each custom atlas a private material and preserve stock shader inputs."""
import json

from compose_buildings import ART, pack, rc
from garrison_shared import model_variants as mv


def material_donors(visuals):
    rows = json.loads((visuals / "units.json").read_bytes())
    donors = {ART + label + "/" + label: donor for row in rows
              if row["blueprint"] not in ("ck_horse", "ck_corpse")
              for donor, label in row["models"].items()}
    template = next(iter(next(r for r in rows if r["blueprint"] == "ck_archer_foot_2")["models"]))
    donors.update({r["resource"]: template for r in json.loads((visuals / "buildings.json").read_bytes())})
    return donors


def material_name(resource):
    return "ck_" + resource.removeprefix(ART).replace("/", "_") + "_atlas"


def rename_slots(raw, name):
    doc = rc.parse(raw)
    changes = {}
    for chunk in rc.walk(doc.roots):
        if chunk.tag in (b"\x00LOD", b"GOHD") and rc.lp_string("main") in chunk.payload:
            changes[chunk.offset] = chunk.payload.replace(rc.lp_string("main"), rc.lp_string(name))
    if not changes and rc.lp_string(name) not in raw:
        raise ValueError("No expected material slots")
    return rc.rebuild(doc, lambda c: changes.get(c.offset))


def stock_material(raw, stock, name):
    textures = {k: v for k, v in mv.material_slots(raw)["textures"].items() if k != "__default"}
    source = rc.parse(stock)
    header = stock[:source.roots[0].offset]
    first = next(c for c in source.roots if c.tag == b"GMat" and b"skinTintLUT" in c.payload)
    if first.tag != b"GMat":
        raise ValueError("Unknown stock material document")
    # One custom atlas serves all LODs. Retain one complete official unit
    # shader block, including its native tint LUT, then bind our cooked maps.
    one = header + pack(first)
    result = mv.rewrite_material(one, textures, {})
    result = rc.rebuild(rc.parse(result), lambda c: rc.Rename(name.encode() + b"\0") if c.tag == b"GMat" else None)
    slots = mv.material_slots(result)["textures"]
    if not slots.get("skinTintLUT") or any(slots[k] != v for k,v in textures.items()):
        raise ValueError("Native tint or custom atlas binding lost")
    return result


def repair_resource(member, raw, donors, game):
    resource, extension = member.rsplit(".", 1)
    if resource not in donors:
        return raw
    name = material_name(resource)
    if extension in ("rgm", "rrgeom"):
        return rename_slots(raw, name)
    if extension == "rrmaterial":
        stock = game.model_files(donors[resource], required=(".rrmaterial",))[".rrmaterial"]
        return stock_material(raw, stock, name)
    return raw
