import asyncio
import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import aiohttp
import random
import json
import time

# local files
from utils.database import DB

# Load environment variables
load_dotenv()

# Server config
db = DB()

# Load dog data from file
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
current_dog = None
dog_message = None
dog_spawn_channel = None  # Track where the dog spawned

# Define intents and create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Needed for slash commands
bot = commands.Bot(command_prefix='!dog=', intents=intents)

@bot.event
async def on_ready():

    """Triggered when the bot is ready."""

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name=f"in {len(bot.guilds):,} servers!")
    )
    print(f"Logged in as {bot.user.name}")
    send_dog_message.start()
    await bot.tree.sync()  # Sync commands with Discord

def get_random_dog() -> dict:

    """Helper function to get a random dog based on chance."""

    total_chance = sum(dog["chance"] for dog in dogs)
    roll = random.uniform(0, total_chance)
    upto = 0
    for dog in dogs:
        if upto + dog["chance"] >= roll:
            return dog
        upto += dog["chance"]

@tasks.loop(minutes=random.randint(5, 10))
async def send_dog_message():

    """Periodically sends a message to spawn a random dog in configured channels."""

    for guild in bot.guilds:
        try:
            config = db.list_server_config(guild.id)

            if config is None:
                continue

            CATCHING_CHANNEL_ID, SLOW_CATCHING_CHANNEL_ID = config
            if CATCHING_CHANNEL_ID is None or SLOW_CATCHING_CHANNEL_ID is None:
                continue

            guild_state = guild_dog_states.get(guild.id, {"current_dog": None, "dog_message": None})

            if guild_state["current_dog"] is not None:
                continue

            dog_spawn_channel = bot.get_channel(random.choice([SLOW_CATCHING_CHANNEL_ID, CATCHING_CHANNEL_ID]))
            if dog_spawn_channel is None:
                print(f"Skipping guild {guild.name}: Invalid catching channels.")
                continue

            current_dog = get_random_dog()
            if os.path.exists(current_dog['image']):
                file = discord.File(current_dog['image'], filename=os.path.basename(current_dog['image']))
                dog_message = await dog_spawn_channel.send(
                    f"A {current_dog['emoji']} {current_dog['name']} has spawned! Type 'dog' to catch it!",
                    file=file
                )
            else:
                print(f"Error: File {current_dog['image']} not found!")
                continue

            guild_dog_states[guild.id] = {
                "current_dog": current_dog,
                "dog_message": dog_message,
                "dog_spawn_channel": dog_spawn_channel
            }

        except Exception as e:
            print(f"Error spawning dog in {guild.name}: {e}")

@bot.event
async def on_message(message):
    
    """Handles dog catching logic and custom phrases like 'horse' and 'fog'."""

    if isinstance(message.channel, discord.DMChannel) or message.author == bot.user:
        return

    guild_state = guild_dog_states.get(message.guild.id, {"current_dog": None, "dog_message": None})
    current_dog = guild_state["current_dog"]
    dog_message = guild_state["dog_message"]

    if message.content.lower() == 'dog' and current_dog is not None:
        if message.channel.id == dog_message.channel.id:
            spawn_time = dog_message.created_at.timestamp()
            catch_time = time.time()
            elapsed_time = catch_time - spawn_time

            await dog_message.delete()

            db.catch_dog(current_dog['name'], message.author.id, message.guild.id, 1)

            dogs = db.list_dogs(message.author.id, message.guild.id)
            amount = next((dog[1] for dog in dogs if dog[0] == current_dog['name']), 0)

            await message.channel.send(f'{message.author.name} caught {current_dog["emoji"]} {current_dog["name"]} dog!!!\n'
                                       f'You have now caught {amount} dogs of that type!!!\n'
                                       f'This fella was caught in {int(elapsed_time)} seconds!!!')

            guild_dog_states[message.guild.id] = {"current_dog": None, "dog_message": None}

    elif message.content == "horse":
        embed = discord.Embed(title="Horse!")
        embed.set_image(url="attachment://Horse.png")
        await message.channel.send(embed=embed, file=discord.File('media/Horse.png'))

    elif message.content.lower() == "fog":
        embed = discord.Embed(title="fog.")
        embed.set_image(url="attachment://fog.png")
        await message.channel.send(embed=embed, file=discord.File('media/fog.png'))

    await bot.process_commands(message)

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
                await interaction.followup.send("Failed to fetch a dog fact.")

@bot.tree.command(name="inventory", description="See all of your dawgs")
async def inventory_command(interaction: discord.Interaction):

    """
    Shows all of the dogs in a user's inventory.

    This command shows all of the dogs that a user has caught (doesnt share across servers).
    If the user has no dogs, it will say so in the embed.
    """
    
    if isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("This command cannot be used in DMs.", ephemeral=True)
        return

    await interaction.response.defer()
    user_id = interaction.user.id
    guild_id = interaction.guild.id 

    dogs = db.list_dogs(user_id, guild_id)

    embed = discord.Embed(title="Dogs", description="Here are all your dogs:", color=discord.Color.blue())
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)

    if dogs:
        for dog in dogs:
            embed.add_field(name=dog[0], value=dog[1], inline=False)
    else:
        embed.description = "You don't have any dogs in your inventory."

    await interaction.followup.send(embed=embed)

