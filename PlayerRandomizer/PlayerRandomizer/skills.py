# Classes and methods for handling skills.

import unrealsdk
from mods_base import ENGINE
from . import characters

EAttributeDataType = unrealsdk.find_enum("EAttributeDataType")
EAttributeInitializationRounding = unrealsdk.find_enum("EAttributeInitializationRounding")
EModifierType = unrealsdk.find_enum("EModifierType")
ESkillType = unrealsdk.find_enum("ESkillType")
ETrackedSkillType = unrealsdk.find_enum("ETrackedSkillType")


class Skill:
    """
    Stores skill information in a format safe from the UE memory manager.
    """

    def __init__(self,
                 skill_def : unrealsdk.unreal.UObject) -> None:
        """
        Args:
            skill_def : SkillDefinition for the skill
        """
        self.name = skill_def.Name
        self.full_name = skill_def._path_name()
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
            char_class = characters.class_from_obj_name(self.full_name)
            self.character = characters.Character.from_cls(char_class)
            self.skill_name = skill_def.SkillName
                
        self._attribute_def = None
        self.free_attribute_def = False
        self._presentation = None
        self.free_presentation = False

    @property
    def skill_def(self) -> unrealsdk.unreal.UObject:
        """
        Retrieve the SkillDefinition for this Skill.  Don't hold onto it after
        returning control to the game - it tends to go stale.

        Returns:
            The SkillDefinition corresponding to this Skill.
        """
        return unrealsdk.find_object("SkillDefinition", self.full_name)

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
    def attribute_def(self) -> unrealsdk.unreal.UObject:
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
            path = unrealsdk.make_struct("NameBasedObjectPath",
                PathComponentNames = path_component_names,
                IsSubobjectMask = 0,
            )

            package = unrealsdk.find_object(
                "Package", self.character.attribute_package)
            self._attribute_def = unrealsdk.construct_object(
                cls="InventoryAttributeDefinition",
                outer=package,
                name=self.name,
                flags=0x4000,  # keepalive
                template_obj=self.attribute_def_template)
            self._attribute_def.AttributeDataType = EAttributeDataType.ADT_Int

            self.player_resolver = unrealsdk.construct_object(
                cls="PlayerControllerAttributeContextResolver",
                outer=self._attribute_def,
                name="PlayerControllerAttributeContextResolver_0",
                flags=0x4000,  # keepalive
                template_obj=self.player_resolver_template)

            self.context_resolver = unrealsdk.construct_object(
                cls="SkillAttributeContextResolver",
                outer=self._attribute_def,
                name="SkillAttributeContextResolver_0",
                flags=0x4000,  # keepalive
                template_obj=self.skill_attr_resolver_template)
            self.context_resolver.AssociatedSkillPathName = path
            self._attribute_def.ContextResolverChain = [
                self.player_resolver,
                self.context_resolver,
            ]

            self.value_resolver = unrealsdk.construct_object(
                cls="ObjectPropertyAttributeValueResolver",
                outer=self._attribute_def,
                name="ObjectPropertyAttributeValueResolver_20",
                flags=0x4000,  # keepalive
                template_obj=self.value_resolver_template,
            )
            self.value_resolver.PropertyName="Grade"
            self._attribute_def.ValueResolverChain = [
                self.value_resolver,
            ]
        
            self.free_attribute_def = True
        return self._attribute_def

    @attribute_def.setter
    def attribute_def(self, attr_def: unrealsdk.unreal.UObject) -> None:
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
    def presentation(self) -> unrealsdk.unreal.UObject:
        """
        Retrieves the AttributePresentationDefinition that renders this skill
        for class mod item cards.  Creates it if it does not already exist.

        Returns:
            An AttributePresentationDefinition corresponding to this Skill.
        """
        if self._presentation is None:
            self._presentation = unrealsdk.construct_object(
                cls="AttributePresentationDefinition",
                outer=self.presentation_package,
                name="AttrPresent_" + self.name,
                flags=0x4000,  # keepalive
                template_obj=self.presentation_template)
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
            ENGINE.GamePlayers[0].Actor.ConsoleCommand(
                f"set {self._presentation.Outer.Name}.{self._presentation.Name} Description {desc}"
            )

        return self._presentation

    @presentation.setter
    def presentation(self, preso_def: unrealsdk.unreal.UObject) -> None:
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
    attribute_def_template = unrealsdk.find_object(
        "InventoryAttributeDefinition",
        "WillowGame.Default__InventoryAttributeDefinition")
    player_resolver_template = unrealsdk.find_object(
        "PlayerControllerAttributeContextResolver",
        "WillowGame.Default__PlayerControllerAttributeContextResolver")
    skill_attr_resolver_template = unrealsdk.find_object(
        "SkillAttributeContextResolver",
        "WillowGame.Default__SkillAttributeContextResolver")
    value_resolver_template = unrealsdk.find_object(
        "ObjectPropertyAttributeValueResolver",
        "Engine.Default__ObjectPropertyAttributeValueResolver")
    presentation_package = unrealsdk.find_object(
        "Package",
        "GD_AttributePresentation")         
    presentation_template = unrealsdk.find_object(
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


__skills = None
__dirty = True
__original_plist = None

def mark_dirty() -> None:
    """
    Indicate that the SkillCatalog needs to reload skill data.
    """
    global __dirty
    __dirty = True

def find_skills() -> None:
    """
    Find all player skills and associate them with player character classes.
    """
    global __dirty
    global __skills

    if not __dirty:
        return

    __skills = {}
        
    # Process skills from the skill trees.
    for character in characters.Character.characters():
        for skill_def in character.iterate_tree_skills():
            skill = Skill(skill_def)
            if not skill.is_player_skill:
                # Bonus skill, like Krieg's Hellborn.FireStatusDetector.
                character.add_extra_skill(skill)
                continue

            if skill.is_action_skill:
                character.set_action_skill(skill)
            else:
                character.add_passive_skill(skill)
                __skills[skill.full_name] = skill

    # Now go through all skills, determine which are player skills,
    # and add them as either misdocumented or suppressed skills.
    for skill_def in unrealsdk.find_all("SkillDefinition"):
        skill = Skill(skill_def)
        if not skill.is_player_skill:
            continue
        if skill.full_name in __skills:
            # already listed in a skill tree
            continue
        if skill.is_action_skill:
            # This actually happens for Jack in TPS - there's a skill that
            # looks like an earlier version of Expendable Assets.  Not
            # entirely sure what to do with it.
            continue
        __skills[skill.full_name] = skill
        character = skill.character
        if character is None:
            continue
        character.add_undocumented_skill(skill)

    __dirty = False

def find_attribute_defs() -> None:
    """
    Collect existing InventoryAttributeDefinitions for each skill.
    """
    global __skills

    for attribute_def in unrealsdk.find_all("InventoryAttributeDefinition"):
        if len(attribute_def.ContextResolverChain) < 2:
            # attribute doesn't represent a skill
            continue
        resolver = attribute_def.ContextResolverChain[1]
        skill_name = ".".join(
            resolver.AssociatedSkillPathName.PathComponentnames[3:6])
        if skill_name in __skills:
            __skills[skill_name].attribute_def = attribute_def

        # Also capture the containing class or package.
        char_class_name = characters.class_from_obj_name(
            attribute_def._path_name())
        char = characters.Character.from_cls(char_class_name)
        if (not char is None) and char.attribute_package is None:
            char.attribute_package = attribute_def.Outer._path_name()

def find_presentations() -> None:
    """
    Collect AttributePresentationDefinitions for each skill.
    """
    global __skills

    for presentation in unrealsdk.find_all(
        "AttributePresentationDefinition"
    ):
        attribute_def = presentation.attribute
        if attribute_def is None:
            continue
        # I could go through ContextResolverChain[1].AssociatedSkillPathName
        # but this is probably easier and safer.
        for skill in __skills.values():
            if skill.attribute_def == attribute_def:
                skill.presentation = presentation
                break

def flatten_presentations() -> None:
    """
    Create one common AttributePresentationListDefinition that covers
    AttributePresentationDefinitions for the whole game.
    
    The base game default presentation list doesn't reference the DLC
    objects, so base game COMs can't locate any DLC skills.
    Unfortunately there doesn't seem to be a good way to append items
    to existing arrays, and TPS doesn't have enough gaps in its version,
    so we have to re-create the whole thing.
    """
    global __skills
    global __original_plist

    presentation_list: unrealsdk.unreal.UObject = unrealsdk.find_object(
        "AttributePresentationListDefinition",
        "GD_AttributePresentation._AttributeList.DefaultPresentationList")
    __original_plist = [
        "None" if presentation is None or presentation.Class is None
        else f"{presentation.Class.Name}\'{presentation._path_name()}\'"
        for presentation in presentation_list.Attributes
    ]
    replacement_plist = __original_plist[:]
    for skill in __skills.values():
        if skill.presentation is None:
            continue
        presentation_name = f"{skill.presentation.Class.Name}\'{skill.presentation._path_name()}\'"
        if not presentation_name in replacement_plist:
            replacement_plist.append(presentation_name)
    console_value = ", ".join(replacement_plist)
    ENGINE.GamePlayers[0].Actor.ConsoleCommand(
        f"set GD_AttributePresentation._AttributeList.DefaultPresentationList Attributes ({console_value})")

def unflatten_presentations() -> None:
    """
    Restore the AttributePresentationListDefinition to its original state.
    """
    global __original_plist

    console_value = ",".join(__original_plist)
    ENGINE.GamePlayers[0].Actor.ConsoleCommand(
        f"set GD_AttributePresentation._AttributeList.DefaultPresentationList Attributes ({console_value})")

