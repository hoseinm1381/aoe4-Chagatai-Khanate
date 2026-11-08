# Building color correction inputs

These PNGs are produced by `tools/building_color.py:prepare_textures` from the immutable source/visuals/art atlases. Only pixels selected by the existing red owner mask are rebased to red cloth. PNGs are vertically flipped because the native Static Textures rule flips input on cook.

The isolated .aoe4mod contains only an art PNG texture rule. Its Static Textures parameters force BC1, matching the original albedo format and texture memory footprint. It uses the original dimensions, including the 512x256 Wonder, and generates full mip chains.

Cook this project with Garrison core `essence build-mod`, then run `tools/collect_building_colors.py <cooked-sga>`. Collection checks native formats/dimensions/mips and compression error against the corrected PNGs, then updates source/visuals/building-colors-native and its digest manifest. The normal build overlays precisely those manifest members without changing source art.

The earlier direct RGBA8 encoding and default-format cook were internal experiments, not the delivered candidate. The final native cook receipt is in authoring/verification-0.1.10/texture-cook.json. Native player-color appearance awaits the owner test.
