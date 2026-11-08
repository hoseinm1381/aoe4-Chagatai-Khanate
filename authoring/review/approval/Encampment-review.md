# Encampment model review

The packed Blender masters use the installed Mongol Barracks and Archery Range controls. In each file, show the desired age and lifecycle collection in the Outliner. The model collections are named m1_healthy through m4_ruins for Melee and r2_healthy through r4_ruins for Ranged. Preview ground and lighting are separate from asset geometry. Use the material node labeled Owner dye preview to change the Blender swatch. The separate mask image is packed for native export.

The verification JSON measures projected owner-mask coverage from a fixed isometric camera using the first visible mesh surface. It also verifies the finished and ruin collections, their weapon cues, and packed textures. These are Blender checks.

Native staging still needs age-specific LODs and lifecycle selectors. The inherited Mongol building tier group has no Imperial model tier. The installed English production building controls provide a native pattern for an Imperial tier using imperial_age and act_set_current_age_imperial. Preserve the Chagatai production and existing non-art tier groups when wiring it. The player package has not been updated with this art.
