#H1 Character Randomizer
An overengineered redesign and expansion of Abahbob's elegant Cross-Class Skill
Randomizer, this mod scrambles a player character's skills and class mods.

#H2 Features
  - Change or randomize the action skill.
  - Choose which characters you want to borrow skills from.
  - Select how densely you want the skill trees populated.

#H2 Notes
  - I have no idea if this works in multiplayer, but I would assume it doesn't.
      If it does, all players will need to start from the same seed, which means
      you'll need to edit the mod's settings.json on each game installation.
  - Action skill graphics and user interfaces are not updated.  Characters using
      Gunzerk will notice the offhand weapon is not visible, but it still fires
      projectiles.  Characters using Decepti0n will miss part of Zer0's HUD,
      and Zer0 characters using another action skill may notice his HUD behaving
      strangely.  Characters whose original action skills can't normally be
      terminated early will notice that they can't pull back turrets, Deathtrap,
      the Aspis shield, or Digi-Jacks early to reduce cooldown.  (And, yes,
      Gaige breathing like Salvador when she's gunzerking is one of the more
      disturbing things I've encountered in a game.)
  - The mod may hang if it runs out of skills to choose for a character.
      If you limit Zer0 to just his own skills, and then set the skill density
      higher than 55% (30 expected skills), skill selection will never complete.
  - The mod does not work with custom characters as anything other than the
      main character.  It may work with custom characters as the main character,
      but there are no guarantees.  In particular, skills that have been
      cannibalized to make other skills work (such as Maya's Cloud Kill in the
      Lilith mod) will probably malfunction or even crash the game.  Back up
      your game save, try 'em, and see!
    - Custom character text mods must have the Offline checkbox selected in
        BLCMM, or COM randomization will tend to crash.
    - After loading the custom character mod, disable and re-enable the
        Character Randomizer to pick up the new changes.  Verify by opening
	the Options -> Mods -> Skill Sources menu and checking that the
	custom character's name is in the list.
    - Known successes:
      - Roland works unchanged.  Axton's extra turret skills appear to stack
          on Roland's turret without issue.
      - Lilith works, but only if "GD_Siren_Skills.Cataclysm.BlightPhoenix":5
          (which the mod turns into Lilith's Phoenix skill) is manually added to
	  the SkillPool.wanted_skills sequence (__init__.py:1578).
