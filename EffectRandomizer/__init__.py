from __future__ import annotations

import unrealsdk
import sys
import random
import os
from dataclasses import dataclass, field
from typing import Set, List, Dict, Generator, Union, Optional, Any

from ..ModManager import SDKMod, RegisterMod
from Mods.ModMenu import Game, Hook, ModTypes, Options, EnabledSaveType, LoadModSettings, SaveModSettings

try:
    import Mods.Structs
except ImportError as ex:
    import webbrowser
    webbrowser.open("https://bl-sdk.github.io/requirements/?mod=EffectRandomizer&Structs")
    raise ex

try:
    from Mods.Enums import EAttributeDataType, EAttributeInitializationRounding, ESkillType, EWeaponPartType, EProjectileType, EWillowWeaponFireType
except ImportError as ex:
    import webbrowser
    webbrowser.open("https://bl-sdk.github.io/requirements/?mod=EffectRandomizer&Enums")
    raise ex

try:
    from Mods.ChangeUtil import Changes
except ImportError as ex:
    import webbrowser
    webbrowser.open("https://bl-sdk.github.io/requirements/?mod=EffectRandomizer&ChangeUtil")
    raise ex


class ProjectileBehaviorScrambler:
    """
    Randomizes behavior of projectiles.
    """

    def __init__(self, changes):
        """
        Constructs a ProjectileBehaviorScrambler.

        Args:
            changes:  Game engine change tracker
        """
        self.changes = changes

    def scramble(self, rng):
        # Don't scramble grenade behaviors.  Grenades require correct
        # interaction between several pieces to operate, and nearly any
        # tweaking breaks them.
        unrealsdk.Log("Scrambling projectile behaviors.")       

        projectiles = []
        dangerous_projectiles = set([
            "WillowGame.Default__ProjectileDefinition",
        ])
        behaviors = []
        for projectile in unrealsdk.FindAll("ProjectileDefinition"):
            name = projectile.GetObjectName()
            if name in dangerous_projectiles:
                continue
            if "TedioreReload" in name:
                # Don't mess with Tediore reloads.
                continue
            projectiles.append(name)
            behavior = projectile.BehaviorProviderDefinition
            if behavior is None:
                continue
            if projectile.ProjectileType == EProjectileType.PROJECTILE_TYPE_Protean_Grenade:
                continue
            behaviors.append(behavior)  # can't store name, because lookup fails
        behaviors.sort(key=lambda uobj: uobj.GetObjectName())
        projectiles.sort()
        unrealsdk.Log(f"Found {len(projectiles)} projectiles and {len(behaviors)} BPDs.")

        # Scramble projectile behaviors.
        used = {}
        count = 0
        for projectile in unrealsdk.FindAll("ProjectileDefinition"):
            if projectile.Name.startswith("Default__"):
                continue
            if "TedioreReload" in projectile.Name:
                # Really don't mess with Tediore reloads.
                continue
            if projectile.ProjectileType == EProjectileType.PROJECTILE_TYPE_Protean_Grenade:
                continue
            old_behavior = rng.choice(behaviors)
            name = old_behavior.GetObjectName()
            used[name] = used.get(name, 0) + 1
            _, shortname = name.rsplit(".", 1)
            new_behavior = unrealsdk.ConstructObject(
                Class="BehaviorProviderDefinition",
                Outer=old_behavior.Outer,
                Name=f"{shortname}_{used[name]}",
                Template=old_behavior)
            unrealsdk.KeepAlive(new_behavior)
            unrealsdk.Log(f"Assigning {new_behavior.GetObjectName()} to {projectile.GetObjectName()}.BehaviorProviderDefinition")
            self.changes.set_obj_direct(
                projectile,
                "BehaviorProviderDefinition",
                new_behavior)
            count += 1
        unrealsdk.Log(f"Updated {count} projectiles.")
        
        # Assign a projectile to any firing mode that doesn't already have one.
        count = 0
        used = {}
        default_explosion = unrealsdk.FindObject(
            "ExplosionCollectionDefinition",
            "GD_Weap_Shared_Effects.Default_Elemental_Explosions"
        )
        default_damage = unrealsdk.FindObject(
            "WillowDamageTypeDefinition",
            "GD_Impact.DamageType.DmgType_Normal"
        )
        damage_attribute = unrealsdk.FindObject(
            "AttributeDefinition",
            "D_Attributes.Weapon.WeaponDamage"
        )
        for firing_mode in unrealsdk.FindAll("FiringModeDefinition"):
            fm_name = firing_mode.GetObjectName()
            if "Default__" in fm_name:
                continue
            if firing_mode.FireType == EWillowWeaponFireType.EWWFT_Beam:
                # Beam weapons don't use projectiles.
                continue

            # Force the FiringMode to pick up the projectile.
            if firing_mode.FireType == EWillowWeaponFireType.EWWFT_Bullet:
                continue  # bullet FMs don't seem to pass on weapon damage

            original = firing_mode.ProjectileDefinition
            if not original is None:
                continue
            while True:
                name = rng.choice(projectiles)
                old_projectile = unrealsdk.FindObject(
                    "ProjectileDefinition", name)
                if old_projectile is None:
                    continue
                break
            _, shortname = name.rsplit(".", 1)
            used[name] = used.get(name, 0) + 1
            new_projectile_def = unrealsdk.ConstructObject(
                Class="ProjectileDefinition",
                Outer=old_projectile.Outer,
                Name=f"{shortname}_{used[name]}",
                Template=old_projectile)
            unrealsdk.KeepAlive(new_projectile_def)
            unrealsdk.Log(f"Assigning {new_projectile_def.GetObjectName()} to {fm_name}.ProjectileDefinition")
            new_projectile_def.Damage = Mods.Structs.AttributeInitializationData(
                BaseValueAttribute=damage_attribute,
                InitializationDefinition=None,
                BaseValueScaleConstant=1.0)
            self.changes.set_obj_direct(
                firing_mode,
                "ProjectileDefinition",
                new_projectile_def)
            count += 1
        unrealsdk.Log(f"Updated {count} FiringModes.")

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: Str = "projectiles"
    OPTION: Options.Boolean = Options.Boolean(
        Caption = "Scramble Weapon Projectiles",
        Description = "Randomizes the projectiles a weapon fires",
        StartingValue = False,
        Choices = ("Off", "On"),
        IsHidden = False
    )
    SCRAMBLES_ITEMS: Bool = False
    SCRAMBLES_WEAPONS: Bool = True
        

