"""Check the final archive against the owner-tested 0.1.9 art and SCAR."""
import json
import sys
from pathlib import Path
from build import ROOT, sha


def verify(previous, current, output):
    colors = json.loads((ROOT/'source/visuals/building-colors-native/manifest.json').read_bytes())
    allowed = {r['member'] for r in colors}
    changes = []
    unchanged = 0
    for path in (previous/'art').rglob('*'):
        if not path.is_file():
            continue
        member = path.relative_to(previous).as_posix()
        target = current/member
        assert target.is_file(), member
        if path.read_bytes() != target.read_bytes():
            assert member in allowed, member
            changes.append(member)
        else:
            unchanged += 1
    assert set(changes) == allowed
    for row in colors:
        assert sha((current/row['member']).read_bytes()) == row['sha256']
    scripts = 0
    for path in (previous/'scar').rglob('*.scar'):
        member = path.relative_to(previous)
        assert path.read_bytes() == (current/member).read_bytes(), str(member)
        scripts += 1
    result = dict(changed_art=changes, unchanged_art_files=unchanged,
                  unchanged_scar_files=scripts, building_texture_readback=colors,
                  native_game_tested=False)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print('Only 11 building albedo textures changed; all other art and SCAR match 0.1.9.')


if __name__ == '__main__':
    verify(*(Path(p) for p in sys.argv[1:]))
