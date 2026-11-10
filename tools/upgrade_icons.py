"""Draw Chagatai's illustrated technology icons with the native age pips."""
import argparse
from pathlib import Path
import re

from PIL import Image, ImageDraw
from build import SOURCE, stock_game
from garrison_shared import rrtex_decoder
from technology_art import technology_icon


UPGRADES = {
    'jida_spearheads': 2,
    'yam_logistics': 2,
    'compassionate_care': 3,
    'lamellar_reinforcement': 4,
}
for family in ('production', 'horse_hp', 'livestock'):
    UPGRADES.update({f'{family}_{tier}': tier+1 for tier in range(1, 4)})

PAIRED_TIERS = {
    f'tier_{family}_{age}': f'races/common/upgrades/{donor}_{age}'
    for family, donor, ages in (
        ('spearman', 'spearman', (2, 3, 4)),
        ('archer', 'archer', (3, 4)),
        ('nokor', 'manatarms', (3, 4)),
        ('crossbow', 'crossbowman', (4,)),
    )
    for age in ages
}


def paired_badge(image):
    """Mark paired infantry and cavalry research in the bottom-left corner."""
    draw = ImageDraw.Draw(image)
    draw.polygon([(4, 78), (11, 70), (28, 70), (34, 78), (28, 91), (10, 91)],
                 fill='#795226', outline='#bd9661', width=2)
    for x in (11, 20):
        draw.polygon([(x, 84), (x + 4, 77), (x + 7, 77), (x + 3, 84)],
                     fill='#f2d4a0')
    return image


def render(work, paired_only=False):
    work.mkdir(parents=True, exist_ok=True)
    game = stock_game.current()
    assets = SOURCE/'tuning/assets'
    stock_decoder = rrtex_decoder._select_dxgi

    def choose_format(code, name, mip):
        # Native UI format 28 is BC7, confirmed with the installed Spearman icons.
        return (98, 'native_ui_bc7') if code == 28 else stock_decoder(code, name, mip)

    def stock_icon(icon):
        member = 'ui/icons/'+icon+'.rrtex'
        for archive in ('UIArt.sga', 'UIArtLow.sga'):
            try:
                raw = game.member(archive, member)
                break
            except Exception as error:
                if 'member not found' not in str(error):
                    raise
        else:
            raise ValueError(f'Missing stock icon {member}')
        path = work/(icon.replace('/', '_')+'.rrtex')
        path.write_bytes(raw)
        dds = path.with_suffix('.dds')
        rrtex_decoder.decode_rrtex(path, dds, validate_stream=True)
        with Image.open(dds) as source:
            return source.convert('RGBA')

    rrtex_decoder._select_dxgi = choose_format
    try:
        # All four native pips fit in this strip, without any unit silhouette.
        strip = (43, 2, 92, 14)
        pips = {age: stock_icon(f'races/common/units/spearman_{age}').crop(strip)
                for age in (2, 3, 4)}
        icon_dir = assets/'ui/icons/chagatai/upgrades'
        icon_dir.mkdir(parents=True, exist_ok=True)
        for name, age in ({} if paired_only else UPGRADES).items():
            image = technology_icon(name)
            image.alpha_composite(pips[age], strip[:2])
            image.save(icon_dir/(name+'.png'))
            xml = assets/f'attrib/instances/upgrade/races/chagatai/ck_{name}.xml'
            text = xml.read_bytes().decode('utf-8')
            icon_path = 'chagatai\\upgrades\\'+name
            text, count = re.subn(r'(<file name="icon_name" value=")[^"]+',
                                  lambda m: m[1]+icon_path, text)
            if count == 0:
                raise ValueError(f'Missing icon binding for {name}')
            xml.write_bytes(text.encode('utf-8'))
        for name, donor in PAIRED_TIERS.items():
            image = stock_icon(donor).resize((96, 96), Image.Resampling.LANCZOS)
            paired_badge(image).save(icon_dir/(name+'.png'))
            xml = assets/f'attrib/instances/upgrade/races/chagatai/ck_{name}.xml'
            text = xml.read_bytes().decode('utf-8')
            icon = f'<file name="icon_name" value="chagatai\\upgrades\\{name}" overrideParent="True" />'
            if icon not in text:
                text, count = re.subn(r'(?m)^(\t+)<group name="ui_info">(\r?\n)',
                                      lambda m: m[0] + m[1] + '\t' + icon + m[2], text)
                if count != 2:
                    raise ValueError(f'Expected default and xp3 icon bindings for {name}')
                xml.write_bytes(text.encode('utf-8'))
    finally:
        rrtex_decoder._select_dxgi = stock_decoder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scratch', type=Path)
    parser.add_argument('--paired-only', action='store_true')
    args = parser.parse_args()
    render(args.scratch, args.paired_only)
