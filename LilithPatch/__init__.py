# Quick-n-dirty mod to remove the need for Lilith's Phasewalk to have a target.

import unrealsdk
from typing import Set, List, Dict, Generator, Union

from ..ModManager import SDKMod, RegisterMod
from Mods.ModMenu import Game, Hook, ModTypes, Options, EnabledSaveType, LoadModSettings, SaveModSettings
from Mods.Structs import Vector, Rotator
from Mods.Enums import EPhysics

class LilithPatch(SDKMod):
    Name: str = "Lilith Phasewalk Patch"
    Description: str = "Remove the need for Lilith's Phasewalk to have a target."
    Version: str = "0.1"
    Author: str = "Milo"
    SupportedGames: Game = Game.BL2   # add Tiny Tina after testing
    Types: ModTypes = ModTypes.Gameplay
    SaveEnabledState: EnabledSaveType = EnabledSaveType.LoadOnMainMenu
    SettingsInputs: Dict[str,str] = { "Enter" : "Enable" }

    def __init__(self):
        self.target = None
        self.template = None

    @Hook("WillowGame.WillowPawn.NotifyTeleported")
    def notify_teleported(self, caller: unrealsdk.UObject,
                          function: unrealsdk.UFunction,
                          params: unrealsdk.FStruct) -> bool:
        # Create a fake, hidden target pawn for Phasewalk.
        self.target = caller.SpawnForMap(
            self.template.Class,
            None,
            "Phasewalk Target",
            Vector(0,0,0),
            Rotator(0,0,0),
            self.template,
            True
        )
        self.target.SetHidden(True)
        # TODO: figure out how to keep the target from falling off the map
        
        return True

    @Hook("Engine.Pawn.FellOutOfWorld")
    def on_fell_out_of_world(self, caller: unrealsdk.UObject,
                             function: unrealsdk.UFunction,
                             params: unrealsdk.FStruct) -> bool:
        return caller != self.target
        
    @Hook("WillowGame.LiftActionSkill.OnActionSkillStarted")
    def on_action_skill_started(self, caller: unrealsdk.UObject,
                                function: unrealsdk.UFunction,
                                params: unrealsdk.FStruct) -> bool:
        # Inject our fake target.
        caller.OnActionSkillStarted(params.TheWillowPawn,
                                    params.TheController,
                                    self.target)
        return False
        
    def Enable(self) -> None:
        self.template = unrealsdk.FindObject(
            "WillowAIPawn",
            "WillowGame.Default__WillowAIPawn"
        )
        super().Enable()


RegisterMod(LilithPatch())
