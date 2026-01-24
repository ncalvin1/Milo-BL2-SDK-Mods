from typing import TYPE_CHECKING, Any

import sys
import random
import unrealsdk
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct
from mods_base import build_mod, get_pc, hook, BoolOption, SliderOption, SpinnerOption, HiddenOption, NestedOption, DropdownOption, ButtonOption, SETTINGS_DIR

from . import characters, skills, skill_pool, class_mod_patcher

seed_option = HiddenOption[int](
    identifier="Seed",
    description="Random Number Generator seed value for current randomization.",
    value=0,
)

skill_sources = NestedOption(
    identifier="Skill Sources",
    description="Select which character classes will supply skills.",
    children=[],  # will be updated later
)

hidden_skills = SpinnerOption(
    identifier="Additional Skills",
    description="Include skills that may work only partially, not work at all, or even crash the game.  Misdocumented skills refer to a particular Action Skill but should work with any.",
    value="None",
    choices=["None", "Misdocumented", "All"],
)

action_skill = SpinnerOption(
    identifier="Action Skill",
    description="Select whether the action skill for the character is the default skill, one for a particular character class, or random.",
    value="Default",
    choices=["Default", "Random",],  # will be updated later
)

skill_density = SliderOption(
    identifier="Skill Density",
    description="Select how densely to populate the skill tree.",
    value=63,
    min_value=0,
    max_value=100,
    step=1,
    is_integer=True,  # floating-point not actually supported
)

randomize_tiers = BoolOption(
    identifier="Randomize Tier Points",
    description="Select how many skill points are needed to open each new tier of skills.",
    value=False,
    true_text="Random",
    false_text="5",
)

randomize_coms = BoolOption(
    identifier="Randomize COMs",
    description="Select whether to update class mods to reflect the character's new skills.",
    value=True,
    true_text="Random",
    false_text="Traditional",
)

__skill_choices = ["None"]

__cheat_entries = []
__active_cheat_idx = 0

def cleanup_cheats() -> None:
    """
    Go through cheat list, removing empty and duplicate entries.
    """

    global __active_cheat_idx

    cheat_skills = set()
    write_idx = 0

    cheat_skills.add("None")
    for read_idx in range(0, __active_cheat_idx):
        entry = __cheat_entries[read_idx]
        if not entry.children[0].value in cheat_skills:
            if read_idx > write_idx:
                target = __cheat_entries[write_idx]
                target.display_name = entry.display_name
                target.children[0].value = entry.children[0].value
                target.children[1].value = entry.children[1].value
                target.children[2].value = entry.children[2].value
            write_idx += 1
            cheat_skills.add(entry.children[0].value)
    if write_idx < __active_cheat_idx:
        # Create a new 'Add New' entry.
        target = __cheat_entries[write_idx]
        target.display_name = "Add New Cheat"
        target.description = "Force a skill to be granted."
        target.children[0].value = target.children[0].default_value
        target.children[1].value = target.children[1].default_value
        target.children[2].value = target.children[2].default_value
        __active_cheat_idx = write_idx
        
        # Hide all the rest up to the old 'Add New entry.'
        for write_idx in range(__active_cheat_idx + 1, len(__cheat_entries)):
             __cheat_entries[write_idx].is_hidden = True

        
def on_create_cheat(option, value) -> None:
    """
    Handle a skill change in a cheat entry.

    Args:
        option : SpinnerOption that was changed
        value : New value about to be assigned to SpinnerOption
    """
    global __active_cheat_idx

    if value == "None":
        # Delete when player returns to the previous menu.
        return
    
    parent = option.parent
    if __active_cheat_idx == parent.idx:
        # 'Add New' entry changed.
        __active_cheat_idx += 1
        if __active_cheat_idx < 10:
            __cheat_entries[__active_cheat_idx].is_hidden = False
            __cheat_entries[__active_cheat_idx].display_name = "Add New Cheat"
            __cheat_entries[__active_cheat_idx].description = "Force a skill to be granted."
    parent.description = f"Force \'{value}\' to be granted."
    parent.display_name = value
       

for option_idx in range(0,10):
    skill_option = SpinnerOption(
        identifier = "Skill",
        description = "Skill to insert into character's skillset.  Set to None to delete this cheat.",
        choices = __skill_choices,
        value = "None",
        on_change = on_create_cheat,
    )
    tier_option = SliderOption(
        identifier = "Maximum Tier",
        description = "Latest tier at which skill should appear.",
        value = 6,
        min_value = 1,
        max_value = 6,
        step = 1,
        is_integer = True,
    )
    com_option = BoolOption(
        identifier = "Include in special COM",
        description = "Add skill to one particular class mod.",
        value = False,
        true_text = "Include",
        false_text = "Do Not Include",
    )
    if option_idx != __active_cheat_idx:
        __cheat_entries.append(
            NestedOption(
                identifier = f"Cheat{option_idx}",
                description = "Force a skill to be granted.",
                display_name = "TBD",
                description_title = "",
                is_hidden = True,
                children = [skill_option, tier_option, com_option],
            ))                
    else:
        __cheat_entries.append(
            NestedOption(
                identifier = f"Cheat{option_idx}",
                description = "Force a skill to be granted.",
                display_name = "Add New Cheat",
                description_title = "",
                is_hidden = False,
                children = [skill_option, tier_option, com_option],
            ))
    __cheat_entries[-1].idx = option_idx
    skill_option.parent = __cheat_entries[-1]
        
