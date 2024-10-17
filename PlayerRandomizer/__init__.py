from __future__ import annotations

import unrealsdk
import os
import sys
import json
import random
import re
from collections import namedtuple
from dataclasses import dataclass, field
from typing import Set, List, Dict, Generator, Union

from ..ModManager import SDKMod, RegisterMod
from Mods.ModMenu import Game, Hook, ModTypes, Options, EnabledSaveType, LoadModSettings, SaveModSettings

try:
    from Mods.Structs import NameBasedObjectPath, AttributeInitializationData, AttributeSlotEffectData, Tier
except ImportError as ex:
    import webbrowser
    webbrowser.open("https://bl-sdk.github.io/requirements/?mod=PlayerRandomizer&Structs")
    raise ex

try:
    from Mods.Enums import EAttributeDataType, EAttributeInitializationRounding, ESkillType, ETrackedSkillType, EModifierType
except ImportError as ex:
    import webbrowser
    webbrowser.open("https://bl-sdk.github.io/requirements/?mod=PlayerRandomizer&Enums")
    raise ex


class UnlistedSkillException(Exception):
    """
    Thrown when a required skill is not in the set of selected skill sources.
    """
    def __init__(self, skill_name):
        self.skill_name = skill_name

        
def patch_nth_degree() -> None:
    """
    Fix game freeze when The Nth Degree is boosted more than +8.
    """
    nth_bpd = unrealsdk.FindObject(
        "BehaviorProviderDefinition",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TheNthDegree.BehaviorProviderDefinition_0"
    )
    if nth_bpd is None:
        return

    nth_seq = nth_bpd.BehaviorSequences[0]
    nth_seq.EventData2[0].OutputLinks.ArrayIndexAndLength = 327681
    nth_seq.EventData2[1].OutputLinks.ArrayIndexAndLength = 262145
    nth_seq.BehaviorData2[3].OutputLinks.ArrayIndexAndLength = 131075
    nth_seq.ConsolidatedOutputLinkData[0].LinkIdAndLinkedBehavior = -16777213
    nth_seq.ConsolidatedOutputLinkData[2].LinkIdAndLinkedBehavior = 5
    nth_seq.ConsolidatedOutputLinkData[3].LinkIdAndLinkedBehavior = 16777218
    nth_seq.ConsolidatedOutputLinkData[4].LinkIdAndLinkedBehavior = 33554432
    nth_seq.ConsolidatedOutputLinkData[5].LinkIdAndLinkedBehavior = 1
    
    nth_seq.BehaviorData2[2].Behavior.bNoSkillStacking=True

def unpatch_nth_degree() -> None:
    """
    Undo the effects of patch_nth_degree.
    """
    nth_bpd = unrealsdk.FindObject(
        "BehaviorProviderDefinition",
        "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TheNthDegree.BehaviorProviderDefinition_0"
    )
    if nth_bpd is None:
        return
    
    nth_seq = nth_bpd.BehaviorSequences[0]
    nth_seq.EventData2[0].OutputLinks.ArrayIndexAndLength = 262145
    nth_seq.EventData2[1].OutputLinks.ArrayIndexAndLength = 327681
    nth_seq.BehaviorData2[3].OutputLinks.ArrayIndexAndLength = 131074
    nth_seq.ConsolidatedOutputLinkData[0].LinkIdAndLinkedBehavior = -16777212
    nth_seq.ConsolidatedOutputLinkData[2].LinkIdAndLinkedBehavior = 16777218
    nth_seq.ConsolidatedOutputLinkData[3].LinkIdAndLinkedBehavior = 33554432
    nth_seq.ConsolidatedOutputLinkData[4].LinkIdAndLinkedBehavior = 1
    nth_seq.ConsolidatedOutputLinkData[5].LinkIdAndLinkedBehavior = 5
    
    nth_seq.BehaviorData2[2].Behavior.bNoSkillStacking=False


class Dependency:
    """
    Declares relationships between skills.  A dependency can be provided by
    one or more skills; it can grant zero or more 'free' skills when satisfied;
    it can be required by zero or more skills; and it can be wanted by skills
    that are documented to need it but don't actually require it to function.
    """

    def __init__(self, name : str) -> None:
        """
        Args:
            name : A human-friendly label for the dependency.  Used for logging.
        """
        self.name = name
        self.providers = []
        self.extra_skills = []
        self.dependers = []
        self.wanters = []

    def provided_by(self, providers : List[str]) -> Dependency:
        """
        Sets the skills that supply the dependency.  See the Builder pattern.

        Args:
            providers:  List of skills that fulfill the dependency.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.providers = providers
        return self

    def grants(self, extra_skills : List[str]) -> Dependency:
        """
        Sets the skills supplied free by the dependency.  See the Builder
        pattern.

        Args:
            extra_skills:  List of skills granted by the dependency.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.extra_skills = extra_skills
        return self

    def required_by(self, dependers : List[str]) -> Dependency:
        """
        Sets the skills that need the dependency.  See the Builder pattern.

        Args:
            dependers:  List of skills that need the dependency to function
                properly.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.dependers = dependers
        return self

    def wanted_by(self, wanters : List[str]) -> Dependency:
        """
        Sets the skills that don't really need the dependency but are documented
            to require it.

        Args:
            wanters:  List of skills that want the dependency.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.wanters = wanters
        return self


class CharacterHint:
    """
    Stores any quirks about a character when using it with the PlayerRandomizer.
    """

    def __init__(self) -> None:
        self.dependencies = []
        self.suppressed_skills = []
        self.patches = []

    def add_dependency(self, dependency : Dependency) -> CharacterHint:
        """
        Adds a skill dependency declaration to the CharacterHint.  See the
        Builder pattern.

        Args:
            dependency:  Skill dependency to add.

        Returns:
            The CharacterHint, so that other builders can be chained.
        """
        self.dependencies.append(dependency)
        return self

    def suppress(self, suppressed_skills : List[str]) -> CharacterHint:
        """
        Prevents a skill from being considered for the character's skill set.
        Most of these will be helper skills that for some reason contain a
        description and an icon.

        Args:
            suppressed_skills:  Skills to remove from consideration.

        Returns:
            The CharacterHint, so that other builders can be chained.
        """
        self.suppressed_skills = suppressed_skills
        return self

    def patch(self, patch_function : Callable[None, None],
              unpatch_function : Callable[None, None]) -> CharacterHint:
        """
        Declares a skill patch and its corresponding unpatch.  Some skills
        were not designed to be boosted with class mods, and need minor fixes
        to function correctly.

        Args:
            patch_function:  Parameter-less function to patch a SkillDefinition.
            unpatch_function:  Parameter-less function to undo the effects
                of patch_function.

        Returns:
            The CharacterHint, so that other builders can be chained.
        """
        self.patches.append((patch_function, unpatch_function))
        return self

            
