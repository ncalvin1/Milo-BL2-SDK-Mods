# Character hints describe skill and patch requirements for a player character.

import unrealsdk
from . import dependency
from typing import Callable, List, Self

class CharacterHint:
    """
    Stores any quirks about a character when using it with the PlayerRandomizer.
    """

    def __init__(self) -> None:
        self.dependencies = []
        self.suppressed_skills = []
        self.patches = []
        
    def add_dependency(self, dep : dependency.Dependency) -> Self:
        """
        Adds a skill dependency declaration to the CharacterHint.  See the
        Builder pattern.

        Args:
            dep:  Skill dependency to add.

        Returns:
            The CharacterHint, so that other builders can be chained.
        """
        self.dependencies.append(dep)
        return self
    
    def suppress(self, suppressed_skills : List[str]) -> Self:
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
              unpatch_function : Callable[None, None]) -> Self:
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


# Character-specific patch functions

def __patch_nth_degree() -> None:
    """
    Fix game freeze when The Nth Degree is boosted more than +8.
    """
    try:
        nth_bpd = unrealsdk.find_object(
            "BehaviorProviderDefinition",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TheNthDegree:BehaviorProviderDefinition_0"
        )
    except ValueError:
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


def __unpatch_nth_degree() -> None:
    """
    Undo the effects of patch_nth_degree.
    """
    try:
        nth_bpd = unrealsdk.find_object(
            "BehaviorProviderDefinition",
            "GD_Tulip_Mechromancer_Skills.EmbraceChaos.TheNthDegree:BehaviorProviderDefinition_0"
        )
    except ValueError:
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