class FiringModeScrambler:
    """
    Randomizes aspects of weapon firing modes.
    """

    def __init__(self, changes):
        """
        Constructs a BehaviorProjectileScrambler.

        Args:
            changes:  Game engine change tracker
        """
        self.changes = changes

    def scramble(self, rng):
        unrealsdk.Log("Scrambling firing modes.")
        
        count = 0
        for firing_mode in unrealsdk.FindAll("FiringModeDefinition"):
            if "Default__" in firing_mode.Name:
                continue

            # Don't bother with firing patterns.  They usually make a weapon
            # less usable, they're only noticeable for high-projectile-count
            # weapons, and scrambling them is pretty much equivalent to
            # scrambling barrels.

            # Same goes for Acceleration, WaveFreq, WaveAmp, and WavePhase.
            # If the weapon already has them set, leave it alone.
            
            fire_type = firing_mode.FireType
            if (fire_type != EWillowWeaponFireType.EWWFT_Beam and
                rng.randint(1, 20) == 1):
                # Create a beam weapon.
                fire_type = EWillowWeaponFireType.EWWFT_Beam
                self.changes.set_obj_direct(firing_mode, "FireType", fire_type)
                self.changes.set_obj_direct(firing_mode, "BeamChainDelay", 0.1)

            # Speed ranges from 0 for rockets to 45K for snipers.
            speed = min(45000, 250 * pow(2, rng.randint(0, 8)))
            self.changes.set_obj_direct(firing_mode, "Speed", speed)

            # Give weapons a small chance to penetrate targets, B0re-style.
            penetrate = False
            if rng.randint(1, 60) == 1:
                penetrate = True
                self.changes.set_obj_direct(firing_mode, "bPenetratePawn", True)

            num_ricochets = 0
            num_ricochet_splits = 0
            while rng.randint(1, 4) == 1:
                num_ricochets += 1
                if num_ricochets > 2:
                    # nobody notices past two, so instead boost splits
                    num_ricochets = 1
                    num_ricochet_splits += rng.randint(1,8)

            self.changes.set_obj_direct(
                firing_mode, "NumRicochets", num_ricochets)
            if num_ricochets > 0:
                # Friction varies from 0 to 0.75 but has little effect.
                self.changes.set_obj_direct(
                    firing_mode, "RicochetFriction", 0.2 * rng.randint(0,4))
            if num_ricochet_splits > 0:
                split_firing_mode = unrealsdk.ConstructObject(
                    Class="FiringModeDefinition",
                    Outer=firing_mode.Outer,
                    Name=f"{firing_mode.Name}_Split",
                    Template=firing_mode)
                unrealsdk.KeepAlive(split_firing_mode)
                split_firing_mode.TimingEvents = None
                split_firing_mode.RicochetResponse.SplitNum = 0
                ricochet_response = Mods.Structs.BulletEventResponse(
                    SplitNum=num_ricochet_splits,
                    SplitAngle=rng.randint(2,30),
                    SplitFire=split_firing_mode,
                    NewSpeed=0.0,
                    bDetonate=False,
                    bRespawnTracer=True,
                    bUpdateBeamSourceLocation=False)
                self.changes.set_obj_direct(
                    firing_mode, "RicochetResponse", ricochet_response)

            # TimingEvents are the most complicated part.  Because splits should
            # occur at a visible distance, their timing has to be calculated
            # relative to the projectile velocity.
            period = float(100 * rng.randint(1,4)) / speed
            events = []
            tick = 0
            # Find any existing Behavior_Explode objects
            explosion = None
            if not firing_mode.TimingEvents is None:
                for event in firing_mode.TimingEvents:
                    if event.Response.Behaviors is None:
                        continue
                    if len(event.Response.Behaviors) == 0:
                        continue
                    explosion = event.Response.Behaviors[0]
                    break
            while rng.randint(1,5) == 1:
                tick += 1
                if explosion is None:
                    # No explosion found in original - split projectiles.
                    # Go with multiples of two to avoid asymmetric spreads.
                    num_children = 2 * rng.choice([1,1,1,2,2,3,5,7])
                    angle = rng.randint(5,int(180/(num_children + 1)))
                    # Create the split firing mode as a copy of the main one,
                    # minus the timing events.
                    split_firing_mode = unrealsdk.ConstructObject(
                        Class="FiringModeDefinition",
                        Outer=firing_mode.Outer,
                        Name=f"{firing_mode.Name}_Child{tick}",
                        Template=firing_mode)
                    unrealsdk.KeepAlive(split_firing_mode)
                    split_firing_mode.TimingEvents = None
                    response = Mods.Structs.BulletEventResponse(
                        SplitNum=num_children,
                        SplitAngle=angle,
                        SplitAngleOffset=0,
                        SplitDistance=0,
                        SplitFire=split_firing_mode,
                        NewSpeed=0.0,
                        bDetonate=True,
                        bRespawnTracer=False,
                        bUpdateBeamSourceLocation=False
                    )
                else:
                    # Explosion found.  Use it.
                    response = Mods.Structs.BulletEventResponse(
                        NewSpeed=5000.0,
                        Behaviors=[explosion]
                    )
                event = Mods.Structs.BulletTimerEvent(
                    Time=period * tick,
                    Response=response
                )
                events.append(event)

            self.changes.set_obj_direct(
                firing_mode,
                "TimerEvents",
                events                
            )
            unrealsdk.Log(f"{firing_mode.Name}: FireType={fire_type}, NumRicochets={num_ricochets}, NumRicochetSplits={num_ricochet_splits}, Penetrate={penetrate}, Speed={speed}, TimingEvents has {len(events)} events")  
            count += 1
        unrealsdk.Log(f"Updated {count} FiringModeDefinitions.")

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: Str = "firing_modes"
    OPTION: Options.Boolean = Options.Boolean(
        Caption = "Scramble Weapon Firing Modes",
        Description = "Randomizes how a weapon fires projectiles",
        StartingValue = False,
        Choices = ("Off", "On"),
        IsHidden = False
    )
    SCRAMBLES_ITEMS: Bool = False
    SCRAMBLES_WEAPONS: Bool = True
                           
            