class Character:
    """
    Represents a playable class in the game.
    """

    def __init__(self, class_def : unrealsdk.UObject) -> None:
        """
        Set up the base class portion.  Call update() to fill in customized
        class info, such as the character's name.  Initialization is split in
        two to accommodate late-changing information from custom characters.

        Args:
            class_def : PlayerClassDefinition object for the character
        """
        self.name = Characters.class_from_obj_name(class_def.SkillTreePath)
        self.skill_tree_name = None
        self.character_name = None
        self.attribute_package = None
        self.is_custom = False

        self.skill_option = Options.Boolean(
            Caption = "TBD",
            Description = "Add skills for TBD to the selection pool.",
            StartingValue = True,
            Choices = ("No", "Yes"),
            IsHidden = False,
        )

    def update(self, class_def : unrealsdk.UObject) -> Bool:
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
            self.skill_option.Caption = f"Use {self.character_name} Skills"
            self.skill_option.Description = f"Add skills for {self.character_name} to the selection pool."
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
        
    def iterate_tree_skills(self) -> Generator[unrealsdk.UObject, None, None]:
        """
        Iterate through all skills for this player character class.

        Yields:
            A SkillDefinition object.
        """
        tree = unrealsdk.FindObject(
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

    def get_suppressed_skills(self) -> List(Skill):
        """
        Retrieve the list of skills eliminated from consideration.

        Returns:
            The list of skills eliminated from consideration.
        """
        return self.suppressed_skill_names

    def set_action_skill(self, skill: Skill) -> None:
        """
        Store the action skill for the player character class.

        Args:
            skill:  The action Skill.
        """
        self.action_skill = skill

    def add_passive_skill(self, skill: Skill) -> None:
        """
        Add a passive skill to the player character class.

        Args:
            skill:  The passive Skill to add.
        """
        self.pure_skills.append(skill)

    def add_extra_skill(self, skill: Skill) -> None:
        """
        Add a 'free' skill to the player character class.

        Args:
            skill:  The 'free' skill to add.
        """
        self.extra_skills.append(skill)

    def add_undocumented_skill(self, skill: Skill) -> None:
        """
        Add a skill that was not included in the original skill tree.

        Args:
            skill:  The 'undocumented' skill to add.
        """
        if skill.full_name in self.suppressed_skill_names:
            self.suppressed_skills.append(skill)
        else:
            self.misdocumented_skills.append(skill)

    def add_dependency(self, dependency) -> None:
        """
        Declare a skill dependency.

        Args:
            dependency:  The Dependency to add.
        """
        self.dependencies.append(dependency)

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


class Characters:
    """
    Tracks the set of available player character classes.
    """

    def __init__(self) -> None:
        self.char_by_name = {}
        self.char_by_cls = {}
        self.has_custom_char = False

    @staticmethod
    def class_from_obj_name(name: str) -> str:
        """
        Determine the associated base player class from a UE object name.
        
        Args:
            name:  Results of a GetObjectName() call on a UObject.

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
        
    def update(self) -> Bool:
        """
        Update all character classes in the pool.

        Returns:
            True if any of the character classes changed since the last update.
        """
        changed = False
        self.char_by_name = {}
        for class_def in unrealsdk.FindAll("PlayerClassDefinition"):
            if not class_def.CharacterNameId is None:
                char_class = Characters.class_from_obj_name(
                    class_def.SkillTreePath)
                try:
                    character = self.char_by_cls[char_class]
                except KeyError:
                    character = Character(class_def)
                    self.char_by_cls[char_class] = character
                if character.update(class_def):
                    # Name changed.  Need to reread skills.
                    changed = True
                    if character.character_name in self.hint_map:
                        hint = self.hint_map[character.character_name]
                        character.dependencies = hint.dependencies
                        character.suppressed_skill_names = hint.suppressed_skills
                        character.patches = hint.patches
                        character.is_custom = False
                    else:
                        character.is_custom = True
                        self.has_custom_char = True
                self.char_by_name[character.character_name] = character

        if changed:
            # Also locate skill trees.  There has to be a more direct way...
            for tree in unrealsdk.FindAll("SkillTreeBranchDefinition"):
                if len(tree.Children) == 0:
                    continue
                tree_obj_name = tree.GetObjectName()
                char_class = Characters.class_from_obj_name(tree_obj_name)
                character = self.char_by_cls[char_class]
                character.skill_tree_name = tree_obj_name

        return changed

    def from_name(self, name : str) -> Character:
        """
        Given a character name, return the associated Character.

        Args:
            name : Name of the Character being requested.

        Returns:
            The associated Character, or None if name is not recognized.
        """
        return self.char_by_name.get(name, None)

    def from_cls(self, cls : str) -> Character:
        """
        Given a base player class, return the associated Character.

        Args:
            cls : Base class name of the Character being requested.

        Returns:
            The associated Character, or None if the class is not recognized.
        """
        return self.char_by_cls.get(cls, None)

    def names(self) -> List[str]:
        """
        Retrieve a list of all known player character names.

        Returns:
            A sequence of known player character names.
        """
        return list(self.char_by_name.keys())

    def __iter__(self):
        """
        Iterate over the Characters in the pool.

        Yields:
            A Character.
        """
        for character in self.char_by_name.values():
            yield character

    hint_map : Dict(str, CharacterHint) = {
        # BL2
        "Axton" : CharacterHint().add_dependency(Dependency(
            "Scorpio"
        ).provided_by([
            "GD_Soldier_Skills.Scorpio.Skill_Scorpio",
        ]).required_by([
            "GD_Soldier_Skills.Guerrilla.DoubleUp",
            "GD_Soldier_Skills.Guerrilla.LaserSight",
            "GD_Soldier_Skills.Guerrilla.ScorchedEarth",
            "GD_Soldier_Skills.Guerrilla.Sentry",
            "GD_Soldier_Skills.Guerrilla.TacticalWithdrawal",
            "GD_Soldier_Skills.Gunpowder.Battlefront",
            "GD_Soldier_Skills.Gunpowder.LongBowTurret",
            "GD_Soldier_Skills.Gunpowder.Nuke",
            "GD_Soldier_Skills.Survival.Gemini",
            "GD_Soldier_Skills.Survival.Mag-Lock",
            "GD_Soldier_Skills.Survival.PhalanxShield",
        ])),

        "Gaige" : CharacterHint().add_dependency(Dependency(
            "DeathTrap"
        ).provided_by([
            "GD_Tulip_Mechromancer_Skills.Action.Skill_DeathTrap",
        ]).required_by([
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.BuckUp",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.ExplosiveClap",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.SharingIsCaring",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.AnnoyedAndroid",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.RobotRampage",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.LightningStrike",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.MakeItSparkle",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.OneTwoBoom",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.TheStare",
        ]).wanted_by([
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.20PercentCooler",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.MadeOfSternerStuff",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.PotentAsAPony",
            "GD_Tulip_Mechromancer_Skills.BestFriendsForever.UpshotRobot",
            "GD_Tulip_Mechromancer_Skills.LittleBigTrouble.StrengthOfFiveGorillas",
        ])).add_dependency(Dependency(
            "Anarchy"
        ).provided_by([
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.Anarchy",
        ]).required_by([
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.PreshrunkCyberpunk",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.Discord",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TypecastIconoclast",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.RationalAnarchist",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.WithClaws",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.BloodSoakedShields",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.DeathFromAbove",
        ])),

        "Krieg" : CharacterHint().add_dependency(Dependency(
            "BuzzAxe"
        ).provided_by([
            "GD_Lilac_SkillsBase.ActionSkill.Skill_Psycho",
        ]).required_by([
            "GD_Lilac_Skills_Bloodlust.Skills.BloodTrance",
            "GD_Lilac_Skills_Bloodlust.Skills.BuzzAxeBombadier",
            "GD_Lilac_Skills_Bloodlust.Skills.TasteOfBlood",
            "GD_Lilac_Skills_Mania.Skills.ReleaseTheBeast",
        ]).wanted_by([
            "GD_Lilac_Skills_Mania.Skills.FuelTheRampage",
            "GD_Lilac_Skills_Mania.Skills.LightTheFuse",
        ])).add_dependency(Dependency(
            "Bloodlust"
        ).provided_by([
            "GD_Lilac_Skills_Bloodlust.Skills.BloodfilledGuns",
            "GD_Lilac_Skills_Bloodlust.Skills.BloodyTwitch",
        ]).required_by([
            "GD_Lilac_Skills_Bloodlust.Skills.BloodOverdrive",
            "GD_Lilac_Skills_Bloodlust.Skills.BloodyRevival",
            "GD_Lilac_Skills_Bloodlust.Skills.BloodBath",
            "GD_Lilac_Skills_Bloodlust.Skills.BloodEuphoria",
            "GD_Lilac_Skills_Bloodlust.Skills.FuelTheBlood",
            "GD_Lilac_Skills_Bloodlust.Skills.BoilingBlood",
            "GD_Lilac_Skills_Bloodlust.Skills.NervousBlood",
            "GD_Lilac_Skills_Bloodlust.Skills.Bloodsplosion",
        ]).grants([
            "GD_Lilac_Skills_Bloodlust.Skills._Bloodlust",
        ])).add_dependency(Dependency(
            "Hellborn"
        ).provided_by([
            "GD_Lilac_Skills_Hellborn.Skills.BurnBabyBurn",
            "GD_Lilac_Skills_Hellborn.Skills.DelusionalDamage",
            "GD_Lilac_Skills_Hellborn.Skills.ElementalElation",
            "GD_Lilac_Skills_Hellborn.Skills.ElementalEmpathy",
            "GD_Lilac_Skills_Hellborn.Skills.FireFiend",
            "GD_Lilac_Skills_Hellborn.Skills.FlameFlare",
            "GD_Lilac_Skills_Hellborn.Skills.FuelTheFire",
            "GD_Lilac_Skills_Hellborn.Skills.HellfireHalitosis",
            "GD_Lilac_Skills_Hellborn.Skills.NumbedNerves",
            "GD_Lilac_Skills_Hellborn.Skills.PainIsPower",
            "GD_Lilac_Skills_Hellborn.Skills.RavingRetribution",
        ]).grants([
            "GD_Lilac_Skills_Hellborn.Skills.FireStatusDetector",
            "GD_Lilac_Skills_Hellborn.Skills.AppliedStatusEffectListener",
        ])).suppress([
            "GD_Lilac_Skills_Bloodlust.Skills.FuelTheBloodChild",
        ]),

        "Maya" : CharacterHint().add_dependency(Dependency(
            "Phaselock"
        ).provided_by([
            "GD_Siren_Skills.Phaselock.Skill_Phaselock",
        ]).required_by([
                "GD_Siren_Skills.Cataclysm.Helios",
                "GD_Siren_Skills.Cataclysm.Ruin",
                "GD_Siren_Skills.Harmony.Elated",
                "GD_Siren_Skills.Harmony.Res",
                "GD_Siren_Skills.Harmony.Wreck",
                "GD_Siren_Skills.Motion.Quicken",
                "GD_Siren_Skills.Motion.SubSequence",
                "GD_Siren_Skills.Motion.Suspension",
                "GD_Siren_Skills.Motion.ThoughtLock",
        ]).wanted_by([
            "GD_Siren_Skills.Cataclysm.ChainReaction",
            "GD_Siren_Skills.Harmony.SweetRelease",
            "GD_Siren_Skills.Motion.Converge",
        ])).patch(patch_nth_degree, unpatch_nth_degree),

        "Salvador" : CharacterHint().add_dependency(Dependency(
            "Gunzerk"
        ).provided_by([
            "GD_Mercenary_Skills.ActionSkill.Skill_Gunzerking",
        ]).required_by([
            "GD_Mercenary_Skills.Gun_Lust.DivergentLikness",
            "GD_Mercenary_Skills.Gun_Lust.DownNotOut",
            "GD_Mercenary_Skills.Rampage.YippeeKiYay",
        ]).wanted_by([
            "GD_Mercenary_Skills.Brawn.AintGotTimeToBleed",
            "GD_Mercenary_Skills.Brawn.BusThatCantSlowDown",
            "GD_Mercenary_Skills.Brawn.ComeAtMeBro",
            "GD_Mercenary_Skills.Gun_Lust.KeepItPipingHot",
            "GD_Mercenary_Skills.Rampage.DoubleYourFun",
            "GD_Mercenary_Skills.Rampage.GetSome",
            "GD_Mercenary_Skills.Rampage.ImReadyAlready",
            "GD_Mercenary_Skills.Rampage.KeepFiring",
            "GD_Mercenary_Skills.Rampage.LastLonger",
            "GD_Mercenary_Skills.Rampage.SteadyAsSheGoes",
        ])),

        "Zero" : CharacterHint().add_dependency(Dependency(
            "Deception"
        ).provided_by([
            "GD_Assassin_Skills.ActionSkill.Skill_Deception",
        ]).required_by([
            "GD_Assassin_Skills.Bloodshed.Execute",
            "GD_Assassin_Skills.Bloodshed.ManyMustFall",
            "GD_Assassin_Skills.Cunning.DeathBlossom",
            "GD_Assassin_Skills.Cunning.Unforseen",
        ]).wanted_by([
            "GD_Assassin_Skills.Cunning.Innervate",
        ])),

        # TPS
        "Athena" : CharacterHint().add_dependency(Dependency(
            "Aspis"
        ).provided_by([
            "GD_Gladiator_Skills.ActionSkill.Skill_Gladiator",
        ]).required_by([
            "GD_Gladiator_Skills.Phalanx.Clear",                
            "GD_Gladiator_Skills.Phalanx.Ephodos",
            "GD_Gladiator_Skills.Phalanx.HoldTheLine",
            "GD_Gladiator_Skills.Phalanx.Invictus",
            "GD_Gladiator_Skills.Phalanx.PrepareForGlory",
            "GD_Gladiator_Skills.Phalanx.PrismaticAegis",
            "GD_Gladiator_Skills.Phalanx.ReturningFire",
            "GD_Gladiator_Skills.Phalanx.Stalwart",
            "GD_Gladiator_Skills.Phalanx.UnitedFront",
            "GD_Gladiator_Skills.Phalanx.User",
            "GD_Gladiator_Skills.Phalanx.Vanguard",
            "GD_Gladiator_Skills.CeraunicStorm.Superconductor",
            "GD_Gladiator_Skills.CeraunicStorm.ZeusRage",
        ])).add_dependency(Dependency(
            "Bleeding"
        ).provided_by([
            "GD_Gladiator_Skills.Xiphos.Rend",
        ]).required_by([
            "GD_Gladiator_Skills.Xiphos.Bloodlust",
            "GD_Gladiator_Skills.Xiphos.Tear",
            "GD_Gladiator_Skills.Xiphos.FuryOfTheArena",
        ])).add_dependency(Dependency(
            "Storm Weaving"
        ).provided_by([
            "GD_Gladiator_Skills.CeraunicStorm.StormWeaving",
        ]).required_by([
            "GD_Gladiator_Skills.CeraunicStorm.ElementalBarrage",
        ])).add_dependency(Dependency(
            "Maelstrom"
        ).provided_by([
            "GD_Gladiator_Skills.CeraunicStorm.Maelstrom",
            "GD_Gladiator_Skills.CeraunicStorm.Overload",
            "GD_Gladiator_Skills.CeraunicStorm.HadesShackles",
        ]).required_by([
            "GD_Gladiator_Skills.CeraunicStorm.Conduit",
            "GD_Gladiator_Skills.CeraunicStorm.Smite",
            "GD_Gladiator_Skills.CeraunicStorm.Unrelenting",
        ])),

        "Aurelia" : CharacterHint().add_dependency(Dependency(
            "Frost Shard"
        ).provided_by([
            "Crocus_Baroness_ActionSkill.ActionSkill.Skill_ColdAsIce",
        ]).required_by([
            "Crocus_Baroness_ColdMoney.Skills.ColdAdvance",
            "Crocus_Baroness_ColdMoney.Skills.FragmentRain",
            "Crocus_Baroness_ColdMoney.Skills.Frostbite",
            "Crocus_Baroness_ColdMoney.Skills.PolarVortex",
            "Crocus_Baroness_ColdMoney.Skills.ShortSummer",
            'Crocus_Baroness_ColdMoney.Skills.Whiteout',
        ])).add_dependency(Dependency(
            "Contract"
        ).provided_by([
            "Crocus_Baroness_Servant.Skills.ContractualObligations",
        ]).required_by([
            "Crocus_Baroness_Servant.Skills.AllGloryToTheMaster",
            "Crocus_Baroness_Servant.Skills.Duchess",
            "Crocus_Baroness_Servant.Skills.ExcellentShotMadam",
            "Crocus_Baroness_Servant.Skills.KeepYourChinUp",
            "Crocus_Baroness_Servant.Skills.ProtectYourAssets",
            "Crocus_Baroness_Servant.Skills.SaveTheQueen",
            "Crocus_Baroness_Servant.Skills.Valet",
            "Crocus_Baroness_Servant.Skills.YouFirst",
        ])),
                       
        "Claptrap" : CharacterHint().add_dependency(Dependency(
            "VaultHunter.EXE"
        ).provided_by([
            "GD_Prototype_Skills_GBX.ActionSkill.Skill_VaultHunterEXE",
        ]).required_by([
            "GD_Prototype_Skills.ILoveYouGuys.ThroughThickAndThin",
        ])),

        "Jack" : CharacterHint().add_dependency(Dependency(
            "Expendable Assets"
        ).provided_by([
            "Quince_Doppel_Skills.ActionSkill.Skill_SummonDigiJack",
        ]).required_by([
            "Quince_Doppel_GreaterGood.Skills.Accountability",
            "Quince_Doppel_GreaterGood.Skills.Collaborate",
            "Quince_Doppel_GreaterGood.Skills.Commitment",
            "Quince_Doppel_GreaterGood.Skills.Delegation",
            "Quince_Doppel_GreaterGood.Skills.Diversify",
            "Quince_Doppel_GreaterGood.Skills.Leadership",
            "Quince_Doppel_GreaterGood.Skills.Optimism",
            "Quince_Doppel_GreaterGood.Skills.Potential",
            "Quince_Doppel_GreaterGood.Skills.Teamwork",
            "Quince_Doppel_Hero.Skills.BestFootForward",
            "Quince_Doppel_Hero.Skills.Bolster",
            "Quince_Doppel_Hero.Skills.LeanOnMe",
            "Quince_Doppel_Hero.Skills.OnMyMark",
            "Quince_Doppel_Hero.Skills.PromotetheRanks",
            "Quince_Doppel_Hero.Skills.TakeTheirFreedom",
            "Quince_Doppel_Hero.Skills.YouHaveMyShield",
        ])).suppress([
            "Quince_Doppel_Streaming.ActionSkill.Skill_Doppelganging",
        ]),

        "Nisha" : CharacterHint().add_dependency(Dependency(
            "Showdown"
        ).provided_by([
            "GD_Lawbringer_Skills.ActionSkill.Skill_Showdown",
        ]).required_by([
            "GD_Lawbringer_Skills.FanTheHammer.BottledCourage",
            "GD_Lawbringer_Skills.FanTheHammer.Gunslinger",
            "GD_Lawbringer_Skills.FanTheHammer.HighNoon",
            "GD_Lawbringer_Skills.FanTheHammer.Ruthless",
            "GD_Lawbringer_Skills.Riflewoman.TheUnforgiven",
            "GD_Lawbringer_Skills.Order.Jurisdiction",
            "GD_Lawbringer_Skills.Order.TheThirdDegree",
        ])).add_dependency(Dependency(
            "Order"
        ).provided_by([
            "GD_Lawbringer_Skills.Order.Order",
        ]).required_by([
            "GD_Lawbringer_Skills.Order.RoughRider",
            "GD_Lawbringer_Skills.Order.Wanted",
            "GD_Lawbringer_Skills.Order.Discipline",
            "GD_Lawbringer_Skills.Order.BloodOfTheGuilty",
            "GD_Lawbringer_Skills.Order.RarinToGo",
            "GD_Lawbringer_Skills.Order.ThunderCrackdown",
        ])).suppress([
            "GD_Lawbringer_Skills.Riflewoman.CrackShot_Mainhand",
            "GD_Lawbringer_Skills.Riflewoman.CrackShot_Offhand",
            "GD_Lawbringer_Skills.Riflewoman.CrackShot_Mainhand_Secondary",
            "GD_Lawbringer_Skills.Riflewoman.CrackShot_Offhand_Secondary",
            "GD_Lawbringer_Skills.Riflewoman.Impatience_Effect",
            "GD_Lawbringer_Skills.Riflewoman.QuickShot_Effect",
            "GD_Lawbringer_Skills.Order.Discipline_Effect",
            "GD_Lawbringer_Skills.Order.DueProcess_Effect",
            "GD_Lawbringer_Skills.FanTheHammer.MagnificentSix_Mainhand",
            "GD_Lawbringer_Skills.FanTheHammer.MagnificentSix_Offhand",
            "GD_Lawbringer_Skills.FanTheHammer.HellsCominWithMe_Effect",
        ]),

        "Wilhelm" : CharacterHint().add_dependency(Dependency(
            "Drones"
        ).provided_by([
            "GD_Enforcer_Skills.ActionSkill.Skill_AirPower",
        ]).required_by([
            "GD_Enforcer_Skills.CyberCommando.EmergencyResponse",
            "GD_Enforcer_Skills.CyberCommando.ManandMachine",
            "GD_Enforcer_Skills.Dreadnought.AuxillaryTanks",
            "GD_Enforcer_Skills.Dreadnought.Energize",
            "GD_Enforcer_Skills.Dreadnought.Fortify",
            "GD_Enforcer_Skills.Dreadnought.Heatsinks",
            "GD_Enforcer_Skills.Dreadnought.Overcharge",
            "GD_Enforcer_Skills.Dreadnought.RapidReinforcement",
            "GD_Enforcer_Skills.Dreadnought.ZeroHour",
            "GD_Enforcer_Skills.HunterKiller.Afterburner",
            "GD_Enforcer_Skills.HunterKiller.Escalation",
            "GD_Enforcer_Skills.HunterKiller.FireSupport",
            "GD_Enforcer_Skills.HunterKiller.KillSwitch",
            "GD_Enforcer_Skills.HunterKiller.LaserGuided",
            "GD_Enforcer_Skills.HunterKiller.OmegaStrike",
            "GD_Enforcer_Skills.HunterKiller.RollingThunder",
            "GD_Enforcer_Skills.HunterKiller.Scramble",
            "GD_Enforcer_Skills.HunterKiller.Suppression",
            "GD_Enforcer_Skills.HunterKiller.VenomBolts",
        ])),
    }        
    
class Skill:
    """
    Stores skill information in a format safe from the UE memory manager.
    """

    def __init__(self,
                 skill_def : unrealsdk.UObject,
                 characters : Characters) -> None:
        """
        Args:
            skill_def : SkillDefinition for the skill
            characters:  Pool of playable characters
        """
        self.name = skill_def.Name
        self.full_name = skill_def.GetObjectName()
        self.is_player_skill = False
        self.is_action_skill = False
        self.character = None
        if not (skill_def.SkillIcon is None or
                skill_def.SkillName is None or
                skill_def.SkillDescription is None or
                skill_def.bSubjectToGradeRules == False):
            self.is_player_skill = True
            self.is_action_skill = (
                skill_def.SkillType == ESkillType.SKILL_TYPE_Action)
            self.max_grade = skill_def.MaxGrade
            char_class = Characters.class_from_obj_name(self.full_name)
            self.character = characters.from_cls(char_class)
            self.skill_name = skill_def.SkillName
                
        self._attribute_def = None
        self.free_attribute_def = False
        self._presentation = None
        self.free_presentation = False

    @property
    def skill_def(self) -> unrealsdk.UObject:
        """
        Retrieve the SkillDefinition for this Skill.  Don't hold onto it after
        returning control to the game - it tends to go stale.

        Returns:
            The SkillDefinition corresponding to this Skill.
        """
        return unrealsdk.FindObject("SkillDefinition", self.full_name)

    def __hash__(self) -> int:
        """
        Computes a hashcode for this Skill.

        Returns:
            A value likely to be unique for this Skill.
        """
        return self.full_name.__hash__()

    def is_upgradable(self) -> bool:
        """
        Determines if the Skill can be upgraded with skill points or class mods.

        Returns:
            True if the Skill can be upgraded.
        """
        return self.max_grade > 1

    @property
    def attribute_def(self) -> unrealsdk.UObject:
        """
        Retrieves the InventoryAttributeDefinition for this Skill.  Creates it
        if it does not already exist.

        Returns:
            An InventoryAttributeDefinition corresponding to this Skill.
        """
        if self._attribute_def is None:
            # It's necessary to create two levels of the object tree to
            # support a previously-unsupported skill.  The AttributeDefinition
            # itself defines how to boost a skill, and the three Resolver
            # classes link the AttributeDefinition to the player and the skill.
            path_component_names = [ "" ] * 3 + self.full_name.split(".")
            path = NameBasedObjectPath(
                PathComponentNames = path_component_names,
                IsSubobjectMask = 0
            )

            package = unrealsdk.FindObject(
                "Package", self.character.attribute_package)
            self._attribute_def = unrealsdk.ConstructObject(
                Class="InventoryAttributeDefinition",
                Outer=package,
                Name=self.name,
                Template=self.attribute_def_template)
            self._attribute_def.AttributeDataType = EAttributeDataType.ADT_Int
            unrealsdk.KeepAlive(self._attribute_def)

            self.player_resolver = unrealsdk.ConstructObject(
                Class="PlayerControllerAttributeContextResolver",
                Outer=self._attribute_def,
                Name="PlayerControllerAttributeContextResolver_0",
                Template=self.player_resolver_template)
            unrealsdk.KeepAlive(self.player_resolver)

            self.context_resolver = unrealsdk.ConstructObject(
                Class="SkillAttributeContextResolver",
                Outer=self._attribute_def,
                Name="SkillAttributeContextResolver_0",
                Template=self.skill_attr_resolver_template)
            self.context_resolver.AssociatedSkillPathName = path
            unrealsdk.KeepAlive(self.context_resolver)
            self._attribute_def.ContextResolverChain = [
                self.player_resolver,
                self.context_resolver,
            ]

            self.value_resolver = unrealsdk.ConstructObject(
                Class="ObjectPropertyAttributeValueResolver",
                Outer=self._attribute_def,
                Name="ObjectPropertyAttributeValueResolver_20",
                Template=self.value_resolver_template,
            )
            self.value_resolver.PropertyName="Grade"
            unrealsdk.KeepAlive(self.value_resolver)
            self._attribute_def.ValueResolverChain = [
                self.value_resolver,
            ]
        
            self.free_attribute_def = True
        return self._attribute_def

    @attribute_def.setter
    def attribute_def(self, attr_def: unrealsdk.UObject) -> None:
        """
        Assigns an InventoryAttributeDefinition to this Skill.

        Args:
            attr_def : The InventoryAttributeDefinition to attach to this Skill.
        """
        if self.free_attribute_def and not self._attribute_def is None:
            self.player_resolver = None
            self.context_resolver = None
            self.value_resolver = None
            self.free_attribute_def = False
        self._attribute_def = attr_def

    @property
    def presentation(self) -> unrealsdk.UObject:
        """
        Retrieves the AttributePresentationDefinition that renders this skill
        for class mod item cards.  Creates it if it does not already exist.

        Returns:
            An AttributePresentationDefinition corresponding to this Skill.
        """
        if self._presentation is None:
            self._presentation = unrealsdk.ConstructObject(
                Class="AttributePresentationDefinition",
                Outer=self.presentation_package,
                Name="AttrPresent_" + self.name,
                Template=self.presentation_template)
            unrealsdk.KeepAlive(self._presentation)
            self.free_presentation = True
            self._presentation.RoundingMode = EAttributeInitializationRounding.ATTRROUNDING_IntFloor
            self._presentation.bDisplayAsPercentage = False
            self._presentation.Attribute = self.attribute_def

            # Modder-style i18n:  Luckily the Description field always follows
            # a particular format in each language.  As localization has already
            # taken place by the time the mod is loaded, we can steal the name
            # from the associated Skill and stuff it into a language-specific
            # template.
            skill_name = self.skill_name  # localized
            language = self._presentation.GetLanguage()
            desc = eval(f"f'{self.skill_localization[language]}'")
            # We have to use the console to set the string, because the game
            # crashes if we try to set the description directly.
            unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(
                f"set {self._presentation.Outer.Name}.{self._presentation.Name} Description {desc}"
            )

        return self._presentation

    @presentation.setter
    def presentation(self, preso_def: unrealsdk.UObject) -> None:
        """
        Assigns an AttributePresentationDefinition to this Skill.

        Args:
            preso_def : The AttributePresentationDefinition to attach to this
                Skill.
        """
        self._presentation = preso_def
        self.free_presentation = False

    # Class archetypes and common packages are around from the start of the game
    # and don't get freed or swapped out, so it's safe to cache them.
    attribute_def_template = unrealsdk.FindObject(
        "InventoryAttributeDefinition",
        "WillowGame.Default__InventoryAttributeDefinition")
    player_resolver_template = unrealsdk.FindObject(
        "PlayerControllerAttributeContextResolver",
        "WillowGame.Default__PlayerControllerAttributeContextResolver")
    skill_attr_resolver_template = unrealsdk.FindObject(
        "SkillAttributeContextResolver",
        "WillowGame.Default__SkillAttributeContextResolver")
    value_resolver_template = unrealsdk.FindObject(
        "ObjectPropertyAttributeValueResolver",
        "WillowGame.Default__ObjectPropertyAttributeValueResolver")
    presentation_package = unrealsdk.FindObject(
        "Package",
        "GD_AttributePresentation")         
    presentation_template = unrealsdk.FindObject(
        "AttributePresentationDefinition",
        "WillowGame.Default__AttributePresentationDefinition")

    skill_localization = {
        "DEU" : "{skill_name}-Skill",
        "ESN" : "Habilidad {skill_name}",
        "FRA" : "{skill_name}",
        "INT" : "{skill_name} Skill",
        "ITA" : "{skill_name}",
        "JPN" : "{skill_name} スキル",
        "KOR" : "{skill_name} 스킬",
        "TWN" : "{skill_name}技能",
    }


class SkillCatalog:
    """
    Collects known skills into four groups:  action skills, passive skills,
    misdocumented/unreleased skills, and suppressed skills.
    """

    def __init__(self) -> None:
        self.skills = None
        self.dirty = True

    def mark_dirty(self) -> None:
        """
        Indicate that the SkillCatalog needs to reload skill data.
        """
        self.dirty = True

    def find_skills(self, characters: Characters) -> None:
        """
        Find all player skills and associate them with player character classes.

        Args:
            characters:  Pool of player character classes.
        """
        if not self.dirty:
            return

        self.skills = {}
        
        # Process skills from the skill trees.
        for character in characters:
            for skill_def in character.iterate_tree_skills():
                skill = Skill(skill_def, characters)
                if not skill.is_player_skill:
                    # Bonus skill, like Krieg's Hellborn.FireStatusDetector.
                    character.add_extra_skill(skill)
                    continue

                if skill.is_action_skill:
                    character.set_action_skill(skill)
                else:
                    character.add_passive_skill(skill)
                    self.skills[skill.full_name] = skill

        # Now go through all skills, determine which are player skills,
        # and add them as either misdocumented or suppressed skills.
        for skill_def in unrealsdk.FindAll("SkillDefinition"):
            skill = Skill(skill_def, characters)
            if not skill.is_player_skill:
                continue
            if skill.full_name in self.skills:
                # already listed in a skill tree
                continue
            if skill.is_action_skill:
                # This actually happens for Jack in TPS - there's a skill that
                # looks like an earlier version of Expendable Assets.  Not
                # entirely sure what to do with it.
                continue
            self.skills[skill.full_name] = skill
            character = skill.character
            if character is None:
                continue
            character.add_undocumented_skill(skill)

        self.dirty = False

    def find_attribute_defs(self, characters: Characters) -> None:
        """
        Collect existing InventoryAttributeDefinitions for each skill.

        Args:
            characters:  Pool of player character classes.
        """

        for attribute_def in unrealsdk.FindAll("InventoryAttributeDefinition"):
            if len(attribute_def.ContextResolverChain) < 2:
                # attribute doesn't represent a skill
                continue
            resolver = attribute_def.ContextResolverChain[1]
            skill_name = ".".join(
                resolver.AssociatedSkillPathName.PathComponentnames[3:6])
            if skill_name in self.skills:
                self.skills[skill_name].attribute_def = attribute_def

            # Also capture the containing class or package.
            char_class_name = Characters.class_from_obj_name(
                attribute_def.GetObjectName())
            char = characters.from_cls(char_class_name)
            if (not char is None) and char.attribute_package is None:
                char.attribute_package = attribute_def.Outer.GetObjectName()

    def find_presentations(self) -> None:
        """
        Collect AttributePresentationDefinitions for each skill.
        """
        for presentation in unrealsdk.FindAll(
                "AttributePresentationDefinition"
        ):
            attribute_def = presentation.attribute
            if attribute_def is None:
                continue
            # I could go through ContextResolverChain[1].AssociatedSkillPathName
            # but this is probably easier and safer.
            for skill in self.skills.values():
                if skill.attribute_def == attribute_def:
                    skill.presentation = presentation
                    break

    def flatten_presentations(self) -> None:
        """
        Create one common AttributePresentationListDefinition that covers
        AttributePresentationDefinitions for the whole game.

        The base game default presentation list doesn't reference the DLC
        objects, so base game COMs can't locate any DLC skills.
        Unfortunately there doesn't seem to be a good way to append items
        to existing arrays, and TPS doesn't have enough gaps in its version,
        so we have to re-create the whole thing.
        """
        presentation_list: unrealsdk.UObject = unrealsdk.FindObject(
            "AttributePresentationListDefinition",
            "GD_AttributePresentation._AttributeList.DefaultPresentationList")
        self.original_plist = [
            "None" if presentation is None
            else presentation.GetFullName().replace(" ", "'") + "'"
            for presentation in presentation_list.Attributes
        ]
        replacement_plist = self.original_plist[:]
        for skill in self.skills.values():
            if skill.presentation is None:
                continue
            presentation_name = skill.presentation.GetFullName().replace(
                " ","'") + "'"
            if not presentation_name in replacement_plist:
                replacement_plist.append(presentation_name)
        console_value = ", ".join(replacement_plist)
        unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(
            f"set GD_AttributePresentation._AttributeList.DefaultPresentationList Attributes ({console_value})")

    def unflatten_presentations(self) -> None:
        """
        Restore the AttributePresentationListDefinition to its original state.
        """
        console_value = ",".join(self.original_plist)
        unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(
            f"set GD_AttributePresentation._AttributeList.DefaultPresentationList Attributes ({console_value})")


class Branch:
    """
    Represents one of the three skill trees for a character.
    """

    @classmethod
    def from_branch(self, branch: unrealsdk.UObject) -> Branch:
        """
        Creates a Branch from a non-action SkillTreeBranchDefinition.

        Args:
            branch:  The SkillTreeBranchDefinition to base this Branch on.

        Returns:
            A new Branch object representing the SkillTreeBranchDefinition.
        """
        new_branch = Branch()
        new_branch.full_name = branch.GetObjectName()
        new_branch.layout_name = branch.Layout.GetObjectName()
        for tier in branch.Tiers:
            new_branch.skills.append([skill.GetObjectName() for skill in tier.Skills])
            new_branch.points_to_unlock.append(tier.PointsToUnlockNextTier)
        for tier in branch.Layout.Tiers:
            new_branch.layout.append([flag for flag in tier.bCellIsOccupied])
        return new_branch

    @classmethod
    def from_other(self, other: Branch) -> Branch:
        """
        Creates a Branch from another Branch (copy constructor).

        Args:
            other:  The Branch to copy contents from.

        Returns:
            A new Branch object with contents deep-copied from the original.
        """
        new_branch = Branch()
        new_branch.full_name = other.full_name
        new_branch.layout_name = other.layout_name
        new_branch.skills = [tier[:] for tier in other.skills]
        new_branch.points_to_unlock = other.points_to_unlock[:]
        new_branch.layout = [tier[:] for tier in other.layout]
        return new_branch
    
    def __init__(self) -> None:
        self.skills = []
        self.points_to_unlock = []
        self.layout = []
        self.full_name = None
        self.layout_name = None
        
    def patch(self) -> None:
        """
        Writes the Branch into the game engine.
        """
        command = f"set SkillTreeBranchDefinition'{self.full_name}' Tiers ("
        command += ",".join(["(Skills=(" + ",".join([
            f"SkillDefinition'{tier_skill}'"
            for tier_skill in tier_skills]) +
                             f"),PointsToUnlockNextTier={unlock})"
                             for tier_skills, unlock
                             in zip(self.skills, self.points_to_unlock)]) + ")"
        unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(command)
        command = f"set SkillTreeBranchLayoutDefinition'{self.layout_name}' Tiers ("
        command += ",".join(["(bCellIsOccupied=(" + ",".join([
            str(skill_present) for skill_present in tier_layout])
                             + "))" for tier_layout in self.layout]) + ")"
        unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(command)


class SkillPool:
    """
    Tracks the skills selected as candidates for a randomized Player.
    """

    def __init__(self, rng: random.Random):
        """
        Args:
            rng:  A seeded random number generator.
        """
        self.rng = rng
        self.dependencies = {}
        self.skills = {}
        self.skill_order = None
        self.extra_skills = []
        self.class_mod_skills = []
        self.current_char_class = None
        self.current_char_class = None
        self.original_branches = None
        self.seed = None

    def add_skills(self, skills : List[Skill]) -> None:
        """
        Add skills to the SkillPool.

        Args:
            skills:  Skills to add to the SkillPool.
        """
        for skill in skills:
            self.skills[skill.full_name] = skill

    def add_dependency(self, dependency : Dependency) -> None:
        """
        Add a dependency to the SkillPool.

        Args:
            dependency:  The Dependency to add.
        """
        for skill_name in dependency.providers:
            self.dependencies[skill_name] = dependency

    def mark_used(self, skill: Skill) -> Skill:
        """
        Consume a skill from the skill pool.

        Args:
            skill:  The Skill to remove from the pool.

        Returns:
            The removed Skill.
        """
        
        if skill.full_name in self.dependencies:
            dependency = self.dependencies[skill.full_name]
            # Save any 'free' skills granted by the initial one.
            self.extra_skills.extend(dependency.extra_skills)
            for skill_name in dependency.providers:
                del self.dependencies[skill_name]
        if skill.full_name in self.skills:
            del self.skills[skill.full_name]
            self.skill_order.remove(skill.full_name)
        return skill

    def get_next_skill(self, hidden_skills) -> Skill:
        """
        Select a random skill from the skill pool.

        Args:
            hidden_skills:  If "All", allow any skill.  If "Misdocumented",
                allow skills with unsatisfied "Wanted" dependencies.  If "None",
                allow only skills with fully-satisfied dependencies.

        Returns:
            A random Skill, which is removed from the skill pool.
        """
        while True:
            skill_name = self.rng.choice(self.skill_order)
            if hidden_skills == "All":
                return self.mark_used(self.skills[skill_name])
            for dependency in self.dependencies.values():
                if ((hidden_skills == "None" and
                     skill_name in dependency.wanters) or
                    skill_name in dependency.dependers):
                    # Since the skill is missing a dependency, pick one of the
                    # dependencies instead.
                    skill_name = self.rng.choice(dependency.providers)
                    if skill_name in self.skills:
                        return self.mark_used(self.skills[skill_name])
                    # Dependency is not in the skill pool.  It's probably an
                    # action skill for a different character.  Skip.
                    break
            else:
                return self.mark_used(self.skills[skill_name])

    def get_extra_skills(self) -> List[str]:
        """
        Retrieve any free skills granted by satisfied dependencies since the
        last get_extra_skills call.

        Returns:
            A list of skill object names representing 'free' skills.
        """
        extra_skills = self.extra_skills
        self.extra_skills = []
        return extra_skills

    def randomize_tree(self,
                       skill_tree : unrealsdk.UObject,
                       chars : Characters,
                       config : Dict[str, Union[bool, int, float, List[str]]],
                       dry_run : bool) -> bool:
        """
        Generate a random skill set for a character.

        Args:
            skill_tree:  The action SkillTreeBranchDefinition for the character.
            chars:  A pool of player character classes.
            config:  The configuration map for the random player.
            dry_run:  If True, makes no changes to the game engine.

        Returns:
            True if the resulting tree satisfies requirements declared in
                the wanted_skills class variable.
        """
        self.current_char_class = Characters.class_from_obj_name(
            skill_tree.Root.GetObjectName())

        current_char = None
        for char in config["enabled_classes"]:
            source_char = chars.from_name(char)
            if source_char is None:
                unrealsdk.Log(f"Warning: ignoring unknown skill source {char}")
                continue
            self.add_skills(source_char.pure_skills)
            if config["hidden_skills"] != "none":
                self.add_skills(source_char.misdocumented_skills)
                if config["hidden_skills"] == "all":
                    self.add_skills(source_char.suppressed_skills)
            for dependency in source_char.dependencies:
                self.add_dependency(dependency)
            if source_char.name == self.current_char_class:
                current_char = source_char

        # Sanity check: make sure all wanted skills are in the pool
        for skill_name in self.wanted_skills:
            if not skill_name in self.skills:
                unrealsdk.Log(f"Error: desired skill {skill_name} is not in the pool.")
                raise UnlistedSkillException(skill_name)

        # Sort the current skill list for reproducibility.
        self.skill_order = list(self.skills)
        self.skill_order.sort()

        if config["action_skill"] == "Default":
            if current_char is None:
                unrealsdk.Log("Warning: Default is not a currently-enabled class.  Choosing a random action skill instead.")
                desired_char = chars.from_name(self.rng.choice(
                    config["enabled_classes"]))
            else:
                desired_char = current_char
        elif config["action_skill"] == "Random":
            desired_char = chars.from_name(self.rng.choice(
                config["enabled_classes"]))
        else:
            desired_char = chars.from_name(config["action_skill"])
            if desired_char is None:
                unrealsdk.Log(f"Warning: desired class {config['action_skill']} is not installed.  Choosing a random action skill instead.")
                desired_char = self.rng.choice(config["enabled_classes"])
            elif not desired_char.character_name in config["enabled_classes"]:
                unrealsdk.Log(f"Warning: {desired_char.character_name} is not a currently-enabled class.  Choosing a random action skill instead.")
                desired_char = self.rng.choice(config["enabled_classes"])

        if dry_run:
            _ = self.mark_used(desired_char.action_skill)
        else:
            # Sadly, even though this takes a list, only the first action skill
            # is used.
            skill_tree.Root.Tiers[0].Skills = [
                self.mark_used(desired_char.action_skill).skill_def,
            ]

        wanted = 0
        self.original_branches = []
        for branch in skill_tree.Root.Children:
            old_branch = Branch.from_branch(branch)
            new_branch = Branch.from_other(old_branch)
            self.original_branches.append(old_branch)

            wanted += self.randomize_branch(
                new_branch,
                config["skill_density"],
                config["randomize_tiers"],
                config["hidden_skills"],
                dry_run)
            
        return wanted == len(self.wanted_skills)

    def randomize_branch(self,
                         branch : Branch,
                         skill_density : int,
                         randomize_tiers : bool,
                         hidden_skills : str,
                         dry_run : bool) -> int:
        """
        Randomize one of the three skill branches for a character.  Helper
        function for randomize_tree().

        Args:
            branch:  A non-action SkillTreeBranchDefinition for the character.
            skill_density:  Percentage of skills to fill in.  BL2 characters
                average a 60% skill density, while TPS characters average 65%.
            randomize_tiers:  If True, randomize how many skill points it takes
                to unlock each tier.  If False, set the tier unlock level to
                the skill point cost of the most expensive skill in the tier.
            hidden_skills:  If "All", allow any skill.  If "Misdocumented",
                allow skills with unsatisfied "Wanted" dependencies.  If "None",
                allow only skills with fully-satisfied dependencies.
            dry_run:  If True, make no changes to the game engine.

        Returns:
            A count of the number of skills selectedf from the wanted_skills
                class variable.
        """

        # We want behavior such that at 33% density, each tier has one skill,
        # and at 100%, each tier has three skills.  Within that, we want to
        # weight earlier tiers more heavily than later ones.  Assign one skill
        # to each tier, then scatter between 0 (33%) and 12 (100%) extras.
        # Note that the center skill is always filled.
        expected_skills = int(18 * (skill_density - 33) / 100)
        spots_left = 12
        wanted = 0
        bias = [self.bias, 0, self.bias]
        for tier in range(0, 6):
            tier_layout = [False, False, False]
            tier_skills = []
            max_points = 0
            total_points = 0

            for slot in range(0, 3):
                # Scattering skills evenly across the open spaces would need a
                # probability of (number_of_skills_left/open_spots_left).
                # We can skew that towards the earlier spaces by applying a bias
                # that simulates having fewer spaces available to fill.
                # Setting bias to 0 for the center slot guarantees a skill in
                # each tier.
                if slot == 1:
                    # guarantee a spot
                    spots_left += 1
                    expected_skills += 1
                if self.rng.randint(
                        0, int(bias[slot] * spots_left)
                ) < expected_skills:
                    skill = self.get_next_skill(hidden_skills)
                    if skill.is_upgradable():
                        self.class_mod_skills.append(skill)
                    try:
                        if tier < self.wanted_skills[skill.full_name]:
                            wanted += 1
                    except KeyError:
                        pass
                    max_points = max(max_points, skill.max_grade)
                    total_points += skill.max_grade
                    if not dry_run:
                        tier_skills.append(skill.full_name)
                    tier_layout[slot] = True
                else:
                    tier_layout[slot] = False
                    expected_skills -= 1
                spots_left -= 1

            if dry_run:
                # keep RNG synced with real run
                if randomize_tiers:
                    _ = self.rng.randint(1, max(1, int(0.66 * total_points)))
                continue
            
            branch.layout[tier] = tier_layout
            branch.skills[tier] = tier_skills
            if randomize_tiers:
                branch.points_to_unlock[tier] = self.rng.randint(
                    1, max(1, int(0.66 * total_points)))
            else:
                branch.points_to_unlock[tier] = max_points

        if not dry_run:
            branch.skills[5].extend(self.get_extra_skills())
            branch.patch()
        return wanted

    def unrandomize_tree(self) -> None:
        """
        Restore the game engine to the original skill tree.
        """
        if not self.original_branches is None:
            for branch in self.original_branches:
                branch.patch()
        self.original_branches = None

    def get_class_mod_skills(self) -> List[Skill]:
        """
        Retrieve all skills that should be considered for the random player's
        class mods.
        
        Returns:
            A list of passive, upgradable skills from the random player's skill
                tree.
        """
        return self.class_mod_skills

    def get_current_char(self) -> Character:
        """
        Retrieves the player class for the random player.

        Returns:
            The Character corresponding to the random player.
        """
        return self.current_char_class

    # Add any skills here that the random player must have.  The Lilith mod, for
    # example, must have the GD_Siren_Skills.Cataclysm.BlightPhoenix skill
    # listed or the game will crash.  Format is skill_name : latest permissible
    # tier.
    wanted_skills : Dict[str, int] = {
    }

    # Amount to shift skills from later tiers to earlier tiers
    bias: float = 0.63

    
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
            char_class: str) -> Generator[unrealsdk.UObject, None, None]:
        """
        Iterate through all known class mods.

        Args:
            char_class:  Character class whose COMs should be updated

        Yields:
            A ClassModDefinition assigned to the specified char_class.
        """
        for com in unrealsdk.FindAll("ClassModDefinition"):
            if com.RequiredPlayerClass is None:
                continue
            if com.RequiredPlayerClass.Name == char_class:
                yield com

        # DLC classmods referencing another DLC use the CMDef subclass instead.
        for com in unrealsdk.FindAll("CrossDLCClassModDefinition"):
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
            self.coms[com.GetObjectName()] = skill_slot_map
            slot_index = 0
            for attribute_slot in com.AttributeSlotEffects:
                if attribute_slot.SlotName.startswith("Skill"):
                    if attribute_slot.AttributeToModify is None:
                        unrealsdk.Log(f"Null {com.GetObjectName()}.AttributeSlotEffects[{slot_index}].AttributeToModify")
                        continue
                    skill_slot_map[
                        slot_index
                    ] = attribute_slot.AttributeToModify.GetObjectName()
                slot_index += 1

    def randomize_coms(self,
                       skills : List[Skill],
                       rng: random.Random,
                       char_class : str,
                       dry_run: bool) -> bool:
        """
        Modify the random character's class mods to boost random skills from
            the character's new skill tree.

        Args:
            skills:  A list of Skills from which to choose COM boosts.
            rng:  The seeded random number generator to use when choosing.
            char_class:  Character class whose COMs should be randomized.
            dry_run:  If True, do not modify the game engine.

        Returns:
            True if at least one of the resulting class mods satisfies
                requirements declared in the wanted_class_mod_skills class
                variable.
        """
        want_satisfied = False
        com = None
        for com_name, skill_slot_map in self.coms.items():
            used_skills = set()
            wanted_com_skills = 0
            if not dry_run:
                com = unrealsdk.FindObject("ClassModDefinition", com_name)
                pass
            for slot_index in skill_slot_map:
                while True:
                    skill = rng.choice(skills)
                    if not skill.full_name in used_skills:
                        used_skills.add(skill.full_name)
                        break
                if skill.full_name in self.wanted_class_mod_skills:
                    wanted_com_skills += 1
                if not dry_run:
                    com.AttributeSlotEffects[
                        slot_index
                    ].AttributeToModify = skill.attribute_def
                    pass
            if wanted_com_skills == len(self.wanted_class_mod_skills):
                unrealsdk.Log(f"{com_name} has all requested skills!")
                if len(skill_slot_map) > 3 and len(
                        self.wanted_class_mod_skills) <= 3:
                    # Legendary COM - too scarce.
                    continue
                if com_name.startswith("GD_Aster"):
                    # Tiny Tina DLC mod - too scarce.
                    continue
                want_satisfied = True
        return want_satisfied
                
    def unrandomize_coms(self, char_class) -> None:
        """
        Restore the original contents of the modified class mods.

        Args:
            char_class:  Character class whose COMs were randomized.
        """
        if self.coms is None:
            return
        for com in ClassModPatcher.iterate_coms(char_class):
            for slot_index, attr_name in self.coms[com.GetObjectName()].items():
                com.AttributeSlotEffects[
                    slot_index
                ].AttributeToModify = unrealsdk.FindObject(
                    "InventoryAttributeDefinition", attr_name)

    # Add any skills that one of the class mods must have.  Do not specify more
    # than five skills or the game will hang.
    wanted_class_mod_skills : Set[str] = set([
    ])

class SeededPlayerRandomizer(SDKMod):
    """
    Provides the interface for a PlayerRandomizer with a particular seed.
    """

    Name: str = "Player Randomizer ({})"
    Version: str = "0.1"
    Author: str = "Milo"
    Description: str = ""
    SupportedGames: Game = Game.BL2 | Game.TPS | Game.AoDK
    Types: ModTypes = ModTypes.Gameplay
    SaveEnabledState: EnabledSaveType = EnabledSaveType.NotSaved

    def __init__(self,
                 parent: SDKMod,
                 config: Dict[str, Union[bool, int, float, List[str]]] = None
                 ) -> None:
        """
        Args:
            parent:  PlayerRandomizer instance owning the seeds
            config:  Dictionary containing the child's configuration
        """
        self.Name = self.Name.format(config["seed"])
        self.Description = self.child_desc_format.format(
            config["action_skill"], config["hidden_skills"],
            config["skill_density"],
            config["randomize_tiers"], config["randomize_coms"])
        self.config = config
        self.parent = parent
        self.pool = None
        self.SettingsInputs: Dict[str, str] = { "Enter" : "Enable",
                                                "Delete" : "Remove" }

    def SettingsInputPressed(self, action: str) -> None:
        """
        Handle actions triggered by keypresses when the mod menu is open.

        Args:
            action:  "Enable", "Disable", "Remove", or "Restore"
        """
        unrealsdk.Log(f"{self.Name}: user requested {action}")
        if action == "Remove":
            self.parent.delete_seed(self.config["seed"])
            self.Description = "Will be removed from the menu on the next game restart."
            if self.IsEnabled:
                self.SettingsInputPressed("Disable")
            self.SettingsInputs = { "Insert" : "Restore" }
            SaveModSettings(self.parent)
        elif action == "Restore":
            self.parent.add_child(self)
            self.Description = self.child_desc_format.format(
                self.config["action_skill"], self.config["skill_density"],
                self.config["randomize_tiers"], self.config["randomize_coms"])
            self.SettingsInputs = { "Enter" : "Enable",
                                    "Delete" : "Remove" }
            SaveModSettings(self.parent)
        else:
            super().SettingsInputPressed(action)

    def Enable(self) -> None:
        """
        Enable the child and activate game engine hooks.
        """
        self.parent.SettingsInputPressed("Enable")  # make sure parent's active
        self.parent.set_active_child(self.config["seed"])
        super().Enable()

    def Disable(self) -> None:
        """
        Disable the child and deactivate game engine hooks.  Also undo any
           changes to the game engine.
        """
        self.parent.disable_child(self.config["seed"])
        if self.parent.com_patched:
            for char in self.config["enabled_classes"]:
                self.parent.characters.from_name(char).remove_patches()
            self.parent.com_patcher.unrandomize_coms(self.current_char)
            self.parent.skill_catalog.unflatten_presentations()
            self.parent.com_patched = False            
        super().Disable()

    @Hook("WillowGame.PlayerSkillTree.Initialize")
    def inject_skills(self, caller: unrealsdk.UObject,
                      function: unrealsdk.UFunction,
                      params: unrealsdk.FStruct) -> bool:
        """
        Set up new skills for the randomized player, and update classmods.

        Args:
            caller:  Object invoking PlayerSkillTree.Initialize
            function:  Stack context for function call
            params:  Argument bindings for the call

        Returns:
            True if the hook should call the originally replaced function
        """
        self.parent.load_game_info()
        self.parent.skill_catalog.find_skills(self.parent.characters)
        self.rng = random.Random(self.config["seed"])
        self.pool = SkillPool(self.rng)
        self.pool.randomize_tree(params.SkillTreeDef,
                                 self.parent.characters,
                                 self.config,
                                 False)
        if self.config["randomize_coms"] and not self.parent.com_patched:
            self.parent.skill_catalog.find_attribute_defs(
                self.parent.characters)
            self.parent.skill_catalog.find_presentations()
            self.parent.skill_catalog.flatten_presentations()
            self.parent.com_patcher.record_coms(self.pool.get_current_char())
            self.parent.com_patcher.randomize_coms(
                self.pool.get_class_mod_skills(), self.rng,
                self.pool.get_current_char(), False)
            self.current_char = self.pool.get_current_char()
            for char in self.config["enabled_classes"]:
                self.parent.characters.from_name(char).apply_patches()
            self.parent.com_patched = True

        return True

    # Template to use for each child's description.
    child_desc_format: str = "Action Skill: {}\nAdditional Skills: {}\nSkill Density: {}%\nRandomized Tiers: {}\nRandomized Coms: {}"


class DynamicSpinner(Options.Spinner):
    """
    Variant of the Spinner control that captures some menu events.
    """

    def SetListener(self, listener: PlayerRandomizer) -> None:
        """
        Assigns an event listener to the menu control.
        
        Args:
            listener:  PlayerRandomizer instance to send events to
        """
        self.listener = listener
    
    @property
    def CurrentValue(self) -> str:
        """
        Retrieve the current value of the spinner control.

        Returns:
            The current string value of the spinner control.
        """
        if not self.listener is None:
            self.listener.on_menu_invoked()
        return self._CurrentValue

    @CurrentValue.setter
    def CurrentValue(self, value) -> None:
        """
        Sets the current value of the spinner control.

        Args:
            value:  The value to assign to the spinner control.
        """
        self._CurrentValue = value


class PlayerRandomizer(SDKMod):
    """
    Provides the interface for a PlayerRandomizer with no seed assigned.
    """

    Name: str = "Player Randomizer (New Seed)"
    Description: str = "Construct a random class!\nEvolved from Abahbob's nifty Cross Class Skill Randomizer."
    Version: str = "0.1"
    Author: str = "Milo"
    SupportedGames: Game = Game.BL2 | Game.TPS | Game.AoDK
    Types: ModTypes = ModTypes.Gameplay
    SaveEnabledState: EnabledSaveType = EnabledSaveType.LoadOnMainMenu
    SettingsInputs: Dict[str,str] = { "Enter" : "Enable" }
    
    # It would be nice to have all child instances store their own configs,
    # but the SettingsManager design forces everything in a directory to share
    # a single settings.json.  Instead, store configs on the parent and pass
    # them to child instances.

    def __init__(self) -> None:
        self.children = {}
        self.characters = None
        self.Options = []
        self.skill_catalog = SkillCatalog()
        self.com_patcher = ClassModPatcher()
        self.com_patched = False
        self.create_initial_options()

    def load_game_info(self) -> None:
        """
        Cache static game info.
        """
        if self.characters is None:
            self.characters = Characters()
            self.load_packages()
            if self.characters.update():
                self.skill_catalog.mark_dirty()
            self.fill_in_full_options()
            LoadModSettings(self)
        else:
            self.load_packages()

    def load_packages(self) -> None:
        """
        Force dynamically-loaded packages into memory.
        """
        for package in self.packages:
            # If a package is missing, I think LoadPackage fails silently.
            unrealsdk.LoadPackage(package)
        
    def create_initial_options(self) -> None:
        """
        Create the initial list of options for the Options menu.
        """
        
        # Several of the options depend on having all of the player classes
        # available, and custom classes may still be missing when the options
        # are first read from settings.json.  We work around this by creating
        # fake options to mimic them until we're truly ready to read config.
        self.children_option = Options.Hidden(
            Caption = "Children",
            Description = "Stores the configurations of the child instances.",
            StartingValue = {},
            IsHidden = True,
        )

        self.active_child_option = Options.Hidden(
            Caption = "Active Child",
            Description = "Stores the current enabled child, if any.",
            StartingValue = None,
            IsHidden = True,
        )

        # Fake option.  This will later be replaced with a nested set of
        # boolean options, one for each player class.
        self.skill_source_option = Options.Hidden(
            Caption = "Skill Sources",
            Description = "Selects which classes will supply skills.",
            StartingValue = {},
            IsHidden = True,
        )

        self.hidden_skill_option = Options.Spinner(
            Caption = "Additional Skills",
            Description = "Include skills that may work only partially, not work at all, or even crash the game.  Misdocumented skills refer to a particular Action Skill but should work with any.",
            StartingValue = "None",
            Choices = ("None", "Misdocumented", "All"),
            IsHidden = False,
        )

        # Fake option.  This will be replaced with a spinner once all the
        # player classes are known.
        self.action_skill_option = Options.Hidden(
            Caption = "Action Skill",
            Description = "Selects whether the action skill for the character is the default skill, one for a particular class, or random.",
            StartingValue = "Default",
            IsHidden = True,
        )

        self.skill_density_option = Options.Slider(
            Caption = "Skill Density",
            Description = "Selects how densely to populate the skill tree.",
            StartingValue = 63.0,
            MinValue = 33.0,
            MaxValue = 100.0,
            Increment = 1.0,
            IsHidden = False,
        )
        
        self.randomize_tier_option = Options.Boolean(
            Caption = "Randomize Tier Points",
            Description = "Selects whether to randomize next-tier skill point thresholds.",
            StartingValue = False,
            Choices = [ "Traditional", "Random" ],
            IsHidden = False,
        )        

        self.randomize_com_option = Options.Boolean(
            Caption = "Randomize COMs",
            Description = "Selects whether to update class mods for the current character.",
            StartingValue = True,
            Choices = ("No", "Yes"),
            IsHidden = False,
        )

        self.Options = [
            self.skill_source_option,
            self.children_option,
            self.active_child_option,
            self.hidden_skill_option,
            self.action_skill_option,
            self.skill_density_option,
            self.randomize_tier_option,
            self.randomize_com_option,
        ]
        
    def fill_in_full_options(self) -> None:
        """
        Update the list of options with full player character information.
        """

        self.skill_source_option = Options.Nested(
            Caption = "Skill Sources",
            Description = "Selects which classes will supply skills.",
            Children = [character.skill_option
                        for character in self.characters],
            IsHidden = False,
        )

        self.action_skill_option = DynamicSpinner(
            Caption = "Action Skill",
            Description = "Selects whether the action skill for the character is the default skill, one for a particular class, or random.",
            StartingValue = "Default",
            Choices = [ "Default", "Random" ] + [
                character.character_name for character in self.characters],
            IsHidden = False,
        )
        self.action_skill_option.SetListener(self)

        self.Options = [
            self.skill_source_option,
            self.children_option,
            self.active_child_option,
            self.hidden_skill_option,
            self.action_skill_option,
            self.skill_density_option,
            self.randomize_tier_option,
            self.randomize_com_option,
        ]
        LoadModSettings(self)

    def on_menu_invoked(self) -> None:
        """
        Update characters in case other mods were loaded in the Mods menu or
        at the console.

        This is a callback from the DynamicSpinner widget.
        """
        if self.characters.update():
            self.skill_catalog.mark_dirty()
            self.action_skill_option.Choices = [
                "Default", "Random" ] + [
                    character.character_name for character in self.characters]

    def create_seeded_instances(self) -> None:
        """
        Construct child instances for each seed tracked in the config.
        """
        for config in self.children_option.CurrentValue.values():
            child = SeededPlayerRandomizer(parent=self, config=config)
            self.children[config["seed"]] = child
            RegisterMod(child)
        if not self.active_child_option.CurrentValue is None:
            self.SettingsInputPressed("Disable")
            active_mod = self.children[self.active_child_option.CurrentValue]
            active_mod.SettingsInputPressed("Enable")

    def set_active_child(self, active_child: str) -> None:
        """
        Change the active child and disable any others.

        Args:
            active_child:  stringified seed of the child to make active
        """
        current_active = self.active_child_option.CurrentValue
        if current_active is None:
            if self.IsEnabled:
                self.SettingsInputPressed("Disable")
        elif active_child != current_active:
            self.children[current_active].SettingsInputPressed("Disable")
        self.active_child_option.CurrentValue = active_child

    def disable_child(self, active_child: str) -> None:
        """
        Deactivate the specified child.

        Args:
            active_child:  stringified seed of the child to deactivate
        """
        if self.active_child_option.CurrentValue == active_child:
            self.active_child_option.CurrentValue = None

    def add_child(self, child: SeededPlayerRandomizer) -> None:
        """
        Adds a new seeded child to the configuration.

        Args:
            child:  SeededPlayerRandomizer instance to add
        """
        seed = child.config["seed"]
        if not str(seed) in self.children_option.CurrentValue:
            self.children_option.CurrentValue[str(seed)] = child.config
        if not seed in self.children:
            self.children[seed] = child

    def delete_seed(self, seed: str) -> None:
        """
        Removes a child from the configuration.

        Args:
            seed:  stringified seed of the child to remove
        """
        if self.active_child_option.CurrentValue == seed:
            self.active_child_option.CurrentValue = None
        if str(seed) in self.children_option.CurrentValue:
            del self.children_option.CurrentValue[str(seed)]
        if seed in self.children:
            del self.children[seed]

    @Hook("WillowGame.PlayerSkillTree.Initialize")
    def inject_skills(self, caller: unrealsdk.UObject,
                      function: unrealsdk.UFunction,
                      params: unrealsdk.FStruct) -> bool:
        """
        Creates a new SeededPlayerRandomizer using the current configuration.

        Args:
            caller:  Object invoking PlayerSkillTree.Initialize
            function:  Stack context for function call
            params:  Argument bindings for the call

        Returns:
            True if the hook should call the originally replaced function
        """
        self.load_packages()
        self.skill_catalog.find_skills(self.characters)
        if self.randomize_com_option.CurrentValue:
            self.com_patcher.record_coms(Characters.class_from_obj_name(
                params.SkillTreeDef.Root.GetObjectName()))
        while True:
            # Test possible seeds for acceptability.
            # Note that this loop should try to avoid FindAll and FindObject
            # calls - they appear to leak memory, and will crash the game if
            # invoked too many times.
            config = {
                "seed" : random.randrange(sys.maxsize),
                "enabled_classes" : [
                    character.character_name
                    for character in self.characters
                    if character.skill_option.CurrentValue == True
                ],
                "hidden_skills" : self.hidden_skill_option.CurrentValue,
                "action_skill" : self.action_skill_option.CurrentValue,
                "skill_density" : self.skill_density_option.CurrentValue,
                "randomize_tiers" : self.randomize_tier_option.CurrentValue,
                "randomize_coms" : self.randomize_com_option.CurrentValue,
            }
            if config["seed"] in self.children:
                continue
            rng = random.Random(config["seed"])
            pool = SkillPool(rng)
            if pool.randomize_tree(params.SkillTreeDef, self.characters,
                                   config, True):
                unrealsdk.Log(f"Seed {config['seed']} satisfies constraints... checking COMs")
                if config["randomize_coms"]:
                    if self.com_patcher.randomize_coms(
                            pool.get_class_mod_skills(),
                            rng,
                            pool.get_current_char(),
                            True):
                        break
                else:
                    break

        seed = config["seed"]
        unrealsdk.Log(f"Randomizing skills with seed '{seed}'")
        new_child = SeededPlayerRandomizer(parent=self, config=config)
        self.add_child(new_child)
        RegisterMod(new_child)
        self.set_active_child(seed)
        new_child.SettingsInputPressed("Enable")
        return new_child.inject_skills(caller, function, params)

    def Enable(self) -> None:
        """
        Activates the PlayerRandomizer and disables any children.
        """
        # By now the DLC packages should be available.  Load game data;
        self.load_game_info()
        if not self.active_child_option.CurrentValue is None:
            self.children[
                self.active_child_option.CurrentValue
            ].SettingsInputPressed("Disable")
            self.active_child_option.CurrentValue = None
        super().Enable()

    # Dynamically-loaded packages that have to be in memory to randomize skills
    packages: List[str] = [
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

parent = PlayerRandomizer()
RegisterMod(parent)
parent.create_seeded_instances()
