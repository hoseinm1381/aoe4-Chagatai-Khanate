"""Build the round Ordu master, with independent construction and damage collections.

Run in background Blender with Pillow and NumPy on sys.path. Pass an output
directory after --. Set CK_ORDU_RENDER=1 to render the review panels.
"""
from math import cos, sin, pi, tau
from pathlib import Path
from random import Random
import os
import sys

import bpy
from mathutils import Vector
import numpy as np
from PIL import Image, ImageDraw

from ordu import Mesh

OUT = Path(sys.argv[-1])
OUT.mkdir(parents=True, exist_ok=True)
STATES = (
    "healthy", "frame00", "frame25", "frame50", "frame75",
    "damage_1", "damage_2", "damage_3", "damage_4", "damage_5", "ruins",
)
# The measured early ger profile is retained. All parts use these joint rings.
ROOF = ((3.22, 3.01, 2.13), (3.23, 3.03, 2.24), (2.70, 2.55, 2.77),
        (1.78, 1.65, 3.38), (.75, .70, 3.91), (.53, .51, 4.10))
WALL = (3.10, 2.91)
SECTORS = 32
DOOR = -pi / 2
# Damage propagates from the entrance's right shoulder across the roof.
DAMAGE_ANGLE = DOOR + .82

CLAY, STONE, FELT, FELT_DARK, WOOD, IRON, TRIM, ORNAMENT, SOOT, ASH, SCORCHED, EMBER = range(12)
MATERIALS = (
    ("Stamped earth", (113, 87, 61)),
    ("Weathered sandstone", (148, 132, 102)),
    ("Ivory felt", (205, 188, 152)),
    ("Warm felt", (168, 138, 96)),
    ("Larch and hide", (91, 57, 33)),
    ("Dark forged iron", (78, 78, 71)),
    ("Owner dyed cloth", (118, 118, 118)),
    ("Embroidered owner border", (113, 113, 113)),
    ("Smoke-stained felt", (91, 75, 57)),
    ("Ash and charcoal", (59, 51, 44)),
    ("Scorched owner cloth", (81, 75, 69)),
    ("Cooling embers", (75, 45, 34)),
)
OWNER = {TRIM, ORNAMENT, SCORCHED}
UV_QUAD = ((.015, .015), (.985, .015), (.985, .985), (.015, .985))


