# Chagatai Khanate 0.4.0 for base Age of Empires IV

## Play

Extract the release ZIP into your game profile’s
Documents/My Games/Age of Empires IV/mods/extension/local directory. It creates
the Chagatai-Khanate folder with the mod archive. Restart the game and select
the Chagatai Khanate game mode in Skirmish or a custom lobby.

## Rebuild

The Content Editor project is chagatai_khanate/chagatai_khanate.aoe4mod. It
retains the Normal game-mode identity, localization, attributes, and custom
landmark resources. Use the installed Age of Empires IV Content Editor and
Garrison Blender extension for the archive tools, plus Python 3.13.

Run ./tools/build.ps1 from this directory and supply -EditorRoot and -Python
for your installation. If needed, set GARRISON_EXTENSION to the installed
Blender extension folder. The script prints the playable archive path after
verifying the project and attaching the six native landmark models.