class ShieldBonusScrambler:
    """
    Randomizes shield part SpecialXX bonuses.
    """

    def __init__(self, changes):
        """
        Constructs a ShieldBonusScrambler.

        Args:
            changes:  Game engine change tracker
        """
        self.changes = changes

    def scramble(self, rng):
        """
        Randomizes all SpecialXX shield part bonuses.

        Args:
            rng:  Random number generator.
        """
        unrealsdk.Log("Scrambling shield bonuses.")

        # Grab all the existing slot bonuses.
        values = []
        known_parts = set()
        for shield_part in unrealsdk.FindAll("ShieldPartDefinition"):
            shield_part_name = shield_part.GetObjectName()
            if shield_part_name in known_parts:
                # Somehow this part got duplicated.  Ignore.
                continue
            known_parts.add(shield_part_name)
            for slot_upgrade in shield_part.AttributeSlotUpgrades:
                if slot_upgrade.SlotName.startswith("Special"):
                    values.append(slot_upgrade.GradeIncrease)
            for item_effect in shield_part.ItemAttributeEffects:
                if item_effect.AttributeToModify.Name == "ShieldSpecialSlotGradeMinusRarity":
                    values.append(
                        int(item_effect.BaseModifierValue.BaseValueConstant +
                            0.5))
        unrealsdk.Log(f"Found {len(values)} shield bonuses.")

        # Assign new random bonuses from the list.
        upgrade_count = 0
        shield_count = 0
        known_parts = set()
        for shield_part in unrealsdk.FindAll("ShieldPartDefinition"):
            if shield_part.Name.startswith("Default__"):
                continue
            shield_part_name = shield_part.GetObjectName()
            if shield_part_name in known_parts:
                # Somehow this part got duplicated.  Ignore.
                continue
            known_parts.add(shield_part_name)
            if (not shield_part.AttributeSlotUpgrades is None) and len(shield_part.AttributeSlotUpgrades) > 0:
                upgrades = self.changes.edit_obj(
                    shield_part, "AttributeSlotUpgrades", list)
                for index in range(0, len(upgrades)):
                    if upgrades[index].SlotName.startswith("Special"):
                        upgrades[index] = upgrades[index]._replace(
                            GradeIncrease = rng.choice(values))
                        upgrade_count += 1
            if (not shield_part.ItemAttributeEffects is None) and len(shield_part.ItemAttributeEffects) > 0:
                effects = self.changes.edit_obj(
                    shield_part, "ItemAttributeEffects", list)
                for index in range(0, len(effects)):
                    if effects[index].AttributeToModify.Name == "ShieldSpecialSlotGradeMinusRarity":
                        effects[index] = effects[index]._replace(
                            BaseModifierValue = effects[index].BaseModifierValue._replace(
                                BaseValueConstant = rng.choice(values)))
                        upgrade_count += 1
            shield_count += 1
        unrealsdk.Log(f"Updated {upgrade_count} slots/effects on {shield_count} shields.")

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: Str = "shield"
    OPTION: Options.Boolean = Options.Boolean(
            Caption = "Scramble Shield Bonuses",
            Description = "Randomizes shield part special bonuses",
            StartingValue = False,
            Choices = ("Off", "On"),
            IsHidden = False
    )
    SCRAMBLES_ITEMS: Bool = True
    SCRAMBLES_WEAPONS: Bool = False


                    
