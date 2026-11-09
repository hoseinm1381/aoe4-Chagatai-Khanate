"""Stock loose-horse bindings and safe building controller defaults."""
import struct

from compose_buildings import ROOT, find, pack, rc

HORSE = "art/civilizations/common/animals/archetypes/base_horse/base_horse"
HORSE_IDLE = r"calm_idle\idle_calm_01_checkers_d"
HORSE_SELECT = "sfx_horse_idle_whinnies"


def building_controller(raw, record):
    """Restore the tested building controller defaults for the SCAR geometry selectors."""
    doc = rc.parse(raw)
    defaults = find(doc, b"DTBP")
    behaviors = find(doc, b"BBPC")
    actions = find(doc, b"ACTC")
    safe = (ROOT / "authoring/templates/building-lifecycle-defaults.bin").read_bytes()
    extra_states = [state for tier in record.get("age_tiers", {}).values()
                    for state in tier.values()]
    if extra_states:
        _, offset = rc.read_lp_string(safe, 8)
        count, = struct.unpack_from("<I", safe, offset)
        end = offset + 4
        for _ in range(count):
            _, end = rc.read_lp_string(safe, end)
        safe = (safe[:offset] + struct.pack("<I", count+len(extra_states)) +
                safe[offset+4:end] + b"".join(rc.lp_string(s) for s in extra_states) + safe[end:])
    patches = {defaults.offset: safe, behaviors.offset: b"", actions.offset: b""}
    return rc.rebuild(doc,lambda c:patches.get(c.offset))
