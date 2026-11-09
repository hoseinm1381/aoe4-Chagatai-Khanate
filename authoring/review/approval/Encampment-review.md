# Encampment model review

The packed Blender masters use the installed Mongol Barracks and Archery Range controls. In each file, show the desired age and lifecycle collection in the Outliner. The model collections are named m1_healthy through m4_ruins for Melee and r2_healthy through r4_ruins for Ranged. Preview ground and lighting are separate from asset geometry. Use the material node labeled Owner dye preview to change the Blender swatch. The separate mask image is packed for native export.

The verification JSON measures projected owner-mask coverage from a fixed isometric camera using the first visible mesh surface. It also verifies the finished and ruin collections, their weapon cues, and packed textures. These are Blender checks.

For 0.2.1, stage the packed master with `authoring/reviewed-landmarks/stage_age_encampment.py`. Cook the staged project and pass its archive to `tools/compose_encampments.py`. This produces one model per encampment with all its age-specific construction, completed and rubble meshes. The composed atlases contain neutral player-color cloth. Keep them with the matching model and replace the record in `source/visuals/buildings.json`.

The package uses a single lifecycle state field for age and construction. The existing presentation tick selects it from the owner's age and the building's condition. Age transitions still require in-game verification.