# Character hint data for BL2 and TPS base+DLC characters.
HINT_MAP : dict[str, CharacterHint] = {
    # BL2
    "Axton" : CharacterHint().add_dependency(dependency.Dependency(
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
    
    "Gaige" : CharacterHint().add_dependency(dependency.Dependency(
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
    ])).add_dependency(dependency.Dependency(
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
    ])).patch(__patch_nth_degree, __unpatch_nth_degree),
    
    "Krieg" : CharacterHint().add_dependency(dependency.Dependency(
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
    ])).add_dependency(dependency.Dependency(
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
    ])).add_dependency(dependency.Dependency(
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
        "GD_Lilac_Skills_Bloodlust.Skills.BloodBathChild",
        "GD_Lilac_Skills_Bloodlust.Skills.BloodOverdriveChild",
        "GD_Lilac_Skills_Bloodlust.Skills.FuelTheBloodChild",
        "GD_Lilac_Skills_Hellborn.Skills.BurnBabyBurnChild",
    ]),
    
    "Maya" : CharacterHint().add_dependency(dependency.Dependency(
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
    ])),
    
    "Salvador" : CharacterHint().add_dependency(dependency.Dependency(
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
    
    "Zero" : CharacterHint().add_dependency(dependency.Dependency(
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
    "Athena" : CharacterHint().add_dependency(dependency.Dependency(
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
    ])).add_dependency(dependency.Dependency(
        "Bleeding"
    ).provided_by([
        "GD_Gladiator_Skills.Xiphos.Rend",
    ]).required_by([
        "GD_Gladiator_Skills.Xiphos.Bloodlust",
        "GD_Gladiator_Skills.Xiphos.Tear",
        "GD_Gladiator_Skills.Xiphos.FuryOfTheArena",
    ])).add_dependency(dependency.Dependency(
        "Storm Weaving"
    ).provided_by([
        "GD_Gladiator_Skills.CeraunicStorm.StormWeaving",
    ]).required_by([
        "GD_Gladiator_Skills.CeraunicStorm.ElementalBarrage",
    ])).add_dependency(dependency.Dependency(
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
    
    "Aurelia" : CharacterHint().add_dependency(dependency.Dependency(
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
    ])).add_dependency(dependency.Dependency(
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
    
    "Claptrap" : CharacterHint().add_dependency(dependency.Dependency(
        "VaultHunter.EXE"
    ).provided_by([
        "GD_Prototype_Skills_GBX.ActionSkill.Skill_VaultHunterEXE",
    ]).required_by([
        "GD_Prototype_Skills.ILoveYouGuys.ThroughThickAndThin",
    ])).suppress([
        "GD_Prototype_Skills.Boomtrap.DropTheHammer_Active",
        "GD_Prototype_Skills.Boomtrap.HyperionPunch_Active",
        "GD_Prototype_Skills.Boomtrap.HyperionPunch_Feedback",
        "GD_Prototype_Skills.Boomtrap.LoadNSplode_Feedback",
        "GD_Prototype_Skills.Boomtrap.OneLastThing_Active",
        "GD_Prototype_Skills.Boomtrap.Repulsive_Cooldown",
        "GD_Prototype_Skills.Boomtrap.StartWithABang_Active",
        "GD_Prototype_Skills.Fragmented.BlueShell_Active",
        "GD_Prototype_Skills.Fragmented.CryogenicExhaustManifold_Active",
        "GD_Prototype_Skills.Fragmented.FloatLikeABee_Active",
        "GD_Prototype_Skills.Fragmented.FragStacks_Active",
        "GD_Prototype_Skills.Fragmented.FuzzyLogic_Active",
        "GD_Prototype_Skills.Fragmented.FuzzyLogic_Feedback",
        "GD_Prototype_Skills.Fragmented.FuzzySurprise_Feedback",
        "GD_Prototype_Skills.Fragmented.SurprisedStabalize_Active",
        "GD_Prototype_Skills.ILoveYouGuys.BestBuds4Life_DownState",
        "GD_Prototype_Skills.ILoveYouGuys.BestBuds4Life_RewardBuff",
        "GD_Prototype_Skills.ILoveYouGuys.HighFivesGuys_Active",
        "GD_Prototype_Skills.ILoveYouGuys.HighFivesGuys_Solo",
        "GD_Prototype_Skills.ILoveYouGuys.HighFivesGuys_Team",
        "GD_Prototype_Skills.ILoveYouGuys.KickHimWhileHesDown_Active",
        "GD_Prototype_Skills.ILoveYouGuys.KickHimWhileHesUp_Active",
        "GD_Prototype_Skills.ILoveYouGuys.ManiacalLaughter_Active",
        "GD_Prototype_Skills.ILoveYouGuys.ThroughThickAndThin_Active",
    ]),
    
    "Jack" : CharacterHint().add_dependency(dependency.Dependency(
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
        "Quince_Doppel_FreeEnterprise.Skills.CompoundInterest_Active",
        "Quince_Doppel_FreeEnterprise.Skills.Incentives_Active",
        "Quince_Doppel_FreeEnterprise.Skills.LaserSurplus_Active",
        "Quince_Doppel_FreeEnterprise.Skills.Merger_Active",
        "Quince_Doppel_FreeEnterprise.Skills.Merger_Feedback",
        "Quince_Doppel_FreeEnterprise.Skills.MoneyIsPower_Feedback",
    ]),
    
    "Nisha" : CharacterHint().add_dependency(dependency.Dependency(
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
    ])).add_dependency(dependency.Dependency(
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
        "GD_Lawbringer_Skills.Riflewoman.TheUnforgiven_Secondary",
        "GD_Lawbringer_Skills.Riflewoman.Unchained_Effect",
        "GD_Lawbringer_Skills.Order_BloodOfTheGuilty_HealEffect",
        "GD_Lawbringer_Skills.Order.Discipline_Effect",
        "GD_Lawbringer_Skills.Order.Discipline_Feedback",
        "GD_Lawbringer_Skills.Order.DueProcess_Effect",
        "GD_Lawbringer_Skills.Order.Order_Stacks",
        "GD_Lawbringer_Skills.Order.TheThirdDegree_Effect",
        "GD_Lawbringer_Skills.Order.ThunderCrackdown_MeleeOverride",
        "GD_Lawbringer_Skills.FanTheHammer.MagnificentSix_Mainhand",
        "GD_Lawbringer_Skills.FanTheHammer.MagnificentSix_Offhand",
        "GD_Lawbringer_Skills.FanTheHammer.HellsCominWithMe_Effect",
        "GD_Lawbringer_Skills.FanTheHammer.Pickpocket_Feedback",
    ]),
    
    "Wilhelm" : CharacterHint().add_dependency(dependency.Dependency(
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
