# Quick-n-dirty mod to block selling or dropping starred items.

import unrealsdk
from typing import Set, List, Dict, Generator, Union

from ..ModManager import SDKMod, RegisterMod
from Mods.ModMenu import Game, Hook, ModTypes, Options, EnabledSaveType, LoadModSettings, SaveModSettings
from Mods.Enums import PlayerMark

class MyFavorite(SDKMod):
    Name: str = "My Favorite"
    Description: str = "Block selling or dropping starred items."
    Version: str = "0.1"
    Author: str = "Milo"
    SupportedGames: Game = Game.BL2 | Game.TPS | Game.AoDK
    Types: ModTypes = ModTypes.Gameplay
    SaveEnabledState: EnabledSaveType = EnabledSaveType.LoadOnMainMenu
    SettingsInputs: Dict[str,str] = { "Enter" : "Enable" }

    def __init__(self):
        pass

    @Hook("WillowGame.VendingMachineExGFxMovie.ConditionalStartTransfer")
    def conditional_start_transfer(self, caller: unrealsdk.UObject,
                                   function: unrealsdk.UFunction,
                                   params: unrealsdk.FStruct) -> bool:
        unrealsdk.Log("ConditionalStartTransfer called")
        if caller.IsCurrentSelectionSell() and caller.CurrentSelectionItem.GetMark() == PlayerMark.PM_Favorite:
            caller.PlayFeedback_CannotAfford()
            return False
        return True

    @Hook("WillowGame.StatusMenuInventoryPanelGFxObject.DropSelectedThing")
    def drop_selected_thing(self, caller: unrealsdk.UObject,
                            function: unrealsdk.UFunction,
                            params: unrealsdk.FStruct) -> bool:
        unrealsdk.Log("DropSelectedThing called")
        item = caller.GetSelectedThing()
        if item.GetMark() == PlayerMark.PM_Favorite:
            caller.ParentMovie.PlayUISound("ResultFailure")
            return False
        return True


RegisterMod(MyFavorite())
