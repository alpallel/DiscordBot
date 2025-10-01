import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio
from collections import deque
import sqlite3
import aiohttp
import hashlib
from datetime import datetime
import uuid
import requests
import shutil
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload



BASE_DIR = os.path.dirname(os.path.abspath(__file__))




# ===== Google Drive API setup =====
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'
PARENT_FOLDER_ID = "1a8rNFWfAARWZlJK2Cmg2tV1y8di8bUHl" # Gallery drive folder ID

credentials = service_account.Credentials.from_service_account_file(
  SERVICE_ACCOUNT_FILE, scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=credentials)

def upload_to_shared_drive(filepath, drive_service, shared_drive_id):
  file_metadata = {
    'name': os.path.basename(filepath),
    'parents': [shared_drive_id]
  }
  media = MediaFileUpload(filepath, resumable=True)
  file = drive_service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id',
    supportsAllDrives=True
  ).execute()
  print('File ID:', file.get('id'))


# ===== Database functions for warning system =====

# Swear word warning system def
profanity = ["ajg", "anjing", "babi", "bgst", "tai", "fak"]

def create_user_table():
  connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
  cursor = connection.cursor()
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS "users_per_guild" (
      "user_id" INTEGER, 
      "warning_count" INTEGER,
      "guild_id" INTEGER,
      PRIMARY KEY ("user_id", "guild_id")
    )
  """)

  connection.commit()
  connection.close()
create_user_table()

def get_warnings(user_id, guild_id):
  connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
  cursor = connection.cursor()

  cursor.execute("""
    SELECT warning_count 
    FROM users_per_guild
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (user_id, guild_id))

  result = cursor.fetchone()
  connection.close()

  if result is None:
    return 0
  return result[0]

def increase_and_get_warnings(user_id, guild_id):
  connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
  cursor = connection.cursor()

  cursor.execute("""
    SELECT warning_count 
    FROM users_per_guild
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (user_id, guild_id))

  result = cursor.fetchone()

  if result is None:
    cursor.execute("""
      INSERT INTO users_per_guild (user_id, warning_count, guild_id)
      VALUES (?, 1, ?)
    """, (user_id, guild_id))

    connection.commit()
    connection.close()

    return 1
  
  cursor.execute("""
    UPDATE users_per_guild
    SET warning_count = ?
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (result[0] + 1, user_id, guild_id))

  connection.commit()
  connection.close()

  return result[0] + 1

def remove_and_get_warnings(user_id, guild_id):
  connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
  cursor = connection.cursor()

  cursor.execute("""
    SELECT warning_count 
    FROM users_per_guild
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (user_id, guild_id))

  result = cursor.fetchone()

  if result is None:
    return 0

  new_warning_count = max(0, result[0] - result[0])  # Reset to 0

  cursor.execute("""
    UPDATE users_per_guild
    SET warning_count = ?
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (new_warning_count, user_id, guild_id))

  connection.commit()
  connection.close()

  return new_warning_count

def add_and_get_warnings(user_id, guild_id, add_amount):
  connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
  cursor = connection.cursor()

  cursor.execute("""
    SELECT warning_count 
    FROM users_per_guild
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (user_id, guild_id))

  result = cursor.fetchone()

  if result is None:
    return 0

  new_warning_count = max(0, result[0] + add_amount)

  cursor.execute("""
    UPDATE users_per_guild
    SET warning_count = ?
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (new_warning_count, user_id, guild_id))

  connection.commit()
  connection.close()

  return new_warning_count

def set_and_get_warnings(user_id, guild_id, set_amount):
  connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
  cursor = connection.cursor()

  cursor.execute("""
    SELECT warning_count 
    FROM users_per_guild
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (user_id, guild_id))

  result = cursor.fetchone()

  if result is None:
    cursor.execute("""
      INSERT INTO users_per_guild (user_id, warning_count, guild_id)
      VALUES (?, ?, ?)
    """, (user_id, set_amount, guild_id))

    connection.commit()
    connection.close()

    return set_amount
  
  cursor.execute("""
    UPDATE users_per_guild
    SET warning_count = ?
    WHERE (user_id = ?) AND (guild_id = ?)
  """, (set_amount, user_id, guild_id))

  connection.commit()
  connection.close()

  return set_amount


# ===== Image downloading system =====
# TODO
# Database functions for downloaded images
def create_image_table():
  connection = sqlite3.connect(f"{BASE_DIR}\\downloaded_images.db")
  cursor = connection.cursor()
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS "images" (
      "id" INTEGER PRIMARY KEY AUTOINCREMENT, 
      "url" TEXT, 
      "local_path" TEXT,
      "hash" TEXT,
      "timestamp" DATETIME
    )
  """)

  connection.commit()
  connection.close()
create_image_table()

