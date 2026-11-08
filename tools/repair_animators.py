"""Stock loose-horse bindings and safe building controller defaults."""
import struct

from compose_buildings import ROOT, find, pack, rc

HORSE = "art/civilizations/common/animals/archetypes/base_horse/base_horse"
HORSE_IDLE = r"calm_idle\idle_calm_01_checkers_d"
HORSE_SELECT = "sfx_horse_idle_whinnies"


def building_controller(raw, game):
    """Preserve the owner-tested 0.1.7 controller; SCAR drives its selectors."""
    doc = rc.parse(raw)
    defaults = find(doc, b"DTBP")
    behaviors = find(doc, b"BBPC")
    actions = find(doc, b"ACTC")
    safe = (ROOT / "authoring/templates/building-lifecycle-defaults.bin").read_bytes()
    age_key = rc.lp_string("current_age_state")
    age_field = None
    if age_key in defaults.payload:
        start = defaults.payload.index(age_key)
        offset = start + len(age_key)
        count, = struct.unpack_from("<I", defaults.payload, offset)
        offset += 4
        for _ in range(count + 1):
            _, offset = rc.read_lp_string(defaults.payload, offset)
        age_field = defaults.payload[start:offset]
    age_actions = [c for c in actions.children if c.decoded_name.startswith("act_set_current_age_")]
    if bool(age_actions) != bool(age_field):
        raise ValueError("The building age state and its actions disagree")
    if age_field:
        safe=safe[:4]+struct.pack('<I',2)+age_field+safe[8:]
    patches = {defaults.offset: safe, behaviors.offset: b"",
               actions.offset: b"".join(pack(c) for c in age_actions)}
    return rc.rebuild(doc,lambda c:patches.get(c.offset))
