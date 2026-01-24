from typing import TYPE_CHECKING, Any

import sys
import random
import copy
import unrealsdk
from unrealsdk.hooks import Block
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct
from mods_base import build_mod, get_pc, hook, Game, BaseOption, BoolOption, HiddenOption, ButtonOption, SETTINGS_DIR
from .changes import Changes

EProjectileType = unrealsdk.find_enum("EProjectileType")
EWillowWeaponFireType = unrealsdk.find_enum("EWillowWeaponFireType")

__changes : Changes = Changes()
#__changes.verbose = True   # get extra logging

class ProjectileBehaviorScrambler:
    """
    Randomizes behavior of projectiles.
    """

    def __init__(self):
        """
        Constructs a ProjectileBehaviorScrambler.
        """
        pass

    def scramble(self, rng : random.Random, changes : Changes) -> None:
        """
        Randomizes projectile behaviors.

        Args:
            rng:  Random number generator to use.
            changes:  Change manager to update and roll back UE objects.
        """
        
        # Don't scramble grenade behaviors.  Grenades require correct
        # interaction between several pieces to operate, and nearly any
        # tweaking breaks them.
        unrealsdk.Log("Scrambling projectile behaviors.")       

        projectiles = []
        dangerous_projectiles = set([
            "WillowGame.Default__ProjectileDefinition",
        ])
        behaviors = []
        for projectile in unrealsdk.find_all("ProjectileDefinition"):
            name = projectile._path_name()
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
        behaviors.sort(key=lambda uobj: uobj._path_name())
        projectiles.sort()

        # Scramble projectile behaviors.
        used = {}
        count = 0
        for projectile in unrealsdk.find_all("ProjectileDefinition"):
            if projectile.Name.startswith("Default__"):
                continue
            if "TedioreReload" in projectile.Name:
                # Really don't mess with Tediore reloads.
                continue
            if projectile.ProjectileType == EProjectileType.PROJECTILE_TYPE_Protean_Grenade:
                continue
            old_behavior = rng.choice(behaviors)
            name = old_behavior._path_name()
            used[name] = used.get(name, 0) + 1
            _, shortname = name.rsplit(".", 1)
            new_behavior = unrealsdk.construct_object(
                cls="BehaviorProviderDefinition",
                outer=old_behavior.Outer,
                name=f"{shortname}_{used[name]}",
                flags=0x4000,
                template_obj=old_behavior)
            changes.set_obj_direct(
                projectile,
                "BehaviorProviderDefinition",
                new_behavior)
            count += 1
        
        # Assign a projectile to any firing mode that doesn't already have one.
        count = 0
        used = {}
        default_explosion = unrealsdk.find_object(
            "ExplosionCollectionDefinition",
            "GD_Weap_Shared_Effects.Default_Elemental_Explosions"
        )
        default_damage = unrealsdk.find_object(
            "WillowDamageTypeDefinition",
            "GD_Impact.DamageType.DmgType_Normal"
        )
        damage_attribute = unrealsdk.find_object(
            "AttributeDefinition",
            "D_Attributes.Weapon.WeaponDamage"
        )
        for firing_mode in unrealsdk.find_all("FiringModeDefinition"):
            fm_name = firing_mode._path_name()
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
                old_projectile = unrealsdk.find_object(
                    "ProjectileDefinition", name)
                if old_projectile is None:
                    continue
                break
            _, shortname = name.rsplit(".", 1)
            used[name] = used.get(name, 0) + 1
            new_projectile_def = unrealsdk.construct_object(
                cls="ProjectileDefinition",
                outer=old_projectile.Outer,
                name=f"{shortname}_{used[name]}",
                flags=0x4000,
                template_obj=old_projectile)
            new_projectile_def.Damage = unrealsdk.make_struct(
                "AttributeInitializationData",
                BaseValueAttribute=damage_attribute,
                InitializationDefinition=None,
                BaseValueScaleConstant=1.0
            )
            changes.set_obj_direct(
                firing_mode,
                "ProjectileDefinition",
                new_projectile_def)
            count += 1

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: str = "projectiles"
    OPTION: BoolOption = BoolOption(
        identifier="Scramble Weapon Projectiles",
        description="Randomizes the projectiles a weapon fires",
        value=False,
        true_text="On",
        false_text="Off",
    )
    SCRAMBLES_ITEMS: bool = False
    SCRAMBLES_WEAPONS: bool = True
        