cheat_option = NestedOption(
    identifier = "Cheats",
    description = "Force selected skills to appear in the character\'s skill set and optionally one class mod.",
    children = __cheat_entries,
)

def reroll(option):
    """
    Calculates a new random-number generator seed.
    """
    seed_option.value = random.randrange(sys.maxsize)

reroll_option = ButtonOption(
    identifier = "Reroll",
    description = "Roll a new set of skills.",
    on_press=reroll,
)    

__player_name : str = None

# This gets called after legacy LoadOnMainMenu mods are loaded, but before the
# main menu is populated.
@hook("WillowGame.WillowScrollingList:Refresh")
def post_main_menu(
        _obj: UObject,
        _args: WrappedStruct,
        _ret: Any,
        _func: BoundFunction,
) -> None:
    global __player_name
    global __skill_choices

    # Load character class info.
    if characters.Character.update_all():
        # Force skill catalog reload.
        skills.mark_dirty()
        skills.find_skills()  # needed early for required skill selection

        # Update menu options that depend on available classes.
        action_skill.choices = [ "Default", "Random" ] + characters.Character.names()
        skill_sources.children = [character.skill_option
                                  for character in characters.Character.characters()]

        # Set up the cheat menu skill list.
        # Make sure to keep the same mutable list so that we don't have to
        # update all of the cheat skill options.
        __skill_choices.clear()
        __skill_choices.append("None")
        for skill_fullname, skill in skills.__skills.items():
            __skill_choices.append(skill.skill_name)

    # Remove any empty or duplicate cheats from the cheat menu.
    cleanup_cheats()
             
    # Check if player name changed, and swap settings if it did.
    player_name : str = get_pc().PlayerPreferredCharacterName
    if player_name != __player_name:
        # Player changed.  Save old settings and change settings file.
        mod.save_settings()  # this might not be necessary
        mod.settings_file = SETTINGS_DIR / f"PlayerRandomizer_{player_name}.json"
        mod.load_settings()
        __player_name = player_name

        if seed_option.value == 0:
            # Hack: simulate pushing the Reroll button.
            reroll(reroll_option)


pool : skill_pool.SkillPool = None
enabled_sources : set[str] = None
com_patcher : class_mod_patcher.ClassModPatcher = class_mod_patcher.ClassModPatcher()
com_patched : bool = False

# This gets called when the player's skills are assembled at start of play.
@hook("WillowGame.PlayerSkillTree:Initialize")
def inject_skills(
        caller: UObject,
        args: WrappedStruct,
        _ret: Any,
        _func: BoundFunction,
) -> type[Block] | None:
    """
    Set up new skills for the randomized player, and update classmods.

    Args:
        caller:  Object invoking PlayerSkillTree.Initialize
        args:  Argument bindings for the call
        _ret:  no clue, but hoping it controls if next func in chain is called
        _func:  Stack context for function call
    """
    global pool
    global enabled_sources
    global com_patched

    # Force skills back into memory.
    characters.Character.load_packages()
    
    enabled_sources = set()
    for child in skill_sources.children:
        if child.value:
            enabled_sources.add(child.identifier)

    cheats = {}
    com_skills = set()
    for cheat in __cheat_entries:
        if cheat.idx >= __active_cheat_idx:
            break
        for skill_fullname, skill in skills.__skills.items():
            if skill.skill_name == cheat.children[0].value:
                cheats[skill_fullname] = cheat.children[1].value - 1
                if cheat.children[2].value:
                    com_skills.add(skill)
                break
            
    rng = random.Random(seed_option.value)
    pool = skill_pool.SkillPool(rng)
    pool.randomize_tree(args.SkillTreeDef,
                        enabled_sources,
                        hidden_skills.value,
                        action_skill.value,
                        skill_density.value,
                        randomize_tiers.value,
                        cheats)
    if randomize_coms.value:
        if not com_patched:
            skills.find_attribute_defs()
            skills.find_presentations()
            skills.flatten_presentations()
            com_patcher.record_coms(pool.get_current_char())
            com_patcher.randomize_coms(
                pool.get_class_mod_skills(),
                rng,
                pool.get_current_char(),
                com_skills,
            )
            for char in enabled_sources:
                characters.Character.from_name(char).apply_patches()
            com_patched = True
            
    #return Block

def reset_game() -> None:
    """
    Undoes any patches and changes the savefile back to the default file on
    disable.
    """
    global __player_name
    global com_patched

    # Unpatch coms, players, and skills.
    if com_patched:
        for char in enabled_sources:
            characters.Character.from_name(char).remove_patches()
        com_patcher.unrandomize_coms(pool.get_current_char())
        skills.unflatten_presentations()
        com_patched = False
    
    mod.settings_file = SETTINGS_DIR / "PlayerRandomizer.json"
    # TODO: consider hiding most options here
    mod.save_settings()
    __player_name = None  # do this to force reinit if mod is re-enabled later
    
mod = build_mod(
    options=(
        seed_option,
        skill_sources,
        hidden_skills,
        action_skill,
        skill_density,
        randomize_tiers,
        randomize_coms,
        cheat_option,
        reroll_option,
    ),
    on_disable=reset_game,
)