def download_image(url):
  try:
    response = requests.get(url, stream=True)
    response.raise_for_status()

    # Generate a unique filename
    file_ext = url.split('.')[-1].split('?')[0]  # Get file extension from URL
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    local_path = os.path.join(BASE_DIR, "downloaded_images", unique_filename)

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    with open(local_path, 'wb') as out_file:
      shutil.copyfileobj(response.raw, out_file)

    # Calculate hash
    hasher = hashlib.sha256()
    with open(local_path, 'rb') as f:
      buf = f.read()
      hasher.update(buf)
    img_hash = hasher.hexdigest()

    # Store in database
    connection = sqlite3.connect(f"{BASE_DIR}\\downloaded_images.db")
    cursor = connection.cursor()
    cursor.execute("""
      INSERT INTO images (url, local_path, hash, timestamp)
      VALUES (?, ?, ?, ?)
    """, (url, local_path, img_hash, datetime.now()))

    connection.commit()
    connection.close()

    return local_path

  except Exception as e:
    print(f"Error downloading image: {e}")
    return None




load_dotenv()

token_dc = os.getenv("DISCORD_TOKEN")

SONG_QUEUES = {}

guild_id = 1412794996901285890



# music commands stuff
async def search_ytdlp_async(query, ydl_opts):
  loop = asyncio.get_event_loop()
  return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(query, download=False)



handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
  await bot.tree.sync()

  print(f"{bot.user.name} sudah redi king")




# === Music commands ===

# play command
@bot.tree.command(name="play", description="play a song or add a song to queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
  await interaction.response.defer()

  voice_channel = interaction.user.voice.channel

  if not voice_channel:
    await interaction.followup.send("Masuk voice dulu bang")
    return

  voice_client = interaction.guild.voice_client

  if voice_client is None:
    voice_client = await voice_channel.connect()
  elif voice_channel != voice_client.channel:
    await voice_client.move_to(voice_channel)

  ydl_opts = {
    "format": "bestaudio[abr<=96]/bestaudio",
    "noplaylist": True,
    "youtube_include_dash_manifest": False,
    "youtube_include_hls_manifest": False,
  }

  query = "ytsearch: " + song_query
  results = await search_ytdlp_async(query, ydl_opts)
  tracks = results.get("entries", [])

  if tracks is None:
    await interaction.followup.send("Takde lagunya bang")
    return

  first_track = tracks[0]
  audio_url = first_track["url"]
  title = first_track.get("title", "unlisted")

  guild_id = str(interaction.guild.id)
  if SONG_QUEUES.get(guild_id) is None:
    SONG_QUEUES[guild_id] = deque()

    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
      await interaction.followup.send(f"Added to queue: **{title}**")
    else:
      await interaction.followup.send(f"Now playing: **{title}**")
      await play_next_song(voice_client, guild_id, interaction.channel)

# skip command
@bot.tree.command(name="skip", description="Skip the current song.")
async def skip(interaction: discord.Interaction):
  if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
    interaction.guild.voice_client.stop()
    await interaction.response.send_message("Skipped the current song.")

  else:
    await interaction.response.send_message("No song is currently playing.")

# stop command
@bot.tree.command(name="stop", description="Stop the music and clear the queue.")
async def stop(interaction: discord.Interaction):
  await interaction.response.defer()
  voice_client = interaction.guild.voice_client
  
  if not voice_client or not voice_client.is_connected():
    return await interaction.followup.send_message("I'm not connected to a voice channel.")
  
  guild_id_str = str(interaction.guild.id)
  if guild_id_str in SONG_QUEUES:
    SONG_QUEUES[guild_id_str].clear()

  if voice_client.is_playing() or voice_client.is_paused():
    voice_client.stop()

  await interaction.followup.send("Stopped playing and disconected")

  await voice_client.disconnect()

# next song command
async def play_next_song(voice_client, guild_id, channel):
  if SONG_QUEUES[guild_id]:
    audio_url, title = SONG_QUEUES[guild_id].popleft()

    ffmpeg_options = {
      "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
      "options": "-vn -c:a libopus -b:a 96k",
    }

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options, executable="bin\\ffmpeg\\ffmpeg.exe")

    def after_play(error):
      if error:
        print(f"Error playing {title}: {error}")
      asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

    voice_client.play(source, after=after_play)
    asyncio.create_task(channel.send(f"Now playing: **{title}**"))

  else:
    await voice_client.disconnect()
    SONG_QUEUES[guild_id] = deque()


# === General commands ===

# ping command
@bot.tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
  await interaction.response.send_message(f"yo ({bot.latency * 1000:.2f}ms)")

# spam command
@bot.tree.command(name="spam", description="Spam a message a specified number of times.")
@app_commands.describe(message="The message to spam", times="Number of times to spam the message")
async def spam(interaction: discord.Interaction, message: str, times: int):
  await interaction.response.defer()
  await interaction.followup.send("Spamming...")
  for i in range(times):
    await interaction.channel.send(message)
  await interaction.edit_original_response(content="Don ya bang")


# === Warning system commands ===