def material(index, name, rgb):
    size = 192
    y, x = np.indices((size, size))
    rng = np.random.default_rng(7315 + index)
    fine = rng.normal(0, 3.3, (size, size))
    weave = 3 * np.sin(x * 2.1) + 2.8 * np.sin(y * 2.8)
    broad = 4 * np.sin(x * .052 + y * .031) + 5 * np.sin(y * .10 - x * .042)
    if index == WOOD:
        weave = 11 * np.sin(x * .49 + 2 * np.sin(y * .036))
    if index in (STONE, CLAY, ASH):
        weave = rng.normal(0, 6, (size, size))
    variation = (fine + weave + broad)[..., None]
    pixels = np.uint8(np.clip(np.array(rgb) + variation, 0, 255))
    albedo = Image.fromarray(pixels).convert("RGBA")
    owner = Image.new("RGB", (size, size), (255 if index in OWNER else 0, 0, 0))
    if index == ORNAMENT:
        ink = ImageDraw.Draw(albedo)
        mask = ImageDraw.Draw(owner)
        for yline in (24, 33, 159, 168):
            ink.line((0, yline, size, yline), fill=(182, 141, 75, 255), width=3)
            mask.line((0, yline, size, yline), fill=(0, 0, 0), width=5)
        for center in range(24, size, 48):
            outer = [(center, 54), (center + 20, 96), (center, 138), (center - 20, 96), (center, 54)]
            inner = [(center, 72), (center + 11, 96), (center, 120), (center - 11, 96), (center, 72)]
            ink.line(outer, fill=(200, 159, 87, 255), width=5)
            ink.line(inner, fill=(174, 124, 61, 255), width=3)
            mask.line(outer, fill=(0, 0, 0), width=7)
            mask.line(inner, fill=(0, 0, 0), width=5)
    elif index == SCORCHED:
        mask = ImageDraw.Draw(owner)
        mask.polygon([(0, 0), (size, 0), (size, 70), (140, 49), (66, 90), (0, 60)], fill=(0, 0, 0))
    elif index == EMBER:
        ink = ImageDraw.Draw(albedo)
        sparks = Random(620)
        for _ in range(52):
            a, b = sparks.randrange(size), sparks.randrange(size)
            ink.ellipse((a, b, a + 4, b + 3), fill=(198, 83, 32, 255))

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = tuple(v / 255 for v in rgb) + (1,)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = .58 if index == IRON else .87
    shader.inputs["Metallic"].default_value = .27 if index == IRON else 0
    textures = []
    for label, bitmap in (("Albedo source", albedo), ("Owner mask", owner)):
        path = OUT / (name.replace(" ", "_") + "_" + label.replace(" ", "_") + ".png")
        bitmap.save(path)
        texture = nodes.new("ShaderNodeTexImage")
        texture.label = label
        texture.image = bpy.data.images.load(str(path))
        if label == "Owner mask":
            texture.image.colorspace_settings.name = "Non-Color"
        texture.image.pack()
        textures.append(texture)
    links.new(textures[0].outputs["Color"], shader.inputs["Base Color"])
    if index in OWNER:
        channels = nodes.new("ShaderNodeSeparateColor")
        links.new(textures[1].outputs["Color"], channels.inputs[0])
        strength = nodes.new("ShaderNodeMath")
        strength.operation = "MULTIPLY"
        strength.inputs[1].default_value = .85
        links.new(channels.outputs["Red"], strength.inputs[0])
        tint = nodes.new("ShaderNodeMixRGB")
        tint.blend_type = "MULTIPLY"
        tint.inputs[2].default_value = (.10, .34, .77, 1)
        tint.label = "Preview owner tint"
        links.new(strength.outputs[0], tint.inputs[0])
        links.new(textures[0].outputs["Color"], tint.inputs[1])
        links.new(tint.outputs[0], shader.inputs["Base Color"])
    if index == EMBER:
        # The native unit shader uses the albedo. Emission is a review light.
        links.new(textures[0].outputs["Color"], shader.inputs["Emission Color"])
        shader.inputs["Emission Strength"].default_value = .19
    return mat


def radial(rx, ry, z, i):
    angle = DOOR + i * tau / SECTORS
    return (rx * cos(angle), ry * sin(angle), z)


def span(i):
    angle = DOOR + (i + .5) * tau / SECTORS
    return abs((angle - DAMAGE_ANGLE + pi) % tau - pi)


def panel(mesh, points, tile):
    # Opposing faces keep the torn fabric legible from the side and inside.
    mesh.part(points, [(0, 1, 2, 3), (3, 2, 1, 0)], tile)


def box(mesh, x, y, z, length, width, height, tile, yaw=0):
    dx, dy = cos(yaw) * length / 2, sin(yaw) * length / 2
    mesh.beam((x - dx, y - dy, z + height / 2), (x + dx, y + dy, z + height / 2),
              width, height, tile)


def foundation(mesh, construction):
    mesh.shell((0, 0), ((3.63, 3.46, -.10), (3.64, 3.47, .04), (3.42, 3.25, .28),
                         (3.31, 3.12, .36)), SECTORS, lambda row, _: STONE if row == 1 else CLAY)
    for i in range(SECTORS):
        a, b = radial(3.51, 3.33, .145, i), radial(3.51, 3.33, .145, i + .88)
        mesh.beam(a, b, .29, .25, STONE if i % 5 else FELT_DARK)
    if construction:
        for y, width, height in ((-3.44, 2.24, .28), (-3.76, 2.24, .18), (-4.07, 2.24, .09)):
            box(mesh, 0, y, 0, width, .38, height, WOOD)
        for side in (-1, 1):
            for j in range(4):
                box(mesh, side * (1.30 + j * .21), -3.49 + j * .24, 0, .23, .28, .15, STONE, .2)


