# Code to update a randomized player's class mods to boost appropriate skills.


import unrealsdk
import random
from typing import Set, List, Generator
from .skills import Skill

class ClassModPatcher:
    """
    Updates the random player's COMs to boost skills from the randomized skill
    trees.
    """

    def __init__(self):
        self.original = {}
        self.coms = None

    @staticmethod
    def iterate_coms(
            char_class: str) -> Generator[unrealsdk.unreal.UObject, None, None]:
        """
        Iterate through all known class mods.

        Args:
            char_class:  Character class whose COMs should be updated

        Yields:
            A ClassModDefinition assigned to the specified char_class.
        """
        for com in unrealsdk.find_all("ClassModDefinition", True):
            if com.RequiredPlayerClass is None:
                continue
            if com.RequiredPlayerClass.Name == char_class:
                yield com

        # DLC classmods referencing another DLC use the
        # CrossDLCClassModDefinition subclass instead.
        for com in unrealsdk.find_all("CrossDLCClassModDefinition", True):
            if com.RequiredPlayerClassPathName.PathComponentNames[5] == char_class:
                yield com

    def record_coms(self, char_class: str) -> None:
        """
        Store the original contents of the modified class mods.

        Args:
            char_class:  Character class whose COMs should be archived
        """
        self.coms = {}
        for com in ClassModPatcher.iterate_coms(char_class):
            skill_slot_map = {}
            self.coms[com._path_name()] = skill_slot_map
            slot_index = 0
            for attribute_slot in com.AttributeSlotEffects:
                if attribute_slot.SlotName.startswith("Skill"):
                    if attribute_slot.AttributeToModify is None:
                        unrealsdk.Log(f"Null {com._path_name()}.AttributeSlotEffects[{slot_index}].AttributeToModify")
                        continue
                    skill_slot_map[
                        slot_index
                    ] = attribute_slot.AttributeToModify._path_name()
                slot_index += 1

    def randomize_coms(self,
                       skills : List[Skill],
                       rng: random.Random,
                       char_class : str,
                       cheat_skills : set[Skill]) -> None:
        """
        Modify the random character's class mods to boost random skills from
            the character's new skill tree.

        Args:
            skills:  A list of Skills from which to choose COM boosts.
            rng:  The seeded random number generator to use when choosing.
            char_class:  Character class whose COMs should be randomized.
            cheat_skills:  Skills to stuff into one random COM.
        """
        com = None
        special_com_name = None

        if len(skills) < 5:
            unrealsdk.logging.warning(f"Skipping class mod randomization as there are only {len(skills)} upgradable skills available.")
            return

        while True:
            special_com_name = rng.choice(list(self.coms.keys()))
            if special_com_name.startswith("GD_Aster"):
                # Avoid the Tiny Tina class mods; they're too rare.
                continue
            skill_slot_map = self.coms[special_com_name]
            if len(cheat_skills) > 3:
                # Look for a legendary COM.
                if len(skill_slot_map) < 4:
                    continue
            elif len(skill_slot_map) > 3:
                # Look for a non-legendary COM - NOT one of the Tiny Tina ones.
                continue
            break
        unrealsdk.logging.warning(f"Special COM is {special_com_name}")

        for com_name, skill_slot_map in self.coms.items():
            used_skills = set()
            wanted_com_skills = 0
            com = unrealsdk.find_object("ClassModDefinition", com_name)
            for slot_index in skill_slot_map:
                skill = None
                if com_name == special_com_name and len(cheat_skills) > 0:
                    skill = cheat_skills.pop()
                else:
                    while True:
                        skill = rng.choice(skills)
                        if not skill.full_name in used_skills:
                            break
                used_skills.add(skill.full_name)
                com.AttributeSlotEffects[
                    slot_index
                ].AttributeToModify = skill.attribute_def
                
                
    def unrandomize_coms(self, char_class) -> None:
        """
        Restore the original contents of the modified class mods.

        Args:
            char_class:  Character class whose COMs were randomized.
        """
        if self.coms is None:
            return
        for com in ClassModPatcher.iterate_coms(char_class):
            for slot_index, attr_name in self.coms[com._path_name()].items():
                com.AttributeSlotEffects[
                    slot_index
                ].AttributeToModify = unrealsdk.find_object(
                    "InventoryAttributeDefinition", attr_name)

