"""Promote the 180-degree building recook and reduced native color atlases."""

import argparse
import json
import re
from pathlib import Path
import shutil
import struct
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from compose_buildings import compose_asset, find, rc, stock_game
from verify_visual_zip import lifecycle_rows
from build import sha
from native_materials import mv
from garrison_shared import rrtex_decoder


def merge_stages(work, lifecycle_root):
    visuals = ROOT / "source/visuals"
    rows = json.loads((visuals / "buildings.json").read_bytes())
    template = ROOT / "authoring/cook-template"
    dest = work / "cook-input"
    shutil.copytree(template, dest, ignore=shutil.ignore_patterns("art", "evidence", "cache", "archives"))
    source = dest / "source"
    prefix = Path("art/scenario/chagatai")
    includes = r"<Includes>([^<]*)</Includes>"
    expected = {state for row in rows for state in row["states"]}
    rules, found = [], set()
    for row in rows:
        asset = row["asset"]
        stage = lifecycle_root / asset if asset in {"pasture", "steppe_hearth"} else work / f"stage-{asset}"
        inputs = stage / "source"
        rules.append((inputs / "_default.burnproj").read_text(encoding="utf-8-sig"))
        for model in (inputs / prefix).iterdir():
            found.add(model.name)
            shutil.copytree(model, source / prefix / model.name)
    assert found == expected, (found - expected, expected - found)
    columns = zip(*(re.findall(includes, rule) for rule in rules), strict=True)
    merged = iter(";".join(dict.fromkeys(item for row in column for item in row.split(";")))
                  for column in columns)
    (source / "_default.burnproj").write_text(
        re.sub(includes, lambda _: "<Includes>" + next(merged) + "</Includes>", rules[0]),
        encoding="utf-8")


def bounds(path):
    model = find(rc.parse(path.read_bytes()), b"MODL")
    return {
        mesh.decoded_name: [
            struct.unpack("<I6f", chunk.payload)[1:]
            for chunk in rc.walk([mesh]) if chunk.tag == b"RFBD"
        ]
        for mesh in model.children if mesh.tag == b"SKMS"
    }


def verify_rotation(previous, rotated):
    before, after = bounds(previous), bounds(rotated)
    assert before.keys() == after.keys(), rotated
    for name, lods in before.items():
        assert len(lods) == len(after[name]) == 3, name
        for (x, y, z, X, Y, Z), box in zip(lods, after[name], strict=True):
            np.testing.assert_allclose(box, (-X, y, -Z, -x, Y, -z), rtol=0, atol=.018,
                                       err_msg=name)


def inspect_texture(previous, current, work):
    fields = ("width", "height", "internal_format", "mip_count")
    dds = work / "texture.dds"
    before = rrtex_decoder.decode_rrtex(previous, dds, validate_stream=True)
    after = rrtex_decoder.decode_rrtex(current, dds, validate_stream=True)
    assert all(before[field] == after[field] for field in fields), (current, before, after)
    return after, np.array(Image.open(dds).convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM))


def promote(archive, work, verify_half_turn):
    visuals = ROOT / "source/visuals"
    source = visuals / "art"
    overlay = visuals / "building-colors-native"
    manifest = overlay / "manifest.json"
    catalog = json.loads((visuals / "buildings.json").read_bytes())
    measurements = {row["asset"]: row for row in json.loads((work / "palette-coverage.json").read_bytes())}
    manifest_rows = [row for row in json.loads(manifest.read_bytes()) if row["asset"] not in measurements]
    assert {row["asset"] for row in manifest_rows} == {"steppe_hearth", "pasture"}
    game = stock_game.current()
    verified = game.archiver.run(["list", str(archive), "--verify"])
    assert verified["archive"]["verification"]["verified"]
    cooked, assembled = work / "read-model-cook", work / "assembled-art"
    game.archiver.run(["extract", str(archive), str(cooked), "--filter", ""])
    writes = {}
    for record in catalog:
        asset, resource = record["asset"], record["resource"]
        state_groups = {mesh.removeprefix(asset + "_"): tuple(state for _, state in states)
                        for mesh, states, _ in lifecycle_rows(record)}
        compose_asset(asset, cooked, assembled, None, states=state_groups)
        model = resource + ".rgm"
        if verify_half_turn:
            verify_rotation(source / model, assembled / model)
        before = rc.parse((source / model).read_bytes())
        after = rc.parse((assembled / model).read_bytes())
        for tag in (b"MRKS", b"SKLN", b"MSBP", b"BANA"):
            assert find(before, tag).payload == find(after, tag).payload, (asset, tag)
        for ext in (".rgm", ".rrgeom"):
            writes[source / (resource + ext)] = assembled / (resource + ext)
        if asset not in measurements:
            continue
        material = mv.material_slots((source / (resource + ".rrmaterial")).read_bytes())
        for role in ("albedoTexture", "patternTex"):
            member = material["textures"][role].replace("\\", "/")
            path = assembled / member
            info, pixels = inspect_texture(source / member, path, work)
            with Image.open(work / "cook-input/source" / Path(member).with_suffix(".png")) as image:
                expected = np.array(image.convert("RGBA"))
            error = np.abs(pixels[:, :, :3].astype(float) - expected[:, :, :3]).mean()
            assert error < 5, (asset, role, error)
            entry = {"asset": asset, "member": member, "sha256": sha(path.read_bytes()),
                     "native_internal_format": info["internal_format"], "mips": info["mip_count"],
                     "mean_compression_error": round(float(error), 4)}
            if role == "patternTex":
                observed = {}
                for sample in measurements[asset]["healthy_lod1_surfaces"]:
                    areas = np.load(work / "surface-samples" / (sample + ".npy"))
                    coverage = float(areas[pixels[:, :, 0] >= 128].sum() / areas.sum())
                    assert .048 <= coverage <= .255, (asset, sample, coverage)
                    observed[sample] = round(coverage, 4)
                entry["cooked_healthy_lod1_owner_color_area"] = observed
            manifest_rows.append(entry)
            writes[overlay / member] = path
    # Retain the previous files and promote only after the entire candidate passes.
    backup = work / "0.2.3-visual-inputs"
    assert not backup.exists()
    for target in [manifest, *writes]:
        if target.is_file():
            destination = backup / target.relative_to(visuals)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
    for target, origin in writes.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    manifest.write_text(json.dumps(manifest_rows, indent=2) + "\n", encoding="utf-8")
    print(f"Verified and promoted {len(catalog)} rotated models and {len(measurements)} palettes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("work", type=Path)
    stage.add_argument("lifecycle_root", type=Path)
    collect = commands.add_parser("promote")
    collect.add_argument("archive", type=Path)
    collect.add_argument("work", type=Path)
    collect.add_argument("--verify-half-turn", action="store_true",
                         help="Compare against the previous facing during a 180-degree migration.")
    args = parser.parse_args()
    if args.command == "stage":
        merge_stages(args.work, args.lifecycle_root)
    else:
        promote(args.archive, args.work, args.verify_half_turn)
