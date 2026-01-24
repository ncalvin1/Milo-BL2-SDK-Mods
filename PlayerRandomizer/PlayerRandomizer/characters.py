# Classes and methods for handling player characters.

import unrealsdk
from mods_base import BoolOption
from . import character_hint, dependency, skills
from typing import Dict, Generator, List


def class_from_obj_name(name: str) -> str:
    """
    Determine the associated base player class from a UE object name.
        
    Args:
        name:  Results of a _path_name() call on a UObject.

    Returns:
        The base class name associated with the UObject.
    """
    elements = name.split("_")
    if len(elements) < 2:
        return None
    char = elements[1]
    if char.startswith("Lilac"):
        char = "Psycho"
    elif char.startswith("Tulip"):
        char = "Mechromancer"
    elif char.startswith("Doppel"):
        char = "Doppelganger"
    return char


class Character:
    """
    Represents a playable class in the game.
    """

    def __init__(self, class_def : unrealsdk.unreal.UObject) -> None:
        """
        Set up the base class portion.  Call update() to fill in customized
        class info, such as the character's name.  Initialization is split in
        two to accommodate late-changing information from custom characters.

        Args:
            class_def : PlayerClassDefinition object for the character
        """
        self.name = class_from_obj_name(class_def.SkillTreePath)
        self.skill_tree_name = None
        self.character_name = None
        self.attribute_package = None
        self.is_custom = False

        self.skill_option = BoolOption(
            identifier = "",
            description = "Add skills for TBD to the selection pool.",
            value = True,
            true_text = "Yes",
            false_text = "No",
        )

    def update(self, class_def : unrealsdk.unreal.UObject) -> bool:
        """
        Finish initializing the playable class.  Call this after any custom
        characters have been loaded.

        Args:
            class_def:  PlayerClassDefinition object for the character

        Returns:
            True if the Character has changed since initialization or the last
            update.
        """
        if self.character_name != class_def.CharacterNameId.CharacterName:
            self.character_name = class_def.CharacterNameId.CharacterName
            self.skill_option.identifier = self.character_name
            self.skill_option.display_name = f"Use {self.character_name} Skills"
            self.skill_option.description = f"Add skills for {self.character_name} to the selection pool."
            self.action_skill = None
            self.pure_skills = []
            self.extra_skills = []
            self.suppressed_skills = []
            self.misdocumented_skills = []
            self.suppressed_skill_names = []
            self.dependencies = []
            self.patches = []
            return True
        return False
        
    def iterate_tree_skills(self) -> Generator[unrealsdk.unreal.UObject, None, None]:
        """
        Iterate through all skills for this player character class.

        Yields:
            A SkillDefinition object.
        """
        tree = unrealsdk.find_object(
            "SkillTreeBranchDefinition", self.skill_tree_name)
        if tree is None:
            unrealsdk.Log(f"Warning: {self.skill_tree_name} not found.")
            return
        yield tree.Tiers[0].Skills[0]  # action skill
        for branch in tree.Children:
            for tier in branch.Tiers:
                for skill in tier.Skills:
                    if skill is None:
                        continue
                    yield skill

    def get_suppressed_skills(self) -> List[skills.Skill]:
        """
        Retrieve the list of skills eliminated from consideration.

        Returns:
            The list of skills eliminated from consideration.
        """
        return self.suppressed_skill_names

    def set_action_skill(self, skill: skills.Skill) -> None:
        """
        Store the action skill for the player character class.

        Args:
            skill:  The action Skill.
        """
        self.action_skill = skill

    def add_passive_skill(self, skill: skills.Skill) -> None:
        """
        Add a passive skill to the player character class.

        Args:
            skill:  The passive Skill to add.
        """
        self.pure_skills.append(skill)

    def add_extra_skill(self, skill: skills.Skill) -> None:
        """
        Add a 'free' skill to the player character class.

        Args:
            skill:  The 'free' skill to add.
        """
        self.extra_skills.append(skill)

    def add_undocumented_skill(self, skill: skills.Skill) -> None:
        """
        Add a skill that was not included in the original skill tree.

        Args:
            skill:  The 'undocumented' skill to add.
        """
        if skill.full_name in self.suppressed_skill_names:
            self.suppressed_skills.append(skill)
        else:
            self.misdocumented_skills.append(skill)

    def add_dependency(self, dep : dependency.Dependency) -> None:
        """
        Declare a skill dependency.

        Args:
            dep:  The dependency.Dependency to add.
        """
        self.dependencies.append(dep)

    def apply_patches(self) -> None:
        """
        Apply all applicable patches to the skill pool for this player class.
        """
        for patch, _ in self.patches:
            patch()

    def remove_patches(self) -> None:
        """
        Remove all applicable patches from the skill pool for this player class.
        """
        for _, unpatch in self.patches:
            unpatch()

    @classmethod
    def update_all(cls) -> bool:
        """
        Update all character classes in the pool.

        Returns:
            True if any of the character classes changed since the last update.
        """
        changed = False
        cls.__char_by_name = {}
        cls.__has_custom_char = False
        for class_def in unrealsdk.find_all("PlayerClassDefinition"):
            if not class_def.CharacterNameId is None:
                char_class = class_from_obj_name(
                    class_def.SkillTreePath)
                try:
                    character = cls.__char_by_cls[char_class]
                except KeyError:
                    character = Character(class_def)
                    cls.__char_by_cls[char_class] = character

                if character.update(class_def):
                    # Name changed.  Need to reread skills.
                    changed = True
                    if character.character_name in character_hint.HINT_MAP:
                        hint = character_hint.HINT_MAP[character.character_name]
                        character.dependencies = hint.dependencies
                        character.suppressed_skill_names = hint.suppressed_skills
                        character.patches = hint.patches
                        character.is_custom = False
                    else:
                        character.is_custom = True
                        cls.__has_custom_char = True
                cls.__char_by_name[character.character_name] = character

        if changed:
            # Also locate skill trees.  There has to be a more direct way...
            Character.load_packages()

            for tree in unrealsdk.find_all("SkillTreeBranchDefinition", False):
                if len(tree.Children) == 0:
                    continue
                tree_obj_name = tree._path_name()
                char_class = class_from_obj_name(tree_obj_name)
                character = cls.__char_by_cls[char_class]
                character.skill_tree_name = tree_obj_name

        return changed

    @classmethod
    def load_packages(cls) -> None:
        """
        Force-loads all character packages.
        """
        for package in cls.__PACKAGES:
            # Loads of nonexistent packages fail silently.
            unrealsdk.load_package(package, flags=0x4000)

    
    @classmethod
    def from_name(cls, name : str) -> 'Character':
        """
        Given a character name, return the associated Character.

        Args:
            name : Name of the Character being requested.

        Returns:
            The associated Character, or None if name is not recognized.
        """
        return cls.__char_by_name.get(name, None)

    @classmethod
    def from_cls(cls, char_class : str) -> 'Character':
        """
        Given a base player class, return the associated Character.

        Args:
            char_class : Base class name of the Character being requested.

        Returns:
            The associated Character, or None if the class is not recognized.
        """
        return cls.__char_by_cls.get(char_class, None)
    
    @classmethod
    def names(cls) -> List[str]:
        """
        Retrieve a list of all known player character names.

        Returns:
            A sequence of known player character names.
        """
        return list(cls.__char_by_name.keys())

    @classmethod
    def characters(cls) -> List['Character']:
        """
        Retrieve a list of all characters.

        Returns:
            A sequence of known Character objects.
        """
        return list(cls.__char_by_name.values())


    __char_by_name : Dict[str, 'Character'] = {}
    __char_by_cls : Dict[str, 'Character'] = {}
    __has_custom_char : bool = False

    __PACKAGES : List[str] = [
        # BL2
        "GD_Assassin_Streaming_SF",
        "GD_Mercenary_Streaming_SF",
        "GD_Siren_Streaming_SF",
        "GD_Lilac_Psycho_Streaming_SF",
        "GD_Tulip_Mechro_Streaming_SF",
        "GD_Soldier_Streaming_SF",
        
        # TPS
        "GD_Enforcer_Streaming_SF",
        "GD_Gladiator_Streaming_SF",
        "GD_Lawbringer_Streaming_SF",
        "GD_Prototype_Streaming_SF",
        "Quince_Doppel_Streaming_SF",
        "Crocus_Baroness_Streaming_SF",
    ]
