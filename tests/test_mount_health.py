import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


class MountHealth(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        modules = Path(__file__).resolve().parents[1] / "source/tuning/assets/scar/chagatai"
        self.lua.execute("""
            ChagataiCatalog = {
                ['ebps/races/chagatai/buildings/ck_building_pasture'] = {
                    influenceProductionSpeedBonus = 0.15
                }
            }
        """)
        for name in ("config", "horse_core", "native_world", "native_units", "native_runtime"):
            self.lua.execute((modules / f"{name}.scar").read_text(encoding="utf-8"))
        self.lua.execute("""
            N = ChagataiNative
            H = ChagataiHorse
            p = {id=3, horses=H.New(3), research={}, workers={}}
            position = {x=0,y=0,z=0}
            horse = H.AddHorse(p.horses, 2, H.Profile('baseline'), 45, position)
            horse.nativeID=2
            rider = H.AddRider(p.horses, 1, 'villager', 35, 50, position)
            actors = {{id=1,bp='foot',maximum=50,hp=35}, {id=2,bp='horse'}}
            N.entities[1]={player=p,riderID=1}
            N.entities[2]={player=p,horseID=2}
            function N.Entity(id) return actors[id] end
            function N.Owner() return p.id end
            function N.Unit(_,form) return {bp=form,riderHP=50} end
            function N.Record() return {form=rider.form} end
            function Entity_GetID(e) return e.id end
            function Entity_GetSquad(e) return e end
            function Entity_IsAlive() return true end
            function Entity_GetBlueprint(e) return e.bp end
            function Squad_GetBlueprint(s) return s.bp end
            function Entity_GetHealth(e) return e.hp end
            function Entity_GetHealthMax(e) return e.maximum end
            function Entity_GetHealthPercentage(e) return e.hp/e.maximum end
            function Player_GetCurrentAge() return 2 end
            function N.Health(_,e,maximum,hp) e.maximum=maximum;e.hp=hp end
        """)

    def test_reserved_horse_deselects_and_unlocks_on_cancel(self):
        self.lua.execute("""
            local calls, localPlayer, selected = 0, p.id, true
            function Game_GetLocalPlayer() return localPlayer end
            function Entity_IsInHold() return false end
            function N.IsPlaying(player) return player==p end
            function Misc_IsSquadSelected(s) return s.id==2 and selected end
            function Misc_SelectSquad(s,value) assert(s.id==2);selected=value end
            function Misc_SetSquadSelectable(s,value)
                assert(s.id==2)
                s.selectable=value
                calls=calls+1
            end
            p.pendingMounts={[1]=rider}
            N.DrainMountRequests(p,10)
            assert(horse.status=='mount' and not actors[2].selectable and not selected and calls==1)
            N.LockHorseSelection(horse.nativeID,true)
            assert(calls==1)
            -- An already queued player order can still reach the listener.
            ChagataiNative_OnHorseOrder({command='move',squad=actors[2]},{id=2})
            assert(p.horses.requests[1].interrupted)
            N.FailRider(p,rider,11)
            assert(horse.status=='loose' and actors[2].selectable and calls==2)
            localPlayer=4
            N.LockHorseSelection(horse.nativeID,true)
            assert(calls==2)
        """)

    def test_textiles_is_applied_once_and_cycles_conserve_health(self):
        self.lua.execute("""
            assert(H.RequestMount(p.horses,1,0,2))
            assert(H.Approach(p.horses,1,0))
            local mounted=H.PrepareConversion(p.horses,1,0)
            assert(mounted.maximum==110 and mounted.hp==80)
            assert(H.CommitConversion(p.horses,1,0,mounted,true))
            local e=actors[1]
            e.bp='mounted';e.maximum=mounted.maximum;e.hp=mounted.hp

            p.research.textiles=1
            N.EnsureWorker(p,e)
            assert(rider.riderMaximum==75 and e.maximum==135 and horse.maximum==60)
            local combined=e.hp
            N.EnsureWorker(p,e)
            assert(e.maximum==135 and e.hp==combined)
            for i=1,3 do
                local now=i*100
                assert(H.RequestDismount(p.horses,1,now))
                local foot=H.PrepareConversion(p.horses,1,now,position)
                assert(foot.maximum==75 and math.abs(foot.hp+foot.horseHP-combined)<0.001)
                assert(H.CommitConversion(p.horses,1,now,foot,true))
                assert(H.RequestMount(p.horses,1,now+30,2))
                assert(H.Approach(p.horses,1,now+30))
                local again=H.PrepareConversion(p.horses,1,now+30)
                assert(again.maximum==135 and math.abs(again.hp-combined)<0.001)
                assert(H.CommitConversion(p.horses,1,now+30,again,true))
            end
        """)
