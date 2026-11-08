"""Restore native rig metadata and size stock simulation boxes to Chagatai sites."""
import json
import struct
from pathlib import Path

from compose_buildings import ART, find, rc

ANIMATED_FAMILIES = (
    "ck_scout_foot_", "ck_nokor_foot_", "ck_nokor_mounted_", "ck_spearman_mounted_",
    "ck_archer_foot_", "ck_archer_mounted_", "ck_crossbow_mounted_", "ck_handcannon_mounted_",
    "ck_religious_foot_", "ck_religious_mounted_", "ck_villager_mounted_", "ck_trader_foot_",
)
SCOUT_MODEL = ART + "scout_foot_1_1/scout_foot_1_1.rgm"
BOX_DONOR = ("art/civilizations/mongols/layouts/archetypes/"
             "mon_layout_barracks/mon_layout_barracks.simbox")
STOCK_BOX_SIZE = struct.pack("<3f", 4, 4, 4)


def rig_donors(visuals):
    catalog = json.loads((visuals / "units.json").read_bytes())
    return {f"{ART}{label}/{label}.rgm": stock
            for row in catalog if row["blueprint"].startswith(ANIMATED_FAMILIES)
            for stock, label in row["models"].items()}


def bone_names(payload):
    version, count = struct.unpack_from("<II", payload)
    if version != 0 or not 0 < count < 1024:
        raise ValueError("Unknown native skeleton hierarchy")
    offset = 8
    names = []
    for _ in range(count):
        name, offset = rc.read_lp_string(payload, offset)
        names.append(name)
        offset += 2
    return names, payload[:offset]


def skin_records(payload):
    count, = struct.unpack_from("<I", payload)
    offset, records = 4, []
    for _ in range(count):
        name, offset = rc.read_lp_string(payload, offset)
        parent, = struct.unpack_from("<h", payload, offset)
        records.append((name, parent, payload[offset + 2:offset + 42]))
        offset += 42
    if offset != len(payload):
        raise ValueError("Unknown cooked skin palette layout")
    return records


def skeleton_bind_pairs(payload):
    """Resolve full native local reference poses, including unmeshed cloth bones."""
    names, hierarchy = bone_names(payload)
    offset, parents = 8, []
    for name in names:
        _, offset = rc.read_lp_string(payload, offset)
        parents.append(struct.unpack_from("<h", payload, offset)[0])
        offset += 2
    # SKLN's final block is one native local TRS per hierarchy bone.
    start = len(payload) - 40 * len(names)
    if start <= len(hierarchy):
        raise ValueError("Missing native reference pose")
    def mul(a, b):
        x,y,z,w=a; X,Y,Z,W=b
        return (w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
                w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z)
    def rotate(q, v):
        return mul(mul(q, (*v, 0)), (-q[0],-q[1],-q[2],q[3]))[:3]
    globals_, result = [], {}
    for i, name in enumerate(names):
        values = struct.unpack_from("<10f", payload, start + i * 40)
        q,t,s = values[:4],values[4:7],values[7:]
        parent = parents[i]
        if parent >= 0:
            if parent >= i: raise ValueError("Native hierarchy is not parent-first")
            pq,pt,ps=globals_[parent]
            t=tuple(a+b for a,b in zip(pt,rotate(pq,tuple(a*b for a,b in zip(ps,t)))))
            q=mul(pq,q);s=tuple(a*b for a,b in zip(ps,s))
        globals_.append((q,t,s))
        iq=(-q[0],-q[1],-q[2],q[3])
        it=tuple(a/b for a,b in zip(rotate(iq,tuple(-x for x in t)),s))
        result[name]=(struct.pack("<10f",*q,*t,*s),struct.pack("<10f",*iq,*it,*(1/x for x in s)))
    return result


