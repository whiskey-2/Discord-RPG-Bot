from replit import db
import enum, random, sys
from copy import deepcopy

#Helper Functions


def str_to_class(classname):
  return getattr(sys.modules[__name__], classname)


def make_stats_enemy(min_level, bias):
  enemy_health = random.randint(min_level * 10, min_level * 20 * bias)
  enemy_attack = random.randint(min_level * 2, min_level * 4 * bias)
  enemy_defense = random.randint(min_level, min_level * 2 * bias)
  enemy_xp = random.randint(
    round((enemy_attack + enemy_defense + enemy_health) / (min_level * 2), 0),
    round((enemy_attack + enemy_defense + enemy_health) * bias / min_level, 0))
  enemy_gold = random.randint(min_level, (min_level * 10) + bias)
  return [enemy_health, enemy_attack, enemy_defense, enemy_xp, enemy_gold]


class GameMode(enum.IntEnum):
  ADVENTURE = 1
  BATTLE = 2
  AFK = 3
  TRANCE = 4

class Skill:
    def __init__(self, name, level, damage_attributes, damage_amount, cooldown, skill_type):
        self.name = name
        self.level = level
        self.damage_attributes = damage_attributes
        self.damage_amount = damage_amount
        self.cooldown = cooldown
        self.skill_type = skill_type
        self.debuffs = []

    def __str__(self):
        return f"{self.name} (Level {self.level}): {self.damage_amount} {self.damage_attributes} damage with a cooldown of {self.cooldown} turns. Type: {self.skill_type}. Debuffs: {', '.join(self.debuffs)}"


class Actor:

  def __init__(self, name, hp, max_hp, attack, defense, level, xp, gold):
    self.name = name
    self.hp = hp
    self.max_hp = max_hp
    self.attack = attack
    self.defense = defense
    self.level = level
    self.xp = xp
    self.gold = gold

  def fight(self, other):
    defense = min(other.defense, 19)  # cap defense value
    chance_to_hit = random.randint(0, 20 - defense)
    if chance_to_hit:

      damage = self.attack
    else:
      damage = 0

    other.hp -= damage

    return (self.attack, other.hp <= 0)  #(damage, fatal)


class Character(Actor):

  level_cap = 999

  def __init__(self, name, hp, max_hp, attack, defense, mana, max_mana,
               stamina, max_stamina, xp, level, gold, inventory, mode,
               battling, user_id):
    super().__init__(name, hp, max_hp, attack, defense, xp, gold)
    self.name = name
    self.hp = hp
    self.max_hp = max_hp
    self.mana = mana
    self.max_mana = max_mana
    self.stamina = stamina
    self.max_stamina = max_stamina
    self.level = level

    self.skills = []

    self.inventory = inventory

    self.mode = mode

    if battling != None:
      enemy_class = str_to_class(battling["enemy"])
      self.battling = enemy_class()
      self.battling.rehydrate(**battling)
    else:
      self.battling = None

    self.user_id = user_id

  def save_to_db(self):
    character_dict = deepcopy(vars(self))
    if self.battling != None:
      character_dict["battling"] = deepcopy(vars(self.battling))

      db["characters"][self.user_id] = character_dict

  def create_skill(self, name, level, damage_attributes, damage_amount, cooldown, skill_type):
    if skill_type == "intent" and self.level < 200:
      print("You must be at least level 200 to create an intent skill.")
      return

    skill = Skill(name, level, damage_attributes, damage_amount, cooldown, skill_type)
    debuff_type = random.choice(["health", "mana", "stamina"])
    debuff_amount = random.randint(1, 100)
    skill.debuffs.append(f"-{debuff_amount} {debuff_type}")
    self.skills.append(skill)
  
  def hunt(self):
    # Generate random enemy to fight
    while True:
      enemy_type = random.choice(Enemy.__subclasses__())

      if enemy_type.min_level <= self.level:
        break

      enemy = enemy_type()

      # Enter battle mode
      self.mode = GameMode.BATTLE
      self.battling = enemy

      # Save changes to db after state change
      self.save_to_db()

      return enemy

    def fight(self, enemy):
      outcome = super().fight(enemy)

      # Save changes to db after state change
      self.save_to_db()

      return outcome

    def flee(self, enemy):
      if random.randint(0, 1 + self.defense):  # flee unscathed
        damage = 0
      else:  # take damage
        damage = enemy.attack / 2
        self.hp -= damage

      # Exit battle mode
      self.battling = None
      self.mode = GameMode.ADVENTURE

      # Save to db after state change
      self.save_to_db()

      return (damage, self.hp <= 0)  #(damage, killed)

    def defeat(self, enemy):
      if self.level < self.level_cap:  # no more XP after hitting level cap
        self.xp += enemy.xp

      self.gold += enemy.gold  # loot enemy

      # Exit battle mode
      self.battling = None
      self.mode = GameMode.ADVENTURE

      # Check if ready to level up after earning XP
      ready, _ = self.ready_to_level_up()

      # Save to db after state change
      self.save_to_db()

      return (enemy.xp, enemy.gold, ready)

    def ready_to_level_up(self):
      if self.level == self.level_cap:  # zero values if we've ready the level cap
        return (False, 0)

      xp_needed = (self.level) * 10
      return (self.xp >= xp_needed, xp_needed - self.xp)  #(ready, XP needed)

    def level_up(self, increase):
      ready, _ = self.ready_to_level_up()
      if not ready:
        return (False, self.level)  # (not leveled up, current level)

      self.level += 1  # increase level
      setattr(self, increase,
              getattr(self, increase) + 1)  # increase chosen stat

      self.hp = self.max_hp  #refill HP

      # Save to db after state change
      self.save_to_db()

      return (True, self.level)  # (leveled up, new level)

    def die(self, player_id):
      if self.user_id in db["characters"].keys():
        del db["characters"][self.user_id]


class Enemy(Actor):

  def __init__(self, name, max_hp, attack, defense, xp, gold):
    super().__init__(name, max_hp, attack, defense, xp, gold)

    self.enemy = self.__class__.__name__

  def rehydrate(self, name, hp, max_hp, attack, defense, xp, gold, enemy):
    self.name = name
    self.hp = hp
    self.max_hp = max_hp
    self.attack = attack
    self.defense = defense
    self.xp = xp
    self.gold = gold


class GiantRat(Enemy):
  min_level = 1
  bias = 1
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Giant Rat", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class GiantSpider(Enemy):
  min_level = 3
  bias = 2
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Giant Spider", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Bat(Enemy):
  min_level = 5
  bias = 3
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Bat", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Skeleton(Enemy):
  min_level = 10
  bias = 5
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Skeleton", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Wolf(Enemy):
  min_level = 15
  bias = 8
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Wolf", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Ogre(Enemy):
  min_level = 25
  bias = 10
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Ogre", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Living_Armor(Enemy):
  min_level = 30
  bias = 15
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Living Armor", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Bear(Enemy):
  min_level = 40
  bias = 25
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Bear", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold


class Drake(Enemy):
  min_level = 80
  bias = 40
  stat = make_stats_enemy(min_level, bias)

  def __init__(self):
    super().__init__("Lesser Drake", self.stat[0], self.stat[1], self.stat[2],
                     self.stat[3],
                     self.stat[4])  # HP, attack, defense, XP, gold