class ClassModPartScrambler:
    """
    Randomizes class mod part behavior.
    """

    def __init__(self, changes):
        """
        Constructs a ClassModPartScrambler.

        Args:
            changes:  Game engine change tracker
        """
        self.changes = changes

    def scramble(self, rng):
        """
        Randomizes slot contents for all classmod parts.

        Args:
            rng:  Random number generator.
        """
        unrealsdk.Log("Scrambling class mod part functions.")

        # Grab all of the existing slot upgrades.
        upgrades = []
        for part in unrealsdk.FindAll("ClassModPartDefinition"):
            if part.AttributeSlotUpgrades is None:
                continue
            upgrades.extend([Mods.Structs.AttributeSlotUpgradeData(upgrade)
                             for upgrade in part.AttributeSlotUpgrades])
        unrealsdk.Log(f"Found {len(upgrades)} classmod upgrades.")

        # Assign new upgrades.
        count = 0
        for part in unrealsdk.FindAll("ClassModPartDefinition"):
            if part.Name.startswith("Default__"):
                continue
            if part.AttributeSlotUpgrades is None or len(
                    part.AttributeSlotUpgrades) == 0:
                continue            
            used = set()
            attribute_slot_upgrades = []
            for slot in range(0, 4):
                while True:
                    upgrade = rng.choice(upgrades)
                    if not upgrade.SlotName in used:
                        used.add(upgrade.SlotName)
                        attribute_slot_upgrades.append(upgrade)
                        break
            self.changes.set_obj(
                part, "AttributeSlotUpgrades", attribute_slot_upgrades)
            count += 1
        unrealsdk.Log(f"Updated {count} ClassModParts.")

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: Str = "classmod"
    OPTION: Options.Boolean = Options.Boolean(
        Caption = "Scramble Classmod Part Purposes",
        Description = "Randomizes what each classmod part does",
        StartingValue = False,
        Choices = ("Off", "On"),
        IsHidden = False
    )
    SCRAMBLES_ITEMS: Bool = True
    SCRAMBLES_WEAPONS: Bool = False


