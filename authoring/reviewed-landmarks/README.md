# Feudal landmark rebuild inputs

For Ordu in 0.2.7, use the packed authoring/review/approval/ordu-of-almaliq/Chagatai-Ordu-Round.blend as CK_MASTER. The procedural master can be regenerated with authoring/rebuild_ordu.py in background Blender with authoring and .tools/python313 on sys.path, passing a fresh output directory after --. Set CK_REVERSE_BUILDING_FACING=1 when staging. Promote the composed .rgm, .rrgeom, .rrmaterial and textures, updating the two Ordu entries in the building-color overlay. Preserve the hash-pinned controller at source/visuals/art/art/scenario/chagatai/ordu/model.rgo. The earlier Kurultai-derived master is retained in the same authoring folder.

The packed Blender masters live under authoring/review/approval/almaliq-market and authoring/review/approval/ordu-of-almaliq. Each master has one finished collection, four construction collections, five damage collections and a dedicated ruin collection. Preview terrain and lighting have separate collections.

Almaliq Market modifies stock Abbasid and Mongol market geometry into a caravan court. It uses a Central Asian portal, brickwork, market textiles, fruit and a stock-derived horse to show the landmark's import role. Its gateway piers and trade aisle survive destruction. The historical evidence documents a Silk Road trading centre and local building materials. The design is a reconstruction.

Ordu of Almaliq modifies the stock Mongol Kurultai's roof, wings and entry. Its south-facing audience ger, ceremonial textiles, open muster yard and arms racks follow documented Mongol camp and royal tent patterns. Its ruin retains part of the timber lattice, the dais and the fallen crown.

Historical sources

- https://www.archnet.org/publications/5406
- https://en.unesco.org/silkroad/sites/default/files/knowledge-bank-article/vol_IVb%20silk%20road_urban%20development%20and%20architecture%20BIS.pdf
- https://www.metmuseum.org/essays/the-mongolian-tent-in-the-ilkhanid-period
- https://doi.org/10.1186/s43238-025-00191-2

For a clean export, set CK_ROOT to the editable project, CK_RUN to a new dedicated folder under the project's .build directory, and CK_MASTER to the packed Blender file. Set TEMP and TMP to CK_RUN. Run Blender in background with Python Pillow and NumPy and call stage_landmark.py with almaliq or ordu as the argument after --. It writes the model-capable Content Editor project to CK_RUN/stage-<key>. It preserves the original master and exports one owner-mask atlas and three LODs per state.

Cook the isolated project using the Garrison Kit model-capable Content Editor. Pass the fresh SGA and key to compose_landmark.py as <key> <archive>. This verifies the archive, all eleven mesh selectors and three LOD groups per state and grafts the installed Forbidden Palace's health-conditioned lifecycle actions. The output belongs in a build candidate after approval and archive readback. The stock Chagatai receivers already have can_repair enabled. A native game is still needed to verify repairing from zero health and restoring the intact visuals.


For the full build, promote the two candidate trees and update the visual manifest and final ZIP validator to accept eleven states for these two assets. The legacy nine-state validation still applies to the prior building assets.
