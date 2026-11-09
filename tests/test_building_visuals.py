import unittest
from pathlib import Path
from lupa.lua51 import LuaRuntime

class BuildingVisuals(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime()
        self.lua.execute('''
            ChagataiNative={ended=false}
            actor={valid=true,alive=true,hp=1,constructing=false,progress=1}
            calls={}
            function Entity_GetID(e) return 1 end
            function Entity_IsValid(id) return actor.valid end
            function Entity_IsAlive(e) return e.alive end
            function Entity_GetHealthPercentage(e) return e.hp end
            function Entity_IsUnderConstruction(e) return e.constructing end
            function Entity_GetBuildingProgress(e) return e.progress end
            function Entity_SetAnimatorState(e,m,s)
                assert(m=='life_cycle_state');calls[#calls+1]=s
            end
            building={role='steppe_hearth'}
        ''')
        self.lua.execute((Path(__file__).resolve().parents[1]/'source/tuning/assets/scar/chagatai/building_visuals.scar').read_text())
    def test_damage_death_and_repair(self):
        self.lua.execute('''
            local n=ChagataiNative
            n.BuildingVisual(building,actor,0)
            actor.hp=.4;n.BuildingVisual(building,actor,1)
            actor.hp=0;actor.alive=false;n.BuildingVisual(building,actor,2)
            actor.hp=.6;actor.alive=true;n.BuildingVisual(building,actor,3)
            actor.hp=1;n.BuildingVisual(building,actor,4)
            assert(table.concat(calls,',')=='healthy,damage_3,ruins,damage_2,healthy')
        ''')
    def test_construction_does_not_show_damage_for_low_initial_health(self):
        self.lua.execute('''
            actor.hp=.1;actor.constructing=true;actor.progress=.5
            ChagataiNative.BuildingVisual(building,actor,0)
            assert(calls[1]=='construct_50')
        ''')
    def test_refresh_and_invalid_or_stopped_entities(self):
        self.lua.execute('''
            local n=ChagataiNative
            n.BuildingVisual(building,actor,0)
            n.BuildingVisual(building,actor,.5);assert(#calls==1)
            n.BuildingVisual(building,actor,2);assert(#calls==2)
            actor.valid=false;n.BuildingVisual(building,actor,5)
            actor.valid=true;n.ended=true;n.BuildingVisual(building,actor,6)
            assert(#calls==2)
        ''')
    def test_encampment_switches_tier_and_keeps_age_on_destruction(self):
        self.lua.execute('''
            building.role='ranged'
            local n=ChagataiNative
            local age=2
            function n.Owner() return 1 end
            function Player_GetCurrentAge() return age end
            n.BuildingVisual(building,actor,0)
            age=3;n.BuildingVisual(building,actor,1)
            actor.constructing=true;actor.progress=.63
            age=4;n.BuildingVisual(building,actor,2)
            actor.alive=false;actor.hp=0
            age=3;n.BuildingVisual(building,actor,3)
            assert(table.concat(calls,',')=='healthy,castle_healthy,imperial_construct_50,imperial_ruins')
        ''')

    def test_stock_building_is_untouched(self):
        self.lua.execute('''
            building.role='blacksmith'
            ChagataiNative.BuildingVisual(building,actor,0)
            assert(#calls==0)
        ''')

if __name__=='__main__':unittest.main()
