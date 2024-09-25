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
    send_dog_message.start()  # Start the background task
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

@tasks.loop(minutes=random.randint(1, 5))
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

    if message.content == 'dog' and current_dog is not None:
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

    await interaction.response.defer()
    user_id = interaction.user.id
    guild_id = interaction.guild.id  # Ensure you're using the guild ID

    dogs = db.list_dogs(user_id, guild_id)

    embed = discord.Embed(title="Dogs", description="Here are all your dogs:", color=discord.Color.blue())
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)

    if dogs:
        for dog in dogs:
            embed.add_field(name=dog[0], value=dog[1], inline=False)
    else:
        embed.description = "You don't have any dogs in your inventory."

    await interaction.followup.send(embed=embed)
    
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
    
    # Update the server configuration in the database
    db.update_server_config(catching_channel.id, slow_catching_channel.id, interaction.guild.id)

    if not send_dog_message.is_running():
        await send_dog_message.start()
    
    await interaction.response.send_message(f"Catching channels have been configured for this server!", ephemeral=True)

token = os.getenv("BOT_TOKEN")
if not token:
    raise EnvironmentError("BOT_TOKEN is not set in the environment.")

# Run the bot with the token
bot.run(token)
