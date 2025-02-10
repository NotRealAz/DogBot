import asyncio
from typing import List, Tuple
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import os
from dotenv import load_dotenv
import aiohttp
import random
import json
import time

# local files
from utils.database import DB
from utils.ach import Achievement

# Load environment variables
load_dotenv()

# Server config
db = DB()

# Load dog json from file, important step
try:
    with open("config/dogs.json") as f:
        dog_data = json.load(f)
        dogs = dog_data["dogs"]
except FileNotFoundError:
    print("Error: dogs.json not found!")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error parsing dogs.json: {e}")
    exit(1)

# Initialize variables
guild_dog_states = {}

# intents and bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Needed for slash commands
bot = commands.Bot(command_prefix='!dog=', intents=intents)

EMOJI_ID = "<:staring_dog:1285440635117113344>"
PROCESSED_IDS_FILE = "databases/processed_ids.json"

# Load processed message IDs from file
def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        try:
            with open(PROCESSED_IDS_FILE, "r") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return set(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error loading JSON file: {e}")
    return set()

# Save processed message IDs to file
def save_processed_ids(processed_ids):
    with open(PROCESSED_IDS_FILE, "w") as file:
        json.dump(list(processed_ids), file)

# Initialize the processed message IDs
processed_message_ids = load_processed_ids()

@bot.event
async def on_ready():
    """Triggered when the bot is ready."""
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name=f"in {len(bot.guilds):,} servers!")
    )
    print(f"Logged in as {bot.user.name}")

    if not send_dog_message.is_running():
        send_dog_message.start()

    await bot.tree.sync()  # Sync commands


def get_random_dog():
    """Helper function to get a random dog based on chance."""
    total_chance = sum(dog["chance"] for dog in dogs)
    roll = random.uniform(0, total_chance)
    upto = 0
    for dog in dogs:
        if upto + dog["chance"] >= roll:
            return dog
        upto += dog["chance"]

def ClaimAch(gid: int, uid: int, id: str, Callback: callable):
    achievements = Achievement.Retrieve(gid, uid)
    if not any(ach['ID'] == id for ach in achievements):
        Achievement.Claim(gid, uid, id)
        Callback()

@tasks.loop(minutes=random.randint(1, 5))
async def send_dog_message():
    """Periodically sends a message to spawn a random dog in configured channels."""
    for guild in bot.guilds:
        try:
            # Get the list of channels where dogs can spawn for this guild
            dog_channels = db.list_server_channels(guild.id)

            for channel_id in dog_channels:
                channel = bot.get_channel(channel_id)
                if channel is None:
                    print(f"Skipping guild {guild.name}: Invalid channel {channel_id}.")
                    continue

                permissions = channel.permissions_for(guild.me)
                if not permissions.send_messages or not permissions.view_channel:
                    print(f"Removing channel {channel_id} from guild {guild.id} because the bot can't send messages or view the channel.")
                    try:
                        db.remove_channel(channel_id, guild.id)
                    except Exception as e:
                        print(f"Error removing channel {channel_id} from database: {e}")
                    continue

                guild_state = guild_dog_states.get(guild.id, {})
                channel_state = guild_state.get(channel_id, {"current_dog": None, "dog_message": None})

                if channel_state["current_dog"] is not None:
                    continue  # Skip if a dog has already spawned in this channel

                current_dog = get_random_dog()
                if os.path.exists(current_dog['image']):
                    file = discord.File(current_dog['image'], filename=os.path.basename(current_dog['image']))
                    dog_message = await channel.send(
                          f"A {current_dog['emoji']} {current_dog['name']} has spawned! Type 'dog' to catch it!",
                          file=file
                    )
                else:
                    print(f"Error: File {current_dog['image']} not found!")
                    return

                # Save the current dog and message for this channel
                if guild.id not in guild_dog_states:
                    guild_dog_states[guild.id] = {}
                guild_dog_states[guild.id][channel_id] = {
                    "current_dog": current_dog,
                    "dog_message": dog_message
                }

        except Exception as e:
            print(f"Error spawning dog in {guild.name}: {e}")