def restore_rig(raw, stock):
    model = rc.parse(raw)
    current = find(model, b"SKLN")
    native = find(rc.parse(stock), b"SKLN")
    names, hierarchy = bone_names(current.payload)
    if hierarchy != bone_names(native.payload)[1]:
        raise ValueError("The cooked rig hierarchy differs from the stock body")
    reference = {}
    for mesh in (c for c in rc.walk(rc.parse(stock).roots) if c.tag == b"SKMS"):
        skin = next(c for c in mesh.children if c.tag == b"SKIN")
        inverse = next(c for c in mesh.children if c.tag == b"SKEL")
        records = skin_records(skin.payload)
        if len(inverse.payload) != len(records) * 40:
            raise ValueError("Unknown native inverse-bind layout")
        for i, (name, parent, bind) in enumerate(records):
            pair = bind, inverse.payload[i * 40:(i + 1) * 40]
            if name in reference and reference[name] != pair:
                raise ValueError(f"Ambiguous native bind for {name}")
            reference[name] = pair
    # A combined custom mesh can weight a native cloth bone unused by the
    # donor's mesh palettes. Its full stock skeleton still owns the bind pose.
    full_reference = skeleton_bind_pairs(native.payload)
    for name, pair in reference.items():
        expected = struct.unpack("<10f", full_reference[name][0])
        actual = struct.unpack("<10f", pair[0])
        if max(abs(a-b) for a,b in zip(expected[4:], actual[4:])) > 0.0001:
            raise ValueError(f"Native reference pose disagrees for {name}")
    patches = {current.offset: native.payload}
    for mesh in (c for c in rc.walk(model.roots) if c.tag == b"SKMS"):
        skin = next(c for c in mesh.children if c.tag == b"SKIN")
        inverse = next(c for c in mesh.children if c.tag == b"SKEL")
        records = skin_records(skin.payload)
        binds, inverses = [], []
        for name, parent, bind in records:
            if name not in names:
                raise ValueError(f"Weight palette uses an unknown bone: {name}")
            native_bind, native_inverse = reference.get(name, full_reference[name])
            # Palette order and parent indices belong to the custom vertex stream.
            binds.append(rc.lp_string(name) + struct.pack("<h", parent) + native_bind)
            inverses.append(native_inverse)
        patches[skin.offset] = struct.pack("<I", len(records)) + b"".join(binds)
        patches[inverse.offset] = b"".join(inverses)
    return rc.rebuild(model, lambda c: patches.get(c.offset))


PASSAGE_WIDTH = 2.0


def opening_box(raw, width, depth, scale=1.0):
    model = rc.parse(raw)
    data = find(model, b"AEGD")
    if data.version != 3 or data.payload.count(STOCK_BOX_SIZE) != 2:
        raise ValueError("Unexpected stock impass and default simulation boxes")
    # Reserve one world unit at each site edge: adjacent sites leave a
    # two-unit passage. Divide out animator scale (e.g. landmarks at 125%).
    if min(width, depth) <= PASSAGE_WIDTH or scale <= 0:
        raise ValueError("Invalid building clearance or animator scale")
    replacement = struct.pack("<3f", (width-PASSAGE_WIDTH)/scale, 4, (depth-PASSAGE_WIDTH)/scale)
    payload = data.payload.replace(STOCK_BOX_SIZE, replacement)
    return rc.rebuild(model, lambda c: payload if c.offset == data.offset else None)


def building_boxes(tables, game, models):
    from bind_art import node, variants

    template = game.member("Data.sga", BOX_DONOR)
    out = {}
    for member, doc in tables.items():
        name = Path(member).stem
        if not member.startswith("attrib/ebps/") or name not in models:
            continue
        sizes = set()
        for variant in variants(doc):
            size = node(node(variant, "site_ext"), "footprint_scale")
            impass = node(variant, "impass_ext")
            if not node(node(impass, "impass_simboxes"), "default_simbox").value:
                raise ValueError(f"{name} does not consume its default simulation box")
            scale = node(node(variant, "entity_blueprint_ext"), "animator_scale").value / 100
            sizes.add((node(size, "x").value, node(size, "y").value, scale))
        [(width, depth, scale)] = sizes
        if min(width, depth) <= 0:
            raise ValueError(f"{name} has no valid build footprint")
        out[models[name] + ".simbox"] = opening_box(template, width, depth, scale)
    if len(out) != len(models):
        raise ValueError("Missing building simulation boxes")
    return out
