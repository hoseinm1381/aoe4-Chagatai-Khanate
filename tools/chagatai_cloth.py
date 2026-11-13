"""Correct landmark cloth in the native atlas using the exact authored UV tiles."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

TOOLS = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(TOOLS))
from art016.repair import encode_bc3
from art037.srgb_landmarks import encode_srgb_bc1
from garrison_shared import rrtex_decoder as rr

# Names come from the approved 0.3.0 Blender masters and their atlas exporter.
CLOTH = {
    'court': ('Court gold and ivory embroidered ridge',),
    'mint': ('030 Royal treasury stamped and woven silk', 'Royal treasury stamped and woven silk',
             'Owner dye on Mint hammered copper and oxide'),
    'qarshi': ('030 Qarshi knotted palace textiles', 'Qarshi knotted palace textiles',
               'Owner dye on 030 Qarshi knotted palace textiles'),
}


def levels(image):
    for i in range(max(image.size).bit_length()):
        size = tuple(max(1, dim >> i) for dim in image.size)
        # The native pattern has unused zero alpha, so resize the channels separately.
        layer = Image.merge('RGBA', tuple(c.resize(size, Image.Resampling.BOX) for c in image.split()))
        with BytesIO() as stream:
            layer.save(stream, format='DDS', pixel_format='DXT5')
            yield *size, stream.getvalue()[128:]


def paint(albedo, pattern, slots, names, reference):
    color = np.asarray(albedo.convert('RGBA')).copy()
    mask = np.asarray(pattern.convert('RGBA')).copy()
    step = color.shape[0] // slots['grid']
    changed = 0
    for name in names:
        x, y = slots['tiles'][name]
        # Content Editor texture origin is at the lower left.
        region = np.s_[color.shape[0]-(y+1)*step:color.shape[0]-y*step, x*step:(x+1)*step]
        rgb = color[region][:,:,:3].astype(float)
        light = rgb @ np.array([.2126,.7152,.0722])
        low, high = np.quantile(light, (.02, .98))
        tone = np.clip((light-low)/max(high-low,12),0,1)
        keep_motif = ('silk' in name.lower() or 'embroidered' in name.lower()
                      or 'textile' in name.lower())
        red = np.full(light.shape, 255, dtype=np.uint8)
        if keep_motif:
            motif = (tone > .80) & ((rgb[:,:,0] - rgb[:,:,2]) > 14)
            red[motif] = 0
        color[region][:,:,:3] = np.where(red[:,:,None]>0,
            np.clip(reference-19+39*tone, 50, 145)[:,:,None], rgb).astype(np.uint8)
        mask[region][:,:,0] = red
        changed += int((red>=128).sum())
    return Image.fromarray(color), Image.fromarray(mask), changed


def run(stage):
    assets = json.loads((stage/'atlas-slots.json').read_text(encoding='utf-8'))
    source = stage/'baseline'
    pictures = stage/'texture-inspection'
    authored = stage/'cloth-masters'
    authored.mkdir(exist_ok=True)
    reference_rgb = np.asarray(Image.open(pictures/'ordu-albedoTexture.dds').convert('RGB'))
    reference_mask = np.asarray(Image.open(pictures/'ordu-patternTex.dds').convert('RGB'))[:,:,0]
    reference = float(np.median(reference_rgb[reference_mask>220]))
    audit = {}
    for asset, names in CLOTH.items():
        before = Image.open(pictures/f'{asset}-albedoTexture.dds')
        mask = Image.open(pictures/f'{asset}-patternTex.dds')
        albedo, pattern, changed = paint(before, mask, assets[asset], names, reference)
        for role, image in (('albedo',albedo),('pattern',pattern)):
            member = f'art/scenario/chagatai/{asset}_healthy/{asset}_healthy_{role}.rrtex'
            image.save(authored/f'{asset}-{role}.png',optimize=True)
            target = stage/'overlay'/member
            target.parent.mkdir(parents=True,exist_ok=True)
            template = ((TOOLS.parent / 'inputs/native/art/kr036/architecture/gyeongbok_palace.rrtex').read_bytes()
                        if role=='albedo' else (source/member).read_bytes())
            result = (encode_srgb_bc1(template,member,image) if role=='albedo'
                      else encode_bc3(template,member.removesuffix('.rrtex'),list(levels(image))))
            target.write_bytes(result)
            readback = authored/f'{asset}-{role}.dds'
            info = rr.decode_rrtex(target, readback, validate_stream=True)
            assert info['mip_count']==12 and info['internal_format']==(19 if role=='albedo' else 22)
            if role=='pattern':
                decoded = np.asarray(Image.open(readback).convert('RGBA'))
                assert (decoded[:,:,0]>=128).sum() > 0
                assert not decoded[:,:,1:].any()
        audit[asset] = {'tinted_atlas_pixels_in_target_tiles': changed, 'ordu_reference_luminance': reference,
                        'authored_tiles': list(names), 'mips_per_texture': 12}
    (stage/'cloth-verification.json').write_text(json.dumps(audit,indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    run(Path(sys.argv[1]))