class RelicScrambler:
    """
    Randomizes relic bonuses.  Works only for BL2 and AoDK; Oz kits in TPS
    are a little too difficult to tackle.
    """
    
    def __init__(self, changes):
        """
        Constructs a RelicScrambler.

        Args:
            changes:  Game engine change tracker
        """
        self.changes = changes

    def scramble(self, rng):
        """
        Randomizes relic bonuses.  Note that all relics are now assigned
        seven potential bonuses, of which at most four are enabled, so two
        instances of the same relic may be quite different from each other.

        Args:
            rng:  Random number generator.
        """
        unrealsdk.Log("Scrambling relics.")

        # Grab all the existing slot effects and UIStatList entries.
        ui_stats = {}
        slots = {}
        behaviors = {}
        for relic in unrealsdk.FindAll("ArtifactDefinition"):
            if relic.UIStatList is None or relic.AttributeSlotEffects is None:
                continue
            for ui_stat in relic.UIStatList:
                if ui_stat.Attribute is None:
                    continue
                attribute_name = ui_stat.Attribute.GetObjectName()
                if not ui_stat.ConstraintAttribute is None:
                    attribute_name += "/" + ui_stat.ConstraintAttribute.GetObjectName()
                ui_stats[attribute_name] = Mods.Structs.UIStatData(ui_stat)
            for slot in relic.AttributeSlotEffects:
                if slot.AttributeToModify is None:
                    continue
                attribute_name = slot.AttributeToModify.GetObjectName()
                if not slot.ConstraintAttribute is None:
                    attribute_name += "/" + slot.ConstraintAttribute.GetObjectName()
                slots[attribute_name] = Mods.Structs.AttributeSlotEffectData(slot)
                if slot.AttributeToModify.Class.Name == "DesignerAttributeDefinition":
                    # Designer attributes do nothing without a behavior
                    if not attribute_name in behaviors:
                        behaviors[
                            attribute_name] = relic.BehaviorProviderDefinition

        # TODO: figure out how to keep offhand effects boosted correctly

        # It's possible that an attribute is affected with varying scales
        # across two different artifacts.  Not going to worry about that yet.
        # TODO: fix problem with Maliwan where constraints are different
        #   between UI entry and slot entry
        partlists = {
            part : unrealsdk.FindObject("ItemPartListDefinition", partlist)
            for part, partlist in self.ENABLERS.items()
        }
        
        attribute_names = [name for name in ui_stats if name in slots]
        unrealsdk.Log(f"Found {len(attribute_names)} relic bonuses.")

        count = 0
        for relic in unrealsdk.FindAll("ArtifactDefinition"):
            if relic.Name.startswith("Default__"):
                continue
            ui_stat_list = []
            attribute_slot_effects = []
            used = set()

            # Set a bonus for certain powerful relics.
            fullname = relic.GetObjectName()
            if "Seraph" in fullname:
                scale = 2.0
            elif "Unique" in fullname:
                scale = 1.5
            else:
                scale = 1.0

            behavior = None
            for index in range(0,7):
                while True:
                    attribute_name = rng.choice(attribute_names)
                    if not attribute_name in used:
                        used.add(attribute_name)
                        break
                unrealsdk.Log(f"Adding attr {attribute_name} to {relic.GetObjectName()} as Effect{index+1}")
                ui_stat_list.append(ui_stats[attribute_name])
                attribute_slot_effects.append(
                    slots[attribute_name]._replace(
                        SlotName=f"Effect{index+1}",
                        PerGradeUpgrade=slots[
                            attribute_name
                        ].PerGradeUpgrade._replace(
                            BaseValueScaleConstant=scale)))
                if attribute_name in behaviors and behavior is None:
                    behavior = behaviors[attribute_name]
            self.changes.set_obj(relic,
                                 "UIStatList",
                                 ui_stat_list)
            self.changes.set_obj(relic,
                                 "AttributeSlotEffects",
                                 attribute_slot_effects)
            if (relic.BehaviorProviderDefinition is None) and (
                    not behavior is None):
                unrealsdk.Log(f"Adding behavior {behavior.GetObjectName()}")
                self.changes.set_obj_direct(relic,
                                            "BehaviorProviderDefinition",
                                            behavior)
            for part, partlist in partlists.items():
                self.changes.set_obj(relic, part, partlist)
            count += 1
                                 
        unrealsdk.Log(f"Updated {count} relics.")

        # Update the ItemPartListCollectionDefinition objects to cover all
        # effect options.
        count = 0
        for partlist in unrealsdk.FindAll("ItemPartListCollectionDefinition"):
            relic = partlist.AssociatedItem
            if relic is None:
                continue
            if relic.Class.Name != "ArtifactDefinition":
                continue
            for partdata_attr in self.PARTDATA_ATTRS:
                partdata = getattr(partlist, partdata_attr, None)
                if partdata is None:
                    continue
                if partdata.WeightedParts is None:
                    continue
                if len(partdata.WeightedParts) == 0:
                    continue
                # Each partdata is usually a weighted list of enablers for
                # different effects, tied to a set of 'manufacturers' who
                # include that enabler in their artifact product.  Keep the
                # same manufacturers, but replace with a full set of enablers
                # for all seven slots.
                unrealsdk.Log(f"Updating {partlist.GetObjectName()}.{partdata_attr}")
                weighted_parts = []
                for part_option in partdata.WeightedParts:
                    weight_template = Mods.Structs.ItemPartGradeWeightData(
                        part_option)
                    part_prefix = weight_template.Part.GetObjectName()[:-1]
                    for index in range(1,8):
                        enabler = unrealsdk.FindObject(
                            "ArtifactPartDefinition",
                            f"{part_prefix}{index}")
                        weight_data = weight_template._replace(Part=enabler)
                        weighted_parts.append(weight_data)
                self.changes.set_obj(partlist, partdata_attr,
                                     Mods.Structs.ItemCustomPartTypeData(
                                         bEnabled=True,
                                         WeightedParts=weighted_parts))
            count += 1
        unrealsdk.Log(f"Updated {count} relic ItemPartListCollectionDefinitions.")
                                
    ENABLERS: dict[Str, Str] = {
        "AlphaParts" : "GD_Artifacts.Enable1st.PartList_EnableFirstEffect",
        "BetaParts" : "GD_Artifacts.Enable2nd.PartList_EnableSecondEffect",
        "GammaParts" : "GD_Artifacts.Enable3rd.PartList_EnableThirdEffect",
        "DeltaParts" : "GD_Artifacts.Enable4th.PartList_EnableFourthEffect",
    }
    
    PARTDATA_ATTRS: list[Str] = [
        "AlphaPartData",
        "BetaPartData",
        "GammaPartData",
        "DeltaPartData",
        "EpsilonPartData",
        "ZetaPartData",
    ]

    SUPPORTS: int = Game.BL2 | Game.AoDK
    CONFIG_KEY: Str = "relic"
    OPTION: Options.Boolean = Options.Boolean(
        Caption = "Scramble Relic Bonuses",
        Description = "Randomizes relic bonuses",
        StartingValue = False,
        Choices = ("Off", "On"),
        IsHidden = False
    )
    SCRAMBLES_ITEMS: Bool = True
    SCRAMBLES_WEAPONS: Bool = False