def upper_wall(mesh, level, damage):
    opening = {0, 1, 30, 31}
    reach = (0, .24, .52, .83, 1.36, 2.53, 4)[damage]
    for i in range(SECTORS):
        if i in opening:
            continue
        dist = span(i)
        broken = damage >= 2 and dist < reach
        a, b = radial(*WALL, .36, i), radial(*WALL, .36, i + 1)
        height = (.64 + (i % 5) * .19 if damage < 6 else .42 + (i % 3) * .15) if broken else 2.14
        c, d = (*b[:2], height), (*a[:2], height)
        dark = ASH if broken and damage >= 3 else WOOD
        if not (broken and damage >= 5 and i % 3 == 1):
            mesh.beam(a, d, .082, .081, dark)
            mesh.beam(a, c, .049, .049, dark)
            mesh.beam(b, d, .049, .049, dark)
        if level < 2 or (broken and (damage >= 4 or i % 2 == 0)):
            continue
        skirt = SOOT if damage > 1 and dist < reach + .31 else FELT_DARK
        for lo, hi, tile in ((.39, .56, WOOD), (.56, .84, ORNAMENT), (.84, 1.87, skirt), (1.87, 2.11, FELT)):
            if lo >= height:
                break
            lower = radial(3.12, 2.93, lo, i), radial(3.12, 2.93, lo, i + 1)
            upper = radial(3.12, 2.93, min(hi, height), i + 1), radial(3.12, 2.93, min(hi, height), i)
            panel(mesh, (*lower, *upper), tile if not broken else SOOT)
    if damage < 5:
        post = (-.98, .98)
        for x in post:
            box(mesh, x, -2.79, .32, .23, .25, 1.94, WOOD)
        box(mesh, 0, -2.79, 2.11, 2.28, .28, .18, WOOD)
        if level >= 2:
            box(mesh, 0, -2.95, 2.05, 1.78, .08, .17, ORNAMENT)


def roof(mesh, level, damage):
    reach = (0, .15, .44, .79, 1.35, 2.53, 4)[damage]
    def point(row, i):
        rx, ry, z = ROOF[row]
        distance = span(i % SECTORS)
        sag = max(0., 1 - distance / max(.1, reach + .52))
        collapse = (.0, .04, .11, .38, 1.02, 1.78)[damage]
        if damage == 5:
            collapse += .34
        return radial(rx, ry, z - sag * collapse * (.38 + row * .10), i)

    for i in range(SECTORS):
        if level == 3 and i % 12 > 5:
            # Bare rafters are installed before the felt wraps the dome.
            cover = False
        else:
            cover = True
        distance = span(i)
        exposed = damage >= 2 and distance < reach
        if damage >= 4 and exposed:
            # The broken wall cannot carry any part of the roof in this sector.
            continue
        if not exposed:
            a = point(0, i)
            mesh.beam(radial(*WALL, 2.10, i), a, .071, .073, WOOD)
        for row in range(len(ROOF) - 1):
            a, b = point(row, i), point(row + 1, i)
            if exposed and damage >= 3 and row >= (2 + i % 3):
                break
            mesh.beam((a[0] * .993, a[1] * .993, a[2] - .026),
                      (b[0] * .993, b[1] * .993, b[2] - .026), .057, .051,
                      ASH if damage >= 3 and distance < reach + .25 else WOOD)
        if not cover:
            continue
        for row in range(len(ROOF) - 1):
            if exposed and row >= max(1, 4 - damage + (i % 3)):
                continue
            tile = (ORNAMENT, FELT, FELT, FELT_DARK, TRIM)[row]
            if row in (1, 2, 3) and i % 8 == 0:
                tile = TRIM
            if damage >= 2 and distance < reach + .30:
                tile = SCORCHED if tile in OWNER else SOOT
            corners = (point(row, i), point(row, i + 1), point(row + 1, i + 1), point(row + 1, i))
            if damage == 1 and distance < reach and row == 2:
                # Keep two attached felt flaps at opposite ends of the tear.
                a, b, c, d = (Vector(v) for v in corners)
                panel(mesh, (a, b, b.lerp(c, .21), a.lerp(d, .52)), SOOT)
                panel(mesh, (a.lerp(d, .84), b.lerp(c, .61), c, d), FELT_DARK)
            else:
                panel(mesh, corners, tile)

    if level == 4 and damage < 4:
        lean = (0, 0, .02, .06)[damage]
        mesh.shell((lean, -.5 * lean),
                   ((.56, .54, 4.06 - lean), (.52, .49, 4.20 - lean),
                    (.34, .32, 4.31 - lean), (.29, .28, 4.34 - lean)), 16,
                   lambda row, _: (WOOD, ORNAMENT, IRON)[row], cap=False)
        mesh.shell((lean, -.5 * lean), ((.17, .17, 4.28 - lean), (.19, .19, 4.43 - lean),
                                        (.07, .07, 4.59 - lean)), 10, IRON)


