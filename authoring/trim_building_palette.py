"""Reduce the red owner mask to trim on staged Chagatai building atlases."""

import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from building_color import neutral_cloth

ASSETS = ("almaliq", "ordu", "qarshi", "court", "ili", "mint", "melee", "ranged", "wonder")


def edge_distances(mask):
    """Measure the width of owner-mask islands in atlas texels."""
    inside = np.pad(mask, 1, constant_values=False)
    x = np.arange(inside.shape[1])
    left = x - np.maximum.accumulate(np.where(inside, -1, x), axis=1)
    right = np.minimum.accumulate(np.where(inside, inside.shape[1], x)[:, ::-1], axis=1)[:, ::-1] - x
    distance = np.minimum(left, right).T
    y = np.arange(distance.shape[1])
    up = y + np.minimum.accumulate(distance - y, axis=1)
    down = np.minimum.accumulate((distance + y)[:, ::-1], axis=1)[:, ::-1] - y
    return np.minimum(up, down).T[1:-1, 1:-1]


def apply(work, asset):
    atlas = work / f"stage-{asset}" / "source/art/scenario/chagatai" / f"{asset}_healthy"
    albedo = atlas / f"{asset}_healthy_albedo.png"
    pattern = atlas / f"{asset}_healthy_pattern.png"
    with Image.open(albedo) as image:
        base = np.array(image.convert("RGBA"))
    with Image.open(pattern) as image:
        masks = np.array(image.convert("RGBA"))
    owner = masks[:, :, 0].copy()
    distances = edge_distances(owner >= 128)
    distance_index = distances.flatten()
    samples = sorted((work / "surface-samples").glob(f"{asset}*_healthy.npy"))
    curves = []
    for sample in samples:
        areas = np.load(sample).flatten()
        coverage = np.bincount(distance_index, weights=areas, minlength=distances.max() + 1)
        curves.append(np.cumsum(coverage[1:]) / areas.sum())
    curves = np.array(curves)
    target = np.clip(curves[:, -1].mean() * .4, .055, .18)
    candidates = np.flatnonzero(((curves >= .05) & (curves <= .25)).all(axis=0))
    if not candidates.size:
        raise ValueError(f"{asset} has no shared trim width in the target range")
    width = candidates[np.argmin(np.abs(curves[:, candidates].mean(axis=0) - target))] + 1
    kept = (distances > 0) & (distances <= width)
    masks[:, :, 0] = np.where(kept, owner, 0)
    Image.fromarray(neutral_cloth(base, masks[:, :, 0])).save(albedo)
    Image.fromarray(masks).save(pattern)
    return {
        "asset": asset, "trim_width_atlas_pixels": int(width),
        "healthy_lod1_surfaces": {
            sample.stem: {"previous_mask_coverage": round(float(curve[-1]), 4),
                          "trim_mask_coverage": round(float(curve[width - 1]), 4)}
            for sample, curve in zip(samples, curves, strict=True)
        },
    }


if __name__ == "__main__":
    work = Path(sys.argv[1])
    receipt = [apply(work, asset) for asset in ASSETS]
    (work / "palette-coverage.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