@bot.event
async def on_message(message):
    """Handles dog catching logic and custom phrases."""
    if isinstance(message.channel, discord.DMChannel) or message.author == bot.user:
        return

    guild_state = guild_dog_states.get(message.guild.id, {})
    channel_state = guild_state.get(message.channel.id, {"current_dog": None, "dog_message": None})
    current_dog = channel_state["current_dog"]
    dog_message = channel_state["dog_message"]

    if message.content.lower() == 'dog' and current_dog is not None:
        if message.channel.id == dog_message.channel.id:
            spawn_time = dog_message.created_at.timestamp()
            catch_time = time.time()
            elapsed_time = catch_time - spawn_time

            await dog_message.delete()

            embed = discord.Embed(title="Dog!")
            embed.set_image(url="attachment://Dog.png")

            if current_dog['name'] == "eboy":
                embedC = discord.Embed(
                    color=discord.Color(0x265526),
                    title="professional gamer",
                    description="touch grass please <a:typing:1336980116554645534>"
                )
                embedC.set_author(
                    name="Achievement Unlocked!",
                    icon_url="attachment://achievements.png"
                )
                embedC.set_footer(text=f"Unlocked by {message.author.name}")

                async def callback():
                    try:
                        await message.channel.send(embed=embedC, file=discord.File('media/achievements.png'))
                    except discord.HTTPException as e:
                        print(f"Error sending achievement: {e}")

                # Claim the achievement
                ClaimAch(
                    message.guild.id,
                    message.author.id,
                    "professional_gamer",
                    lambda: asyncio.create_task(callback())
                )
            
            if current_dog['name'] == "sparkle dog":
                embedC = discord.Embed(
                    color=discord.Color(0x265526),
                    title="pretty scene girl!!",
                    description="you know this pretty scene girl"
                )
                embedC.set_author(
                    name="Achievement Unlocked!",
                    icon_url="attachment://achievements.png"
                )
                embedC.set_footer(text=f"Unlocked by {message.author.name}")

                async def callback():
                    try:
                        await message.channel.send(embed=embedC, file=discord.File('media/achievements.png'))
                    except discord.HTTPException as e:
                        print(f"Error sending achievement: {e}")

                # Claim the achievement
                ClaimAch(
                    message.guild.id,
                    message.author.id,
                    "pretty_scene_girl",
                    lambda: asyncio.create_task(callback())
                )

            if elapsed_time < 5:
                embed = discord.Embed(
                    color=discord.Color(0x265526),
                    title="fast dog",
                    description="caught a dog in under 5 seconds! speedy, are we?"
                )
                embed.set_author(
                    name="Achievement Unlocked!",
                    icon_url="attachment://achievements.png"
                )
                embed.set_footer(text=f"Unlocked by {message.author.name}")

                async def callback():
                    try:
                        await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
                    except discord.HTTPException as e:
                        print(f"Error sending achievement: {e}")

                # Claim the achievement
                ClaimAch(
                    message.guild.id,
                    message.author.id,
                    "fast_dog",
                    lambda: asyncio.create_task(callback())
                )


            db.add_dog(current_dog['name'], message.author.id, message.guild.id, 1)

            dogs = db.list_dogs(message.author.id, message.guild.id)
            amount = next((dog[1] for dog in dogs if dog[0] == current_dog['name']), 0)

            if amount >= 1000:
                embed = discord.Embed(
                    color=discord.Color(0x265526),
                    title="ZOO WEE MAMA",
                    description="gimme some of those"
                )
                embed.set_author(
                    name="Achievement Unlocked!",
                    icon_url="attachment://achievements.png"
                )
                embed.set_footer(text=f"Unlocked by {message.author.name}")

                async def callback():
                    try:
                        await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
                    except discord.HTTPException as e:
                        print(f"Error sending achievement: {e}")

                # Claim the achievement
                ClaimAch(
                    message.guild.id,
                    message.author.id,
                    "ZOO_WEE_MAMA",
                    lambda: asyncio.create_task(callback())
                )


            await message.channel.send(f'{message.author.name} caught {current_dog["emoji"]} {current_dog["name"]} dog!!!\n'
                                       f'You have now caught {amount} dogs of that type!!!\n'
                                       f'This fella was caught in {int(elapsed_time)} seconds!!!')

            # Clear the state for this channel
            guild_dog_states[message.guild.id][message.channel.id] = {"current_dog": None, "dog_message": None}
            

    elif message.content.lower() == "i forfeit all mortal possessions to dog":
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="yeah!",
            description="✅✅✅" # this is what limited time does
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "yeah",
            lambda: asyncio.create_task(callback())
        )

    elif message.content == "horse":
        embed = discord.Embed(title="Horse!")
        embed.set_image(url="attachment://Horse.png")
        embedC = discord.Embed(
            color=discord.Color(0x265526),
            title="🏇",
            description="actually it’s ‘dog’… but horse is fine..?"
        )
        embedC.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embedC.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embedC, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "honse",
            lambda: asyncio.create_task(callback())
        )

        await message.channel.send(embed=embed, file=discord.File('media/Horse.png'))

    elif "the game" in message.content.lower():
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="I hate you",
            description="…"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "I_hate_you",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() == "please do not the dog":
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="please do not the dog",
            description="that’s not a meme?? ok…"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "please_do_not_the_dog",
            lambda: asyncio.create_task(callback())
        )


    elif message.content.lower() == "fog":
        embed = discord.Embed(title="fog.")
        embed.set_image(url="attachment://fog.png")

        embedC = discord.Embed(
            color=discord.Color(0x265526),
            title="fog <:fog:1287611863290609684>",
            description="fog"
        )
        embedC.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embedC.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embedC, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "fog",
            lambda: asyncio.create_task(callback())
        )
        await message.channel.send(embed=embed, file=discord.File('media/fog.png'))

    elif message.content.lower() == "cat":
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="BANISHED <:banished:1302758222201098341>",
            description="no. Absolutely not. Please seek professional help."
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "banished",
            lambda: asyncio.create_task(callback())
        )
        
    elif message.content.lower() == "sog":
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="sog",
            description="<:uhok:1289028276672663552>"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "sog",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() == "huh":
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="huh",
            description="huh"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "huh",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() == "bwaa":
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="bwaa",
            description="bwaa"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "bwaa",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() in ["appel", "april"]:
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="this dock is holding an 🍎 April in its Melt",
            description="🍎🍎🍎"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "this_dock_is_holding_an_apple",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() in ["shiba x husky", "husky x shiba", "shusky"]:
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="canon",
            description="they've kissed before"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "canon",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() in ["I love cat", "cat > dog"]:
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="on the run",
            description="run faster"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "on_the_run",
            lambda: asyncio.create_task(callback())
        )

    elif message.content.lower() in ["1+1=2", "1 + 1 = 2"]:
        embed = discord.Embed(
            color=discord.Color(0x265526),
            title="Mathematician",
            description="You passed kindergarten!"
        )
        embed.set_author(
            name="Achievement Unlocked!",
            icon_url="attachment://achievements.png"
        )
        embed.set_footer(text=f"Unlocked by {message.author.name}")

        async def callback():
            try:
                await message.channel.send(embed=embed, file=discord.File('media/achievements.png'))
            except discord.HTTPException as e:
                print(f"Error sending achievement: {e}")

        # Claim the achievement
        ClaimAch(
            message.guild.id,
            message.author.id,
            "mathematician",
            lambda: asyncio.create_task(callback())
        )

    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    emoji = EMOJI_ID

    if payload.guild_id not in (None, 1285438304518406174) or str(payload.emoji) != EMOJI_ID:
        return

    if str(payload.emoji) == emoji:
        # Fetch the message and channel
        channel = bot.get_channel(payload.channel_id)
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            print("Message not found.")
            return
        except discord.Forbidden:
            print("Bot does not have permissions to fetch the message.")
            return

        # Check if the message has already been processed
        if message.id in processed_message_ids:
            return
        
        # Check if the staring dog emoji has enough reactions
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji and reaction.count >= 5:
                # Create the embed
                embed = discord.Embed(
                    description=message.content or "No Content", 
                    url=message.jump_url
                )
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)
                embed.set_author(
                    name=message.author.display_name, 
                    icon_url=message.author.display_avatar.url
                )
                embed.set_footer(
                    text=f"Channel: {message.channel.name} • Guild: {message.guild.name}"
                )

                # Create a button to jump to the original message
                button = Button(label="Jump to message", url=message.jump_url)
                view = View()
                view.add_item(button)

                # Send the embed with the button to the target channel
                target_channel = bot.get_channel(1287625403803897908)
                await target_channel.send(embed=embed, view=view)

                # Add the message ID to the processed list (so you cant spam it..)
                processed_message_ids.add(message.id)
                save_processed_ids(processed_message_ids)

