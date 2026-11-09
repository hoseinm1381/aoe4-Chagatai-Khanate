import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


class IliHerds(unittest.TestCase):
    def test_native_button_dispatch_and_birth_profiles(self):
        lua = LuaRuntime()
        modules = Path(__file__).resolve().parents[1] / "source/tuning/assets/scar/chagatai"
        for name in ("config", "horse_core", "effects_core", "native_world", "native_effects"):
            lua.execute((modules / f"{name}.scar").read_text())
        lua.execute("""
            local n = ChagataiNative
            local p = {id=2, ili=ChagataiEffects.NewIli(), iliActive=true, buildings={}}
            local b = {id=17, role='ili', queue={}}
            p.buildings[17] = b
            n.entities[17] = {player=p, buildingID=17}
            local entity = {}
            function n.Entity(id) if id==17 then return entity end end
            function n.Owner() return p.id end
            function n.IsPlaying(player) return player==p end
            function n.Functioning() return true end
            function n.Lookup(ability) return {action=ability} end
            function n.Ability(action) return action end
            function Entity_IsAlive() return true end
            local buttons = {}
            function Entity_HasAbility(_, action) return buttons[action] end
            function Entity_AddAbility(_, action) buttons[action]=true end
            function Entity_RemoveAbility(_, action) buttons[action]=nil end
            local function cast(action, time)
                ChagataiNative_OnBuildingAbility({ability=action},{id=17})
                assert(#n.pendingBuildingActions==1)
                local item = table.remove(n.pendingBuildingActions)
                n.ExecuteBuildingAbility(item,time)
            end
            n.BuildingButtons(p,b,entity,0)
            assert(buttons.ili_war and buttons.ili_fattened)
            local previous = n.Profile(p,false)
            assert(previous.food==600)
            cast('ili_war',10)
            local war = n.Profile(p,false)
            assert(war.food==300 and war.warFactor==1.4)
            cast('ili_fattened',69)
            assert(n.Profile(p,false).food==300)
            n.BuildingButtons(p,b,entity,69)
            assert(buttons.ili_war and buttons.ili_fattened)
            cast('ili_fattened',70)
            local fattened = n.Profile(p,false)
            assert(fattened.food==600 and fattened.warFactor==1)
            assert(ChagataiHorse.Carcass(fattened,false,true).food==600)
            assert(previous.food==600 and war.food==300)
            p.iliActive=false
            assert(n.Profile(p,false).food==400)
            assert(n.Profile(p,false,true).food==600)
        """)


if __name__ == "__main__":
    unittest.main()
