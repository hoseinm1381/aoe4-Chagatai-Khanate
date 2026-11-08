# Castle landmark rebuild inputs

Both designs are historical interpretations. Qarshi Palace modifies the Abbasid Castle Age Town Center into a low fortified civic court with glazed brickwork, public arcades and a stock-derived remount horse. Khan's Court stretches the stock Mongol Town Center felt roof over a modified Khanbaliq terrace, with an open audience dais, rally standards and benches.

- Qarshi and the Chaghadaid court are discussed by Michal Biran in *Turko-Mongol Rulers, Cities and City Life*. https://paxmongolica.org/wp-content/uploads/2019/06/turko-mongol-rulers-cities-and-city-life-1.pdf
- Ibn Battuta visited Tarmashirin and described the khan's audience. https://fr.wikisource.org/wiki/Voyages_(Ibn_Battuta,_Sanguinetti)/L%E2%80%99Asie_centrale
- The Met documents construction and decoration of Mongol royal tents. https://www.metmuseum.org/essays/the-mongolian-tent-in-the-ilkhanid-period

Use the packed masters in `authoring/review/approval/qarshi-palace` and `authoring/review/approval/khans-court`. Set CK_ROOT, CK_RUN, CK_MASTER, TEMP and TMP as described in README.md. Run `stage_landmark.py` with `qarshi` or `court`, cook the resulting isolated project in the Garrison Kit model-capable Content Editor, then run `compose_landmark.py <key> <fresh-sga>`. The packed masters contain the eleven editable state collections and textures. Native exports have three LODs per state.

The isolated cooks, stock health-conditioned lifecycle bindings, owner masks and three LODs per state passed archive readback. Both Chagatai blueprints have can_repair enabled in each local variant. Verify runtime destruction, repair to the intact mesh, and gameplay zoom in the later combined playtest build.