def porch(mesh, damage):
    if damage >= 4:
        return
    far = -3.96
    sides = (-1.06, 1.06)
    for i, x in enumerate(sides):
        height = 1.92 - (.35 if i and damage >= 2 else 0)
        box(mesh, x, far, .08, .14, .15, height - .08, WOOD)
        mesh.beam((x, far, height), (x, -2.74, 2.30), .105, .11, WOOD)
        mesh.beam((x, far, height - .33), (x * .74, far, height), .055, .06, WOOD)
    for x in (-1.13, -.76, -.38, 0, .38, .76):
        width = .38
        if damage >= 2 and x > .16:
            continue
        panel(mesh, [(x, far - .12, 1.97), (x + width, far - .12, 1.97),
                     (x + width, -2.77, 2.34), (x, -2.77, 2.34)],
              TRIM if int(round(x / width)) % 2 else FELT_DARK)
        panel(mesh, [(x, far - .12, 1.80), (x + width, far - .12, 1.81),
                     (x + width, far - .12, 1.97), (x, far - .12, 1.97)], ORNAMENT)


def standard(mesh, x, y, height, direction, scorched=False):
    tile = SCORCHED if scorched else ORNAMENT
    mesh.shell((x, y), ((.23, .23, 0), (.19, .19, .21)), 8, STONE)
    mesh.beam((x, y, .12), (x, y, height), .105, .105, WOOD)
    mesh.shell((x, y), ((.14, .14, height - .28), (.17, .17, height - .15),
                        (.06, .06, height + .10)), 8, IRON)
    for j in range(4):
        u, v = j * .23 * direction, (j + 1) * .23 * direction
        lift = .10 * sin(j * 1.3)
        panel(mesh, [(x + u, y + lift, height - 1.01 + j * .054),
                     (x + v, y + .10 * sin((j + 1) * 1.3), height - .95 + j * .06),
                     (x + v, y + .10 * sin((j + 1) * 1.3), height - .34 - j * .015),
                     (x + u, y + lift, height - .33 - j * .015)], tile)
        if j == 0:
            box(mesh, x + .28 * direction, y, height - .35, .60, .06, .06, WOOD)


def yard(mesh, damage):
    for i, (x, y, h, direction) in enumerate(
        [(-3.67, -2.96, 3.62, -1), (3.67, -2.96, 3.62, 1),
         (-3.46, 2.43, 2.76, -1), (3.46, 2.43, 2.76, 1)]):
        if damage >= (5, 3, 7, 4)[i]:
            continue
        standard(mesh, x, y, h, direction, damage >= 4)
    if damage < 4:
        standard(mesh, 0, 3.57, 6.28, 1)
        box(mesh, 0, 3.57, 5.60, 1.04, .09, .09, IRON)
        for i in range(5):
            x = (i - 2) * .21
            mesh.beam((x, 3.57, 5.64), (x + .075, 3.61, 4.99 + abs(i - 2) * .15),
                      .083, .065, FELT)
    for side in (-1, 1):
        if side > 0 and damage >= 3 or damage >= 6:
            continue
        x, y = side * 2.67, -3.33
        for offset in (-.35, .35):
            mesh.beam((x + offset, y - .21, .04), (x + offset, y + .09, .91), .09, .09, WOOD)
            mesh.beam((x + offset, y + .38, .04), (x + offset, y + .09, .91), .09, .09, WOOD)
        box(mesh, x, y + .09, .81, .89, .09, .10, WOOD)
        for j in range(5):
            a = x + (j - 2) * .13
            mesh.beam((a, y - .20, .06), (a + .15, y + .26, 1.33 + j * .04), .045, .045, WOOD)
            mesh.beam((a + .15, y + .26, 1.32 + j * .04), (a + .17, y + .30, 1.50 + j * .04),
                      .055, .036, IRON)
        box(mesh, side * 3.13, -2.96, .025, .49, .40, .34, WOOD, side * .20)
        for j in (-1, 1):
            box(mesh, side * 3.13 + j * .14, -2.96, .362, .06, .41, .026, IRON)


