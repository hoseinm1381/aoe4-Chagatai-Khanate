"""Rebase only building owner cloth to the working unit's red dye convention.

Source atlases remain immutable. Native texture cooking regenerates compressed
sRGB mip chains; unmasked source texels and alpha are preserved before cooking.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from native_materials import mv
from garrison_shared import rrtex_decoder


def prepare_textures(visuals, work):
    work.mkdir(parents=True, exist_ok=True)
    root = visuals / 'art'
    seen, records = set(), []
    for row in json.loads((visuals / 'buildings.json').read_bytes()):
        tx = mv.material_slots((root / (row['resource'] + '.rrmaterial')).read_bytes())['textures']
        names = {k: tx[k].replace('\\', '/') for k in ('albedoTexture', 'patternTex')}
        name = names['albedoTexture']
        if name in seen:
            continue
        seen.add(name)
        decoded = {}
        for k, member in names.items():
            dds = work / (row['asset'] + k + '.dds')
            rrtex_decoder.decode_rrtex(root / member, dds, validate_stream=True)
            decoded[k] = np.array(Image.open(dds).convert('RGBA'))
        original = decoded['albedoTexture']
        mask = decoded['patternTex'][:, :, 0].astype(np.float32) / 255
        assert original.shape[:2] == mask.shape
        rgb = original[:, :, :3].astype(np.float32)
        # The owner-tested unit's saturated red cloth supplies the dye basis.
        # Retain cloth highlights/shadows through its maximum channel value.
        dye = np.max(rgb, axis=2)[:, :, None] * np.array([1.0, .30, .28])
        changed = original.copy()
        changed[:, :, :3] = np.rint(rgb * (1-mask[:, :, None]) + dye * mask[:, :, None]).astype(np.uint8)
        assert np.array_equal(changed[mask == 0], original[mask == 0])
        assert np.array_equal(changed[:, :, 3], original[:, :, 3])
        im = Image.fromarray(changed)
        target = work / 'source' / Path(name).with_suffix('.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(target)
        records.append(dict(asset=row['asset'], member=name, size=list(im.size),
                            masked_pixels=int(np.count_nonzero(mask)), unmasked_source_pixels_unchanged=True,
                            alpha_unchanged=True))
    (work / 'verification.json').write_text(json.dumps(records, indent=2)+'\n')
    return records


def corrected_textures(visuals, work):
    import hashlib
    root = visuals / 'building-colors-native'
    manifest = json.loads((root / 'manifest.json').read_bytes())
    result = {}
    for row in manifest:
        raw = (root / row['member']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        result[row['member']] = raw
    return result