class SeededEffectRandomizer(SDKMod):
    """
    Provides the interface for an EffectRandomizer with a particular seed.
    """

    Name: str = "Effect Randomizer ({})"
    Version: str = "0.1"
    Author: str = "Milo"
    Description: str = ""
    SupportedGames: Game = Game.BL2 | Game.TPS | Game.AoDK
    Types: ModTypes = ModTypes.Gameplay
    SaveEnabledState: EnabledSaveType = EnabledSaveType.NotSaved

    def __init__(self,
                 parent: EffectRandomizer,
                 config: Dict[str, Union[bool, int, float, List[str]]] = None) -> None:
        """
        Args:
            parent:  Unseeded EffectRandomizer which tracks all the seeded
                instances.
            config:  Dict containing the seeded instance's configuration.
        """

        self.config = config
        self.parent = parent
        self.Name = self.Name.format(self.config["seed"])
        self.Description = "\n".join([
            f"{scl.OPTION.Caption}: {self.config[scl.CONFIG_KEY]}"
            for scl in self.parent.scrambler_classes
        ])
        self.SettingsInputs: Dict[str, str] = { "Enter" : "Enable",
                                                "Delete" : "Remove" }
        self.changes = Changes()
        #self.changes.verbose = True
        self.rng = None
        self.late_init = False

    def SettingsInputPressed(self, action:str) -> None:
        """
        Handles a keypress.

        Args:
            action:  Action requested by a keypress in the options menu.
        """

        unrealsdk.Log(f"{self.Name}: user requested {action}\n")
        if action == "Remove":
            self.parent.delete_seed(self.config["seed"])
            self.Description = "Will be removed from the menu on the next game restart."
            if self.IsEnabled:
                self.SettingsInputPressed("Disable")
            self.SettingsInputs = { "Insert" : "Restore" }
            SaveModSettings(self.parent)
        elif action == "Restore":
            self.parent.add_child(self)
            self.Description = "\n".join([
                f"{scl.OPTION.Caption}: {self.config[scl.CONFIG_KEY]}"
                for scl in self.parent.scrambler_classes
            ])
            self.SettingsInputs = { "Enter" : "Enable",
                                    "Delete" : "Remove" }
            SaveModSettings(self.parent)
        else:
            super().SettingsInputPressed(action)

    def clean_items(self) -> None:
        """
        Regenerate internal caches for all known items.
        """
        for item in unrealsdk.FindAll("WillowItem"):
            if item.Name.startswith("Default__"):
                continue
            item.InitializeFromDefinitionData(
                item.DefinitionData, item.Owner)

    def clean_weapons(self) -> None:
        """
        Regenerate internal caches for all known weapons.
        """
        for weapon in unrealsdk.FindAll("WillowWeapon"):
            if weapon.Name.startswith("Default__"):
                continue
            weapon.InitializeFromDefinitionData(
                weapon.DefinitionData, weapon.Owner)

    def Enable(self) -> None:
        """
        Called when the seeded instance is activated.  Launches scramblers
        that need to be active before player inventory is loaded.
        """
        
        self.parent.SettingsInputPressed("Enable")  # make sure parent's active
        self.parent.set_active_child(self.config["seed"])
        super().Enable()
        if not self.rng:
            self.rng = random.Random(self.config["seed"])
            items_dirty = False
            weapons_dirty = False
            for scrambler_class in self.parent.scrambler_classes:
                if not Game.GetCurrent() in scrambler_class.SUPPORTS:
                    continue
                seed = self.rng.randrange(sys.maxsize)
                # Generate a new rng for each scrambler so that patches to
                # one don't affect existing saves for the others.
                scrambler_rng = random.Random(seed)

                if self.config[scrambler_class.CONFIG_KEY]:
                    scrambler = scrambler_class(self.changes)
                    scrambler.scramble(scrambler_rng)
                    if scrambler.SCRAMBLES_ITEMS:
                        items_dirty = True
                    if scrambler.SCRAMBLES_WEAPONS:
                        weapons_dirty = True
                
            self.changes.commit()
            if items_dirty:
                self.clean_items()
            if weapons_dirty:
                self.clean_weapons()

    @Hook("WillowGame.WillowPlayerController.WillowClientDisableLoadingMovie")
    def on_disable_loading_movie(self, caller: unrealsdk.UObject,
                                 function: unrealsdk.UFunction,
                                 params:  unrealsdk.FStruct) -> bool:
        """
        Launches scramblers that need all level objects loaded before operating.

        Args:
            caller:  Object invoking OnTeleport
            function:  Stack context for function call
            params:  Argument bindings for the call

        Returns:
            True if the hook should call the originally replaced function
        """
        
        if not self.late_init:
            self.late_init = True
            # Execute late-init scramblers here.
        return True

    def Disable(self) -> None:
        """
        Called when the seeded instance is deactivated.
        """
        unrealsdk.Log(f"Disable called; unwinding {len(self.changes.undo_log)} changes")
        self.changes.unwind()
        unrealsdk.Log("Changes unwound.")
        self.parent.disable_child(self.config["seed"])
        self.rng = None
        self.late_init = False
        super().Disable()


