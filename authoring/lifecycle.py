"""Native lifecycle graft adapted from the Korea Garrison landmark pipeline."""
import struct

def graft(source, donor, rc):
    original, official = (rc.parse(raw) for raw in (source, donor))
    def chunk(doc, tag):
        matches = [c for c in rc.walk(doc.roots) if c.tag == tag]
        assert len(matches) == 1, tag
        return matches[0]
    def lp(raw, offset):
        return rc.read_lp_string(raw, offset)
    def default_fields(raw):
        assert raw[:4] == bytes(4)
        offset = 8
        enums, floats = {}, {}
        for _ in range(struct.unpack_from('<I', raw, 4)[0]):
            start = offset
            name, offset = lp(raw, offset)
            count, = struct.unpack_from('<I', raw, offset)
            offset += 4
            for _ in range(count):
                _, offset = lp(raw, offset)
            _, offset = lp(raw, offset)
            enums[name] = raw[start:offset]
        count, = struct.unpack_from('<I', raw, offset)
        offset += 4
        for _ in range(count):
            start = offset
            name, offset = lp(raw, offset)
            offset += 12
            floats[name] = raw[start:offset]
        return enums, floats, raw[offset:]
    def pack(c):
        return rc.pack_chunk(c.kind, c.tag, c.payload, version=c.version, name=c.name)
    dtbp = chunk(original, b'DTBP')
    enums, floats, tail = default_fields(dtbp.payload)
    official_enums, official_floats, _ = default_fields(chunk(official,b'DTBP').payload)
    assert set(enums) == {'life_cycle_state'} and not floats
    assert enums['life_cycle_state'] == official_enums['life_cycle_state']
    defaults = (struct.pack('<II',0,3) + enums['life_cycle_state']
        + official_enums['life_cycle_state_previous'] + official_enums['preview']
        + struct.pack('<I',2) + official_floats['health'] + official_floats['build'] + tail)
    triggers = {}
    for variant in chunk(official,b'BBPC').children:
        cond, action = variant.children
        assert (cond.tag,action.tag)==(b'CNBP',b'BBPD')
        name, _ = lp(action.payload,0)
        if name.startswith('set_lifecycle_'):
            assert name not in triggers
            triggers[name] = variant
    actions = {a.decoded_name:a for a in chunk(official,b'ACTC').children if a.decoded_name in triggers}
    assert set(actions)==set(triggers) and len(actions)==29
    for name, action in actions.items():
        count, = struct.unpack_from('<I',action.payload)
        assert count==(1 if "construct_" in name else 2)
        offset=4
        for key in ('life_cycle_state','life_cycle_state_previous')[:count]:
            opcode,offset=lp(action.payload,offset)
            assert opcode=='setstate'
            assert struct.unpack_from('<I',action.payload,offset)[0]==2
            offset+=4
            attr,offset=lp(action.payload,offset)
            var,offset=lp(action.payload,offset)
            assert (attr,var)==('StateMachine',key)
            attr,offset=lp(action.payload,offset)
            state,offset=lp(action.payload,offset)
            assert attr=='State' and state in (
                ['healthy','ruins','preview','targeting']
                + [f'construct_{i:02}' for i in range(0,100,5)]
                + [f'damage_{i}' for i in range(1,6)])
            offset+=4
        assert offset==len(action.payload)
    bbpc, actc = chunk(original,b'BBPC'), chunk(original,b'ACTC')
    assert not bbpc.children and not actc.children
    patches = {dtbp.offset:defaults, bbpc.offset:b''.join(map(pack,triggers.values())),
               actc.offset:b''.join(map(pack,actions.values()))}
    output = rc.rebuild(original, lambda c: patches.get(c.offset))
    verified = rc.parse(output)
    assert len(chunk(verified,b'BBPC').children)==29 and len(chunk(verified,b'ACTC').children)==29
    assert all(chunk(verified,tag).payload == chunk(original,tag).payload
               for tag in (b'INFO',b'EVCT',b'STRT',b'CUAT'))
    return output

