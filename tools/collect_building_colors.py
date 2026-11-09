"""Collect a native texture-only cook, checking format, orientation and pixels."""
import sys
import json
import uuid
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
from build import ROOT, SOURCE, TEMP_ROOT, stock_game, sha
from garrison_shared import rrtex_decoder as decoder


def collect(archive, work):
    root = SOURCE / 'visuals'
    dest = root / 'building-colors-native'
    dest.mkdir(exist_ok=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    extracted = TEMP_ROOT / ('chagatai-colors-' + uuid.uuid4().hex)
    stock_game.current().archiver.run(['extract', str(archive), str(extracted), '--filter', 'art/'])
    rows = json.loads((work / 'verification.json').read_bytes())
    for row in rows:
        member = row['member']
        path = extracted / member
        current = decoder.decode_rrtex(path, work/'cooked.dds', validate_stream=True)
        original = decoder.decode_rrtex(root/'art'/member, work/'original.dds', validate_stream=True)
        for key in ('width', 'height', 'internal_format', 'mip_count'):
            assert current[key] == original[key], (member, key, current[key], original[key])
        actual = np.asarray(Image.open(work/'cooked.dds').convert('RGBA')).astype(float)
        expected = np.asarray(Image.open(work/'source'/Path(member).with_suffix('.png'))
                              .transpose(Image.Transpose.FLIP_TOP_BOTTOM)).astype(float)
        error = float(np.mean(np.abs(actual - expected)))
        assert error < 3, (member, error)
        row.update(sha256=sha(path.read_bytes()), native_internal_format=current['internal_format'],
                   mips=current['mip_count'], mean_compression_error=error)
    for row in rows:
        target = dest / row['member']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted / row['member'], target)
    (dest/'manifest.json').write_text(json.dumps(rows, indent=2)+'\n')
    print([(row['asset'], row['mean_compression_error']) for row in rows])


if __name__ == '__main__':
    collect(Path(sys.argv[1]), Path(sys.argv[2]))
