# Classes and methods for representing character skill sets.

import random
import unrealsdk
from mods_base import ENGINE
from . import dependency, skills, characters
from typing import Set, List, Dict, Union

class Branch:
    """
    Represents one of the three skill trees for a character.
    """

    @classmethod
    def from_branch(cls, branch: unrealsdk.unreal.UObject) ->' Branch':
        """
        Creates a Branch from a non-action SkillTreeBranchDefinition.

        Args:
            branch:  The SkillTreeBranchDefinition to base this Branch on.

        Returns:
            A new Branch object representing the SkillTreeBranchDefinition.
        """
        new_branch = Branch()
        new_branch.full_name = branch._path_name()
        new_branch.layout_name = branch.Layout._path_name()
        for tier in branch.Tiers:
            new_branch.skills.append([skill._path_name() for skill in tier.Skills if not skill is None])
            new_branch.points_to_unlock.append(tier.PointsToUnlockNextTier)
        for tier in branch.Layout.Tiers:
            new_branch.layout.append([flag for flag in tier.bCellIsOccupied])
        return new_branch

    @classmethod
    def from_other(cls, other: 'Branch') -> 'Branch':
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

    def prepare(self, idx : int, expected_skills : int, skill_weights : List[int]):
        """
        Set up branch for skill population.

        Args:
            idx:  0 if green/left, 1 if blue/center, 2 if red/right
            expected_skills:  Number of skills to populate branch with.  0-18,
                where BL2 averages 11 and TPS averages 12.
            skill_density:  Percentage of skills to fill in.  BL2 characters
                average a 60% skill density, while TPS characters average 65%.
            skill_weights:  Array of selection weights for each skill in pool.
        """
        self.idx = idx
        self.slots_left = 18
        self.expected_skills = expected_skills
        self.skill_count = 0
        self.skill_weights = skill_weights
        self.total_weight = sum(skill_weights)

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
        ENGINE.GamePlayers[0].Actor.ConsoleCommand(command)
        command = f"set SkillTreeBranchLayoutDefinition'{self.layout_name}' Tiers ("
        command += ",".join(["(bCellIsOccupied=(" + ",".join([
            str(skill_present) for skill_present in tier_layout])
                             + "))" for tier_layout in self.layout]) + ")"
        ENGINE.GamePlayers[0].Actor.ConsoleCommand(command)

