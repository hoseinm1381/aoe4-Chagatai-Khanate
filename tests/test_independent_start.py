"""Exercise the real Chagatai dispatcher and startup against a Lua engine seam."""
import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime

SCAR = Path(__file__).resolve().parents[1] / "source/tuning/assets/scar"

class IndependentStart(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute((SCAR/"chagatai/config.scar").read_text(encoding="utf-8"))
        self.lua.execute((SCAR/"chagatai/native_world.scar").read_text(encoding="utf-8"))
        self.lua.execute("""
          local n = ChagataiNative
          count = {resolve=0, scan=0, player=0, global=0, intervals=0, alerts=0}
          PLAYERS = {
            {id=1,index=1,isHuman=true,race='ac8da4d112bf433c888433228510b447:chagatai'},
            {id=2,index=2,isHuman=true,race='mongol'},
            {id=3,index=3,isHuman=true,race='ac8da4d112bf433c888433228510b447:chagatai'}
          }
          function import() end
          function Scar_AddInit() end
          function Core_RegisterModule(name) assert(name=='ChagataiIndependent') end
          function Player_IsAlive() return true end
          function Player_GetRaceName(id) return PLAYERS[id].race end
          function Player_GetMaxPopulationCap() return 0 end
          caps = {}
          function Player_SetMaxPopulation(id,_,cap) caps[id]=cap end
          function Modifier_Create(_,field) assert(field=='max_vehicle_cap_player_modifier');return {} end
          function Modifier_ApplyToPlayer() return 1 end
          function Rule_AddPlayerEvent() count.player=count.player+1 end
          function Rule_AddGlobalEvent() count.global=count.global+1 end
          function Rule_AddInterval() count.intervals=count.intervals+1 end
          function print() count.alerts=count.alerts+1 end
          n.LocalWarning=function() end
          n.Resolve=function() count.resolve=count.resolve+1 end
          n.Now=function() return 0 end
          n.Scan=function(p) assert(n.players[p.index]==p);count.scan=count.scan+1 end
          n.ReleasePlayer=function(p) n.players[p.index]=nil end
          ChagataiHorse={New=function() return {} end}
          ChagataiEconomy={New=function() return {} end}
          ChagataiProduction={New=function() return {} end}
          ChagataiEffects={NewIli=function() return {} end}
        """)
        dispatcher = (SCAR/"garrison/chagatai/dispatcher.scar").read_text(encoding="utf-8")
        dispatcher = dispatcher.replace("local sharedSquads = {}",
                                        'local sharedSquads = {"unit_naval_combat_ship_2_mon"}')
        self.lua.execute(dispatcher)

    def test_stock_warship_uses_squad_lookup_and_queues_once(self):
        self.lua.execute("""
          local warship = 'unit_naval_combat_ship_2_mon'
          local queued = 0
          function EBP_Exists(name) error('Unexpected EBP lookup for '..name) end
          function SBP_Exists(name) return name == warship end
          function BP_GetSquadBlueprint(name) assert(name == warship); return {name=name} end
          function Scar_PrecachePrematchResource(bp) assert(bp.name == warship); queued=queued+1 end

          ChagataiIndependent_PrecacheSharedSquads()
          ChagataiIndependent_PrecacheSharedSquads()
          assert(queued==1)

          ChagataiIndependent_OnGameSetup()
          PLAYERS={{id=1,race='abbasid'}}
          ChagataiIndependent_PrecacheSharedSquads()
          assert(queued==1)

          PLAYERS=nil
          ChagataiIndependent_PrecacheSharedSquads()
          assert(queued==2)
        """)

    def test_only_chagatai_players_initialize_once(self):
        self.lua.execute("""
          ChagataiIndependent_Start()
          ChagataiIndependent_Start()
          assert(count.resolve==1 and count.scan==2 and count.player==2)
          assert(count.global==6 and count.intervals==1 and count.alerts==0)
          assert(ChagataiNative.players[1] and ChagataiNative.players[3])
          assert(not ChagataiNative.players[2])
        """)

    def test_census_failure_is_cleaned_up_and_does_not_block_another_player(self):
        self.lua.execute("""
          local scan=ChagataiNative.Scan
          ChagataiNative.Scan=function(p)
            if p.id==1 then error('census failed') end
            scan(p)
          end
          ChagataiIndependent_Start()
          assert(not ChagataiNative.players[1] and ChagataiNative.players[3])
          assert(count.alerts==1 and count.scan==1 and count.intervals==1)
          assert(caps[1]==0 and caps[3]==ChagataiConfig.horse.nativeCap)
        """)