# Remove warnings command
@bot.tree.command(name="ampuni_dosa", description="Menghapus segala dosa user")
@app_commands.describe(user="@mention the user")
async def ampuni_dosa(interaction: discord.Interaction, user: discord.Member):
  if not interaction.user.guild_permissions.administrator:
    await interaction.response.send_message("Bukan admin ga usah ngatur")
    return

  new_warning_count = remove_and_get_warnings(user.id, interaction.guild.id)
  await interaction.response.send_message(f"Dosa {user.mention} telah dihapuskan ({new_warning_count} dosa)")

# Add warnings command
@bot.tree.command(name="tambah_dosa", description="Nambah dosa user")
@app_commands.describe(user="@mention the user", amount="Amount to add (use negative to decrease)")
async def tambah_dosa(interaction: discord.Interaction, user: discord.Member, amount: int):
  if not interaction.user.guild_permissions.administrator:
    await interaction.response.send_message("Bukan admin ga usah ngatur")
    return
  
  new_warning_count = add_and_get_warnings(user.id, interaction.guild.id, amount)
  await interaction.response.send_message(f"dosa {user.mention} telah ditambahkan sebanyak {amount} (saat ini {new_warning_count} dosa)")

# Set warnings command
@bot.tree.command(name="set_dosa", description="Set dosa user awokawokaow")
@app_commands.describe(user="@mention the user", amount="Amount to set")
async def set_dosa(interaction: discord.Interaction, user: discord.Member, amount: int):
  if not interaction.user.guild_permissions.administrator:
    await interaction.response.send_message("Bukan admin ga usah ngatur")
    return

  if amount < 0:
    await interaction.response.send_message("Amount must be at least 0")
    return

  new_warning_count = set_and_get_warnings(user.id, interaction.guild.id, amount)
  await interaction.response.send_message(f"dosa {user.mention} telah diatur ke {new_warning_count} dosa")

# Check warnings command
@bot.tree.command(name="cek_dosa", description="Check dosa user")
@app_commands.describe(user="@mention the user")
async def cek_dosa(interaction: discord.Interaction, user: discord.Member):
  warning_count = get_warnings(user.id, interaction.guild.id)
  await interaction.response.send_message(f"{user.mention} memiliki {warning_count} dosa")




# TODO
download_images_toggle = False
# start downloading images after this command
@bot.tree.command(name="toggle_download_images", description="toggle downloading images after this command")
async def toggle_download_images(interaction: discord.Interaction):
  global download_images_toggle
  download_images_toggle = not download_images_toggle
  status = "Foto yg dikirim mulai sekarang **akan didownload**" if download_images_toggle else "Foto yg dikirim mulai sekarang **tidak akan didownload**"
  await interaction.response.send_message(status)

  if download_images_toggle:
    @bot.event
    async def on_message(msg):
      if msg.author == bot.user:
        return

      if msg.attachments:
        for attachment in msg.attachments:
          if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]):
            local_path = download_image(attachment.url)
            if local_path:
              print(f"Foto disimpan di {local_path}")
              try:
                  upload_to_shared_drive(local_path, drive_service, PARENT_FOLDER_ID)
              except Exception as e:
                  await msg.channel.send("Gagal mengupload foto")
                  print(f"Error upload foto: {e}")
            else:
              await msg.channel.send("Gagal mendownload foto")
              print("eror donlot foto")
  
      await bot.process_commands(msg)
  




@bot.event
async def on_member_join(member):
  await member.send(f"Selamat datang, {member.name}!")

@bot.event
async def on_message(msg):
  if msg.author == bot.user:
    return
  
  # testing purposes
  if "tes bot" == msg.content.lower():
    await msg.channel.send("Bot ini berfungsi dengan baik!")
  

  # kata kasar
  profanity_bot = ["ga guna", "useless", "butut", "rusak"]
  if "bot" in msg.content.lower() and any(word in msg.content.lower() for word in profanity_bot):
      await msg.reply("sybau")

  if any(word in msg.content.lower() for word in profanity):
    warning_count = increase_and_get_warnings(msg.author.id, msg.guild.id)    

    await msg.reply(f"Kasar kamu ya {msg.author.mention}")
    await msg.channel.send(f"{msg.author.mention}, anda sudah punya {warning_count} total dosa karena menggunakan kata kasar.")

    # TODO buat role based on berapa warning yg user punya


  # hasil gabut
  if "yo" == msg.content.lower():
    await msg.channel.send("gurt: yo")

  if "pemerintah" in msg.content.lower():
    ancaman_list = [
      "serlok tak parani", "ur not save gng", 
      "im watching u", 
      "hidupmu tidak akan lama lagi bung", 
      "keren kah begitu?", 
      "count your days", 
      "any last wish?",
      "hmph >///<",
    ]
    for ancaman in ancaman_list:
      await msg.author.send(ancaman)

  if msg.guild is None:
    if "buzzer" in msg.content.lower():
      await msg.author.send("sybau")


  await bot.process_commands(msg)



# Run the bot
bot.run(token_dc, log_handler=handler, log_level=logging.DEBUG)





# ===============================================================================













