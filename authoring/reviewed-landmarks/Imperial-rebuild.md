# Imperial landmark rebuild inputs

Ili Royal Pastures modifies the stock Mongol Stable roof and framing with Mongol Pasture rails and stock-derived standing and drinking Horses. The open pens and separate feeders represent the brood and remount herds. William of Rubruck's account describes the grazing country around the Ili Valley and Qayaligh. https://depts.washington.edu/silkroad/texts/rubruck.html

Kebek's Royal Mint reshapes an Abbasid Blacksmith into an open coin workshop with a kiln, dies, chest and fenced horse intake. The sign takes its shape from a surviving Samarqand silver dinar. The gameplay award remains Gold. https://khalilicollections.org/islamic-coins/12477-chaghatayid-silver-kebeki-dinar-samarqand-%DB%B7%DB%B2%DB%B5-725-ah/

The two layouts are historically informed interpretations. Both masters include all 11 lifecycle collections and packed textures. The Pasture ruin retains a torn saddlecloth by the gate. The Mint ruin retains treasury cloth on a low pier.

Run `stage_landmark.py` with `ili` or `mint` and the packed master under `authoring/review/approval`, following the environment setup in README.md. Use the model-capable Content Editor from the Garrison Kit and pass each fresh SGA to `compose_landmark.py <key> <fresh-sga>`. The native lifecycle selects three LODs per state and restores the intact mesh as health rises. Both local blueprint variants enable repair.

Promote these resources with the earlier landmarks when assembling the combined player build. Check placement, horse interaction, destruction and repair in game after integration.