@bot.tree.command(name="ping", description="Check bot latency")
async def ping_command(interaction: discord.Interaction):
    
    """Returns bot latency in milliseconds."""

    latency = bot.latency * 1000  # Convert to milliseconds
    await interaction.response.send_message(f'Pong! Latency: {latency:.2f} ms')

@bot.tree.command(name="rate", description="Rate a user on a scale.")
async def rate_command(interaction: discord.Interaction, target: discord.User, rate: str):
    
    """
    Rates a user on a scale between 0 and 100.

    Args:
        interaction: The interaction object.
        target: The user to rate.
        rate: The scale to rate the user on.

    Returns:
        A message with the rating.
    """
    
    chance = random.randint(0, 100)
    await interaction.response.send_message(f"{target.mention} is {chance}% {rate}")

@bot.tree.command(name="fact", description="Get a random dog fact")
async def dog_fact_command(interaction: discord.Interaction):

    """Gets a random dog fact from the Dog API.

    Args:
        interaction: The interaction object.

    Returns:
        A message with a random dog fact.
    """

    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://dogapi.dog/api/v2/facts?limit=1", timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                await interaction.followup.send(data["data"][0]["attributes"]["body"])
            else:
                await interaction.followup.send("Failed to fetch a dog fact.", ephemeral=True)