def rubble(mesh, damage):
    rng = Random(9175)
    for i in range(2 + damage * 4):
        angle = DAMAGE_ANGLE + rng.uniform(-.34 * damage, .34 * damage)
        distance = rng.uniform(1.0, 3.34)
        x, y = cos(angle) * distance, sin(angle) * distance
        z = .38 if distance < 3.21 else .28
        length = rng.uniform(.32, 1.04)
        yaw = rng.uniform(0, tau)
        mesh.beam((x, y, z + .03), (x + cos(yaw) * length, y + sin(yaw) * length, z + .15),
                  .085 + rng.random() * .04, .09, ASH if i % 3 else WOOD)
        if i % 3 == 0:
            panel(mesh, [(x - .13, y - .20, z + .045), (x + .34, y - .18, z + .055),
                         (x + .29, y + .35, z + .08), (x - .07, y + .41, z + .09)],
                  SCORCHED if i % 2 == 0 else SOOT)
    if damage in (4, 5):
        for i in range(damage + 1):
            angle = DAMAGE_ANGLE + (i - 2) * .15
            radius = 1.35 + (i % 3) * .36
            x, y = radius * cos(angle), radius * sin(angle)
            mesh.shell((x, y), ((.19, .11, .38), (.15, .10, .41), (.07, .045, .45)), 6, EMBER)
    if damage >= 4:
        for i in range(4):
            x = .43 + .49 * i
            y = -.48 + .13 * sin(i * 1.8)
            panel(mesh, [(x, y, .42), (x + .49, y + .11, .43),
                         (x + .44, y + .66, .54), (x, y + .61, .43)],
                  SCORCHED if i % 2 else SOOT)
        mesh.shell((.82, -.65), ((.56, .49, .42), (.48, .43, .51), (.30, .27, .69),
                                (.22, .19, .73)), 14, lambda row, _: (ASH, SCORCHED, IRON)[row],
                   cap=False)
        mesh.beam((-.45, 1.15, .49), (-3.71, 1.78, .15), .14, .14, ASH)


def build(state):
    stage = {"frame00": 0, "frame25": 1, "frame50": 2, "frame75": 3}.get(state, 4)
    damage = 6 if state == "ruins" else int(state[-1]) if state.startswith("damage_") else 0
    mesh = Mesh()
    foundation(mesh, stage > 0)
    if stage > 0:
        upper_wall(mesh, stage, damage)
    if stage >= 3 and damage < 6:
        roof(mesh, stage, damage)
    if stage == 4:
        if damage < 5:
            porch(mesh, damage)
        yard(mesh, damage)
    if damage >= 2:
        rubble(mesh, damage)
    if stage < 3:
        for j in range(6 - stage):
            box(mesh, 1.32 + j * .24, 1.08 + j * .05, .36 + .06 * (j % 2), 1.5, .12, .09, WOOD, .55)
    return mesh


