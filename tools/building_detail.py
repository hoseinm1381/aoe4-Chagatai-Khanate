"""Keep the first detail mesh of each named building part and lifecycle state."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

from garrison_shared import relic_chunky as rc

ONE = struct.pack('<I', 1)


def one(children, tag):
    item, = [c for c in children if c.tag == tag]
    return item


def mesh_triangles(lod):
    count = 0
    for geom in [c for c in lod.children if c.tag == b'GEOM']:
        _, indices = [c.payload for c in geom.children if c.tag == b'GEOB']
        n, _, stride, _ = struct.unpack_from('<4I', indices)
        assert stride in (2, 4) and 16 + n * stride == len(indices) and n % 3 == 0
        count += n // 3
    return count


def single_geometry(raw):
    doc = rc.parse(raw)
    edits = {}
    groups = {}
    for mesh in [c for c in rc.walk(doc.roots) if c.tag == b'MESH']:
        lods = [c for c in mesh.children if c.tag == b'LOD ']
        count = one(mesh.children, b'NBLO')
        assert count.payload == struct.pack('<I', len(lods)) and lods
        names = {rc.read_lp_string(c.payload, 0)[0]
                 for lod in lods for c in rc.walk([lod]) if c.tag == b'GOHD'}
        name, = names
        levels = [mesh_triangles(lod) for lod in lods]
        if name in groups:
            assert len(groups[name]) == len(levels)
            groups[name] = [a+b for a,b in zip(groups[name], levels, strict=True)]
        else:
            groups[name] = levels
        if len(lods) > 1:
            edits[count.offset] = ONE
            edits.update((c.offset, rc.REMOVE) for c in lods[1:])
    return rc.rebuild(doc, lambda c: edits.get(c.offset)), groups


def single_model(raw, groups):
    doc = rc.parse(raw)
    edits = {}
    matched = set()
    for mesh in [c for c in rc.walk(doc.roots) if c.tag in (b'SKMS', b'STMS')]:
        name = mesh.decoded_name
        if name not in groups:
            continue
        matched.add(name)
        total = len(groups[name])
        if total == 1:
            continue
        lod = one(mesh.children, b'LODs')
        count = one(lod.children, b'LODC')
        palettes = [c for c in lod.children if c.tag == b'\0LOD']
        assert count.payload == struct.pack('<I', total) and len(palettes) == total
        assert [rc.read_lp_string(p.payload, 4)[0] for p in palettes] == [
            f'{name}_lod{i}' for i in range(1, total+1)]
        distances = one(mesh.children, b'LODD')
        assert distances.payload[:4] == count.payload and len(distances.payload) == 4*(1+total)
        edits[count.offset] = ONE
        edits[distances.offset] = ONE + distances.payload[-4:]
        edits.update((p.offset, rc.REMOVE) for p in palettes[1:])
        for parent_tag, per_lod_tag in ((b'\0GEO', b'LGEO'), (b'MISC', b'RFBD')):
            parent = one(mesh.children, parent_tag)
            if mesh.tag == b'STMS':
                # Static chunks carry a single collision/auxiliary payload,
                # as in official single-distance STMS resources.
                assert parent.kind == b'DATA'
                continue
            entries = [c for c in parent.children if c.tag == per_lod_tag]
            assert len(entries) == total
            edits.update((c.offset, rc.REMOVE) for c in entries[1:])
    assert {name for name, levels in groups.items() if len(levels) > 1} <= matched
    return rc.rebuild(doc, lambda c: edits.get(c.offset))


def build(native, overlay, stems):
    report = {}
    for stem in sorted(stems):
        source = native / stem
        old_geometry = source.with_suffix('.rrgeom').read_bytes()
        geometry, groups = single_geometry(old_geometry)
        if all(len(levels) == 1 for levels in groups.values()):
            continue
        model_path = source.with_suffix('.rgm')
        old_model = model_path.read_bytes()
        model = single_model(old_model, groups)
        assert model != old_model and geometry != old_geometry
        again, new_groups = single_geometry(geometry)
        assert again == geometry
        assert new_groups == {name: levels[:1] for name, levels in groups.items()}
        assert single_model(model, new_groups) == model
        before = rc.parse(old_model)
        after = rc.parse(model)
        control_tags = (b'MSBP', b'BANA', b'INFO', b'MRKS')
        assert [(c.tag, c.payload) for c in rc.walk(before.roots) if c.tag in control_tags] == [
            (c.tag, c.payload) for c in rc.walk(after.roots) if c.tag in control_tags]
        dest = overlay / stem
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.with_suffix('.rgm').write_bytes(model)
        dest.with_suffix('.rrgeom').write_bytes(geometry)
        report[stem] = {'components': len(groups), 'prior_detail_counts': dict(Counter(map(len, groups.values()))),
                        'triangle_counts_by_mesh': groups, 'archive_payload_delta': len(model)+len(geometry)-len(old_model)-len(old_geometry)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('persia', 'chagatai'))
    parser.add_argument('native', type=Path)
    parser.add_argument('stage', type=Path)
    parser.add_argument('--catalog', type=Path)
    args = parser.parse_args()
    if args.mode == 'persia':
        patterns = ('art/ps100/b/*/*.rrgeom', 'art/ps100/l/*/*.rrgeom',
                    'art/ps100/n/*/*.rrgeom', 'art/ps102/tc/*/*.rrgeom')
        stems = [p.relative_to(args.native).with_suffix('').as_posix()
                 for pattern in patterns for p in args.native.glob(pattern)]
    else:
        stems = [r['resource'] for r in json.loads(args.catalog.read_text(encoding='utf-8'))]
    report = build(args.native, args.stage / 'overlay', stems)
    (args.stage / 'building-detail.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{args.mode}: {len(stems)} models audited, {len(report)} models adjusted', flush=True)


if __name__ == '__main__':
    main()