@bot.tree.command(name="inventory", description="See all of your dawgs")
async def inventory_command(interaction: discord.Interaction, member: discord.Member = None):

    """
    Shows all of the dogs in a user's inventory.

    This command shows all of the dogs that a user has caught (doesn't share across servers).
    If the user has no dogs, it will say so in the embed.
    """

    if isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("this command cannot be used in dms, try it in a server instead", ephemeral=True)
        return

    user_id = member.id if member else interaction.user.id
    guild_id = interaction.guild.id 

    dogs = db.list_dogs(user_id, guild_id)

    embed = discord.Embed(title="Dogs", description="Here are all your dogs:", color=discord.Color.blue())
    display_member = member or interaction.user  # Choose the member to display
    embed.set_author(name=display_member.display_name, icon_url=display_member.avatar.url)

    # Handle the list of dogs
    if dogs:
        for dog in dogs:
            embed.add_field(name=dog[0], value=dog[1], inline=True)
    else:
        no_dogs_msg = f"{display_member.display_name} doesn't have any dogs in their inventory." if member else "You don't have any dogs in your inventory."
        embed.description = no_dogs_msg

    try:
        await interaction.response.send_message(embed=embed)
    except discord.errors.NotFound:
        await interaction.followup.send("Unknown interaction.", ephemeral=True)

@bot.tree.command(name="achievements", description="See your achievements")
async def achievements(interaction: discord.Interaction, member: discord.Member = None):
    """
    Shows all achievements a user has earned.

    If the user has no achievements, it will say so in the embed.
    """

    if isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("This command cannot be used in DMs, try it in a server instead.", ephemeral=True)
        return

    user_id = member.id if member else interaction.user.id
    guild_id = interaction.guild.id 

    achievements = Achievement.Retrieve(guild_id, user_id)

    embed = discord.Embed(title="Achievements", description="Here are your achievements:", color=discord.Color.gold())
    display_member = member or interaction.user  
    embed.set_author(name=display_member.display_name, icon_url=display_member.avatar.url)

    if achievements:
        for achievement in achievements:
            name = achievement.get("name", "Unknown Achievement")
            embed.add_field(name=f"🏆 | {name}", value="\u200b", inline=False)  # Empty value to just display name
    else:
        embed.description = f"{display_member.display_name} hasn't earned any achievements yet." if member else "You haven't earned any achievements yet."

    try:
        await interaction.response.send_message(embed=embed)
    except discord.errors.NotFound:
        await interaction.followup.send("Unknown interaction.", ephemeral=True)

