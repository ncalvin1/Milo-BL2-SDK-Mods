# Quick-n-dirty mod to block selling or dropping starred items.

import unrealsdk
from unrealsdk.hooks import Block
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct
from mods_base import build_mod, hook

from typing import TYPE_CHECKING, Any

PlayerMark = unrealsdk.find_enum("PlayerMark")

@hook("WillowGame.VendingMachineExGFxMovie:ConditionalStartTransfer")
def conditional_start_transfer(
    caller: UObject,
    _args: WrappedStruct,
    _ret: Any,
    _func: BoundFunction,
) -> type[Block] | None:
    """
    Intercepts attempts to sell a starred item.

    Args:
        caller:  Object invoking hook
        _args:  Argument bindings for the call
        ret:  Return value for call
        _func:  Stack context for function call

    Returns:
        Block if the item should not be dropped.
    """
    if caller.IsCurrentSelectionSell() and caller.CurrentSelectionItem.GetMark() == PlayerMark.PM_Favorite:
        caller.PlayFeedback_CannotAfford()
        ret = False
        return Block
    else:
        ret = True

@hook("WillowGame.StatusMenuInventoryPanelGFxObject:DropSelectedThing")
def drop_selected_thing(
    caller: UObject,
    _args: WrappedStruct,
    ret: Any,
    _func: BoundFunction,
) -> type[Block] | None:
    """
    Intercepts attempts to sell a starred item.

    Args:
        caller:  Object invoking hook
        _args:  Argument bindings for the call
        ret:  Return value for call
        _func:  Stack context for function call

    Returns:
        Block if sale has been prevented.
    """   
    item = caller.GetSelectedThing()
    if item.GetMark() == PlayerMark.PM_Favorite:
        caller.ParentMovie.PlayUISound("ResultFailure")
        ret = False
        return Block
    else:
        ret = True

mod = build_mod()

