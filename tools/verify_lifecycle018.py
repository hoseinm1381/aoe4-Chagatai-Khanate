"""Independent archive-readback checks of lifecycle inputs, outputs and trade state."""
import argparse
import json
from pathlib import Path
import struct
import hashlib
from lupa.lua51 import LuaRuntime
from build import stock_game, rgd, ROOT
from bind_art import node, variants, BUILDINGS
from compose_buildings import find, rc

def matches(raw, state):
    count,=struct.unpack_from('<I',raw)
    pos=4; result=True
    for _ in range(count):
        kind,negate,join=struct.unpack_from('<IBI',raw,pos);pos+=9
        key,pos=rc.read_lp_string(raw,pos)
        assert key in state and not negate and join==0
        if kind==2:
            value,pos=rc.read_lp_string(raw,pos); ok=state[key]==value
        elif kind==3:
            value,op=struct.unpack_from('<fI',raw,pos);pos+=8
            ok={0:state[key]==value,3:state[key]>value,4:state[key]<value}[op]
        elif kind==4:
            lo,hi=struct.unpack_from('<ff',raw,pos);pos+=8
            ok=lo<=state[key]<=hi
        else:raise ValueError(kind)
        result &= ok
    assert pos==len(raw)
    return result

def audit(root, previous=None):
    game=stock_game.current();rows=[]
    stable=json.loads((ROOT/'source/visuals/stable-building-controllers.json').read_bytes())
    lua=LuaRuntime()
    lua.execute('ChagataiNative = {}')
    script=(root/'scar/chagatai/building_visuals.scar').read_text()
    assert script==(ROOT/'source/tuning/assets/scar/chagatai/building_visuals.scar').read_text()
    lua.execute(script)
    classify=lua.globals().ChagataiNative.BuildingVisualState
    model_state=lua.globals().ChagataiNative.BuildingModelState
    catalog=json.loads((ROOT/'source/visuals/buildings.json').read_bytes())
    for building in catalog:
        resource=building['resource']; graph=rc.parse((root/(resource+'.rgo')).read_bytes())
        observed=[]
        samples=[(1,'healthy'),(.8,'damage_1'),(.6,'damage_2'),(.4,'damage_3'),(.25,'damage_4'),(.1,'damage_5'),(0,'ruins')]
        for health,expected in samples+list(reversed(samples)):
            hits=[classify(health>0,False,1,health)]
            assert hits==[expected],(resource,health,hits)
            observed.append(hits[0])
        for build,expected in [(0,'construct_00'),(.25,'construct_25'),(.5,'construct_50'),(.75,'construct_75')]:
            hits=[classify(True,True,build,1)]
            assert hits==[expected],(resource,build,hits)
        model=rc.parse((root/(resource+'.rgm')).read_bytes())
        assert hashlib.sha256((root/(resource+'.rgo')).read_bytes()).hexdigest()==stable['sha256'][resource+'.rgo']
        selectors=find(model,b'MSBP'); children=selectors.children
        def visible(state):
            selected=[]
            for i,c in enumerate(children):
                if c.tag!=b'CNBP':continue
                # Catalog selectors use one enum, with optional OR terms.
                count,=struct.unpack_from('<I',c.payload);pos=4;values=[]
                for _ in range(count):
                    kind,negate,join=struct.unpack_from('<IBI',c.payload,pos);pos+=9
                    field,pos=rc.read_lp_string(c.payload,pos);value,pos=rc.read_lp_string(c.payload,pos)
                    assert kind==2 and not negate and field=='life_cycle_state'
                    values.append(value)
                if state in values:
                    record=children[i-1];_,p=rc.read_lp_string(record.payload,0)
                    name,_=rc.read_lp_string(record.payload,p+4);selected.append(name)
            return selected
        assert len(visible('healthy'))==len(visible('ruins'))==1
        assert visible('healthy')!=visible('ruins')
        construction=[]
        if building['asset'] in ('almaliq','ordu','qarshi','court','ili','mint','wonder'):
            for percent in range(100):
                role = building['asset']
                [mesh] = visible(classify(True,True,percent/100,.10,role))
                if role == 'wonder':
                    state = f'frame{percent//25*25:02d}'
                else:
                    state = ('frame00','damage_5','damage_4','damage_3','damage_2','damage_1')[percent*6//100]
                assert mesh == f'{role}_{state}'
                if not construction or mesh != construction[-1]:
                    construction.append(mesh)
            if building['asset'] != 'wonder':
                assert len({tuple(visible(s)) for _,s in samples})==7
        tiers={}
        for age in building.get('age_tiers',{}):
            expected={}
            for name in ('healthy','construct_00','construct_25','construct_50','construct_75','ruins'):
                state=model_state(building['asset'],int(age),name)
                found=visible(state)
                assert len(found)==1,(building['asset'],age,state,found)
                expected[name]=found[0]
            tiers[age]=expected
        if tiers:
            assert len({x['healthy'] for x in tiers.values()})==len(tiers)
            assert len({x['ruins'] for x in tiers.values()})==len(tiers)
        rows.append({'asset':building['asset'],'damage_and_repair_sequence':observed,
                     'ruin_mesh':visible('ruins'),'age_meshes':tiers,
                     'construction_meshes':construction})
    path=next((root/'attrib/ebps').rglob('ck_trader_foot_2.rgd'));trader=rgd.read(path.read_bytes())
    stock=rgd.read(game.blueprint('ebps/races/mongol/units/unit_trade_cart_mon'))
    def leaves(n):return {p:(v.kind,v.value) for p,v in rgd.flatten(n.value) if v.kind not in ('List','List2')}
    for v in variants(trader):
        s=next((x for x in variants(stock) if x.key==v.key),node(stock,'default'))
        for field in ('statemodel_ext','action_tree_ext','action_apply_ext',
                      'animation_action_tree_ext','hit_react_tree_ext','holdable_ext'):
            assert leaves(node(v,field))==leaves(node(s,field)),field
        assert node(node(v,'health_ext'),'delete_when_dead').value
        assert node(node(v,'health_ext'),'death_seconds').value==19
        assert node(node(v,'health_ext'),'remove_from_pathfinding_on_death').value
    gaps=[]
    for path in (root/'attrib/ebps').rglob('*.rgd'):
        if path.stem not in BUILDINGS:continue
        d=node(rgd.read(path.read_bytes()),'default');size=node(node(d,'site_ext'),'footprint_scale')
        scale=node(node(d,'entity_blueprint_ext'),'animator_scale').value/100
        raw=find(rc.parse((root/('art/scenario/chagatai/'+BUILDINGS[path.stem]+'/model.simbox')).read_bytes()),b'AEGD').payload
        x=node(size,'x').value;y=node(size,'y').value
        height=4/scale if path.stem in {'ck_building_melee','ck_building_ranged'} else 4
        if path.stem.startswith('ck_landmark_'):
            height/=1.4
        assert raw.count(struct.pack('<3f',(x-2)/scale,height,(y-2)/scale))==2
        gaps.append({'building':path.stem,'site':[x,y],'scale':scale,'adjacent_clearance':2})
    material_count=0
    if previous:
        for path in (root/'art/scenario/chagatai').rglob('*.rrmaterial'):
            assert path.read_bytes()==(previous/path.relative_to(root)).read_bytes(),path
            material_count+=1
    return {'buildings':rows,'pinned_building_controllers_verified':True,
            'foot_trader_trade_state_preserved':True,'foot_trader_native_trade_contract_and_timed_cleanup':True,
            'passages':gaps,'unchanged_working_materials':material_count,'native_game_tested':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);p.add_argument('--previous',type=Path)
    a=p.parse_args();result=audit(a.root,a.previous);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