class FiringModeScrambler:
    """
    Randomizes aspects of weapon firing modes.
    """

    def __init__(self):
        """
        Constructs a FiringModeScrambler.
        """
        pass

    def scramble(self, rng : random.Random, changes : Changes) -> None:
        """
        Randomizes firing mode behavior.

        Args:
            rng:  Random number generator to use.
            changes:  Change manager to update and roll back UE objects.
        """
        
        count = 0
        for firing_mode in unrealsdk.find_all("FiringModeDefinition"):
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
                __changes.set_obj_direct(firing_mode, "FireType", fire_type)
                __changes.set_obj_direct(firing_mode, "BeamChainDelay", 0.1)

            # Speed ranges from 0 for rockets to 45K for snipers.
            speed = min(45000, 250 * pow(2, rng.randint(0, 8)))
            __changes.set_obj_direct(firing_mode, "Speed", speed)

            # Give weapons a small chance to penetrate targets, B0re-style.
            penetrate = False
            if rng.randint(1, 60) == 1:
                penetrate = True
                __changes.set_obj_direct(firing_mode, "bPenetratePawn", True)

            num_ricochets = 0
            num_ricochet_splits = 0
            while rng.randint(1, 4) == 1:
                num_ricochets += 1
                if num_ricochets > 2:
                    # nobody notices past two, so instead boost splits
                    num_ricochets = 1
                    num_ricochet_splits += rng.randint(1,8)

            __changes.set_obj_direct(
                firing_mode, "NumRicochets", num_ricochets)
            if num_ricochets > 0:
                # Friction varies from 0 to 0.75 but has little effect.
                __changes.set_obj_direct(
                    firing_mode, "RicochetFriction", 0.2 * rng.randint(0,4))
            if num_ricochet_splits > 0:
                split_firing_mode = unrealsdk.construct_object(
                    cls="FiringModeDefinition",
                    outer=firing_mode.Outer,
                    name=f"{firing_mode.Name}_Split",
                    flags=0x4000,
                    template_obj=firing_mode)
                split_firing_mode.TimingEvents = None
                split_firing_mode.RicochetResponse.SplitNum = 0
                ricochet_response = unrealsdk.make_struct(
                    "BulletEventResponse",
                    SplitNum=num_ricochet_splits,
                    SplitAngle=rng.randint(2,30),
                    SplitFire=split_firing_mode,
                    NewSpeed=0.0,
                    bDetonate=False,
                    bRespawnTracer=True,
                    bUpdateBeamSourceLocation=False)
                __changes.set_obj_direct(
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
                    split_firing_mode = unrealsdk.construct_object(
                        cls="FiringModeDefinition",
                        outer=firing_mode.Outer,
                        name=f"{firing_mode.Name}_Child{tick}",
                        flags=0x4000,
                        template_obj=firing_mode)
                    split_firing_mode.TimingEvents = None
                    response = unrealsdk.make_struct(
                        "BulletEventResponse",
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
                    response = unrealsdk.make_struct(
                        "BulletEventResponse",
                        NewSpeed=5000.0,
                        Behaviors=[explosion]
                    )
                event = unrealsdk.make_struct(
                    "BulletTimerEvent",
                    Time=period * tick,
                    Response=response
                )
                events.append(event)

            __changes.set_obj_direct(
                firing_mode,
                "TimerEvents",
                events                
            )
            count += 1

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: str = "firing_modes"
    OPTION: BoolOption = BoolOption(
        identifier="Scramble Weapon Firing Modes",
        description="Randomizes how a weapon fires projectiles",
        value=False,
        true_text="On",
        false_text="Off",
    )
    SCRAMBLES_ITEMS: bool = False
    SCRAMBLES_WEAPONS: bool = True
                           
            
class ShieldBonusScrambler:
    """
    Randomizes shield part SpecialXX bonuses.
    """

    def __init__(self):
        """
        Constructs a ShieldBonusScrambler.
        """
        pass

    def scramble(self, rng : random.Random, changes : Changes) -> None:
        """
        Randomizes all SpecialXX shield part bonuses.

        Args:
            rng:  Random number generator to use.
            changes:  Change manager to update and roll back UE objects.
        """
        # Grab all the existing slot bonuses.
        values = []
        known_parts = set()
        for shield_part in unrealsdk.find_all("ShieldPartDefinition"):
            shield_part_name = shield_part._path_name()
            if shield_part_name in known_parts:
                # Somehow this part got duplicated.  Ignore.
                continue
            known_parts.add(shield_part_name)
            for slot_upgrade in shield_part.AttributeSlotUpgrades:
                if slot_upgrade.SlotName.startswith("Special"):
                    values.append(slot_upgrade.GradeIncrease)
            for item_effect in shield_part.ItemAttributeEffects:
                if item_effect.AttributeToModify is None:
                    continue
                if item_effect.AttributeToModify.Name == "ShieldSpecialSlotGradeMinusRarity":
                    values.append(
                        int(item_effect.BaseModifierValue.BaseValueConstant +
                            0.5))

        # Assign new random bonuses from the list.
        upgrade_count = 0
        shield_count = 0
        known_parts = set()
        for shield_part in unrealsdk.find_all("ShieldPartDefinition"):
            if shield_part.Name.startswith("Default__"):
                continue
            shield_part_name = shield_part._path_name()
            if shield_part_name in known_parts:
                # Somehow this part got duplicated.  Ignore.
                continue
            known_parts.add(shield_part_name)
            if (not shield_part.AttributeSlotUpgrades is None) and len(shield_part.AttributeSlotUpgrades) > 0:
                upgrades = changes.edit_obj(
                    shield_part, "AttributeSlotUpgrades", unrealsdk.unreal.WrappedArray)
                for index in range(0, len(upgrades)):
                    if upgrades[index].SlotName.startswith("Special"):
                        upgrades[index] = copy.copy(upgrades[index])
                        upgrades[index].GradeIncrease = rng.choice(values)
                        upgrade_count += 1
            if (not shield_part.ItemAttributeEffects is None) and len(shield_part.ItemAttributeEffects) > 0:
                effects = changes.edit_obj(
                    shield_part, "ItemAttributeEffects", unrealsdk.unreal.WrappedArray)
                for index in range(0, len(effects)):
                    if effects[index].AttributeToModify is None:
                        continue
                    if effects[index].AttributeToModify.Name == "ShieldSpecialSlotGradeMinusRarity":
                        effects[index] = copy.copy(effects[index])
                        effects[index].BaseModifierValue = copy.copy(effects[index].BaseModifierValue)
                        effects[index].BaseModifierValue.BaseValueConstant = rng.choice(values)
                        upgrade_count += 1
            shield_count += 1

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: str = "shield"
    OPTION: BoolOption = BoolOption(
        identifier="Scramble Shield Bonuses",
        description="Randomizes shield part special bonuses",
        value=False,
        true_text="On",
        false_text="Off",
    )
    SCRAMBLES_ITEMS: bool = True
    SCRAMBLES_WEAPONS: bool = False


                    
class ClassModPartScrambler:
    """
    Randomizes class mod part behavior.
    """

    def __init__(self):
        """
        Constructs a ClassModPartScrambler.
        """
        pass

    def scramble(self, rng : random.Random, changes : Changes):
        """
        Randomizes slot contents for all classmod parts.

        Args:
            rng:  Random number generator to use.
            changes:  Change manager to update and roll back UE objects.
        """
        # Grab all of the existing slot upgrades.
        upgrades = []
        for part in unrealsdk.find_all("ClassModPartDefinition"):
            if part.AttributeSlotUpgrades is None:
                continue
            upgrades.extend([copy.copy(upgrade)
                             for upgrade in part.AttributeSlotUpgrades])

        # Assign new upgrades.
        count = 0
        max_skill_boost = -6
        for part in unrealsdk.find_all("ClassModPartDefinition"):
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
            changes.set_obj(
                part, "AttributeSlotUpgrades", attribute_slot_upgrades)
            count += 1

    SUPPORTS: int = Game.BL2 | Game.AoDK | Game.TPS
    CONFIG_KEY: str = "classmod"
    OPTION: BoolOption = BoolOption(
        identifier="Scramble Classmod Part Purposes",
        description="Randomizes what each classmod part does",
        value=False,
        true_text="On",
        false_text="Off",
    )
    SCRAMBLES_ITEMS: bool = True
    SCRAMBLES_WEAPONS: bool = False


class RelicScrambler:
    """
    Randomizes relic bonuses.  Works only for BL2 and AoDK; Oz kits in TPS
    are a little too difficult to tackle.
    """
    
    def __init__(self):
        """
        Constructs a RelicScrambler.
        """
        pass

    def scramble(self, rng : random.Random, changes : Changes) -> None:
        """
        Randomizes relic bonuses.  Note that all relics are now assigned
        seven potential bonuses, of which at most four are enabled, so two
        instances of the same relic may be quite different from each other.

        Args:
            rng:  Random number generator.
            changes:  Change manager to update and roll back UE objects.
        """
        # Grab all the existing slot effects and UIStatList entries.
        ui_stats = {}
        slots = {}
        behaviors = {}
        for relic in unrealsdk.find_all("ArtifactDefinition"):
            if relic.UIStatList is None or relic.AttributeSlotEffects is None:
                continue
            for ui_stat in relic.UIStatList:
                if ui_stat.Attribute is None:
                    continue
                attribute_name = ui_stat.Attribute._path_name()
                if not ui_stat.ConstraintAttribute is None:
                    attribute_name += "/" + ui_stat.ConstraintAttribute._path_name()
                ui_stats[attribute_name] = copy.copy(ui_stat)
            for slot in relic.AttributeSlotEffects:
                if slot.AttributeToModify is None:
                    continue
                attribute_name = slot.AttributeToModify._path_name()
                if not slot.ConstraintAttribute is None:
                    attribute_name += "/" + slot.ConstraintAttribute._path_name()
                slots[attribute_name] = copy.copy(slot)
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
            part : unrealsdk.find_object("ItemPartListDefinition", partlist)
            for part, partlist in self.ENABLERS.items()
        }
        
        attribute_names = [name for name in ui_stats if name in slots]
        count = 0
        for relic in unrealsdk.find_all("ArtifactDefinition"):
            if relic.Name.startswith("Default__"):
                continue
            ui_stat_list = []
            attribute_slot_effects = []
            used = set()

            # Set a bonus for certain powerful relics.
            fullname = relic._path_name()
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
                ui_stat_list.append(ui_stats[attribute_name])
                slot = copy.copy(slots[attribute_name])
                slot.SlotName=f"Effect{index+1}"
                slot.PerGradeUpgrade = copy.copy(slot.PerGradeUpgrade)
                slot.PerGradeUpgrade.BaseValueScaleConstant=scale
                attribute_slot_effects.append(slot)
                if attribute_name in behaviors and behavior is None:
                    behavior = behaviors[attribute_name]
            changes.set_obj(relic,
                            "UIStatList",
                            ui_stat_list)
            changes.set_obj(relic,
                            "AttributeSlotEffects",
                            attribute_slot_effects)
            if (relic.BehaviorProviderDefinition is None) and (
                    not behavior is None):
                changes.set_obj_direct(relic,
                                       "BehaviorProviderDefinition",
                                       behavior)
            for part, partlist in partlists.items():
                changes.set_obj(relic, part, partlist)
            count += 1
                                 
        # Update the ItemPartListCollectionDefinition objects to cover all
        # effect options.
        count = 0
        for partlist in unrealsdk.find_all("ItemPartListCollectionDefinition"):
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
                weighted_parts = []
                for part_option in partdata.WeightedParts:
                    weight_template = copy.copy(part_option)
                    part_prefix = weight_template.Part._path_name()
                    if part_prefix[:-1].endswith("Effect"):
                        part_prefix = part_prefix[:-1]
                        for index in range(1,8):
                            try:
                                enabler = unrealsdk.find_object(
                                    "ArtifactPartDefinition",
                                    f"{part_prefix}{index}")
                                weight_data = copy.copy(weight_template)
                                weight_data.Part=enabler
                                weighted_parts.append(weight_data)
                            except ValueError:
                                # hiccup in search; skip
                                continue
                    else:
                        weighted_parts.append(weight_template)
                        
                changes.set_obj(partlist, partdata_attr,
                                unrealsdk.make_struct(
                                    "ItemCustomPartTypeData",
                                    bEnabled=True,
                                    WeightedParts=weighted_parts))
            count += 1
                                
    ENABLERS: dict[str, str] = {
        "AlphaParts" : "GD_Artifacts.Enable1st.PartList_EnableFirstEffect",
        "BetaParts" : "GD_Artifacts.Enable2nd.PartList_EnableSecondEffect",
        "GammaParts" : "GD_Artifacts.Enable3rd.PartList_EnableThirdEffect",
        "DeltaParts" : "GD_Artifacts.Enable4th.PartList_EnableFourthEffect",
    }
    
    PARTDATA_ATTRS: list[str] = [
        "AlphaPartData",
        "BetaPartData",
        "GammaPartData",
        "DeltaPartData",
        "EpsilonPartData",
        "ZetaPartData",
    ]

    SUPPORTS: int = Game.BL2 | Game.AoDK
    CONFIG_KEY: str = "relic"
    OPTION: BoolOption = BoolOption(
        identifier="Scramble Relic Bonuses",
        description="Randomizes relic bonuses",
        value=False,
        true_text="On",
        false_text="Off",
    )
    SCRAMBLES_ITEMS: bool = True
    SCRAMBLES_WEAPONS: bool = False


SCRAMBLERS = [
    ProjectileBehaviorScrambler,
    FiringModeScrambler,
    ShieldBonusScrambler,
    ClassModPartScrambler,
    RelicScrambler,
]

seed_option = HiddenOption[int](
    identifier="Seed",
    description="Random Number Generator seed value for current randomization.",
    value=0,
)

def reroll(option):
    """
    Calculates a new random-number generator seed.
    """
    seed_option.value = random.randrange(sys.maxsize)
    mod.save_settings()

reroll_option = ButtonOption(
    identifier = "Reroll",
    description = "Roll a new set of effect modifiers.",
    on_press=reroll,
)    

__player_name : str = None

# This gets called after all mods are loaded, but before the main menu is
# populated.  It's also called whenever the in-game menu pops up.
#@hook("WillowGame.WillowScrollingList:Refresh")
def post_main_menu(
        _obj: UObject,
        _args: WrappedStruct,
        _ret: Any,
        _func: BoundFunction,
) -> None:
    pass

# This gets called after the main menu is populated.
@hook("WillowGame.WillowScrollingListDataProviderFrontEnd:Populate")
def post_main_menu(
        _obj: UObject,
        _args: WrappedStruct,
        _ret: Any,
        _func: BoundFunction,
) -> None:
    global __changes
    global __player_name

    # Unwind any active changes.
    __changes.unwind()

    # Check if player name changed, and swap settings if it did.
    player_name : str = get_pc().PlayerPreferredCharacterName
    if player_name != __player_name:
        # Player changed.  Save old settings and change settings file.
        mod.save_settings()  # this might not be necessary
        mod.settings_file = SETTINGS_DIR / f"EffectRandomizer_{player_name}.json"
        mod.load_settings()
        __player_name = player_name

        if seed_option.value == 0:
            # Hack: simulate pushing the Reroll button.
            reroll(reroll_option)

def clean_items() -> None:
    """
    Regenerates internal caches for all known items.
    """
    for item in unrealsdk.find_all("WillowItem"):
        if item.Name.startswith("Default__"):
            continue
        item.InitializeFromDefinitionData(
            copy.copy(item.DefinitionData),
            item.Owner
        )

def clean_weapons() -> None:
    """
    Regenerates internal caches for all known weapons.
    """
    for weapon in unrealsdk.FindAll("WillowWeapon"):
        if weapon.Name.startswith("Default__"):
            continue
        weapon.InitializeFromDefinitionData(
            copy.copy(weapon.DefinitionData),
            weapon.Owner
        )
            
# This gets called when the player's skills are assembled at start of play.
#@hook("WillowGame.WillowPlayerController:WillowClientDisableLoadingMovie")
@hook("WillowGame.WillowPawn:PostBeginPlay")
def on_disable_loading_movie(
        caller: UObject,
        args: WrappedStruct,
        _ret: Any,
        _func: BoundFunction,
) -> type[Block] | None:
    """
    Randomize effects by calling each registered scrambler.

    Args:
        caller:  Object invoking hook
        args:  Argument bindings for the call
        _ret:  no clue, but hoping it controls if next func in chain is called
        _func:  Stack context for function call
    """
    global __changes    

    if caller.Class.Name != "WillowPlayerPawn":
        return
    
    rng = random.Random(seed_option.value)
    items_dirty = False
    weapons_dirty = False
    for scrambler_class in SCRAMBLERS:
        if not Game.get_current() in scrambler_class.SUPPORTS:
            continue
        # Generate a new rng for each scrambler so that patches to
        # one don't affect existing saves for the others.
        scrambler_rng = random.Random(rng.randrange(sys.maxsize))
        if scrambler_class.OPTION.value:
            scrambler = scrambler_class()
            scrambler.scramble(scrambler_rng, __changes)
            if scrambler.SCRAMBLES_ITEMS:
                items_dirty = True
            if scrambler.SCRAMBLES_WEAPONS:
                weapons_dirty = True

    __changes.commit()
    if items_dirty:
        clean_items()
    if weapons_dirty:
        clean_weapons()


def reset_game() -> None:
    """
    Undoes any patches and changes the savefile back to the default file on
    disable.
    """
    global __player_name
    global __changes

    # Unpatch.
    __changes.unwind()

    # Restore original config file.
    mod.settings_file = SETTINGS_DIR / "EffectRandomizer.json"
    mod.save_settings()
    __player_name = None  # do this to force reinit if mod is re-enabled later
    
# Make sure correct scramblers are in options.
__options : list[BaseOption] = [seed_option]
for scrambler_class in SCRAMBLERS:
    if not Game.get_current() in scrambler_class.SUPPORTS:
        continue
    __options.append(scrambler_class.OPTION)
__options.append(reroll_option)
    
mod = build_mod(
    options=__options,
    on_disable=reset_game,
)
