"""Draw the native age pips on Chagatai's unique upgrade icons."""
import argparse
from pathlib import Path
import re

from PIL import Image
from build import SOURCE, stock_game
from garrison_shared import rrtex_decoder


UPGRADES = {
    'jida_spearheads': ('races/common/units/spearman_2', 2),
    'yam_logistics': ('races/common/units/scout', 2),
    'compassionate_care': ('races/common/units/monk', 3),
    'lamellar_reinforcement': ('races/common/units/manatarms_3', 4),
}
for family, icon in (('production', 'races/mongols/buildings/pasture'),
                     ('horse_hp', 'races/common/units/scout'),
                     ('livestock', 'gaia/animals/reindeer')):
    UPGRADES.update({f'{family}_{tier}': (icon, tier+1) for tier in range(1, 4)})


def render(work):
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
        for name, (donor, age) in UPGRADES.items():
            image = stock_icon(donor).resize((96, 96), Image.Resampling.LANCZOS)
            if donor.endswith(('spearman_2', 'manatarms_3')):
                image.paste(pips[age], strip[:2])
            else:
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
    finally:
        rrtex_decoder._select_dxgi = stock_decoder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scratch', type=Path)
    render(parser.parse_args().scratch)
