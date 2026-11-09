"""Populate the native overview and four age bands from production data."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import re

from build import at, child, LANDMARK_AGE, BUILDING_AGE, ref, refs, rgd


AGES = dict(dark_age=1, feudal_age=2, castle_age=3, imperial_age=4)
PRODUCER_ORDER = ('town_center_capital', 'steppe_hearth', 'pasture', 'outpost',
                  'palisade', 'palisade_gate', 'melee', 'ranged', 'blacksmith',
                  'market', 'religious', 'siege', 'university', 'wonder', 'dock')
STYLES = {'town_center_capital': 'center', 'steppe_hearth': 'economic',
          'pasture': 'economic', 'market': 'economic', 'almaliq': 'economic',
          'religious': 'economic', 'ili': 'economic', 'mint': 'economic',
          'outpost': 'defence', 'palisade': 'defence', 'palisade_gate': 'defence',
          'wonder': 'defence', 'blacksmith': 'tech', 'university': 'tech'}


def optional(node, key):
    return next((n for n in node.value if n.key == key), None)


def populate(doc, tables, owner, game, index):
    namespace = owner + ':'
    private = {(p.split('/')[1], namespace+Path(p).stem): d for p, d in tables.items()
               if p.count('/') > 1}
    stock = {(p.split('/')[0], Path(p).name): p for p in index
             if p.startswith(('upgrade/', 'sbps/', 'ebps/'))}

    @lru_cache(maxsize=None)
    def get(family, name):
        if (family, name) in private:
            return child(private[family, name], 'default')
        path = stock.get((family, name))
        return child(rgd.read(game.blueprint(path)), 'default') if path else None

    def requirements(family, name):
        record = get(family, name)
        if record is None:
            return []
        keys = {'upgrade': ('upgrade_bag', 'requirements'),
                'sbps': ('squad_requirement_ext', 'requirement_table'),
                'ebps': ('requirement_ext', 'requirement_table')}
        ext, field = keys[family]
        ext = optional(record, ext)
        req = optional(ext, field) if ext else None
        return req.value if req else []

    def rule_age(rule, seen):
        if rule.kind not in ('List', 'List2'):
            return 1
        fields = {n.key:n for n in rule.value}
        kind = fields['$REF'].value.split('\\')[-1] if '$REF' in fields else rule.key
        if kind == 'required_not' or ('is_present' in fields and not fields['is_present'].value):
            return 1
        if kind in ('required_player_upgrade', 'required_entity_upgrade'):
            target = fields.get('upgrade_name') or fields.get('upgrade')
            return age('upgrade', child(target, '$PBGNAME').value, seen) if target else 1
        if kind == 'required_any_in_list':
            group = fields.get('requirements') or fields.get('requirement_table')
            return min((rule_age(r, seen) for r in group.value), default=1) if group else 1
        return max((rule_age(r, seen) for r in rule.value), default=1)

    @lru_cache(maxsize=None)
    def age(family, name, seen=()):
        key = (family, name)
        if family == 'upgrade' and name in AGES:
            return AGES[name]
        if key in seen:
            return 1
        return max((rule_age(r, seen+(key,)) for r in requirements(family, name)), default=1)

    # Construction menus define where players encounter the producer.
    build_ages = {}
    for key in ('ck_unit_villager', 'ck_villager_mounted_1'):
        builder = get('sbps', namespace+key)
        if not builder:
            continue
        engineer = optional(builder, 'squad_engineer_ext')
        for group in child(engineer, 'construction_groups').value if engineer else ():
            menu = at(group, 'construction_menu', '$PBGNAME').value
            match = re.search(r'_age([1-4])(?:_wonders)?$', menu)
            tab = int(match[1]) if match else 1
            for item in child(group, 'construction_items').value:
                target = at(item, 'ebp', '$PBGNAME').value
                build_ages[target] = min(tab, build_ages.get(target, tab))

    def products(name):
        record = get('ebps', name)
        result = {(family, target) for path, family, target in refs(record)
                  if (family == 'sbps' and path.startswith('spawner_ext/spawn_items/') and path.endswith('/squad'))
                  or (family == 'upgrade' and path.startswith('upgrade_ext/standard_upgrades/'))}
        return {x for x in result if not x[1].endswith(('_hidden', '_dummy', 'ck_horse_import'))}

    plans = []
    for member in tables:
        if not member.startswith('attrib/ebps/races/chagatai/buildings/'):
            continue
        name = Path(member).stem
        if name == 'ck_building_town_center':
            continue
        landmark = name.startswith('ck_landmark_')
        slug = name.removeprefix('ck_landmark_' if landmark else 'ck_building_')
        producer = namespace+name
        available = (LANDMARK_AGE[slug] if landmark else
                     max(BUILDING_AGE.get(slug, 1), build_ages.get(producer, 1), age('ebps', producer)))
        if slug == 'town_center_capital':
            available = 1
        entries = products(producer)
        if slug == 'town_center_capital':
            entries |= products(namespace+'ck_building_town_center')
            entries |= {('sbps',namespace+x) for x in ('ck_unit_villager','ck_scout_foot_1')}
        if slug in ('market', 'almaliq'):
            entries.add(('sbps', namespace+'ck_trader_mounted_2'))
        items = [(family, target, max(available, age(family,target))) for family,target in sorted(entries)]
        plans.append((slug, producer, landmark, available, items))
    plans.sort(key=lambda p: (0,p[3],p[0]) if p[2] else
               (1, PRODUCER_ORDER.index(p[0]) if p[0] in PRODUCER_ORDER else len(PRODUCER_ORDER),p[0]))

    sample = at(doc,'default','codex_bag')
    group_sample = child(sample,'tech_tree').value[0]
    item_sample = child(group_sample,'items').value[0]
    legacy_sample = at(sample,'root_item','children').value[0]
    container_sample = child(legacy_sample,'children').value[0]
    leaf_sample = child(container_sample,'children').value[0]

    def lane(family, name):
        return re.sub(r'_(?:[1-4]|iv|iii|ii|i)(?=_|$)', '_tier', name)

    report = []
    for variant in (n for n in doc.nodes if n.kind in ('List','List2')):
        bag = child(variant,'codex_bag')
        groups, old_groups = [], []
        for slug, producer, landmark, available, products_list in plans:
            header_age = available-1 if landmark else available
            group, legacy = deepcopy(group_sample), deepcopy(legacy_sample)
            ref(child(legacy,'pbg'),'ebps',producer)
            at(legacy,'ui_codex_info','ui_position','ui_position_column').value = header_age-1
            entries, leaves, positions = [], [], set()
            upgrade_names = {name for f,name,_ in products_list if f == "upgrade"}
            represented_upgrades = set()

            def item(family, name, x, y):
                if not 0 <= y <= 11 or (x,y) in positions:
                    raise ValueError(f'Invalid Codex position for {name}: {(x,y)}')
                positions.add((x,y))
                node = deepcopy(item_sample)
                ref(child(node,'pbg'),family,name)
                ref(child(node,'upgrade_pbg'),'','')
                for k,v in dict(x_position=x,y_position=y,left_branch_length=0,
                                right_branch_length=0,top_line_length=0).items():
                    child(node,k).value = v
                entries.append(node)
                return node

            item('ebps',producer,0,3*(header_age-1)+(2 if landmark else 0))
            for family in ('sbps','upgrade'):
                family_items = sorted(((n,a) for f,n,a in products_list if f==family
                                       and n not in represented_upgrades), key=lambda row: (row[1],row[0]))
                lanes, used = {}, {}
                for name, tier in family_items:
                    key = lane(family,name)
                    slot = used.get((key,tier),0)
                    used[key,tier] = slot+1
                    lanes.setdefault((key,slot),len(lanes))
                used.clear()
                previous_rows = {}
                for name, tier in family_items:
                    key = lane(family,name)
                    slot = used.get((key,tier),0)
                    used[key,tier] = slot+1
                    x = 2*lanes[key,slot]-(len(lanes)-1)
                    y = 3*(tier-1)+(1 if family=='sbps' else 2)
                    node = item(family,name,x,y)
                    if (key,slot) in previous_rows:
                        child(node,'top_line_length').value = 2*(y-previous_rows[key,slot])
                    previous_rows[key,slot] = y
                    if family == 'sbps':
                        record = get(family,name)
                        required = sorted({target for path, f, target in refs(record)
                                           if f=='upgrade' and target in upgrade_names
                                           and path.startswith('squad_requirement_ext/requirement_table/')
                                           and target.split(':')[-1].startswith('ck_tier_')
                                           and age('upgrade',target)==tier}) if record else []
                        if len(required) == 1:
                            ref(child(node,'upgrade_pbg'),'upgrade',required[0])
                            represented_upgrades.add(required[0])
                    container, leaf = deepcopy(container_sample), deepcopy(leaf_sample)
                    ref(child(leaf,'pbg'),family,name)
                    at(leaf,'ui_codex_info','ui_position','ui_position_column').value = tier-1
                    child(leaf,'children').value = []
                    child(container,'children').value = [leaf]
                    leaves.append(container)
            child(group,'items').value = entries
            child(group,'background_height').value = max(y for _,y in positions)
            child(group,'background_template').value = STYLES.get(slug,'military')
            child(legacy,'children').value = leaves
            groups.append(group)
            old_groups.append(legacy)
            if variant.key == 'default':
                report.append(dict(producer=producer, available_age=available, landmark=landmark, products=products_list))
        child(bag,'tech_tree').value = groups
        child(child(bag,'root_item'),'children').value = old_groups
        child(bag,'landmark_count').value = sum(p[2] for p in plans)
        units = ('ck_horse','ck_spearman_mounted_2','ck_nokor_foot_2','ck_archer_mounted_2','ck_religious_foot_3')
        techs = ('ck_jida_spearheads', 'ck_yam_logistics', 'ck_compassionate_care',
                 'ck_lamellar_reinforcement',
                 *(f'ck_{family}_{tier}' for family in ('production','horse_hp','livestock')
                   for tier in range(1,4)))
        for key,family,names in (('unique_units','sbps',units),('unique_techs','upgrade',techs)):
            values = []
            for name in names:
                if (family, namespace+name) not in private:
                    raise ValueError(f'Missing overview entry {name}')
                target = deepcopy(child(item_sample,'pbg'))
                ref(target,family,namespace+name)
                values.append(target)
            child(bag,key).value = values
    return report