@bot.tree.command(name="force_remove", description="remove dogs from someones inventory")
async def force_remove(interaction: discord.Interaction, member: discord.Member, dog: str, amount: int):

    """
    Removes dogs from a user's inventory.

    Args:
        member: The user to remove dogs from.
        dog: The type of the dog to remove.
        amount: The amount of dogs to remove.
    """

    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("You need to be a moderator to use this command.", ephemeral=True)
        return

    if isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("This command cannot be used in DMs.", ephemeral=True)
        return

    user_id = member.id
    guild_id = interaction.guild.id
    
    # Check if the user has enough dogs to remove
    dogs = db.list_dogs(user_id, guild_id)
    if len(dogs) < amount:
        await interaction.response.send_message("You don't have that many dogs in your inventory.", ephemeral=True)
        return

    # Remove the dogs
    db.remove_dog(dog, user_id, guild_id, amount)
    await interaction.response.send_message(f"Removed {amount} {dog} from {member.display_name}'s inventory.", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Shows the leaderboard")
async def leaderboard_command(interaction: discord.Interaction):
    """
    Shows the leaderboard for the current server or globally.
    """
    view = View()

    async def gather_leaderboard_data(leaderboard_type: str, guild_id: int = None) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.blue())
        
        leaderboard_data = {
            "server": {
                "title": "Dogs Leaderboard (Server)",
                "footer": "Server Leaderboard",
                "data": db.get_leaderboard(guild_id)
            },
            "global": {
                "title": "Dogs Leaderboard (Global)",
                "footer": "Global Leaderboard",
                "data": await get_global_leaderboard()
            }
        }
        
        data = leaderboard_data[leaderboard_type]
        rarest_dog, top_users = data["data"]
        
        embed.title = data["title"]
        embed.description = f"Rarest dog: {rarest_dog[0]} ({rarest_dog[1]} exist)" if rarest_dog else ""
        embed.set_footer(text=data["footer"])
        
        if top_users:
            for index, (user_id, total_amount) in enumerate(top_users[:25]):
                embed.add_field(
                    name=f"{index+1}.",
                    value=f"{total_amount:,} dogs: <@{user_id}>",
                    inline=False
                )
        else:
            embed.add_field(name="No users found", value="No data available.", inline=False)
        
        return embed

    async def get_global_leaderboard():
        all_top_users = {}
        rarest_dog = None

        for guild in bot.guilds:
            guild_rarest_dog, guild_top_users = db.get_leaderboard(guild.id)

            if guild_rarest_dog:
                if rarest_dog is None or guild_rarest_dog[1] < rarest_dog[1]:
                    rarest_dog = guild_rarest_dog

            for user_id, amount in guild_top_users:
                all_top_users[user_id] = all_top_users.get(user_id, 0) + amount

        top_users = [(user_id, amount) for user_id, amount in all_top_users.items() if amount >= 20]
        top_users.sort(key=lambda x: x[1], reverse=True)

        return {}, top_users

    # Button callbacks
    async def leaderboard_callback(interaction: discord.Interaction, leaderboard_type: str):
        await interaction.response.defer()
        embed = await gather_leaderboard_data(leaderboard_type, interaction.guild.id)
        await interaction.edit_original_response(embed=embed)

    # Create buttons
    server_button = Button(label="Server", style=discord.ButtonStyle.primary)
    global_button = Button(label="Global", style=discord.ButtonStyle.primary)

    server_button.callback = lambda i: leaderboard_callback(i, "server")
    global_button.callback = lambda i: leaderboard_callback(i, "global")

    view.add_item(server_button)
    view.add_item(global_button)

    embed = await gather_leaderboard_data("server", interaction.guild.id)
    await interaction.response.send_message(embed=embed, view=view)