# info commmand. shows info about dogbot
@bot.tree.command(name="info", description="Shows info about dogbot.")
async def info_command(interaction: discord.Interaction):
    
    """Shows info about dogbot."""
    
    embed = discord.Embed(
        title="DogBot",
        description=("[Discord Server](https://discord.gg/7yv7DEz9a5)\n"
                     "[Github Page](https://github.com/NotRealAz/DogBot)\n\n"
                     "Dog bot adds Dog hunting, silly commands, and more fun features!\n\n"
                     "List of features:"),
        color=discord.Color(0xFFA500)
    )
    
    # Add fields
    embed.add_field(
        name="Dog Hunting",
        value=("Many Dog Types such as mutt, husky, dalmatian, and more!\n"
               "To catch them, type 'dog' when it spawns in a catching channel."),
        inline=True
    )
    
    embed.add_field(
        name="Commands",
        value="Silly Little Commands For Fun!",
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
        text="Dog Bot by notrealaz, Dog stand by meo.isnt.mayo",
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
@bot.tree.command(name="help", description="Shows how to use dogbot.")
async def help_command(interaction: discord.Interaction):
    
    """Shows how to use dogbot."""
    
    embed1 = discord.Embed(
        title="How to Setup",
        description=("To set up catching, you need to use the `/setup_catching` command and specify 2 channels: "
                     "one for `catching` and one for `slow catching`. "
                     "(You need to be an admin or the owner to run this command), "
                     "dogs will start spawning every 5/10 minutes."),
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
               "then it's glitched and doesn't count). Then the dog will be added to your inventory."),
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
        value="Little silly commands to make Dog Bot more fun.",
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

@bot.tree.command(name="setup_catching", description="Set up configuration for catching (slow and normal).")
async def setup_catching_command(interaction: discord.Interaction, catching_channel: discord.TextChannel, slow_catching_channel: discord.TextChannel):
    """
    Set up configuration for catching (slow and normal) by specifying the two channels to use.

    Only the server owner or users with administrator permissions can run this command

    Parameters:.
    - `catching_channel`: The channel where dogs will spawn at a normal rate.
    - `slow_catching_channel`: The channel where dogs will spawn at a normal rate but the channel has a 6 hour slow mode.
    """

    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner.id:
        await interaction.response.send_message("You don't have permission to run this command.", ephemeral=True)
        return

    db.update_server_config(catching_channel.id, slow_catching_channel.id, interaction.guild.id)

    if not send_dog_message.is_running():
        await send_dog_message.start()
    
    await interaction.response.send_message(f"Catching channels have been configured for this server!", ephemeral=True)

@bot.tree.command(name="forcespawn", description="Forces a dog to spawn.")
@commands.has_permissions(manage_guild=True)
async def forcespawn_command(interaction: discord.Interaction, dogname: str):

    """Force spawns a specific dog."""

    # Find the dog with the given name
    current_dog = next((dog for dog in dogs if dog["name"].lower() == dogname.lower()), None)
    if current_dog is None:
        await interaction.response.send_message(f"{dogname} doesn't exist in the database.", ephemeral=True)
        return

    config = db.list_server_config(interaction.guild.id)
    if config is None:
        await interaction.response.send_message("Configuration error for this server.", ephemeral=True)
        return

    CATCHING_CHANNEL_ID, SLOW_CATCHING_CHANNEL_ID = config
    dog_spawn_channel = bot.get_channel(random.choice([SLOW_CATCHING_CHANNEL_ID, CATCHING_CHANNEL_ID]))
    if dog_spawn_channel is None:
        await interaction.response.send_message("Couldn't find a valid channel to spawn the dog.", ephemeral=True)
        return

    # Make sure no dog is currently spawned
    guild_state = guild_dog_states.get(interaction.guild.id, {"current_dog": None, "dog_message": None})
    if guild_state["current_dog"] is not None:
        await interaction.response.send_message("A dog is already spawned!", ephemeral=True)
        return

    # Set the spawn type to "forcespawn" and send the dog message
    if os.path.exists(current_dog['image']):
        file = discord.File(current_dog['image'], filename=os.path.basename(current_dog['image']))
        dog_message = await dog_spawn_channel.send(
            f"A {current_dog['emoji']} {current_dog['name']} has forcefully spawned! Type 'dog' to catch it!",
            file=file
        )

        # Update the guild state with the forced dog spawn info
        guild_dog_states[interaction.guild.id] = {
            "current_dog": current_dog,
            "dog_message": dog_message,
            "dog_spawn_channel": dog_spawn_channel
        }

        await interaction.response.send_message(f"{current_dog['name']} has been forcefully spawned in {dog_spawn_channel.mention}!")
    else:
        await interaction.response.send_message(f"Error: File {current_dog['image']} not found!", ephemeral=True)

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
        await interaction.response.send_message(f"There is no such thing as a '{dog_name}' in your inventory.", ephemeral=True)
        return

    # Notify opponent and ask them to select their dog
    embed = discord.Embed(
        title="Dog Battle Challenge!",
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
