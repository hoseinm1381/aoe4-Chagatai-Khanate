# Chagatai Khanate for Garrison

An independent Age of Empires IV civilization by hosein81 and chilly5. Import the 0.2.4 playable ZIP through Garrison and select Chagatai Khanate in Standard Skirmish with Tuning Pack None. See [START-HERE.md](START-HERE.md).

0.2.4 turns all 11 custom structures by 180°, enlarges the Ranged Encampment by 40% visually, and uses the original material colors with player-color trim on nine structures. The era shown in Garrison and the game is 1227–1705 CE.

0.2.3 restores the working 0.2.1 construction stamps and building animators after the 0.2.2 loading crash. The fire and scaffolding changes are deferred.

0.2.1 adds illustrated bonuses, a fuller unique technology list, and stock age pips for the unique upgrades. The Town Center column no longer lists Horses. The six age-up landmarks render 40% larger with compensated collision bounds, and the encampments use their separate age models.

## Editable source

- `source/tuning/` contains the Content Editor project, attributes, localization and SCAR.
- `source/presentation/` contains civilization images. `source/authoring-profile.json` defines the identity and opening roster.
- `authoring/review/approval/` contains the reviewed Blender masters. The Wonder master is `authoring/Chagatai-buildings.blend`.
- `source/visuals/` contains the active cooked assets, their binding inventories and the verified building color overlay. Keep them with the editable masters for reproducible assembly.

## Build

Use Windows, an installed copy of AoE4, the Garrison Blender extension and Kit Content Editor, and Python 3.13 with Pillow, NumPy and Lupa. Set `GARRISON_EXTENSION` if the extension lives outside the standard Blender 5.2 path.

```powershell
python -m pip install -r .tools/requirements-python313.txt
./Build.ps1 -Python python
```

Pass `-Editor` to select a different model-capable editor and `-Scratch` to use a short local work path. The build generates fresh carrier and tuning cooks, assembles them with the retained art, checks the package, and writes the player ZIP to `release/`. See [BUILD-VERIFICATION.json](BUILD-VERIFICATION.json) for the package receipt.

## Recook edited art

- **Reviewed units.** Set `CK_ROOT` to this project and `CK_RUN` to a fresh scratch run. Supply Python 3.13 Pillow to background Blender and run `authoring/reviewed-units/export.py`. It writes `CK_RUN/reviewed-unit-fbx`. Run `authoring/reviewed-units/stage.py <fbx-directory> authoring/cook-template <stage-directory>` with Python. Cook the staged `garrison_static.aoe4mod` using `garrison-core essence build-mod` and the Kit editor. Pass the archive, a copy of `source/visuals/units.json` filtered to the cooked blueprints, and a fresh output directory to `tools/compose_units.py`. Promote only the returned model folders and their matching `unit-build.json` rows. The same exporter covers the reviewed loose Horse.
- **Landmarks.** Follow the recipes under `authoring/reviewed-landmarks` to stage the packed masters, cook each model, and compose its lifecycle selectors. Retain the matching record in `source/visuals/buildings.json` with the active art.
- **Encampments.** Use the landmark recipe environment and run `authoring/reviewed-landmarks/stage_age_encampment.py -- melee` or `-- ranged` in background Blender. Cook the resulting project with the Kit editor. Run `tools/compose_encampments.py <melee-or-ranged> <fresh-sga> <output-directory>` and promote the model resources and matching manifest row together.
- **Pasture and Hearth.** Use `authoring/reviewed-lifecycle/Stage-ReviewedBuildings.ps1` to regenerate each Content Editor project and its atlas from the lifecycle masters. Cook separately and compose each with `tools/compose_buildings.py`.
- **Wonder.** Generate an atlas with `authoring/ordu_atlas.py` and run `authoring/stage_building_states.py` with the Wonder key. Cook that staged project with the Kit editor and compose the result with `tools/compose_buildings.py`.

For the building color cook, follow [the texture recipe](authoring/building-colors-0.1.10/README.md). Run the full build after promoting new art to verify the bindings and package.

To recook the 0.2.4 facing, set `CK_REVERSE_BUILDING_FACING=1` before running the building staging recipes. Set `CK_KEEP_DEFAULT_CLOTH=1` for the Encampments to keep their original albedo during staging. Run `authoring/sample_building_palette.py` in background Blender on the staged models, then run `authoring/trim_building_palette.py` with Python on the same scratch run. Run `authoring/promote_building_art.py stage <scratch-run> <pasture-and-hearth-run>` to combine the staged models. Cook the resulting project in `cook-input` and run `authoring/promote_building_art.py promote <cooked-sga> <scratch-run>`. Use `--verify-half-turn` when comparing against the previous facing during a rotation change.