class EffectRandomizer(SDKMod):
    """
    Provides the interface for an EffectRandomizer with no seed assigned. 
    """
    Name: str = "Effect Randomizer (New Seed)"
    Description: str = "Scramble item effects!"
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

    def __init__(self):
        self.children = {}
        self.Options = []
        self.scrambler_classes = []
        self.create_initial_options()

    def create_initial_options(self) -> None:
        """
        Constructs the options menu for the EffectRandomizer.
        """
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

        self.Options = [
            self.children_option,
            self.active_child_option,
        ]

    def register_scrambler_class(self, scrambler_class: Class) -> None:
        """
        Adds a scrambler to the mod.
        """
        if Game.GetCurrent() in scrambler_class.SUPPORTS:
            self.scrambler_classes.append(scrambler_class)
            self.Options.append(scrambler_class.OPTION)

    def create_seeded_instances(self) -> None:
        """
        Instantiates a child SeededEffectRandomizer for each known seed.
        """
        for config in self.children_option.CurrentValue.values():
            child = SeededEffectRandomizer(parent=self, config=config)
            self.children[config["seed"]] = child
            RegisterMod(child)
        if not self.active_child_option.CurrentValue is None:
            self.SettingsInputPressed("Disable")
            active_mod = self.children[self.active_child_option.CurrentValue]
            active_mod.SettingsInputPressed("Enable")

    def set_active_child(self, active_child: str) -> None:
        """
        Activates one seeded child and deactivates all others.

        Args:
            active_child:  Stringified seed of child to activate.
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
        Deactivates the currently active child.

        Args:
            active_child:  Stringified seed of child to deactivate.
        """
        self.active_child_option.CurrentValue = None

    def add_child(self, child: SeededEffectRandomizer) -> None:
        """
        Adds a new child to the set of seeds being tracked.

        Args:
            child:  SeededEffectRandomizer instance to add.
        """
        seed = child.config["seed"]
        if not str(seed) in self.children_option.CurrentValue:
            self.children_option.CurrentValue[str(seed)] = child.config
        if not seed in self.children:
            self.children[seed] = child

    def delete_seed(self, seed: int) -> None:
        """
        Removes a child from the set of seeds being tracked.

        Args:
            seed:  Seed of child to remove.
        """
        if self.active_child_option.CurrentValue == seed:
            self.active_child_option.CurrentValue = None
        if str(seed) in self.children_option.CurrentValue:
            del self.children_option.CurrentValue[str(seed)]
        if seed in self.children:
            del self.children[seed]

    def Enable(self) -> None:
        """
        Activates the unseeded instance and deactivates all seeded instances.
        """
        if not self.active_child_option.CurrentValue is None:
            self.children[
                self.active_child_option.CurrentValue
            ].SettingsInputPressed("Disable")
            self.active_child_option.CurrentValue = None
        super().Enable()

    @Hook("WillowGame.WillowPlayerController.WillowClientDisableLoadingMovie")
    def on_disable_loading_movie(self, caller: unrealsdk.UObject,
                                 function: unrealsdk.UFunction,
                                 params: unrealsdk.FStruct) -> bool:
        """
        Constructs a new seeded instance using the current option settings.

        Args:
            caller:  Object invoking OnTeleport
            function:  Stack context for function call
            params:  Argument bindings for the call

        Returns:
            True if the hook should call the originally replaced function
        """
        config = {
            scrambler_class.CONFIG_KEY : scrambler_class.OPTION.CurrentValue
            for scrambler_class in self.scrambler_classes
        }
        while True:
            config["seed"] = random.randrange(sys.maxsize)
            if not config["seed"] in self.children:
                break

        seed = config["seed"]
        unrealsdk.Log(f"Randomizing effects with seed '{seed}'")
        new_child = SeededEffectRandomizer(parent=self, config=config)
        self.add_child(new_child)
        RegisterMod(new_child)
        self.set_active_child(seed)
        new_child.SettingsInputPressed("Enable")
        return new_child.on_disable_loading_movie(caller, function, params)


parent = EffectRandomizer()
parent.register_scrambler_class(ProjectileBehaviorScrambler)
parent.register_scrambler_class(FiringModeScrambler)
parent.register_scrambler_class(ShieldBonusScrambler)
parent.register_scrambler_class(ClassModPartScrambler)
parent.register_scrambler_class(RelicScrambler)
RegisterMod(parent)
parent.create_seeded_instances()