PRIORITY_WEIGHT : int = 1000  # overdue cheats appear ASAP
ACTION_WEIGHT : int = 3  # skills tied to Action Skill appear +200% of time
THEME_WEIGHT : int = 5   # skills tied to dep appear +400% in that branch only
        
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

    def add_skills(self, skill_list : List[skills.Skill]) -> None:
        """
        Add skills to the SkillPool.

        Args:
            skill_list:  Skills to add to the SkillPool.
        """
        for skill in skill_list:
            self.skills[skill.full_name] = skill

    def add_dependency(self, dep : dependency.Dependency) -> None:
        """
        Add a dependency to the SkillPool.

        Args:
            dep:  The Dependency to add.
        """
        for skill_name in dep.providers:
            self.dependencies[skill_name] = dep

    def mark_used(self, skill: skills.Skill, hidden_skills: str, branch_idx: int) -> skills.Skill:
        """
        Consume a skill from the skill pool.

        Args:
            skill:  The Skill to remove from the pool.
            hidden_skills:  If "All", allow any skill.  If "Misdocumented",
                allow skills with unsatisfied "Wanted" dependencies.  If "None",
                allow only skills with fully-satisfied dependencies.
            branch_idx:  Index of branch this will populate, or -1 if action

        Returns:
            The removed Skill.
        """

        if skill.full_name in self.dependencies:
            dep = self.dependencies[skill.full_name]
            # Boost chances of associated skills in the current branch,
            # and zero them in the other branches.
            for idx in range(len(self.new_branches)):
                branch = self.new_branches[idx]
                themed = dep.providers + dep.dependers
                if hidden_skills == "None":
                    themed.extend(dep.wanters)
                for themed_skill in themed:
                    try:
                        skill_idx = self.skill_order.index(themed_skill)
                        branch.total_weight -= branch.skill_weights[skill_idx]
                        if branch_idx < 0:
                            branch.skill_weights[skill_idx] *= ACTION_WEIGHT
                        elif idx == branch_idx:
                            branch.skill_weights[skill_idx] *= THEME_WEIGHT
                        else:
                            branch.skill_weights[skill_idx] = 0
                        branch.total_weight += branch.skill_weights[skill_idx]
                    except ValueError:
                        pass
                        
            # Save any 'free' skills granted by the initial one.
            self.extra_skills.extend(dep.extra_skills)

            # Keep the other providers from retriggering this dependency
            for skill_name in dep.providers:
                del self.dependencies[skill_name]

        # Keep skill from being picked twice.
        try:
            skill_idx = self.skill_order.index(skill.full_name)
            for branch in self.new_branches:
                branch.skill_weights[skill_idx] = 0

            # Also add skill to potential class_mod_skills.
            if skill.is_upgradable():
                self.class_mod_skills.append(skill)
        except ValueError:
            # Probably the action skill.
            pass     
        
        return skill

    def get_next_skill(self, hidden_skills, branch_idx: int) -> skills.Skill:
        """
        Select a random skill from the skill pool.

        Args:
            hidden_skills:  If "All", allow any skill.  If "Misdocumented",
                allow skills with unsatisfied "Wanted" dependencies.  If "None",
                allow only skills with fully-satisfied dependencies.
            branch_idx:  Index of branch this will populate

        Returns:
            A random Skill.
        """
        while True:
            skill_name = self.rng.choices(
                self.skill_order,
                self.new_branches[branch_idx].skill_weights
            )[0]
            if hidden_skills == "All":
                return self.mark_used(self.skills[skill_name],
                                      hidden_skills,
                                      branch_idx)
            for dep in self.dependencies.values():
                if ((hidden_skills == "None" and
                     skill_name in dep.wanters) or
                    skill_name in dep.dependers):
                    # Since the skill is missing a dependency, pick one of the
                    # dependencies instead.
                    skill_name = self.rng.choice(dep.providers)
                    if skill_name in self.skills:
                        return self.mark_used(self.skills[skill_name],
                                              hidden_skills,
                                              branch_idx)
                    # Dependency is not in the skill pool.  It's probably an
                    # action skill for a different character.  Skip.
                    break
            else:
                return self.mark_used(self.skills[skill_name],
                                      hidden_skills,
                                      branch_idx)

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
                       skill_tree : unrealsdk.unreal.UObject,
                       enabled_sources : set[str],
                       hidden_skills : str,
                       action_skill : str,
                       skill_density : float,
                       randomize_tiers : bool,
                       cheats : Dict[str, int]) -> None:
        """
        Generate a random skill set for a character.

        Args:
            skill_tree:  The action SkillTreeBranchDefinition for the character.
            enabled_sources:  Names of characters whose skills may be used.
            hidden_skills:  If "none", follow dependencies strictly.  If
                "misdocumented", ignore "wanted" dependencies.  If "all",
                ignore all dependencies.
            action_skill:  If "Default", use the character's normal action
                skill.  If "Random", choose a random action skill.  If a
                character name, use that character's action skill.
            skill_density:  Amount of skill tree to populate.  34% represents
                a single skill in each tier, 100% represents a completely
                full tree, and 64% represents the average Borderlands tree.
            randomize_tiers:  If false, set the skill points required to reach
                the next tier at the maximum cost of any skill in that tier.
                If true, set the skill points to a random amount from 1 to
                two-thirds the total cost of all skills in that tier.
            cheats:  A map of skill to the maximum tier it should appear in.
        """
        self.current_char_class = characters.class_from_obj_name(
            skill_tree.Root._path_name())

        current_char = None
        for char in enabled_sources:
            source_char = characters.Character.from_name(char)
            if source_char is None:
                unrealsdk.logging.warning(f"Ignoring unknown skill source {char}")
                continue
            self.add_skills(source_char.pure_skills)
            if hidden_skills != "none":
                self.add_skills(source_char.misdocumented_skills)
                if hidden_skills == "all":
                    self.add_skills(source_char.suppressed_skills)
            for dep in source_char.dependencies:
                self.add_dependency(dep)
            if source_char.name == self.current_char_class:
                current_char = source_char

        # Sort the current skill list for reproducibility.
        self.skill_order = list(self.skills)
        self.skill_order.sort()

        if action_skill == "Default":
            if current_char is None:
                unrealsdk.logging.warning("Default is not a currently-enabled class.  Choosing a random action skill instead.")
                desired_char = characters.Character.from_name(self.rng.choice(
                    list(enabled_sources)))
            else:
                desired_char = current_char
        elif action_skill == "Random":
            desired_char = characters.Character.from_name(self.rng.choice(
                list(enabled_sources)))
        else:
            desired_char = characters.Character.from_name(action_skill)
            if desired_char is None:
                unrealsdk.logging.warning(f"Desired class {action_skill} is not installed.  Choosing a random action skill instead.")
                desired_char = characters.Character.from_name(self.rng.choice(
                    list(enabled_sources)))
            elif not desired_char.character_name in enabled_sources:
                unrealsdk.logging.warning(f"{desired_char.character_name} is not a currently-enabled class.  Choosing a random action skill instead.")
                desired_char = characters.Character.from_name(self.rng.choice(
                    list(enabled_sources)))

        if len(self.skill_order) * 100.0 < 54.0 * skill_density:
            skill_density = 100.0 * float(len(self.skill_order)) / 54.0
                
        self.original_branches = []
        self.new_branches = []
        branch_idx = 0
        expected_skills = 54.0 * skill_density / 100.0
        for branch in skill_tree.Root.Children:
            old_branch = Branch.from_branch(branch)
            new_branch = Branch.from_other(old_branch)
            new_branch.prepare(branch_idx,
                               int(expected_skills / (3.0 - branch_idx)),
                               [1.0] * len(self.skill_order))
            expected_skills -= new_branch.expected_skills
            self.original_branches.append(old_branch)
            self.new_branches.append(new_branch)
            branch_idx += 1

        # Sadly, even though this takes a list, only the first action skill
        # is used.
        skill_tree.Root.Tiers[0].Skills = [
            self.mark_used(desired_char.action_skill,
                           hidden_skills,
                           -1).skill_def,
        ]
            
        for tier in range(0,6):
            for branch in self.new_branches:
                self.randomize_branch_tier(branch,
                                           tier,
                                           randomize_tiers,
                                           hidden_skills,
                                           cheats)

        for branch in self.new_branches:
            branch.patch()

    def randomize_branch_tier(self,
                              branch : Branch,
                              tier : int,
                              randomize_tiers : bool,
                              hidden_skills : str,
                              cheats : Dict[str, int],
                              ) -> None:
        """
        Randomize a tier in one of the three skill branches for a character.
        Helper function for randomize_tree().

        Args:
            branch:  A non-action SkillTreeBranchDefinition for the character.
            tier:  The level of the branch to fill in, 0-5.
            randomize_tiers:  If false, set the skill points required to reach
                the next tier at the maximum cost of any skill in that tier.
                If true, set the skill points to a random amount from 1 to
                two-thirds the total cost of all skills in that tier.
            hidden_skills:  If "none", follow dependencies strictly.  If
                "misdocumented", ignore "wanted" dependencies.  If "all",
                ignore all dependencies.
            cheats:  A map of skill name to the maximum tier that skill should
                appear in.
        """
        # Update weights for cheats.
        # If there are N branch-tiers left for a cheat, it should have a 1/N
        # chance of being picked for this branch-tier.  Note that dependencies
        # can restrict remaining branch-tiers to a single branch.  If a cheat
        # is overdue, chance rises to 1.0.
        for (cheat_name, cheat_tier) in cheats.items():
            try:
                cheat_idx = self.skill_order.index(cheat_name)
                if branch.skill_weights[cheat_idx] == 0:
                    # Either already selected or has a dep in another branch.
                    continue
                if cheat_tier < tier:
                    # Overdue to be placed.
                    branch.skill_weights[cheat_idx] = branch.total_weight * PRIORITY_WEIGHT
                    continue
                for other_branch in self.new_branches:
                    if other_branch.skill_weights[cheat_idx] == 0:
                        # Dependency in same branch.
                        if cheat_tier == tier:
                            branch.skill_weights[cheat_idx] = branch.total_weight * PRIORITY_WEIGHT
                        else:
                            branch.skill_weights[cheat_idx] = branch.total_weight / (cheat_tier - tier)
                else:
                    # No dependency.
                    if tier == cheat_tier and branch.idx == 2:
                        branch.skill_weights[cheat_idx] = branch.total_weight * PRIORITY_WEIGHT
                    else:
                        branch.skill_weights[cheat_idx] = branch.total_weight / (3 * (cheat_tier - tier) + 2 - branch.idx)
            except ValueError:
                unrealsdk.logging.error(f"Desired skill {cheat_name} is not in the pool.")
        
        # Choose slot count based on remaining density.  We want a wider set
        # of skills at the base of the tree, narrowing to the tip, with no
        # empty tiers blocking skill progression.
        expected_density : float = float(
            branch.expected_skills - branch.skill_count
        ) / float(branch.slots_left)
        skill_count : int = 0
        if expected_density > 0.99:
            skill_count = 3
        elif expected_density > 0.66:
            skill_count = 3 if (3 * (expected_density - 0.66) > self.rng.random()) else 2
        elif expected_density > 0.33:
            skill_count = 2 if (3 * (expected_density - 0.33) > self.rng.random()) else 1
        elif expected_density > 0:
            skill_count = 1
        tier_layout : List[bool] = [
            skill_count > 1, skill_count & 1 > 0, skill_count > 1
        ]

        max_points : int = 0
        total_points : int = 0
        tier_skills : List[str] = []
        for idx in range(skill_count):
            skill = self.get_next_skill(hidden_skills, branch.idx)
            max_points = max(max_points, skill.max_grade)
            total_points += skill.max_grade
            tier_skills.append(skill.full_name)

        branch.layout[tier] = tier_layout
        branch.skills[tier] = tier_skills
        if randomize_tiers:
            branch.points_to_unlock[tier] = self.rng.randint(
                1, max(1, int(0.66 * total_points)))
        else:
            branch.points_to_unlock[tier] = max_points
        branch.skill_count += skill_count
        branch.slots_left -= 3

        if tier == 5:
            branch.skills[5].extend(self.get_extra_skills())


    def unrandomize_tree(self) -> None:
        """
        Restore the game engine to the original skill tree.
        """
        if not self.original_branches is None:
            for branch in self.original_branches:
                branch.patch()
        self.original_branches = None

    def get_class_mod_skills(self) -> List[skills.Skill]:
        """
        Retrieve all skills that should be considered for the random player's
        class mods.
        
        Returns:
            A list of passive, upgradable skills from the random player's skill
                tree.
        """
        return self.class_mod_skills

    def get_current_char(self) -> characters.Character:
        """
        Retrieves the player class for the random player.

        Returns:
            The Character corresponding to the random player.
        """
        return self.current_char_class
