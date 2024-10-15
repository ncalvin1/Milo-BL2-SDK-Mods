import unrealsdk

from ..ModManager import SDKMod, RegisterMod
from Mods.ModMenu import Game, Hook, ModTypes, Options, EnabledSaveType


class StorageManager(SDKMod):
    Name: str = "StorageManager"
    Description: str = "Customize backpack and bank space.  Merges PureEvil139's BankManager, FromDarkHell's BackpackManager, and Our Lord And Savior Gabe Newell/OB4MA's Bank & Backpack Space Customizer."
    Version: str = "1.0"
    Author: str = "Milo"
    SupportedGames: Game = Game.BL2 | Game.TPS | Game.AoDK

    Types: ModTypes = ModTypes.Gameplay
    SaveEnabledState: EnabledSaveType = EnabledSaveType.LoadOnMainMenu

    def __init__(self) -> None:
        self.Options = []
        self.create_initial_options()

    def create_initial_options(self) -> None:
        """
        Create the initial list of options for the Options menu.
        """
        self.bank_size = Options.Slider(
            "Bank Size",
            "Change the size of your character's bank",
            6,
            0,
            200,
            1,
        )
        self.backpack_size = Options.Slider(
            "Backpack Size",
            "Change the size of your character's backpack",
            39,
            0,
            200,
            1,
        )
        self.backpack_unlimited = Options.Boolean(
            "Backpack Unlimited",
            "Allow your backpack to hold unlimited items.  Does not permit purchasing items from vendors if the backpack contains more than the set limit.",
            False,
            ("Off", "On"),
        )
        self.Options = [
            self.bank_size,
            self.backpack_size,
            self.backpack_unlimited,
        ]

    def set_max_bank_slots(self, max_slots: int) -> None:
        """
        Updates the maximum size of the Bank.
        """
        inv_mgr = self.get_inventory_manager()
        if inv_mgr is None:
            return
        inv_mgr.TheBank.SetMaxSlots(self.bank_size.MaxValue)
        self.bank_size.MaxValue = inv_mgr.TheBank.MaxSlots
        
    def Enable(self) -> None:
        """
        Activates the StorageManager.
        """
        super().Enable()
        
    def Disable(self) -> None:
        """
        Deactivates the StorageManager.
        """
        self.set_max_bank_slots(42)  # original default
        super().Disable()

    def get_inventory_manager(self) -> unrealsdk.UObject:
        """
        Retrieves the InventoryManager for the current player.
        """
        player = unrealsdk.GetEngine().GamePlayers[0].Actor
        if player is None:
            return None
        if player.Pawn is None:
            return None
        return player.Pawn.InvManager

    @Hook("WillowGame.WillowHUD.CreateWeaponScopeMovie")
    def _GameLoad(self, caller: unrealsdk.UObject, function: unrealsdk.UFunction, params: unrealsdk.FStruct) -> bool:
        self.set_max_bank_slots(self.bank_size.MaxValue)
        
        for option in self.Options:
            self.ModOptionChanged(option, option.CurrentValue)
        return True

    def ModOptionChanged(self, option, newValue) -> None:
        inv_mgr = self.get_inventory_manager()
        if inv_mgr is None:
            return True
        if option == self.bank_size:
            if not inv_mgr.TheBank.SetSlotCount(newValue):
                unrealsdk.Log(f"Warning: unable to set bank slots to {newValue} - max slot count is {inv_mgr.TheBank.MaxSlots}")
            self.bank_size.CurrentValue = inv_mgr.TheBank.GetMaxSize()
        elif option == self.backpack_size:
            inv_mgr.SetInventoryMaxSize(newValue)
            self.backpack_size.CurrentValue = inv_mgr.GetUnreadiedInventoryMaxSize()
        elif option == self.backpack_unlimited:
            inv_mgr.bLimitedInventory = not newValue
            self.backpack_unlimited.CurrentValue = not inv_mgr.bLimitedInventory


RegisterMod(StorageManager())