# info commmand. shows info about dogbot
@bot.tree.command(name="info", description="Shows info about DogBot.")
async def info_command(interaction: discord.Interaction):
    
    """Shows info about DogBot."""
    
    embed = discord.Embed(
        title="DogBot",
        description=("[Discord Server](https://discord.gg/7yv7DEz9a5)\n"
                     "[Github Page](https://github.com/NotRealAz/DogBot)\n\n"
                     "Dog bot adds Dog catching, silly commands, and more fun features!\n\n"
                     "List of features:"),
        color=discord.Color(0xFFA500)
    )
    
    # Add fields
    embed.add_field(
        name="Dog Hunting",
        value=("Many dog types such as Mutt, Husky, Dalmatian, and more!\n"
               "To catch them, type 'dog' when it spawns in a catching channel."),
        inline=True
    )
    
    embed.add_field(
        name="Commands",
        value="Silly commands for all your silly needs!",
        inline=True
    )
    
    embed.add_field(
        name="DogBoard (DogStand exclusive)",
        value=("Messages with 5 <:staring_dog:1285440635117113344> reactions "
               "would appear in the dog board to see all of the horrendous or funny stuff people say."),
        inline=True
    )
    
    # Set footer and thumbnail
    embed.set_footer(
        text="Dog Bot by notrealaz, Dog Stand by meo.isnt.mayo",
        icon_url="https://github.com/NotRealAz/DogBot/blob/main/media/dogs/mutt.png?raw=true"
    )
    
    embed.set_thumbnail(
        url="https://github.com/NotRealAz/DogBot/blob/main/media/dogs/mutt.png?raw=true"
    )
    
    try:
        await interaction.response.send_message(embed=embed)
    except discord.errors.NotFound:
        await interaction.response.send_message("Failed to send the help message.", ephemeral=True)

# help commmand. shows how to use dogbot
@bot.tree.command(name="help", description="Shows how to use DogBot.")
async def help_command(interaction: discord.Interaction):
    
    """Shows how to use DogBot."""
    
    embed1 = discord.Embed(
        title="How to Setup",
        description=("To set up catching, you need to use the `/setup` command on a channel that you want dogs to spawn in, after you run the command dogs will start spawning there every 1/5 minutes."),
        color=discord.Color(0xFFA500) 
    )

    embed1.set_thumbnail(url="https://raw.githubusercontent.com/NotRealAz/DogBot/refs/heads/main/media/dogs/mutt.png")
    
    # Second Embed: "How to Play"
    embed2 = discord.Embed(
        title="How to Play",
        color=discord.Color(0xFFA500)
    )

    embed2.add_field(
        name="Catching Dogs",
        value=("From time to time, dogs will spawn.\n\n"
               "To catch them, you must say `dog`. (If you can't catch the dog, "
               "then it's glitched and doesn't count). The dog will then be added to your inventory."),
        inline=True
    )
    
    embed2.add_field(
        name="Viewing Your Inventory",
        value=("You can view your inventory using the `/inventory` command. "
               "It will display all the dogs you own, including the amount and type."),
        inline=True
    )
    
    embed2.add_field(
        name="Silly Commands",
        value="Little silly commands to make DogBot more fun.",
        inline=True
    )
    
    embed2.set_footer(
        text="Dog Bot by notrealaz, Dog stand by meo.isnt.mayo",
        icon_url="https://github.com/NotRealAz/DogBot/blob/main/media/dogs/mutt.png?raw=true"
    )

    try:
        await interaction.response.send_message(embeds=[embed1, embed2])
    except discord.errors.NotFound:
        await interaction.response.send_message("Failed to send the help message.", ephemeral=True)

