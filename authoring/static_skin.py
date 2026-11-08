"""Export a rigid building through the unit shader's one-bone skin stream."""
import re

import bpy
from mathutils import Matrix

ROOT_BONE = "metarig_root"
ROOT_RIG = (
    "[HAVOK SKELETON DEFINITION FILE]\r\n\r\n"
    "[BONES START]\r\nmetarig_root\r\n[END]\r\n\r\n"
    "[PARTITION START]\r\nstatic_lod1 metarig_root metarig_root\r\n[END]\r\n"
)


def export_static_skin(levels, output):
    armature = bpy.data.armatures.new("Building root")
    rig = bpy.data.objects.new("Building root", armature)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armature.edit_bones.new(ROOT_BONE)
    bone.matrix = Matrix.Identity(4)
    bone.length = 1.0
    bpy.ops.object.mode_set(mode="OBJECT")
    try:
        for mesh in levels:
            mesh.vertex_groups.clear()
            group = mesh.vertex_groups.new(name=ROOT_BONE)
            group.add(list(range(len(mesh.data.vertices))), 1.0, "REPLACE")
            mesh.modifiers.new("Rigid building skin", "ARMATURE").object = rig
            mesh.select_set(True)
        result = bpy.ops.export_scene.fbx(
            filepath=str(output), use_selection=True, use_triangles=True,
            object_types={"MESH", "ARMATURE"}, use_mesh_modifiers=False,
            add_leaf_bones=False, bake_anim=False, axis_forward="-Z", axis_up="Y",
            apply_unit_scale=True, use_space_transform=True, apply_scale_options="FBX_SCALE_UNITS",
            primary_bone_axis="Y", secondary_bone_axis="X", armature_nodetype="NULL",
        )
        if result != {"FINISHED"}:
            raise ValueError(f"FBX export failed: {output}")
        output.with_suffix(".rig").write_bytes(ROOT_RIG.encode("ascii"))
    finally:
        bpy.data.objects.remove(rig, do_unlink=True)
        bpy.data.armatures.remove(armature)


def add_rgb_mask_rule(text):
    template = next(m.group() for m in re.finditer(r"<NamedParameters>.*?</NamedParameters>", text, re.S)
                    if "<Name>Static Textures</Name>" in m.group())
    label = "Chagatai RGB Owner Masks"
    native = template.replace("<Name>Static Textures</Name>", f"<Name>{label}</Name>")
    for key, value in {"ColourSpace": "Linear", "PreferredFormat": "BC3", "ForceFormat": "true",
                       "MipmapFilter": "Kaiser", "FlipImage": "true",
                       "ShrinkSingleColorTextures": "false", "PremultiplyAlpha": "false"}.items():
        native, count = re.subn(rf"(<d4p1:{key}>).*?(</d4p1:{key}>)",
                                lambda match: match[1] + value + match[2], native)
        if count != 1:
            raise ValueError(f"Missing native texture parameter {key}")
    rule = (
        "<BurnRule><Alias>data</Alias><Burner>RRTextureBurner</Burner>"
        "<Configurations>Debug Release Profile RTM</Configurations><Excludes></Excludes>"
        r"<Includes>art\scenario\chagatai\*\*_pattern.png</Includes>"
        "<IsEnabled>true</IsEnabled>"
        f"<NamedParameters>{label}</NamedParameters><PathOverride i:nil=\"true\"/>"
        "<Target>Archive</Target></BurnRule>"
    )
    return text.replace("</NamedBurnerParameters>", native + "</NamedBurnerParameters>").replace(
        "</Rules>", rule + "</Rules>")
