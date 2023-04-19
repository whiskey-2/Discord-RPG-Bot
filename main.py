import os, discord
from discord.ext import commands

from replit import db
from game import *

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

#Helper Functions


def load_character(user_id):
  return Character(**db["characters"][str(user_id)])


MODE_COLOR = {
  GameMode.BATTLE: 0xDC143C,
  GameMode.ADVENTURE: 0x005EB8,
}


def status_embed(ctx, character):

  # Current mode
  if character.mode == GameMode.BATTLE:
    mode_text = f"Currently battling a {character.battling.name}."
  elif character.mode == GameMode.ADVENTURE:
    mode_text = "Currently adventuring."

  # Create embed with description as current mode
  embed = discord.Embed(title=f"{character.name} status",
                        description=mode_text,
                        color=MODE_COLOR[character.mode])
  embed.set_author(name=ctx.author.display_name,
                   icon_url=ctx.author.avatar)

  # Stats field
  _, xp_needed = character.ready_to_level_up()

  embed.add_field(name="Stats", value=f"""
**HP:**    {character.hp}/{character.max_hp}
**ATTACK:**   {character.attack}
**DEFENSE:**   {character.defense}
**MANA:**  {character.mana}
**STAMINA** {character.stamina}
**LEVEL:** {character.level}
**XP:**    {character.xp}/{character.xp+xp_needed}
    """, inline=True)

  # Inventory field
  inventory_text = f"Gold: {character.gold}\n"
  if character.inventory:
    inventory_text += "\n".join(character.inventory)

  embed.add_field(name="Inventory", value=inventory_text, inline=True)

  return embed


#Bot Starts
@bot.event
async def on_ready():
  print(f"{bot.user} has connected to Discord!")


# Commands
@bot.command(name="create", help="Create a character.")
async def create(ctx, name=None):
  user_id = ctx.message.author.id

  # if no name is specified, use the creator's nickname
  if not name:
    name = ctx.message.author.name

    # create characters dictionary if it does not exist
  if "characters" not in db.keys():
    db["characters"] = {}

  # only create a new character if the user does not already have one
  if user_id not in db["characters"] or not db["characters"][user_id]:
    character = Character(
      **{
        "name": name,
        "hp": 10,
        "max_hp": 10,
        "attack": 2,
        "defense": 1,
        "mana": 0,
        "max_mana": 10,
        "stamina": 8,
        "max_stamina": 8,
        "xp": 0,
        "level": 1,
        "gold": 0,
        "inventory": [],
        "mode": GameMode.ADVENTURE,
        "battling": None,
        "user_id": user_id
      })
    character.save_to_db()
    await ctx.message.reply(
      f"New level 1 character created: {name}. Enter `!status` to see your stats."
    )
  else:
    await ctx.message.reply("You have already created your character.")


@bot.command(name="status", help="Get information about your character.")
async def status(ctx):
  character = load_character(ctx.message.author.id)

  embed = status_embed(ctx, character)
  await ctx.message.reply(embed=embed)


@bot.command(name="hunt", help="Look for an enemy to fight.")
async def hunt(ctx):
  character = load_character(ctx.message.author.id)

  if character.mode != GameMode.ADVENTURE:
    await ctx.message.reply("Can only call this command outside of battle!")
    return

  enemy = character.hunt()

  # Send reply
  await ctx.message.reply(
    f"You encounter a {enemy.name}. Do you `!fight` or `!flee`?")


bot.run(DISCORD_TOKEN)