def add_state(scene, state, materials):
    mesh = build(state)
    name = f"ordu_{state}"
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    # Keep each material as an individually editable mesh in the master.
    for tile in sorted(set(mesh.tiles)):
        indices = [i for i, material in enumerate(mesh.tiles) if material == tile]
        faces = [mesh.faces[i] for i in indices]
        used = sorted({vertex for face in faces for vertex in face})
        remap = {old: new for new, old in enumerate(used)}
        data = bpy.data.meshes.new(f"{name} / {MATERIALS[tile][0]}")
        data.from_pydata([mesh.vertices[i] for i in used], [],
                         [tuple(remap[v] for v in face) for face in faces])
        data.update()
        data.materials.append(materials[tile])
        uv = data.uv_layers.new(name="UVMap")
        for poly in data.polygons:
            if len(poly.loop_indices) > 4:
                center = poly.center
                radius = max((data.vertices[i].co - center).length for i in poly.vertices)
                for vertex, loop in zip(poly.vertices, poly.loop_indices, strict=True):
                    offset = (data.vertices[vertex].co - center) / radius
                    uv.data[loop].uv = (.50 + .47 * offset.x, .50 + .47 * offset.y)
            else:
                for i, loop in enumerate(poly.loop_indices):
                    uv.data[loop].uv = UV_QUAD[i]
        obj = bpy.data.objects.new(data.name, data)
        collection.objects.link(obj)
    return collection


def review(scene, states, materials):
    preview = bpy.data.collections.new("Preview lighting and ground")
    scene.collection.children.link(preview)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.055))
    floor = bpy.context.object
    for collection in list(floor.users_collection):
        collection.objects.unlink(floor)
    preview.objects.link(floor)
    ground = bpy.data.materials.new("Warm steppe earth")
    ground.use_nodes = True
    ground.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (.30, .27, .20, 1)
    ground.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value = .95
    floor.data.materials.append(ground)
    camera = bpy.data.cameras.new("Review camera")
    camera.type = "ORTHO"
    camera.ortho_scale = 12.9
    rig = bpy.data.objects.new("Review camera", camera)
    preview.objects.link(rig)
    rig.location = (11, -15, 12)
    rig.rotation_euler = (Vector((0, 0, 2.55)) - rig.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = rig
    sun = bpy.data.lights.new("Late-afternoon sun", "SUN")
    sun.energy = 2.4
    sun.angle = .18
    lamp = bpy.data.objects.new(sun.name, sun)
    lamp.rotation_euler = (.43, -.53, -.49)
    preview.objects.link(lamp)
    scene.world = bpy.data.worlds.new("Steppe sky")
    scene.world.color = (.31, .31, .31)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 20
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = (680, 545)
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    for state in ("healthy", "damage_1", "damage_2", "damage_3", "damage_4", "damage_5", "ruins",
                  "frame00", "frame25", "frame50", "frame75", "red"):
        for name, collection in states.items():
            collection.hide_render = name != ("healthy" if state == "red" else state)
        if state == "red":
            for material in materials:
                tint = next((node for node in material.node_tree.nodes if node.label == "Preview owner tint"), None)
                if tint:
                    tint.inputs[2].default_value = (.82, .097, .052, 1)
        scene.render.filepath = str(OUT / (state + ".png"))
        bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene["lifecycle_states"] = ", ".join(STATES)
    scene["design"] = "Original round ger profile with embroidered felt, horse standards and an audience porch"
    materials = [material(i, name, rgb) for i, (name, rgb) in enumerate(MATERIALS)]
    states = {state: add_state(scene, state, materials) for state in STATES}
    for name, collection in states.items():
        collection.hide_viewport = collection.hide_render = name != "healthy"
    # Structural contacts and plot bounds are shared by all health states.
    assert abs(ROOF[0][2] - 2.14) < .02
    for name, collection in states.items():
        vertices = [v.co for obj in collection.objects for v in obj.data.vertices]
        assert min(v.z for v in vertices) >= -.11 and max(v.z for v in vertices) <= 6.4
        assert max(abs(v.x) for v in vertices) <= 4.64 and max(abs(v.y) for v in vertices) <= 4.34
        assert sum(len(obj.data.polygons) for obj in collection.objects) > 50, name
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Chagatai-Ordu-Round.blend"))
    if os.environ.get("CK_ORDU_RENDER") == "1":
        for collection in states.values():
            collection.hide_viewport = False
        review(scene, states, materials)


if __name__ == "__main__":
    main()
