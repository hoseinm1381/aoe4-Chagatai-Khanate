
"""Weight staged atlas texels by visible LOD1 triangle surface area."""
from pathlib import Path
import sys

import bpy
import numpy as np
from PIL import Image

work = Path(sys.argv[-1])
for folder in sorted(work.glob('stage-*/source/art/scenario/chagatai/*_healthy')):
    fbx = folder / (folder.name + '.fbx')
    key = folder.relative_to(work).parts[0].removeprefix('stage-')
    pattern = folder.parent / (key+'_healthy') / (key+'_healthy_pattern.png')
    if not fbx.is_file() or not pattern.is_file():
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    [obj] = [o for o in bpy.data.objects if o.type == 'MESH' and 'lod1' in o.name.lower()]
    data = obj.data
    data.calc_loop_triangles()
    coords = data.uv_layers.active.data
    triangles = np.array([[tuple(coords[i].uv) for i in t.loops] for t in data.loop_triangles])
    areas = np.array([t.area for t in data.loop_triangles])
    # Deterministic, low-discrepancy area quadrature for each UV triangle.
    samples = 196
    a = np.sqrt((np.arange(samples) + .5) / samples)
    b = (np.arange(samples) * .6180339887498949) % 1
    weights = np.array([1 - a, a * (1 - b), a * b]).T
    uvs = np.einsum('sk,tkd->tsd', weights, triangles)
    w,h = Image.open(pattern).size
    xy = np.floor(uvs * (w, h)).astype(np.int32)
    x = xy[:, :, 0].clip(0,w-1)
    y = xy[:, :, 1].clip(0,h-1)
    pixels = y*w+x
    target = work/'surface-samples'/folder.name
    target.parent.mkdir(exist_ok=True)
    density = np.bincount(pixels.flatten(), weights=np.repeat(areas / samples, samples), minlength=w*h)
    np.save(target, density.reshape(h,w).astype(np.float32))
    with Image.open(pattern) as image:
        mask = np.asarray(image.convert('RGB'))[:,:,0] >= 128
    d = density.reshape(h,w)
    print(folder.name, 'current tint area',round(d[mask].sum()/d.sum(),3), 'flipped', round(d[mask[::-1]].sum()/d.sum(),3),flush=True)