@bot.tree.command(name="setup", description="Set up configuration for catching")
async def setup(interaction: discord.Interaction):
    """
    When this is ran, it adds the channel the command was ran in to the list of channels for catching.

    Only the server owner or users with administrator permissions can run this command.
    """

    # Check if the user has administrator permissions or is the server owner
    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner.id:
        await interaction.response.send_message("You don't have permission to run this command.", ephemeral=True)
        return

    # Add the current channel to the list of channels for catching in the database
    channel_id = interaction.channel.id
    guild_id = interaction.guild.id

    try:
        server_channels = db.list_server_channels(guild_id)
        if channel_id not in server_channels:
            db.add_channel(channel_id, guild_id)
            await interaction.response.send_message(f"The channel {interaction.channel.name} has been set up for catching!", ephemeral=True)
        else:
            button = Button(label="Remove", style=discord.ButtonStyle.danger, custom_id="remove_channel")
            view = View()
            view.add_item(button)
            
            async def remove_channel_callback(interaction: discord.Interaction):
                db.remove_channel(channel_id, guild_id)
                await interaction.response.edit_message(content=f"The channel {interaction.channel.mention} has been removed from the catching channels.", view=None)
            
            button.callback = remove_channel_callback

            await interaction.response.send_message(f"The channel {interaction.channel.mention} is already set up for catching.", ephemeral=True, view=view)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred while setting up the channel: {type(e).__name__}: {e}", ephemeral=True)


# forcespawn unmaintanied. TODO: fix forcespawn

@bot.tree.command(name="battle", description="Battle dogs with another member!")
async def battle_command(interaction: discord.Interaction, opponent: discord.User, dog_name: str):
    
    """
    Challenge another user to a dog battle using a selected dog from your inventory.
    Args:
        interaction: The interaction object.
        opponent: The user to challenge.
        dog_name: The name of the dog selected for the battle.
    """

    if opponent == interaction.user:
        await interaction.response.send_message("Why would you want to fight yourself?", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id 

    # Check user's inventory for the selected dog
    dogs = db.list_dogs(user_id, guild_id)
    user_dog = next((dog for dog in dogs if dog[0] == dog_name), None)

    if user_dog is None:
        await interaction.response.send_message(f"You have no '{dog_name}' in your inventory.", ephemeral=True)
        return

    embed = discord.Embed(
        title="A Dog Battle has been requested!",
        description=f"{interaction.user.name} challenges {opponent.name} to a battle with {dog_name}!",
        color=discord.Color.green()
    )
    await interaction.response.send_message("Battle Started.", ephemeral=True)
    await interaction.channel.send(embed=embed)

    def check(msg):
        return msg.author == opponent and msg.channel == interaction.channel

    await interaction.channel.send(f"{opponent.mention}, which dog would you like to battle with?")

    # Retry logic for opponent to choose their dog
    attempts = 0
    max_attempts = 3
    timeout_duration = 300  # 5 minutes

    while attempts < max_attempts:
        try:
            msg = await bot.wait_for('message', check=check, timeout=timeout_duration)
            opponent_dog_name = msg.content

            # Check if the opponent owns the dog they specified
            opponent_dogs = db.list_dogs(opponent.id, guild_id)
            opponent_dog = next((dog for dog in opponent_dogs if dog[0] == opponent_dog_name), None)

            if opponent_dog is not None:
                break
            else:
                await interaction.channel.send(f"{opponent.name}, you don't own a dog named '{opponent_dog_name}'. Please choose again.")
                attempts += 1

        except asyncio.TimeoutError:
            await interaction.channel.send(f"{opponent.name} took too long to respond. The battle has been canceled.")
            return

    if attempts == max_attempts:
        await interaction.channel.send(f"{opponent.name} failed to choose a valid dog in {max_attempts} attempts. The battle has been canceled.")
        return

    # Battle logic: Randomly decide the winner or based on dog stats.
    winner = random.choice([interaction.user, opponent])
    await interaction.channel.send(f"Winner: {winner.name}!")

token = os.getenv("BOT_TOKEN")
if not token:
    raise EnvironmentError("BOT_TOKEN is not set in the environment.")

# Run the bot with the token
bot.run(token)
