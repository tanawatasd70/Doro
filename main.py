import os
import re
import json
import random
import asyncio
import pytz
import logging
import discord
import yt_dlp
import aiohttp
import motor.motor_asyncio
from bson import ObjectId
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from dotenv import load_dotenv
from youtubesearchpython import VideosSearch

# ==========================================
# 🌐 WEB SERVER FOR RENDER
# ==========================================
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "🤖 Doro Bot UI Engine with Music is Fully Active! ✨"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def server_on():
    t = Thread(target=run_server)
    t.start()

server_on()

# ==========================================
# ⚙️ CONFIG & BOT SETUP
# ==========================================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in environment.")

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI missing in environment. (ตั้งค่าใน Render > Environment)")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doro")

# ==========================================
# 🍃 MONGODB ATLAS CONNECTION
# ==========================================
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client["doro_bot"]

roblox_col = db["roblox_servers"]        # _id: game_key -> {name, url, image}
manual_codes_col = db["manual_codes"]    # _id: game_key -> {entries: [{code, desc}, ...]}
welcome_col = db["welcome_config"]       # _id: guild_id -> {config: {channel_id, autorole_id}}
sticky_col = db["sticky_messages"]       # _id: channel_id -> {content, message_id}
afk_col = db["afk_users"]                # _id: user_id -> {reason}
custom_responses_col = db["custom_responses"]  # _id: guild_id -> {responses: {trigger: reply}}
reminders_col = db["reminders"]          # _id: auto -> {user_id, channel_id, guild_id, remind_at, message}
warnings_col = db["warnings"]            # _id: auto -> {guild_id, user_id, reason, moderator_id, timestamp}
code_announce_col = db["code_announce"]  # _id: guild_id -> {channels: {game_key: channel_id}}
known_codes_col = db["known_codes"]      # _id: game_key -> {codes: [code, ...]}  (global baseline สำหรับตรวจจับโค้ดใหม่)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.presences = True 

bot = commands.Bot(command_prefix="!", intents=intents)

custom_responses = {
    "bot ชื่ออะไร": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักของทุกคนน~ 🤖💕",
    "whats your name": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักของทุกคนน~ 🤖💕",
    "doro ช่วยอะไรได้บ้าง": "หนูช่วยตอบคำถามทั่วไป เปิดเพลงเพราะ ๆ ให้ฟัง แล้วก็ช่วยดูแลเซิร์ฟเวอร์ได้ด้วยนะค๊าา! 🎵✨",
    "doro สวัสดี": "งื้อออ สวัสดีค่าา! ยินดีที่ได้คุยด้วยนะคะ วันนี้มีอะไรให้หนูช่วยไหมเอ่ย? 🌸",
}

vote_records = {}  
poll_result_messages = {} 

async def load_roblox_data() -> dict:
    data = {}
    async for doc in roblox_col.find():
        entry = {"name": doc["name"], "url": doc["url"]}
        if doc.get("image"):
            entry["image"] = doc["image"]
        data[doc["_id"]] = entry
    if not data:
        default_data = {"blox_fruits": {"name": "🏴‍☠️ Blox Fruits", "url": "https://www.roblox.com/"}}
        await save_roblox_data(default_data)
        return default_data
    return data

async def save_roblox_data(data: dict):
    # เขียนทับให้ตรงกับ dict ที่ส่งมาทั้งหมด (รองรับทั้งกรณีเพิ่ม/แก้ไข/ลบเกม)
    existing_ids = {doc["_id"] async for doc in roblox_col.find({}, {"_id": 1})}
    for key, val in data.items():
        await roblox_col.update_one({"_id": key}, {"$set": val}, upsert=True)
    for removed_id in existing_ids - set(data.keys()):
        await roblox_col.delete_one({"_id": removed_id})

# ==========================================
# 🔓 DYNAMIC GROUP ROLE VIEW (🐈‍⬛ BLACK CAT THEME)
# ==========================================
class DynamicGroupJoinView(discord.ui.View):
    def __init__(self, role_id: int, emoji_str: str):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.emoji_str = emoji_str
        
        btn_label = "รับยศกลุ่ม"
        if emoji_str == "🌸": btn_label = "ดอกไม้"
        elif emoji_str == "🔓": btn_label = "เข้าสู่กลุ่ม"
        elif emoji_str == "⚔️": btn_label = "รับยศนักรบ"
        elif emoji_str == "🔥": btn_label = "รับยศสายเดือด"

        btn_style = discord.ButtonStyle.danger if emoji_str == "🌸" else discord.ButtonStyle.secondary

        btn = discord.ui.Button(
            label=btn_label, 
            style=btn_style, 
            emoji=emoji_str, 
            custom_id=f"doro_dyn_join_{role_id}"
        )
        btn.callback = self.button_callback
        self.add_item(btn)

    async def button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.followup.send("❌ งื้อออ น้อนหาตัวยศนี้ในเซิร์ฟไม่เจอ แอดมินลบยศไปหรือเปล่านะ?", ephemeral=True)

        if role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(role)
                return await interaction.followup.send(f"🏃‍♂️ ถอนยศ **{role.name}** และออกจากกลุ่มเรียบร้อยค๊าา ไว้แวะมาใหม่น้าา", ephemeral=True)
            except discord.Forbidden:
                return await interaction.followup.send("❌ น้อนไม่มีสิทธิ์ถอนยศนี้ค๊าา", ephemeral=True)

        try:
            await interaction.user.add_roles(role)
            await interaction.followup.send("🎉 ยินดีต้อนรับเข้าสู่กลุ่มค๊าา! มอบยศ M͟͞E͟͞M͟͞B͟͞E͟͞R͟͞ ให้เรียบร้อย ตอนนี้ห้องลับเปิดให้เข้าแล้วน้าา~ 💕", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ น้อน Doro ไม่มีสิทธิ์แจกยศนี้ รบกวนแอดมินลากยศของบอทให้สูงกว่ายศที่จะแจกในตั้งค่าเซิร์ฟเวอร์น้าา", ephemeral=True)

class RoleSetupAdminView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=60)
        self.guild = guild
        self.selected_role_id = None
        self.selected_emoji = "🌸"

        self.group_images = [
            "https://images.alphacoders.com/133/1330962.png",
            "https://images.alphacoders.com/112/1123447.jpg"
        ]
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        role_options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        
        self.role_select = discord.ui.Select(placeholder="🎨 1. เลือกยศที่จะให้คนกดรับ...", options=role_options, row=0)
        self.role_select.callback = self.role_callback
        self.add_item(self.role_select)

        emoji_options = [
            discord.SelectOption(label="🌸 ดอกไม้ซากุระ (แบบในรูป)", value="🌸", emoji="🌸"),
            discord.SelectOption(label="🔓 กุญแจปลดล็อกห้อง", value="🔓", emoji="🔓"),
            discord.SelectOption(label="⚔️ ดาบไขว้สายบวก", value="⚔️", emoji="⚔️"),
            discord.SelectOption(label="🔥 ไฟบรรลัยกัลป์", value="🔥", emoji="🔥")
        ]
        self.emoji_select = discord.ui.Select(placeholder="✨ 2. เลือกอิโมจิประจำปุ่มกด...", options=emoji_options, row=1)
        self.emoji_select.callback = self.emoji_callback
        self.add_item(self.emoji_select)

    async def role_callback(self, interaction: discord.Interaction):
        self.selected_role_id = int(self.role_select.values[0])
        await interaction.response.defer()

    async def emoji_callback(self, interaction: discord.Interaction):
        self.selected_emoji = self.emoji_select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="🚀 ยืนยันและสร้างแผงรับยศเลย!", style=discord.ButtonStyle.success, row=2)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_role_id:
            return await interaction.response.send_message("❌ คุณพี่ลืมเลือกยศหรือเปล่าค๊าา? โปรดเลือกยศก่อนน้าา", ephemeral=True)

        await interaction.response.defer()
        role = self.guild.get_role(self.selected_role_id)
        
        embed = discord.Embed(
            title="ยินดีต้อนรับค๊าาา", 
            description=f"### ดิฉันดีใจมากที่ท่านเข้ามา 😉\n### โปรดกดอิโมจิอันนี้ {self.selected_emoji} ด้วยค่ะ เพื่อยืนยันตัวตนนะคะ🫠\n\n**แมวทมิฬ FAMILY 🐈‍⬛🖤**!",
            color=0xFFB6C1 
        )
        
        embed.set_thumbnail(url="https://i.ytimg.com/vi/jrhV4oltZd0/maxresdefault.jpg") 
        embed.set_image(url=random.choice(self.group_images)) 

        await interaction.channel.send(embed=embed, view=DynamicGroupJoinView(self.selected_role_id, self.selected_emoji))
        await interaction.delete_original_response()

# ==========================================
# 🎵 MUSIC SYSTEM ENGINE
# ==========================================
music_queues = {}  
current_songs = {} 
loop_status = {}   

# ==========================================
# ⚙️ CONFIG HELPERS (เก็บถาวรใน MongoDB Atlas — ไม่หายเมื่อบอทรีสตาร์ท/deploy ใหม่)
# ==========================================

async def get_welcome_config(guild_id: int) -> dict:
    doc = await welcome_col.find_one({"_id": guild_id})
    return doc.get("config", {}) if doc else {}

async def set_welcome_config_field(guild_id: int, field: str, value):
    await welcome_col.update_one({"_id": guild_id}, {"$set": {f"config.{field}": value}}, upsert=True)

async def unset_welcome_config_field(guild_id: int, field: str):
    await welcome_col.update_one({"_id": guild_id}, {"$unset": {f"config.{field}": ""}}, upsert=True)

async def delete_welcome_config(guild_id: int):
    await welcome_col.delete_one({"_id": guild_id})


async def get_sticky(channel_id: int):
    doc = await sticky_col.find_one({"_id": channel_id})
    if not doc:
        return None
    return {"content": doc["content"], "message_id": doc["message_id"]}

async def set_sticky(channel_id: int, content: str, message_id: int):
    await sticky_col.update_one({"_id": channel_id}, {"$set": {"content": content, "message_id": message_id}}, upsert=True)

async def delete_sticky(channel_id: int):
    old = await get_sticky(channel_id)
    await sticky_col.delete_one({"_id": channel_id})
    return old


async def get_afk(user_id: int):
    doc = await afk_col.find_one({"_id": user_id})
    return doc["reason"] if doc else None

async def set_afk(user_id: int, reason: str):
    await afk_col.update_one({"_id": user_id}, {"$set": {"reason": reason}}, upsert=True)

async def clear_afk(user_id: int):
    doc = await afk_col.find_one_and_delete({"_id": user_id})
    return doc["reason"] if doc else None


# --- 💬 ข้อความตอบกลับอัตโนมัติ (Custom Auto-Responses) ---
async def get_custom_responses(guild_id: int) -> dict:
    doc = await custom_responses_col.find_one({"_id": guild_id})
    return doc.get("responses", {}) if doc else {}

async def add_custom_response(guild_id: int, trigger: str, reply: str):
    await custom_responses_col.update_one({"_id": guild_id}, {"$set": {f"responses.{trigger}": reply}}, upsert=True)

async def remove_custom_response(guild_id: int, trigger: str) -> bool:
    doc = await custom_responses_col.find_one({"_id": guild_id})
    if not doc or trigger not in doc.get("responses", {}):
        return False
    await custom_responses_col.update_one({"_id": guild_id}, {"$unset": {f"responses.{trigger}": ""}})
    return True


# --- ⏰ ระบบแจ้งเตือน (Reminders) ---
DURATION_PATTERN = re.compile(r"(\d+)\s*(d|h|m|s|วัน|ชม|ชั่วโมง|นาที|วิ)", re.IGNORECASE)

def parse_duration(text: str):
    """แปลงข้อความเช่น '1d2h30m' หรือ '2h 30m' ให้เป็น timedelta ค่ะ คืนค่า None ถ้าอ่านไม่ออก"""
    total_seconds = 0
    found = False
    for amount, unit in DURATION_PATTERN.findall(text.strip().lower()):
        found = True
        amount = int(amount)
        unit = unit.lower()
        if unit in ("d", "วัน"):
            total_seconds += amount * 86400
        elif unit in ("h", "ชม", "ชั่วโมง"):
            total_seconds += amount * 3600
        elif unit in ("m", "นาที"):
            total_seconds += amount * 60
        elif unit in ("s", "วิ"):
            total_seconds += amount
    if not found or total_seconds <= 0:
        return None
    return timedelta(seconds=total_seconds)

async def create_reminder(user_id: int, channel_id, guild_id, remind_at: datetime, content: str):
    result = await reminders_col.insert_one({
        "user_id": user_id, "channel_id": channel_id, "guild_id": guild_id,
        "remind_at": remind_at, "message": content,
    })
    return result.inserted_id

async def get_due_reminders(now: datetime) -> list:
    return [doc async for doc in reminders_col.find({"remind_at": {"$lte": now}})]

async def get_user_reminders(user_id: int) -> list:
    return [doc async for doc in reminders_col.find({"user_id": user_id}).sort("remind_at", 1)]

async def delete_reminder(reminder_id):
    await reminders_col.delete_one({"_id": reminder_id})


# --- ⚠️ ระบบคำเตือนและ Mod-log (Warnings) ---
async def add_warning(guild_id: int, user_id: int, reason: str, moderator_id: int):
    result = await warnings_col.insert_one({
        "guild_id": guild_id, "user_id": user_id, "reason": reason,
        "moderator_id": moderator_id, "timestamp": datetime.utcnow(),
    })
    return result.inserted_id

async def get_warnings(guild_id: int, user_id: int) -> list:
    return [doc async for doc in warnings_col.find({"guild_id": guild_id, "user_id": user_id}).sort("timestamp", -1)]

async def delete_warning(warning_id) -> bool:
    result = await warnings_col.delete_one({"_id": warning_id})
    return result.deleted_count > 0


YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

def play_next_song(guild_id, vc, channel):
    if guild_id in loop_status and loop_status[guild_id] and guild_id in current_songs:
        song = current_songs[guild_id]
    elif guild_id in music_queues and len(music_queues[guild_id]) > 0:
        song = music_queues[guild_id].pop(0)
        current_songs[guild_id] = song
    else:
        if guild_id in current_songs: 
            del current_songs[guild_id]
        asyncio.run_coroutine_threadsafe(vc.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(channel.send("🎵 คิวเพลงหมดแล้ว หนูขอตัวออกจากห้องเสียงก่อนนะค๊าา~"), bot.loop)
        return

    source = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
    vc.play(source, after=lambda e: play_next_song(guild_id, vc, channel))
    asyncio.run_coroutine_threadsafe(refresh_main_menu_msg(guild_id, channel), bot.loop)

async def refresh_main_menu_msg(guild_id, channel):
    pass

# ==========================================
# ⏰ REMINDER BACKGROUND TASK LOOP
# ==========================================
@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.utcnow()
    due = await get_due_reminders(now)
    for r in due:
        try:
            content = f"⏰ **แจ้งเตือน!** {r['message']}"
            if r.get("channel_id"):
                channel = bot.get_channel(r["channel_id"])
                if channel:
                    await channel.send(f"<@{r['user_id']}> {content}")
            else:
                user = await bot.fetch_user(r["user_id"])
                if user:
                    await user.send(content)
        except Exception as e:
            logger.warning(f"reminder send failed: {type(e).__name__}: {e}")
        finally:
            await delete_reminder(r["_id"])

@check_reminders.before_loop
async def before_check_reminders():
    await bot.wait_until_ready()


# ==========================================
# 🎁 NEW GAME CODE WATCHER (auto-announce) TASK LOOP
# ==========================================
@tasks.loop(minutes=30)
async def check_new_game_codes():
    for game_key, info in GAME_CODE_SOURCES.items():
        try:
            codes = await fetch_game_codes(info["url"])
        except Exception as e:
            logger.warning(f"code-watch fetch failed for {game_key}: {type(e).__name__}: {e}")
            continue
        if not codes:
            continue

        current_set = {c for c, _ in codes}
        known = await get_known_codes(game_key)
        await save_known_codes(game_key, list(current_set))

        if known is None:
            # รอบแรกที่เห็นเกมนี้ — เก็บ baseline ไว้ก่อน ยังไม่ประกาศ (กันสแปมโค้ดเก่าทั้งหมดตอนเปิดใช้ระบบครั้งแรก)
            continue

        new_codes = [(c, d) for c, d in codes if c not in known]
        if not new_codes:
            continue

        configs = await get_all_announce_configs(game_key)
        if not configs:
            continue

        lines = [f"`{c}`" + (f" — {d}" if d else "") for c, d in new_codes[:10]]
        embed = discord.Embed(
            title=f"🎉 เจอโค้ดใหม่แล้วค่าา! — {info['label']}",
            description="\n".join(lines),
            color=0x77DD77,
        )
        embed.set_footer(text="ประกาศอัตโนมัติจากน้อง Doro 🤖 • ที่มา progameguides.com")

        for cfg in configs:
            channel_id = cfg.get("channels", {}).get(game_key)
            channel = bot.get_channel(channel_id) if channel_id else None
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.warning(f"code announce send failed (guild {cfg.get('_id')}): {type(e).__name__}: {e}")

        await asyncio.sleep(2)  # เว้นจังหวะระหว่างเกมนิดนึง กันยิงเว็บถี่เกินไป

@check_new_game_codes.before_loop
async def before_check_new_game_codes():
    await bot.wait_until_ready()
# ==========================================
# 🔍 MUSIC SEARCH MODAL
# ==========================================
class MusicSearchModal(discord.ui.Modal, title="🎵 ค้นหาและเพิ่มเพลงลงคิว"):
    def __init__(self, current_msg=None):
        super().__init__()
        self.current_msg = current_msg
        self.song_query = discord.ui.TextInput(
            label="พิมพ์ชื่อเพลง หรือ ลิงก์ YouTube ที่ต้องการค๊าา", 
            placeholder="เช่น ฝนตกไหม - Three Man Down",
            required=True
        )
        self.add_item(self.song_query)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = self.song_query.value.strip()
        guild = interaction.guild

        if not interaction.user.voice:
            await interaction.channel.send("❌ คุณพี่ต้องเข้ามาอยู่ในห้องคุยเสียงก่อนสั่งหนูเปิดเพลงนะค๊าางึมมม", delete_after=5)
            return
        await interaction.channel.send(f"🔍 น้อน Doro กำลังดำน้ำไปงมหาเพลง **'{query}'** บน YouTube แป๊บน้าน้าา...", delete_after=5)

        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ytdl:
            try:
                info = ytdl.extract_info(query, download=False)
                if 'entries' in info: 
                    info = info['entries'][0]
                song_data = {
                    'url': info['url'],
                    'title': info['title'],
                    'webpage_url': info['webpage_url'],
                    'thumbnail': info.get('thumbnail'),
                    'requester': interaction.user.display_name
                }
            except Exception as e:
                await interaction.channel.send("❌ งื้อออ หนูหาเพลงนี้ไม่เจอหรือติดบล็อกจาก YouTube ค๊าา ลองเปลี่ยนชื่อเพลงดูน้าา", delete_after=5)
                return
        guild_id = guild.id
        vc = guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        if guild_id not in music_queues: 
            music_queues[guild_id] = []
        if vc.is_playing() or vc.is_paused():
            music_queues[guild_id].append(song_data)
            await interaction.channel.send(f"📋 เพิ่มเพลง **{song_data['title']}** เข้าสู่คิวเรียบร้อยแล้วค๊าา!", delete_after=5)
        else:
            current_songs[guild_id] = song_data
            source = discord.FFmpegPCMAudio(song_data['url'], **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next_song(guild_id, vc, interaction.channel))

        target_msg = self.current_msg if self.current_msg else interaction.message

        await update_music_menu_embed(target_msg, guild)
# ==========================================
# 🎛️ MAIN UI COMMAND MENU 
# ==========================================
class BotCommandControlSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🏠 หน้าแรก / เคลียร์เมนูย่อย", description="กลับสู่หน้าจอเริ่มต้น ล้างหน้าต่างการทำงานด้านล่าง", value="main_menu"),
        ]
        for key, cat in CATEGORY_REGISTRY.items():
            options.append(discord.SelectOption(label=cat["label"], description=cat["description"], value=key))
        super().__init__(placeholder="🎛️ เลือกหมวดหมู่การทำงานของน้อน Doro ที่นี่...", min_values=1, max_values=1, options=options, custom_id="doro_main_control_select", row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        value = self.values[0]
        guild = interaction.guild
        if value == "main_menu":
            embed = generate_main_menu_embed(guild)
            await interaction.message.edit(embed=embed, view=BotControlMenuView(guild))
            return
        category = CATEGORY_REGISTRY.get(value)
        if not category:
            return
        embed = discord.Embed(
            title=category["label"],
            description="เลือกฟังก์ชันที่ต้องการจากเมนูด้านล่างนี้ได้เลยค๊าา ✨",
            color=0xFFB6C1,
        )
        await interaction.message.edit(embed=embed, view=CategoryMenuView(guild, value))


class CategoryItemSelect(discord.ui.Select):
    def __init__(self, category_key: str):
        self.category_key = category_key
        category = CATEGORY_REGISTRY[category_key]
        options = [
            discord.SelectOption(
                label=ACTION_REGISTRY[item]["label"],
                description=ACTION_REGISTRY[item]["description"],
                value=item,
            )
            for item in category["items"]
        ]
        super().__init__(placeholder="👉 เลือกฟังก์ชันที่ต้องการค๊าา...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        action = ACTION_REGISTRY.get(self.values[0])
        if not action:
            return
        embed, view = await action["build"](interaction.guild)
        await interaction.message.edit(embed=embed, view=view)


class CategoryMenuView(discord.ui.View):
    def __init__(self, guild, category_key: str):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(CategoryItemSelect(category_key))

    @discord.ui.button(label="กลับหมวดหมู่", style=discord.ButtonStyle.secondary, emoji="↩️", row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = generate_main_menu_embed(self.guild)
        await interaction.message.edit(embed=embed, view=BotControlMenuView(self.guild))


class BotControlMenuView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(BotCommandControlSelect())

    # ปุ่มลัดสำหรับฟังก์ชันที่ใช้บ่อยที่สุด กดใช้งานได้ทันทีไม่ต้องผ่าน dropdown
    @discord.ui.button(label="เพลง", style=discord.ButtonStyle.primary, emoji="🎵", row=1)
    async def quick_music_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, view = await ACTION_REGISTRY["setup_music"]["build"](self.guild)
        await interaction.message.edit(embed=embed, view=view)

    @discord.ui.button(label="ล้างแชท", style=discord.ButtonStyle.secondary, emoji="🧹", row=1)
    async def quick_clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, view = await ACTION_REGISTRY["setup_clear"]["build"](self.guild)
        await interaction.message.edit(embed=embed, view=view)

    @discord.ui.button(label="❌ ปิดแผงควบคุม", style=discord.ButtonStyle.danger, emoji="🔴", row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except:
            pass


# --- ฟังก์ชันสร้าง embed/view ของแต่ละฟังก์ชันย่อย (dispatch table แทน if/elif ยาว ๆ) ---

async def _build_music_view(guild):
    return generate_main_menu_embed(guild), MusicControlView(guild)

async def _build_soundboard_view(guild):
    embed = discord.Embed(title="🔊 ระบบเสียง Soundboard ของน้อง Doro", description="เลือกเสียงที่ต้องการปล่อยในห้องเสียงได้เลยค๊าา! ✨", color=0xF1C40F)
    return embed, SoundboardView(guild)

async def _build_clear_view(guild):
    embed = discord.Embed(
        title="🧹 ระบบจัดการและล้างข้อความในช่องแชท",
        description="คุณพี่ต้องการให้น้อน Doro จัดการช่องแชทนี้อย่างไรดีค๊าา?\n\n"
                    "🔹 **ลบตามจำนวนล่าสุด**: กวาดล้างข้อความเก่าออกตามจำนวนที่เลือก\n"
                    "⚠️ **รีเซ็ตห้องแชท (Nuke)**: ทำการโคลนและลบห้องเดิมทิ้งทันที เพื่อล้างประวัติแชททั้งหมดให้โล่ง 100% ค๊าา! *(ต้องการสิทธิ์จัดการช่องแชลเนล)*",
        color=0x34495E
    )
    return embed, ClearChannelView(guild)

async def _build_roles_view(guild):
    embed = discord.Embed(title="🛡️ ระบบจัดการยศอัตโนมัติค๊าา", description="คุณชอบยศไหนเลือกรับจากเมนูด้านล่างนี้ได้เลยนะค๊าา หรือจะกดปุ่มขอยศพิเศษพร้อมส่งเหตุผลอ้อน ๆ มาให้แอดมินดูก็ได้น้าา~ ✨", color=0xFFB6C1)
    return embed, RequestRoleView(guild)

async def _build_poll_view(guild):
    embed = discord.Embed(title="📊 ระบบสร้างคำถามโพลระดมความคิดค๊าา", description="กรุณากรอกหัวข้อคำถาม และเลือกช่องทางปล่อยโพลให้ครบถ้วนด้านล่างนี้เลยน้าา~ ✨", color=0x9B59B6)
    return embed, AskQuestionView(guild)

async def _build_roblox_view(guild):
    embed = discord.Embed(title="🎮 คลังแสง Private Server ของแก๊งเรา! 🚀", description="อยากไปฟาร์ม ไปเวล หรือไปตึงเกมไหน เลือกชื่อเกมจากเมนูด้านล่างนี้ได้เลยค๊าา\n(สำหรับแอดมินสามารถกดปุ่มเพื่อเพิ่มหรือลบเกมได้เลยนะค๊าา) ✨", color=0x00E5FF)
    roblox_data = await load_roblox_data()
    return embed, RobloxServerView(guild, roblox_data)

async def _build_game_codes_view(guild):
    embed = discord.Embed(
        title="🎮 ระบบเช็คโค้ดเกม Roblox",
        description="เลือกเกมจากเมนูด้านล่างเลยค่ะ หนูจะไปหาโค้ดล่าสุดมาให้น้าา~ 🔍",
        color=0xFFB6C1,
    )
    return embed, GameCodeView()

async def _build_kick_view(guild):
    embed = discord.Embed(title="🚫 ระบบโหวตเตะสมาชิก (โหมด Doro เอาจริง!)", description="โปรดเลือกรายชื่อคนที่ไม่น่ารักที่คุณต้องการเริ่มโหวตลงมติเตะด้านล่างนี้ได้เลยค่ะงึมมม", color=discord.Color.red())
    return embed, MemberSelectView(guild)

async def _build_welcome_view(guild):
    cfg = await get_welcome_config(guild.id)
    channel = guild.get_channel(cfg.get("channel_id")) if cfg.get("channel_id") else None
    role = guild.get_role(cfg.get("autorole_id")) if cfg.get("autorole_id") else None
    embed = discord.Embed(
        title="👋 ตั้งค่าระบบต้อนรับสมาชิกใหม่ / บอกลา / Auto-role",
        description=(
            f"📢 ห้องส่งข้อความทักทาย/บอกลาตอนนี้: {channel.mention if channel else '*ยังไม่ได้ตั้งค่า*'}\n"
            f"🎭 ยศอัตโนมัติให้สมาชิกใหม่: {role.mention if role else '*ปิดอยู่*'}\n\n"
            "เลือกห้องและยศจากเมนูด้านล่างนี้ได้เลยค่ะ\n"
            "✅ *ค่านี้บันทึกลงฐานข้อมูลถาวรแล้ว ไม่หายแม้บอทจะรีสตาร์ทหรือ deploy ใหม่*"
        ),
        color=0x1ABC9C,
    )
    return embed, WelcomeConfigView(guild)

async def _build_afk_view(guild):
    embed = discord.Embed(
        title="😴 ระบบ AFK",
        description=(
            "กดปุ่ม **ตั้งสถานะ AFK** เพื่อกรอกเหตุผล (จะแจ้งอัตโนมัติถ้ามีคนมาแท็กหาคุณ) "
            "หรือกด **ปลด AFK** เพื่อยกเลิกด้วยตัวเองได้เลยค่ะ\n\n"
            "(ระบบจะปลด AFK ให้อัตโนมัติทันทีที่คุณพิมพ์ข้อความในเซิร์ฟด้วยนะคะ)"
        ),
        color=0x95A5A6,
    )
    return embed, AFKConfigView(guild)

async def _build_sticky_view(guild):
    embed = discord.Embed(
        title="📌 ตั้งค่าข้อความปักหมุด (Sticky Message)",
        description=(
            "เลือกห้องที่ต้องการจากเมนูด้านล่าง แล้วกดปุ่ม **ตั้งข้อความปักหมุด** เพื่อพิมพ์ข้อความที่จะปักหมุดค่ะ\n"
            "ข้อความจะลอยอยู่ล่างสุดของห้องนั้นเสมอ ไม่ว่าจะมีคนแชทเพิ่มกี่ข้อความก็ตาม"
        ),
        color=0x3498DB,
    )
    return embed, StickyConfigView(guild)


async def _build_analytics_view(guild):
    embed = discord.Embed(title="📈 ศูนย์บริการข้อมูลสมาชิกเเละสถิติเชิงลึก", description="เลือกดูสถิติภาพรวม ตรวจสอบรายชื่อแอดมิน หรือค้นหาคนไร้ยศในเซิร์ฟเวอร์ได้เลยค๊าา ✨", color=0x2ECC71)
    return embed, MemberAnalyticsView(guild)

async def _build_help_view(guild):
    embed = discord.Embed(
        title="📘 สมุดคู่มือและบันทึกความสามารถของน้อน Doro 🤖✨",
        description=(
            "งื้อออ สวัสดีค่าา! หนูคือ **Doro** ยัยบอทสุดน่ารักที่จะมาช่วยดูแลและสร้างสีสันให้เซิร์ฟเวอร์ของทุกคนค๊าา 💕 หนูทำอะไรได้เยอะแยะเลยนะ ลองมาดูกันเยย! \n\n"
            "**🐈‍⬛ ความสามารถหลักของหนู (ฟังก์ชันเด่น):**\n"
            "* **🎛️ แผงควบคุม UI อัจฉริยะ**: กดสั่งงานง่าย ๆ ผ่านปุ่มและเมนู Dropdown ไม่ต้องพิมพ์คำสั่งให้เหนื่อยค๊าา\n"
            "* **🎵 มิวสิคบอร์ดแยกแท็บ**: เข้าหน้าต่างควบคุมเพลงและคิวได้แบบเป็นสัดส่วนผ่าน Dropdown\n"
            "* **🧹 ระบบล้างแชทและรีเซ็ตห้อง**: สั่งกวาดล้างข้อความขยะ หรือล้างห้องแชทให้ขาวสะอาด 100% ด้วยปุ่ม Nuke\n"
            "* **🛡️ ระบบแจกและขอยศสุดตึง**: เลือกรับยศเอง หรือส่งคำขออ้อน ๆ มาขอยศพิเศษก็ได้น้าา\n"
            "* **📊 โพลระดมความคิด**: สร้างคำถามและส่งไปห้องที่ต้องการ พร้อมระบบนับคะแนนเรียลไทม์\n"
            "* **🎮 คลังแสงเซิร์ฟ Roblox**: รวมลิงก์ตั๋วเข้า Private Server เกมโปรดของแก๊งเราไว้ที่เดียว\n"
            "* **🚫 ศาลเตี้ยโหวตเตะ**: เปิดวาระโหวตลงมติเพื่อดีดออกจากห้องเสียงหรือเซิร์ฟเวอร์\n"
            "* **📊 ระบบตรวจสอบสมาชิก (Analytics)**: เช็คสถิติแบบเรียลไทม์ ตรวจดูทีมงาน และค้นหาคนไร้ยศ\n\n"
            "--------------------------------------------------\n"
            "**✍️ สรุปคำสั่งพิมพ์ด่วน (Quick Commands):**\n"
            "🔹 **`doro เมนู` / `doro menu` / `doro คำสั่งเพลง` / `/menu`** : เรียกเปิดแผงควบคุมระบบ UI ทั้งหมดค๊าา\n"
            "🔹 **`doro ให้ยศ` / `doro addrole`** : หน้าต่างด่วนสำหรับแอดมินแจกยศกลุ่มความเร็วสูง\n"
            "🔹 **`doro ลบข้อความ <จำนวน>`** : สั่งเคลียร์ข้อความขยะในห้องแชท\n"
            "🔹 **`doro เล่น <ชื่อเพลง/ลิงก์>`** : สั่งน้อน Doro ดำน้ำไปเปิดเพลงค๊าา 🎵\n"
            "🔹 **`doro สร้างปุ่มรับยศ`** : สั่งเปิดแผงตั้งค่า UI สร้างระบบรับยศแมวทมิฬกล่องสีดำสุดเท่ 🖤"
        ),
        color=discord.Color.magenta()
    )
    return embed, BackToMainOnlyView(guild)


# ==========================================
# 💬 CUSTOM AUTO-RESPONSES
# ==========================================
class AddCustomResponseModal(discord.ui.Modal, title="➕ เพิ่มข้อความตอบกลับอัตโนมัติ"):
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.trigger_input = discord.ui.TextInput(
            label="คำที่ต้องการให้บอทจับ (พิมพ์เล็กทั้งหมด)",
            placeholder="เช่น doro กินข้าวยัง", max_length=200, required=True,
        )
        self.reply_input = discord.ui.TextInput(
            label="ข้อความที่บอทจะตอบกลับ", style=discord.TextStyle.paragraph,
            max_length=1500, required=True,
        )
        self.add_item(self.trigger_input)
        self.add_item(self.reply_input)

    async def on_submit(self, interaction: discord.Interaction):
        trigger = self.trigger_input.value.strip().lower()
        reply = self.reply_input.value.strip()
        await add_custom_response(self.guild_id, trigger, reply)
        await interaction.response.send_message(f"✅ เพิ่มข้อความตอบกลับสำหรับคำว่า `{trigger}` เรียบร้อยค่ะ", ephemeral=True)


class RemoveCustomResponseModal(discord.ui.Modal, title="🗑️ ลบข้อความตอบกลับอัตโนมัติ"):
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.trigger_input = discord.ui.TextInput(
            label="พิมพ์คำที่ต้องการลบให้ตรงเป๊ะ", placeholder="เช่น doro กินข้าวยัง", required=True,
        )
        self.add_item(self.trigger_input)

    async def on_submit(self, interaction: discord.Interaction):
        trigger = self.trigger_input.value.strip().lower()
        removed = await remove_custom_response(self.guild_id, trigger)
        if removed:
            await interaction.response.send_message(f"🗑️ ลบข้อความตอบกลับ `{trigger}` แล้วค่ะ", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ หาไม่เจอคำว่า `{trigger}` ในรายการที่ตั้งไว้ค่ะ", ephemeral=True)


class CustomResponseConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="ดูรายการทั้งหมด", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def view_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        dynamic = await get_custom_responses(self.guild.id)
        lines = []
        if custom_responses:
            lines.append("**🌸 ค่าเริ่มต้นของระบบ:**")
            lines.extend(f"🔹 `{k}`" for k in custom_responses)
        if dynamic:
            lines.append("\n**⚙️ ตั้งเพิ่มเองในเซิร์ฟนี้:**")
            lines.extend(f"🔸 `{k}` → {v[:60]}" for k, v in dynamic.items())
        if not lines:
            lines = ["ยังไม่มีข้อความตอบกลับอัตโนมัติเลยค่ะ"]
        embed = discord.Embed(title="📋 รายการข้อความตอบกลับอัตโนมัติ", description="\n".join(lines)[:4000], color=0x9B59B6)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="เพิ่มข้อความตอบกลับ", style=discord.ButtonStyle.success, emoji="➕", row=0)
    async def add_response(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะเพิ่มได้ค่ะ", ephemeral=True)
        await interaction.response.send_modal(AddCustomResponseModal(self.guild.id))

    @discord.ui.button(label="ลบข้อความตอบกลับ", style=discord.ButtonStyle.danger, emoji="🗑️", row=0)
    async def remove_response(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะลบได้ค่ะ", ephemeral=True)
        await interaction.response.send_modal(RemoveCustomResponseModal(self.guild.id))

    @discord.ui.button(label="🔙 กลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🪪 SERVER / USER INFO CARDS
# ==========================================
class UserInfoSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 เลือกสมาชิกที่ต้องการดูข้อมูล...", row=0)
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        member = self.guild.get_member(self.values[0].id)
        if not member:
            return
        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
        embed = discord.Embed(
            title=f"👤 ข้อมูลสมาชิก: {member.display_name}",
            color=member.color if member.color.value else 0x3498DB,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏷️ ชื่อผู้ใช้", value=str(member), inline=True)
        embed.add_field(name="🆔 User ID", value=str(member.id), inline=True)
        embed.add_field(name="🤖 บอท?", value="ใช่" if member.bot else "ไม่ใช่", inline=True)
        embed.add_field(name="📅 สมัคร Discord เมื่อ", value=discord.utils.format_dt(member.created_at, style="D"), inline=True)
        embed.add_field(name="📥 เข้าเซิร์ฟเมื่อ", value=discord.utils.format_dt(member.joined_at, style="D") if member.joined_at else "ไม่ทราบ", inline=True)
        embed.add_field(name="🟢 สถานะ", value=str(member.status).title(), inline=True)
        embed.add_field(name=f"🎭 ยศทั้งหมด ({len(roles)})", value=", ".join(roles[:15]) if roles else "ไม่มียศ", inline=False)
        await interaction.message.edit(embed=embed, view=InfoCardView(self.guild))


class InfoCardView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(UserInfoSelect(guild))

    @discord.ui.button(label="ข้อมูลเซิร์ฟเวอร์", style=discord.ButtonStyle.primary, emoji="🏠", row=1)
    async def server_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = self.guild
        embed = discord.Embed(title=f"🏠 ข้อมูลเซิร์ฟเวอร์: {guild.name}", color=0x1ABC9C)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="👑 เจ้าของเซิร์ฟ", value=str(guild.owner) if guild.owner else "ไม่ทราบ", inline=True)
        embed.add_field(name="🆔 Server ID", value=str(guild.id), inline=True)
        embed.add_field(name="📅 สร้างเมื่อ", value=discord.utils.format_dt(guild.created_at, style="D"), inline=True)
        embed.add_field(name="👥 จำนวนสมาชิก", value=str(guild.member_count), inline=True)
        embed.add_field(name="🗂️ จำนวนห้อง", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="🎭 จำนวนยศ", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="🚀 ระดับ Boost", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="🔙 กลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# ⏰ REMINDERS
# ==========================================
class ReminderModal(discord.ui.Modal, title="⏰ ตั้งการแจ้งเตือน"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.time_input = discord.ui.TextInput(
            label="เวลา (เช่น 10m, 2h, 1d3h30m)",
            placeholder="ใช้ d=วัน h=ชม m=นาที s=วิ เช่น 1h30m", required=True, max_length=50,
        )
        self.message_input = discord.ui.TextInput(
            label="ข้อความที่จะแจ้งเตือน", style=discord.TextStyle.paragraph, max_length=1000, required=True,
        )
        self.dm_input = discord.ui.TextInput(
            label="ส่งเป็น DM ไหม? (พิมพ์ ใช่ หรือ ไม่)", placeholder="ไม่ (ค่าเริ่มต้น = ส่งในห้องนี้)", required=False, max_length=10,
        )
        self.add_item(self.time_input)
        self.add_item(self.message_input)
        self.add_item(self.dm_input)

    async def on_submit(self, interaction: discord.Interaction):
        delta = parse_duration(self.time_input.value)
        if not delta:
            return await interaction.response.send_message(
                "❌ อ่านรูปแบบเวลาไม่ออกค่ะ ลองใหม่เช่น `10m`, `2h`, `1d3h30m` นะคะ", ephemeral=True,
            )
        remind_at = datetime.utcnow() + delta
        want_dm = self.dm_input.value.strip().lower() in ("ใช่", "yes", "y", "dm")
        target_channel_id = None if want_dm else self.channel.id
        await create_reminder(
            user_id=interaction.user.id,
            channel_id=target_channel_id,
            guild_id=interaction.guild.id if interaction.guild else None,
            remind_at=remind_at,
            content=self.message_input.value.strip(),
        )
        where = "ทาง DM" if want_dm else f"ในห้อง {self.channel.mention}"
        await interaction.response.send_message(
            f"⏰ ตั้งการแจ้งเตือนแล้วค่ะ! หนูจะเตือน{where} ในอีก **{self.time_input.value.strip()}** น้าา", ephemeral=True,
        )


class ReminderConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="ตั้งการแจ้งเตือนใหม่", style=discord.ButtonStyle.success, emoji="⏰", row=0)
    async def new_reminder(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReminderModal(interaction.channel))

    @discord.ui.button(label="ดูรายการแจ้งเตือนของฉัน", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def list_reminders(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        reminders = await get_user_reminders(interaction.user.id)
        if not reminders:
            return await interaction.followup.send("ยังไม่มีการแจ้งเตือนที่ตั้งไว้เลยค่ะ", ephemeral=True)
        lines = []
        for r in reminders[:15]:
            ts = discord.utils.format_dt(r["remind_at"].replace(tzinfo=timezone.utc), style="R")
            lines.append(f"🔹 {ts} — {r['message'][:80]}")
        embed = discord.Embed(title="📋 รายการแจ้งเตือนของคุณ", description="\n".join(lines), color=0xF39C12)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 กลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# ⚠️ WARNINGS / MOD-LOG
# ==========================================
class WarningReasonModal(discord.ui.Modal, title="⚠️ เพิ่มคำเตือนสมาชิก"):
    def __init__(self, guild_id: int, target: discord.Member, moderator_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.target = target
        self.moderator_id = moderator_id
        self.reason_input = discord.ui.TextInput(
            label="เหตุผลของคำเตือน", style=discord.TextStyle.paragraph, max_length=500, required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await add_warning(self.guild_id, self.target.id, self.reason_input.value.strip(), self.moderator_id)
        await interaction.response.send_message(f"⚠️ เพิ่มคำเตือนให้ **{self.target.display_name}** เรียบร้อยค่ะ", ephemeral=True)


class DeleteWarningSelect(discord.ui.Select):
    def __init__(self, warnings: list):
        options = [
            discord.SelectOption(label=w["reason"][:90] or "(ไม่มีรายละเอียด)", description=f"ID: {str(w['_id'])[-6:]}", value=str(w["_id"]))
            for w in warnings[:25]
        ]
        super().__init__(placeholder="🗑️ เลือกคำเตือนที่ต้องการลบ...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not (interaction.user.guild_permissions.kick_members or interaction.user.guild_permissions.manage_messages):
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ถึงจะลบคำเตือนได้ค่ะ", ephemeral=True)
        removed = await delete_warning(ObjectId(self.values[0]))
        if removed:
            await interaction.response.send_message("🗑️ ลบคำเตือนนั้นแล้วค่ะ", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ลบไม่สำเร็จ อาจถูกลบไปแล้วค่ะ", ephemeral=True)


class WarningTargetSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 เลือกสมาชิกที่ต้องการจัดการคำเตือน...", row=0)
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        member = self.guild.get_member(self.values[0].id)
        if not member:
            return await interaction.response.send_message("❌ หาสมาชิกคนนี้ในเซิร์ฟไม่เจอค่ะ", ephemeral=True)
        view: WarningConfigView = self.view
        view.selected_member = member
        await interaction.response.send_message(f"เลือก **{member.display_name}** แล้วค่ะ กดปุ่มด้านล่างต่อได้เลย", ephemeral=True)


class WarningConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.selected_member = None
        self.add_item(WarningTargetSelect(guild))

    @discord.ui.button(label="เพิ่มคำเตือน", style=discord.ButtonStyle.danger, emoji="⚠️", row=1)
    async def add_warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.kick_members or interaction.user.guild_permissions.manage_messages):
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Kick Members หรือ Manage Messages ถึงจะเตือนได้ค่ะ", ephemeral=True)
        if not self.selected_member:
            return await interaction.response.send_message("❌ กรุณาเลือกสมาชิกจากเมนูด้านบนก่อนค่ะ", ephemeral=True)
        await interaction.response.send_modal(WarningReasonModal(self.guild.id, self.selected_member, interaction.user.id))

    @discord.ui.button(label="ดูคำเตือน", style=discord.ButtonStyle.primary, emoji="📋", row=1)
    async def view_warns(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_member:
            return await interaction.response.send_message("❌ กรุณาเลือกสมาชิกจากเมนูด้านบนก่อนค่ะ", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        warnings = await get_warnings(self.guild.id, self.selected_member.id)
        if not warnings:
            return await interaction.followup.send(f"🎉 **{self.selected_member.display_name}** ยังไม่เคยโดนเตือนเลยค่ะ", ephemeral=True)
        lines = []
        for w in warnings[:15]:
            mod = self.guild.get_member(w["moderator_id"])
            mod_name = mod.display_name if mod else str(w["moderator_id"])
            ts = discord.utils.format_dt(w["timestamp"].replace(tzinfo=timezone.utc), style="D")
            lines.append(f"🔸 `{str(w['_id'])[-6:]}` — {w['reason'][:80]} _(โดย {mod_name}, {ts})_")
        embed = discord.Embed(
            title=f"⚠️ ประวัติคำเตือนของ {self.selected_member.display_name} ({len(warnings)} ครั้ง)",
            description="\n".join(lines), color=0xE74C3C,
        )
        del_view = discord.ui.View(timeout=120)
        del_view.add_item(DeleteWarningSelect(warnings))
        await interaction.followup.send(embed=embed, view=del_view, ephemeral=True)

    @discord.ui.button(label="🔙 กลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


async def _build_custom_responses_view(guild):
    embed = discord.Embed(
        title="💬 ระบบข้อความตอบกลับอัตโนมัติ (Custom Auto-Responses)",
        description="ตั้งคำที่ต้องการให้น้อน Doro จับและตอบกลับอัตโนมัติในเซิร์ฟนี้ได้เลยค่ะ\nกดปุ่มด้านล่างเพื่อดู เพิ่ม หรือลบรายการได้เลยน้าา ✨",
        color=0x9B59B6,
    )
    return embed, CustomResponseConfigView(guild)

async def _build_info_card_view(guild):
    embed = discord.Embed(
        title="🪪 การ์ดข้อมูลเซิร์ฟเวอร์และสมาชิก",
        description="เลือกสมาชิกจากเมนูเพื่อดูการ์ดข้อมูล หรือกดปุ่มเพื่อดูข้อมูลเซิร์ฟเวอร์ได้เลยค่ะ ✨",
        color=0x3498DB,
    )
    return embed, InfoCardView(guild)

async def _build_reminder_view(guild):
    embed = discord.Embed(
        title="⏰ ระบบตั้งการแจ้งเตือน (Reminders)",
        description="กดปุ่มด้านล่างเพื่อตั้งการแจ้งเตือนใหม่ หรือดูรายการที่ตั้งไว้ได้เลยค่ะ\nหนูจะเช็คทุก ๆ 30 วินาทีน้าา~ ⏱️",
        color=0xF39C12,
    )
    return embed, ReminderConfigView(guild)

async def _build_warnings_view(guild):
    embed = discord.Embed(
        title="⚠️ ระบบคำเตือนและ Mod-log",
        description="เลือกสมาชิกจากเมนูด้านล่าง จากนั้นกดปุ่มเพื่อเพิ่มหรือดูคำเตือนได้เลยค่ะ\n*(ต้องมีสิทธิ์ Kick Members หรือ Manage Messages)*",
        color=0xE74C3C,
    )
    return embed, WarningConfigView(guild)


ACTION_REGISTRY = {
    "setup_music": {"label": "🎵 เปิดระบบควบคุมและเล่นเพลง", "description": "เข้าสู่หน้าต่างควบคุมมิวสิคบอร์ด เปิดเพลง/เลือกเพลงค๊าา", "build": _build_music_view},
    "setup_soundboard": {"label": "🔊 เปิดระบบ Soundboard", "description": "ปล่อยเสียงเอฟเฟกต์น่ารักๆ ในห้องเสียง", "build": _build_soundboard_view},
    "setup_clear": {"label": "🧹 เปิดระบบล้างข้อความแชท", "description": "ลบข้อความขยะ/รีเซ็ตล้างห้องแชทให้เกลี้ยงในพริบตา", "build": _build_clear_view},
    "setup_roles": {"label": "🛡️ เปิดระบบจัดการ/ขอยศ", "description": "เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศสุดน่ารัก", "build": _build_roles_view},
    "setup_poll": {"label": "📊 เปิดระบบสร้างคำถามโพล", "description": "สร้างโพลน่ารัก ๆ เพื่อโหวตเลือกคำตอบกันเถอะ", "build": _build_poll_view},
    "roblox_servers": {"label": "🎮 รวมลิงก์ Private Server Roblox", "description": "คลังแสงลิงก์เซิร์ฟเวอร์วีเกมต่าง ๆ ของชาว Robloxค๊าา", "build": _build_roblox_view},
    "game_codes": {"label": "🎁 เช็คโค้ดเกม Roblox", "description": "ดูโค้ดล่าสุดของเกมยอดฮิต พร้อมปุ่มคัดลอกโค้ด", "build": _build_game_codes_view},
    "setup_kick": {"label": "🚫 เริ่มวาระโหวตเตะสมาชิก", "description": "เลือกคนที่ทำตัวไม่น่ารักเพื่อเริ่มโหวตเตะกันค่ะ!", "build": _build_kick_view},
    "setup_welcome": {"label": "👋 ตั้งค่าต้อนรับสมาชิกใหม่ & Auto-role", "description": "ตั้งห้องทักทาย/บอกลา และแจกยศอัตโนมัติให้คนเข้าใหม่", "build": _build_welcome_view},
    "setup_afk": {"label": "😴 ระบบ AFK", "description": "ตั้ง/ปลดสถานะไม่อยู่ พร้อมเหตุผลบอกคนที่มาแท็กหา", "build": _build_afk_view},
    "setup_sticky": {"label": "📌 ตั้งค่าข้อความปักหมุด (Sticky)", "description": "ปักข้อความให้ลอยอยู่ล่างสุดของห้องนี้เสมอ", "build": _build_sticky_view},
    "setup_analytics": {"label": "📊 ตรวจสอบข้อมูลสมาชิกกลุ่ม (NEW!)", "description": "เช็คสถิติแบบเรียลไทม์ ตรวจสอบแอดมิน และคนไม่มียศค๊าา", "build": _build_analytics_view},
    "setup_custom_responses": {"label": "💬 ข้อความตอบกลับอัตโนมัติ", "description": "ตั้ง/ดู/ลบคำที่บอทจะตอบกลับอัตโนมัติในเซิร์ฟนี้", "build": _build_custom_responses_view},
    "setup_warnings": {"label": "⚠️ คำเตือน & Mod-log", "description": "เพิ่ม/ดู/ลบคำเตือนของสมาชิก สำหรับทีมงาน", "build": _build_warnings_view},
    "setup_info_cards": {"label": "🪪 การ์ดข้อมูลเซิร์ฟ/สมาชิก", "description": "ดูข้อมูลเซิร์ฟเวอร์หรือการ์ดข้อมูลของสมาชิกแต่ละคน", "build": _build_info_card_view},
    "setup_reminders": {"label": "⏰ ตั้งการแจ้งเตือน (Reminders)", "description": "ตั้งเตือนตัวเองในอนาคต ผ่าน DM หรือในห้องแชท", "build": _build_reminder_view},
    "show_commands": {"label": "📖 ดูคู่มือคำสั่งบอททั้งหมด", "description": "มาดูคู่มือการสั่งงานและบันทึกความสามารถน้อน Doro กันงับ", "build": _build_help_view},
}

CATEGORY_REGISTRY = {
    "cat_music": {"label": "🎵 บันเทิง", "description": "เพลง และ Soundboard", "items": ["setup_music", "setup_soundboard"]},
    "cat_manage": {"label": "🛡️ จัดการเซิร์ฟเวอร์", "description": "ล้างแชท / ยศ / โหวตเตะ / ต้อนรับ / AFK / Sticky / ตอบกลับอัตโนมัติ / คำเตือน", "items": ["setup_clear", "setup_roles", "setup_kick", "setup_welcome", "setup_afk", "setup_sticky", "setup_custom_responses", "setup_warnings"]},
    "cat_info": {"label": "📊 ข้อมูล & โพล", "description": "สร้างโพล / เช็คสถิติสมาชิก / การ์ดข้อมูล / แจ้งเตือน", "items": ["setup_poll", "setup_analytics", "setup_info_cards", "setup_reminders"]},
    "cat_roblox": {"label": "🎮 Roblox", "description": "ลิงก์เซิร์ฟและโค้ดเกม", "items": ["roblox_servers", "game_codes"]},
    "cat_help": {"label": "📖 คู่มือคำสั่ง", "description": "ดูคู่มือความสามารถของ Doro", "items": ["show_commands"]},
}
def generate_main_menu_embed(guild):
    guild_id = guild.id
    song = current_songs.get(guild_id)
    vc = guild.voice_client
    embed = discord.Embed(
        title="⚙️ Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก ❤️‍🔥", 
        description="ยินดีต้อนรับค๊าา! ตอนนี้ปุ่มควบคุมถูกรวบรวมเข้าไปอยู่ในเมนู Dropdown แถบด้านล่าง นายสามารถเลือกโหมดใช้งานเราได้เลยน้าา ✨", 
        color=0xFFB6C1
    )
    if vc and vc.is_connected() and song:
        status_str = "🟢 กำลังบรรเลงเพลงอย่างเพลิดเพลิน" if not vc.is_paused() else "⏸️ พักเสียงเพลงชั่วคราว"
        embed.add_field(
            name="🎵 Status การเล่นเพลงปัจจุบัน",
            value=f"**เพลง:** [{song['title']}]({song['webpage_url']})\n**ผู้ขอเพลง:** {song['requester']}\n**สถานะ:** {status_str}",
            inline=False
        )
        if song.get('thumbnail'):
            embed.set_thumbnail(url=song['thumbnail'])
        q_txt = "\n".join([f"🔹 {idx+1}. {s['title'][:45]}" for idx, s in enumerate(music_queues.get(guild_id, [])[:3])])
        if q_txt:
            embed.add_field(name="📋 คิวเพลงถัดไปในแถว", value=q_txt, inline=False)
    else:
        embed.add_field(
            name="🎵 Status การเล่นเพลงปัจจุบัน",
            value="❌ ยังไม่ได้เปิดเพลง หรือน้อน Doro ยังไม่ได้เข้าห้องคุยเสียงค๊าา",
            inline=False
        )
        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
    return embed
async def update_music_menu_embed(message, guild):
    try:
        if message:
            await message.edit(embed=generate_main_menu_embed(guild), view=MusicControlView(guild))
    except Exception as e:
        logger.error(f"Error updating music menu: {e}")
class BackToMainOnlyView(discord.ui.View):
    def __init__(self, guild): 
        super().__init__(timeout=None)
        self.guild = guild
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))
# ==========================================
# 🎵 MUSIC CONTROL VIEW 
# ==========================================
class MusicControlView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="📥 Join ห้องเสียง", style=discord.ButtonStyle.primary, emoji="🎙️", row=0)
    async def join_vc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user.voice:
            vc = interaction.guild.voice_client
            if not vc:
                await interaction.user.voice.channel.connect()
                await interaction.channel.send(f"📥 น้อน Doro วิ่งดุ๊กๆ เข้าห้อง **{interaction.user.voice.channel.name}** แล้วค๊าา!", delete_after=3)
            else:
                await vc.move_to(interaction.user.voice.channel)
        else:
            await interaction.channel.send("❌ คุณพี่ต้องเข้าห้องเสียงก่อนน้าา หนูจะได้ตามไปถูกห้องงับ", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild)
    @discord.ui.button(label="🔍 พิมพ์ชื่อเพลง (Play)", style=discord.ButtonStyle.success, emoji="🎵", row=0)
    async def search_play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MusicSearchModal(current_msg=interaction.message))
    @discord.ui.button(label="⏭️ ข้ามเพลง (Skip)", style=discord.ButtonStyle.secondary, emoji="⏩", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            loop_status[self.guild.id] = False
            vc.stop()
            await interaction.channel.send("⏭️ น้อน Doro สะบัดมือข้ามเพลงให้แล้วค๊าา!", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild)

    @discord.ui.button(label="⏹️ Stop & ล้างคิวเพลง", style=discord.ButtonStyle.danger, emoji="🛑", row=1)
    async def stop_music_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild_id = self.guild.id
        vc = interaction.guild.voice_client
        music_queues[guild_id] = []
        if guild_id in current_songs: 
            del current_songs[guild_id]
        if vc: 
            await vc.disconnect()
        await interaction.channel.send("⏹️ เคลียร์คิวเพลงเกลี้ยงแผงเรียบร้อยค๊าา!", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild)
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))
# ==========================================
# 🧹 CLEAR CHANNEL COMPONENTS
# ==========================================
class CustomClearModal(discord.ui.Modal, title="🧹 ระบุจำนวนข้อความที่ต้องการลบ"):
    def __init__(self):
        super().__init__()
        self.amount_input = discord.ui.TextInput(
            label="ต้องการลบกี่ข้อความดีค๊าา? (ใส่ตัวเลข 1-100)",
            placeholder="เช่น 35",
            required=True
        )
        self.add_item(self.amount_input)
    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ คุณพี่ไม่มีสิทธิ์จัดการข้อความน้าา", ephemeral=True)
        try:
            amt = int(self.amount_input.value.strip())
            if amt < 1 or amt > 100:
                return await interaction.response.send_message("❌ กรุณาระบุตัวเลขระหว่าง 1 ถึง 100 ค๊าา", ephemeral=True)
            await interaction.response.defer()
            deleted = await interaction.channel.purge(limit=amt)
            await interaction.channel.send(f"🧹 น้อน Doro กวาดใบไม้และลบข้อความขยะออกไปให้แล้ว {len(deleted)} ข้อความค๊าา! ✨", delete_after=4)
        except ValueError:
            await interaction.response.send_message("❌ กรุณากรอกเฉพาะตัวเลขจำนวนเต็มเท่านั้นค๊าา", ephemeral=True)
class ClearChannelView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
    async def do_purge(self, interaction: discord.Interaction, limit: int):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ คุณพี่ไม่มีสิทธิ์ในการจัดการข้อความนะค๊างึมมม", ephemeral=True)
        await interaction.response.defer()
        deleted = await interaction.channel.purge(limit=limit)
        await interaction.channel.send(f"🧹 น้อน Doro ใช้ไม้กวาดวิเศษเคลียร์ข้อความให้แล้ว {len(deleted)} ข้อความค๊าา! ✨", delete_after=4)
    @discord.ui.button(label="🧹 ลบ 5 แชท", style=discord.ButtonStyle.secondary, row=0)
    async def clear_5(self, interaction: discord.Interaction, btn):
        await self.do_purge(interaction, 5)
    @discord.ui.button(label="🧹 ลบ 10 แชท", style=discord.ButtonStyle.secondary, row=0)
    async def clear_10(self, interaction: discord.Interaction, btn):
        await self.do_purge(interaction, 10)
    @discord.ui.button(label="🔥 ลบ 50 แชท", style=discord.ButtonStyle.secondary, row=0)
    async def clear_50(self, interaction: discord.Interaction, btn):
        await self.do_purge(interaction, 50)
    @discord.ui.button(label="✍️ กำหนดจำนวนเอง", style=discord.ButtonStyle.primary, row=0)
    async def clear_custom(self, interaction: discord.Interaction, btn):
        await interaction.response.send_modal(CustomClearModal())

    @discord.ui.button(label="🚨 รีเซ็ตห้องแชท (Nuke Channel)", style=discord.ButtonStyle.danger, emoji="💥", row=1)
    async def nuke_channel_btn(self, interaction: discord.Interaction, btn):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ คุณพี่ต้องมีสิทธิ์ 'จัดการช่องแชลเนล' ถึงจะสั่งระเบิดห้องได้นะค๊าา", ephemeral=True)
        await interaction.response.defer()
        current_channel = interaction.channel
        new_channel = await current_channel.clone(reason="Doro UI Nuke / Channel Reset Action")
        await new_channel.edit(position=current_channel.position)
        await current_channel.delete(reason="Doro UI Nuke / Channel Reset Action")

        embed_nuke = discord.Embed(
            title="💥 ห้องแชทนี้ถูกรีเซ็ตเรียบร้อยแล้วค๊าา! (Channel Nuked Successfully)",
            description=f"🧹 น้อน Doro จัดการระเบิดแชทเก่าทิ้ง และกวาดข้อมูลขยะออกหมดแล้วค๊าา! ✨\n\n*ผู้สั่งรีเซ็ตห้อง: {interaction.user.mention}*",
            color=0xFF3E3E
        )
        embed_nuke.set_image(url="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2I4N2I5M2M5MmE0MDRmYjllNWE2ZGNmMDFlNTAwYjRjYmU0Zjg2ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hog2UAsK791U1mZ5r9/giphy.gif")
        await new_channel.send(embed=embed_nuke, delete_after=3)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.success, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

# =====================================================================
# 📊 UPDATE FEATURE: MEMBER ANALYTICS SYSTEM (ระบบเปลี่ยนหน้า ไม่สร้างกล่องแชทใหม่)
# =====================================================================
class BulkAssignRoleSelect(discord.ui.Select):
    def __init__(self, guild):
        self.guild = guild
        me_top_role = guild.me.top_role if guild.me else None
        roles = [
            r for r in guild.roles
            if r.name != "@everyone" and not r.managed and (me_top_role is None or r < me_top_role)
        ]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🎁 เลือกยศที่จะแจกให้คนไร้ยศทั้งหมดค๊าา...", options=options or [discord.SelectOption(label="ไม่มียศให้เลือก", value="none")])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.values[0] == "none":
            return await interaction.followup.send("❌ ไม่มียศที่บอทสามารถแจกได้ (เช็คลำดับยศของบอทด้วยนะคะ)", ephemeral=True)
        role = interaction.guild.get_role(int(self.values[0]))
        if not role:
            return await interaction.followup.send("❌ ไม่พบยศนี้แล้วค่ะ", ephemeral=True)
        no_role_members = [m for m in interaction.guild.members if not m.bot and len(m.roles) == 1]
        if not no_role_members:
            return await interaction.followup.send("🎉 ไม่มีใครไร้ยศแล้วค่ะตอนนี้!", ephemeral=True)
        success, failed = 0, 0
        for m in no_role_members:
            try:
                await m.add_roles(role, reason=f"Bulk assign by {interaction.user}")
                success += 1
            except Exception as e:
                failed += 1
                logger.warning(f"bulk role assign failed for {m}: {type(e).__name__}: {e}")
            await asyncio.sleep(0.5)  # กันโดน rate limit ของ Discord ตอนแจกทีละหลายคน
        msg = f"✅ แจกยศ **{role.name}** ให้สมาชิก **{success}** คนเรียบร้อยค๊าา!"
        if failed:
            msg += f"\n⚠️ มี **{failed}** คนที่แจกไม่สำเร็จ (เช็คสิทธิ์/ลำดับยศของบอทด้วยนะคะ)"
        await interaction.followup.send(msg, ephemeral=True)


class MemberAnalyticsView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="📈 สถิติภาพรวมเซิร์ฟ", style=discord.ButtonStyle.success, emoji="📊", row=0)
    async def server_stats(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()

        all_members = self.guild.member_count
        bots = len([m for m in self.guild.members if m.bot])
        humans = all_members - bots
        online_humans = len([m for m in self.guild.members if not m.bot and m.status != discord.Status.offline])
        in_vc = len([m for m in self.guild.members if m.voice])

        embed = discord.Embed(title=f"📈 สถิติประชากรของ {self.guild.name}", color=0x2ECC71)
        embed.add_field(name="👥 ประชากรทั้งหมด", value=f"**{all_members}** คน (มนุษย์: {humans} | บอท: {bots})", inline=False)
        embed.add_field(name="🟢 กำลังออนไลน์ (มนุษย์)", value=f"**{online_humans}** คน", inline=True)
        embed.add_field(name="🔊 กำลังคุยในห้องเสียง", value=f"**{in_vc}** คน", inline=True)

        # เปลี่ยนหน้าข้อมูลของกล่องเดิมโดยใช้ View ของตัวเอง เพื่อให้คงปุ่มสำหรับย้อนกลับหรือเปลี่ยนหัวข้อได้
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="👑 รายชื่อทีมงานที่ออนไลน์", style=discord.ButtonStyle.secondary, emoji="🛡️", row=0)

    async def staff_list(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        staff = [m.mention for m in self.guild.members if not m.bot and m.guild_permissions.kick_members and m.status != discord.Status.offline]
        embed = discord.Embed(title="🛡️ ทีมงานที่พร้อมสแตนด์บายค๊าา", description="\n".join(staff) if staff else "งื้อออ ตอนนี้แอดมินออฟไลน์กันหมดเยยค๊าา", color=0xF1C40F)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="🔍 ค้นหาคนไร้ยศ", style=discord.ButtonStyle.primary, emoji="👤", row=0)
    async def unassigned_members(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        no_role = [m.mention for m in self.guild.members if not m.bot and len(m.roles) == 1]
        embed = discord.Embed(title="👤 รายชื่อสมาชิกที่ยังไม่มีบทบาท/ยศใดๆ", color=0xE67E22)
        if no_role:
            embed.description = ", ".join(no_role[:30]) + (f" ...และคนอื่น ๆ อีก {len(no_role)-30} คน" if len(no_role) > 30 else "")
            embed.set_footer(text=f"พบทั้งหมด {len(no_role)} คนค๊าา")
        else:
            embed.description = "🎉 ยอดเยี่ยมมากค๊าา! ทุกคนในเซิร์ฟเวอร์นี้มียศติดตัวกันหมดเรียบร้อยแล้วจ้าา"
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="แจกยศให้คนไร้ยศ", style=discord.ButtonStyle.success, emoji="🎁", row=0)
    async def bulk_assign_role(self, interaction: discord.Interaction, btn):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Roles ถึงจะแจกยศแบบนี้ได้ค่ะ", ephemeral=True)
        no_role = [m for m in self.guild.members if not m.bot and len(m.roles) == 1]
        if not no_role:
            return await interaction.response.send_message("🎉 ไม่มีใครไร้ยศแล้วค่ะตอนนี้!", ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(BulkAssignRoleSelect(self.guild))
        await interaction.response.send_message(
            f"พบสมาชิกไร้ยศ **{len(no_role)}** คน เลือกยศที่จะแจกให้ทั้งหมดได้จากเมนูด้านล่างนี้เลยค่ะ:",
            view=view, ephemeral=True,
        )

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.danger, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        # เปลี่ยนกลับไปแสดงผลหน้าจอศูนย์ควบคุมหลัก (เมนูแรกสุด)
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))
# ==========================================
# 🎮 ROBLOX MODALS & VIEWS
# ==========================================
class AddRobloxServerModal(discord.ui.Modal, title="🎮 กรอกรายละเอียดเซิร์ฟเวอร์วี"):
    def __init__(self, selected_emoji: str):
        super().__init__()
        self.selected_emoji = selected_emoji

        self.game_id = discord.ui.TextInput(label="รหัสเกม (อังกฤษตัวพิมพ์เล็ก ห้ามเว้นวรรค)", placeholder="เช่น blox_fruits", required=True)
        self.game_name = discord.ui.TextInput(label="ชื่อเกมที่จะแสดงบนเมนู", placeholder="เช่น Blox Fruits", required=True)
        self.game_url = discord.ui.TextInput(label="ลิงก์ Private Server (Roblox URL)", placeholder="https://www.roblox.com/...", required=True)
        self.game_image = discord.ui.TextInput(label="🖼️ ลิงก์รูปภาพปก (ถ้ามี) - เว้นว่างได้", placeholder="วางลิงก์รูปภาพที่นี่ (ถ้าไม่มีไม่ต้องใส่ค๊าา)", required=False)

        self.add_item(self.game_id)
        self.add_item(self.game_name)
        self.add_item(self.game_url)
        self.add_item(self.game_image)

    async def on_submit(self, interaction: discord.Interaction):
        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        full_display_name = f"{self.selected_emoji} {self.game_name.value.strip()}"
        current_data = await load_roblox_data()
        current_data[g_id] = {
            "name": full_display_name, 
            "url": self.game_url.value.strip(),
            "image": self.game_image.value.strip() if self.game_image.value else None
        }
        await save_roblox_data(current_data)
        await interaction.response.send_message(f"✅ บันทึกเกม **{full_display_name}** เรียบร้อยค๊าา!", ephemeral=True)

class RobloxEmojiSelect(discord.ui.Select):

    def __init__(self):

        emoji_options = [
            discord.SelectOption(label="🏴‍☠️ โจรสลัด", value="🏴‍☠️"),
            discord.SelectOption(label="⚔️ ดาบไขว้", value="⚔️"),
            discord.SelectOption(label="🔥 ไฟ/พลัง", value="🔥"),
            discord.SelectOption(label="🥊 นวมต่อสู้", value="🥊"),
            discord.SelectOption(label="⚽ ฟุตบอล", value="⚽"),
            discord.SelectOption(label="⭐ ดาววิเศษ", value="⭐"),
        ]
        super().__init__(placeholder="🎨 เลือกอิโมจิประจำเกมก่อนนะค๊าา...", options=emoji_options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddRobloxServerModal(selected_emoji=self.values[0]))
class RobloxEmojiSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(RobloxEmojiSelect())

class RobloxServerSelect(discord.ui.Select):
    def __init__(self, roblox_data: dict):
        options = [discord.SelectOption(label=data["name"][:90], value=key) for key, data in roblox_data.items()] if roblox_data else [discord.SelectOption(label="ยังไม่มีเกมในคลัง", value="none")]
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", options=options)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        current_data = await load_roblox_data()
        game_data = current_data.get(self.values[0])
        if game_data:
            embed = discord.Embed(title=f"🚀 เข้าเล่นเกม {game_data['name']}", color=0x00E5FF)
            if game_data.get("image"):
                embed.set_image(url=game_data["image"])
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="👉 กดที่นี่เพื่อเข้าเซิร์ฟ", url=game_data['url']))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class DeleteRobloxServerModal(discord.ui.Modal, title="🗑️ ลบลิงก์เซิร์ฟเวอร์วี"):
    def __init__(self):
        super().__init__()
        self.game_id = discord.ui.TextInput(
            label="พิมพ์รหัสเกมที่ต้องการลบ (เช่น blox_fruits)", 
            placeholder="เช่น blox_fruits",
            required=True
        )
        self.add_item(self.game_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        current_data = await load_roblox_data()

        if g_id in current_data:
            deleted_name = current_data[g_id]['name']
            del current_data[g_id]
            await save_roblox_data(current_data)
            await interaction.followup.send(f"🗑️ ลบเกม **{deleted_name}** ออกจากคลังแสงเรียบร้อยค๊าา!", ephemeral=True, delete_after=3)
        else: 
            await interaction.followup.send(f"❌ ไม่พบรหัสเกม '{g_id}' ในระบบค๊าา ลองเช็คตัวพิมพ์ดี ๆ น้าา", ephemeral=True, delete_after=3)

class RobloxServerView(discord.ui.View):
    def __init__(self, guild, roblox_data: dict):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(RobloxServerSelect(roblox_data))
    @discord.ui.button(label="➕ เพิ่มเกม", style=discord.ButtonStyle.primary, emoji="➕", row=1)
    async def add_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_message("🎨 เลือกอิโมจิเพื่อเริ่มตั้งค่าเกมค๊าา:", view=RobloxEmojiSelectView(), ephemeral=True)
    @discord.ui.button(label="🗑️ ลบเกม", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def del_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_modal(DeleteRobloxServerModal())
    @discord.ui.button(label="⬅️ ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))
# ==========================================
# 🛡️ ROLE SYSTEM COMPONENTS
# ==========================================
class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🎨 เลือกรับยศสุดเลิศของคุณที่นี่เลยน้าา...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        role = interaction.guild.get_role(int(self.values[0]))
        if role:
            try: 
                await interaction.user.add_roles(role)
                await interaction.channel.send(f"✅ มอบยศ **{role.name}** ให้คุณเรียบร้อยค๊าา!", delete_after=5)
            except: 
                pass

class TextInputModal(discord.ui.Modal, title="📝 ส่งเหตุผลอ้อน ๆ เพื่อขอยศพิเศษ"):
    def __init__(self):
        super().__init__()
        self.reason = discord.ui.TextInput(label="เหตุผล/ชื่อยศพิเศษที่อยากได้ค๊าา", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)
    async def on_submit(self, interaction: discord.Interaction): 
        await interaction.response.send_message("📨 ส่งคำขออ้อน ๆ ให้แอดมินแล้วน้าา!", ephemeral=True)

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(RoleSelect(guild))
    @discord.ui.button(label="📝 ส่งคำขอยศพิเศษ", style=discord.ButtonStyle.primary, row=1)
    async def req_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_modal(TextInputModal())
    @discord.ui.button(label="ลบยศออกให้หมดเยย", style=discord.ButtonStyle.danger, row=1)
    async def rem_btn(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        roles = [r for r in interaction.user.roles if r.name != "@everyone" and not r.managed]
        if roles: 
            await interaction.user.remove_roles(*roles)
        await interaction.channel.send("🧹 ล้างยศเกลี้ยงตัวแล้วจ้าา!", delete_after=5)
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


class WelcomeConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                        placeholder="📢 เลือกห้องส่งข้อความต้อนรับ/บอกลา...", row=0)
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True)
        channel = select.values[0]
        await set_welcome_config_field(self.guild.id, "channel_id", channel.id)
        await interaction.followup.send(f"✅ ตั้งห้อง {channel.mention} เป็นห้องต้อนรับ/บอกลาแล้วค่ะ", ephemeral=True)

    @discord.ui.select(cls=discord.ui.RoleSelect,
                        placeholder="🎭 เลือกยศแจกอัตโนมัติให้สมาชิกใหม่ (ไม่บังคับ)...", row=1)
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        await interaction.response.defer(ephemeral=True)
        role = select.values[0]
        await set_welcome_config_field(self.guild.id, "autorole_id", role.id)
        await interaction.followup.send(f"✅ ตั้งยศอัตโนมัติเป็น **{role.name}** แล้วค่ะ", ephemeral=True)

    @discord.ui.button(label="ปิด Auto-role", style=discord.ButtonStyle.secondary, emoji="🚫", row=2)
    async def disable_autorole(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await unset_welcome_config_field(self.guild.id, "autorole_id")
        await interaction.followup.send("🚫 ปิด Auto-role แล้วค่ะ", ephemeral=True)

    @discord.ui.button(label="ปิดระบบทั้งหมด", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def disable_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await delete_welcome_config(self.guild.id)
        await interaction.followup.send("❌ ปิดระบบต้อนรับ/บอกลา/Auto-role ทั้งหมดแล้วค่ะ", ephemeral=True)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


class AFKReasonModal(discord.ui.Modal, title="😴 ตั้งสถานะ AFK"):
    def __init__(self):
        super().__init__()
        self.reason_input = discord.ui.TextInput(
            label="เหตุผล (ไม่บังคับ)", required=False, max_length=100,
            placeholder="เช่น ไปกินข้าว, ไปนอนก่อนน้าา",
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value.strip() or "ไปทำธุระก่อนน้าา"
        await set_afk(interaction.user.id, reason)
        await interaction.response.send_message(f"💤 ตั้งสถานะ AFK ให้คุณแล้วค่ะ: _{reason}_", ephemeral=True)


class AFKConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="ตั้งสถานะ AFK", style=discord.ButtonStyle.primary, emoji="😴", row=0)
    async def set_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AFKReasonModal())

    @discord.ui.button(label="ปลด AFK ของฉัน", style=discord.ButtonStyle.secondary, emoji="👋", row=0)
    async def clear_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await clear_afk(interaction.user.id) is not None:
            await interaction.response.send_message("👋 ปลดสถานะ AFK ให้แล้วค่ะ ยินดีต้อนรับกลับมาน้าา~", ephemeral=True)
        else:
            await interaction.response.send_message("ตอนนี้คุณไม่ได้ตั้ง AFK อยู่นะคะ", ephemeral=True)

    @discord.ui.button(label="🔙 กลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


class StickyMessageModal(discord.ui.Modal, title="📌 ตั้งข้อความปักหมุด"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.content_input = discord.ui.TextInput(
            label="ข้อความที่จะปักหมุด", style=discord.TextStyle.paragraph, max_length=2000,
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        content = self.content_input.value.strip()
        old = await delete_sticky(self.channel.id)
        if old:
            try:
                old_msg = await self.channel.fetch_message(old["message_id"])
                await old_msg.delete()
            except Exception:
                pass
        try:
            sent = await self.channel.send(f"📌 **ข้อความปักหมุด:**\n{content}")
        except Exception as e:
            return await interaction.followup.send(f"❌ ส่งข้อความไม่สำเร็จ: {type(e).__name__}", ephemeral=True)
        await set_sticky(self.channel.id, content, sent.id)
        await interaction.followup.send(f"✅ ตั้งข้อความปักหมุดในห้อง {self.channel.mention} เรียบร้อยค่ะ", ephemeral=True)


class StickyConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.selected_channel = None

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                        placeholder="📍 เลือกห้องที่จะตั้ง/ปิด sticky...", row=0)
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.selected_channel = select.values[0]
        await interaction.response.send_message(
            f"เลือกห้อง {self.selected_channel.mention} แล้วค่ะ กดปุ่ม 'ตั้งข้อความปักหมุด' ด้านล่างต่อได้เลย",
            ephemeral=True,
        )

    @discord.ui.button(label="ตั้งข้อความปักหมุด", style=discord.ButtonStyle.success, emoji="📌", row=1)
    async def set_sticky(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Messages ถึงจะตั้ง sticky ได้ค่ะ", ephemeral=True)
        if not self.selected_channel:
            return await interaction.response.send_message("❌ กรุณาเลือกห้องจากเมนูด้านบนก่อนค่ะ", ephemeral=True)
        await interaction.response.send_modal(StickyMessageModal(self.selected_channel))

    @discord.ui.button(label="ปิด Sticky ของห้องที่เลือก", style=discord.ButtonStyle.danger, emoji="🚫", row=1)
    async def clear_sticky(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Messages ถึงจะปิด sticky ได้ค่ะ", ephemeral=True)
        if not self.selected_channel:
            return await interaction.response.send_message("❌ กรุณาเลือกห้องจากเมนูด้านบนก่อนค่ะ", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        old = await delete_sticky(self.selected_channel.id)
        if old:
            try:
                old_msg = await self.selected_channel.fetch_message(old["message_id"])
                await old_msg.delete()
            except Exception:
                pass
            await interaction.followup.send(f"🚫 ปิด sticky ของห้อง {self.selected_channel.mention} แล้วค่ะ", ephemeral=True)
        else:
            await interaction.followup.send("ห้องนี้ไม่มี sticky ตั้งอยู่ค่ะ", ephemeral=True)

    @discord.ui.button(label="🔙 กลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

# ==========================================
# 📊 POLL SYSTEM COMPONENTS
# ==========================================
class AskQuestionTextModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="✍️ รายละเอียดคำถามโพลแสนสนุก")
        self.parent_view = parent_view
        self.question = discord.ui.TextInput(label="หัวข้อคำถามโพลนี้คืออะไรเอ่ย?")
        self.choices_input = discord.ui.TextInput(label="ตัวเลือกคำตอบ (แยกด้วยเครื่องหมาย , น้าา)", style=discord.TextStyle.paragraph)
        self.add_item(self.question)
        self.add_item(self.choices_input)
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value.strip()
        self.parent_view.poll_choices = [c.strip() for c in self.choices_input.value.split(",") if c.strip()]
        await interaction.response.send_message("✏️ บันทึกโพลเรียบร้อย!", ephemeral=True)
# ==========================================
# 📊 POLL SYSTEM COMPONENTS (BEAUTIFUL & INTERACTIVE)
# ==========================================

class VoteView(discord.ui.View):
    def __init__(self, question, choices):
        super().__init__(timeout=None)
        self.question = question
        self.choices = {choice: 0 for choice in choices}
        self.total_votes = 0
        self.voters = set()
        
        for choice in choices:
            # สร้างปุ่มสำหรับแต่ละตัวเลือก
            btn = discord.ui.Button(label=choice, style=discord.ButtonStyle.primary, custom_id=choice)
            btn.callback = self.vote_callback
            self.add_item(btn)

    async def vote_callback(self, interaction: discord.Interaction):
        if interaction.user.id in self.voters:
            return await interaction.response.send_message("❌ คุณโหวตไปแล้วน้าา ห้ามโกงนะคะ! 🌸", ephemeral=True)
        
        self.voters.add(interaction.user.id)
        self.choices[interaction.data['custom_id']] += 1
        self.total_votes += 1
        
        # อัปเดต Embed ใหม่ทุกครั้งที่มีคนโหวต
        await interaction.response.edit_message(embed=self.create_embed())

    def create_embed(self):
        embed = discord.Embed(title=f"❓ โพล: {self.question}", color=0xFFB6C1)
        embed.set_thumbnail(url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcShUD65scpmSHOknkLq8Rglr702yQOys83d7wS8spbaLn5gru-98uG2mrgc&s=10") # ไอคอนโพลน่ารักๆ
        
        desc = "กดปุ่มด้านล่างเพื่อโหวตเลยค๊าา! 👇\n\n"
        for choice, count in self.choices.items():
            percent = (count / self.total_votes * 100) if self.total_votes > 0 else 0
            # สร้าง Progress Bar แบบสวยงาม
            bar_length = int(percent / 10)
            bar = "█" * bar_length + "░" * (10 - bar_length)
            desc += f"**{choice}**\n`{bar}` {percent:.1f}% ({count} คะแนน)\n\n"
            
        embed.description = desc
        embed.set_footer(text=f"📊 ยอดผู้โหวตทั้งหมด: {self.total_votes} คน | Doro Bot 🐈‍⬛")
        return embed

class AskQuestionTextModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="✍️ ตั้งคำถามโพลแสนสนุก")
        self.parent_view = parent_view
        self.question = discord.ui.TextInput(label="หัวข้อโพล", placeholder="เช่น เย็นนี้กินอะไรดีคะ?")
        self.choices_input = discord.ui.TextInput(label="ตัวเลือก (คั่นด้วยเครื่องหมาย ,)", style=discord.TextStyle.paragraph, placeholder="เช่น พิซซ่า, ชาบู, ข้าวมันไก่")
        self.add_item(self.question)
        self.add_item(self.choices_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value.strip()
        self.parent_view.poll_choices = [c.strip() for c in self.choices_input.value.split(",") if c.strip()]
        await interaction.response.send_message("✅ บันทึกรายละเอียดโพลเรียบร้อย! กดปุ่ม 'ยืนยัน' เพื่อเริ่มโพลได้เลยค๊าา", ephemeral=True)

class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = None
        self.poll_choices = []
        self.target_id = None
        
        # ดึงรายชื่อ Text Channel
        channels = [discord.SelectOption(label=f"#{ch.name}", value=str(ch.id)) for ch in guild.text_channels][:25]
        self.s1 = discord.ui.Select(placeholder="📢 เลือกห้องที่จะปล่อยโพล", options=channels)
        self.s1.callback = self.c1
        self.add_item(self.s1)

    async def c1(self, interaction):
        self.target_id = int(self.s1.values[0])
        await interaction.response.send_message(f"📍 เลือกห้องเรียบร้อยค๊าา", ephemeral=True)

    @discord.ui.button(label="✏️ กรอกคำถาม", style=discord.ButtonStyle.primary, row=1)
    async def input_btn(self, interaction: discord.Interaction, btn):
        await interaction.response.send_modal(AskQuestionTextModal(self))

    @discord.ui.button(label="🚀 ยืนยันปล่อยโพล", style=discord.ButtonStyle.success, row=1)
    async def send_btn(self, interaction: discord.Interaction, btn):
        if not self.question_text or not self.poll_choices or not self.target_id:
            return await interaction.response.send_message("❌ กรุณาเลือกห้องและตั้งคำถามก่อนน้าา!", ephemeral=True)
        
        chan = self.guild.get_channel(self.target_id)
        view = VoteView(self.question_text, self.poll_choices)
        await chan.send(embed=view.create_embed(), view=view)
        await interaction.response.send_message("🎉 ปล่อยโพลเรียบร้อยแล้วค๊าา!", ephemeral=True)

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

# ==========================================
# 🔊 SOUNDBOARD SYSTEM
# ==========================================
class SoundboardView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        # คุณสามารถเปลี่ยนลิงก์ตรงนี้เป็น URL ไฟล์ MP3 ของคุณได้เลย
        self.sounds = {
            "ประมวลผล": "https://main-tan-yrmnml8s.edgeone.dev/u_39xav15uou-lightning-237994.mp3",
            "อ้าาา": "https://various-salmon-mhnmnlfm.edgeone.dev/50986408-aa-with-reverb-meme-381632.mp3",
            "ฟ้าร้อง": "https://unhappy-amethyst-otjoq89l.edgeone.dev/u_39xav15uou-lightning-237994.mp3"
        }
        for name, url in self.sounds.items():
            btn = discord.ui.Button(label=name, style=discord.ButtonStyle.secondary, custom_id=url)
            btn.callback = self.play_sound
            self.add_item(btn)

    async def play_sound(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ ต้องเข้าห้องเสียงก่อนน้าา!", ephemeral=True)
        vc = self.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        source = discord.FFmpegPCMAudio(interaction.data['custom_id'])
        vc.play(source)
        await interaction.response.send_message(f"🔊 กำลังปล่อยเสียง {interaction.data['custom_id'].split('/')[-1]}...", ephemeral=True, delete_after=2)
# ==========================================
# 🚫 VOTE KICK SYSTEM COMPONENTS
# ==========================================
class MemberSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 จิ้มเลือกคนที่ไม่น่ารักตรงนี้เลยงับ...")
        self.guild = guild
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        target = self.values[0]
        m_obj = interaction.guild.get_member(target.id)
        if m_obj:
            req = max(2, len([m for m in self.guild.members if m.status != discord.Status.offline and not m.bot]) // 2 + 1)
            await interaction.message.edit(embed=discord.Embed(title="🛠️ ตั้งค่าศาลเตี้ยโหวตเตะ", description=f"เป้าหมาย: {m_obj.mention}"), view=VoteKickTypeView(m_obj, req, self.guild))

class MemberSelectView(discord.ui.View):
    def __init__(self, guild): 
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(MemberSelect(guild))
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

class VoteKickTypeView(discord.ui.View):
    def __init__(self, target, req_votes, guild):
        super().__init__(timeout=60)
        self.target = target
        self.req = req_votes
        self.guild = guild

    @discord.ui.button(label="🔊 เตะออกจากห้องเสียง", style=discord.ButtonStyle.primary)
    async def vc_kick(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=discord.Embed(title="🚨 เริ่มโหวตดีดสายออกจากห้องเสียง!"), view=VoteProgressView(self.target, "voice", self.req, self.guild))

    @discord.ui.button(label="💥 ดีดออกจากเซิร์ฟเวอร์", style=discord.ButtonStyle.danger)
    async def server_kick(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=discord.Embed(title="🚨 เริ่มโหวตเตะออกจากเซิร์ฟเวอร์!"), view=VoteProgressView(self.target, "server", self.req, self.guild))

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

class VoteProgressView(discord.ui.View):
    def __init__(self, target, k_type, req, guild):
        super().__init__(timeout=120)
        self.target = target
        self.k_type = k_type
        self.req = req
        self.guild = guild
        self.voters = set()

    @discord.ui.button(label="🟢 เห็นด้วย ลุยเยย! (Vote)", style=discord.ButtonStyle.success, emoji="👍")
    async def vote(self, interaction: discord.Interaction, btn):
        if interaction.user.id in self.voters or interaction.user.id == self.target.id: return
        self.voters.add(interaction.user.id)
        if len(self.voters) >= self.req:
            try: 
                await interaction.message.delete()
            except: 
                pass
            if self.k_type == "voice" and self.target.voice: 
                await self.target.move_to(None)
            elif self.k_type == "server": 
                await self.target.kick()
            await interaction.channel.send(f"🔨 ประชามติสำเร็จ! ดีด {self.target.mention} ปลิวเรียบร้อยค๊าา")
            self.stop()
        else: 
            await interaction.response.send_message(f"🟢 บันทึกแต้มโหวตแล้ว ({len(self.voters)}/{self.req})", ephemeral=True)
# ==========================================
# 🛡️ SYSTEM MULTI-ROLE BACKPLANE 
# ==========================================
class MultiRoleSelectDropdown(discord.ui.Select):
    def __init__(self, guild):
        super().__init__(placeholder="🛡️ ขั้นตอนที่ 1: เลือกยศที่ต้องการแจก...", options=[discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in guild.roles if r.name != "@everyone" and not r.managed][:25])
    async def callback(self, interaction): 
        self.view.selected_role_id = int(self.values[0])
        await interaction.response.defer()
class MultiMemberSelectDropdown(discord.ui.UserSelect):
    def __init__(self): 
        super().__init__(placeholder="👥 ขั้นตอนที่ 2: เลือกสมาชิกกลุ่ม (เลือกได้ถึง 25 คน)...", min_values=1, max_values=25)
    async def callback(self, interaction): 
        self.view.selected_members = self.values
        await interaction.response.defer()

class MultiRoleManagementView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=180)
        self.guild = guild
        self.selected_role_id = None
        self.selected_members = []
        self.add_item(MultiRoleSelectDropdown(guild))
        self.add_item(MultiMemberSelectDropdown())
    @discord.ui.button(label="🚀 ยืนยันแจกยศให้ทุกคนเลยค๊าา!", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def confirm(self, interaction: discord.Interaction, btn):
        if not self.selected_role_id or not self.selected_members: return
        await interaction.response.defer()
        r = self.guild.get_role(self.selected_role_id)
        for u in self.selected_members:
            m = self.guild.get_member(u.id)
            if m: 
                try: 
                    await m.add_roles(r) 
                except: 
                    pass
        try: 
            await interaction.message.delete()
        except: 
            pass
        await interaction.channel.send("🛡️ มอบยศกลุ่มความเร็วสูงเสร็จเรียบร้อยค๊าา!", delete_after=10)

# ==========================================
# 🎮 ROBLOX GAME CODES (LIVE FETCH + MANUAL FALLBACK)
# ==========================================
# แหล่งข้อมูลหลัก: progameguides.com — ถ้าโดนเว็บบล็อก (403/timeout ฯลฯ)
# ระบบจะ fallback ไปใช้โค้ดที่แอดมินเก็บไว้ในไฟล์ manual_codes.json แทน
GAME_CODE_SOURCES = {
    "blox_fruits": {
        "label": "🍈 Blox Fruits",
        "url": "https://progameguides.com/roblox/roblox-blox-fruits-codes/",
    },
    "grow_a_garden": {
        "label": "🌱 Grow a Garden",
        "url": "https://progameguides.com/roblox/grow-a-garden-codes/",
    },
    "anime_vanguards": {
        "label": "⚔️ Anime Vanguards",
        "url": "https://progameguides.com/roblox/anime-vanguards-codes/",
    },
    "fisch": {
        "label": "🎣 Fisch",
        "url": "https://progameguides.com/roblox/fisch-codes/",
    },
    "fruit_battlegrounds": {
        "label": "🥊 Fruit Battlegrounds",
        "url": "https://progameguides.com/roblox/fruits-battlegrounds-codes/",
    },
    "steal_a_brainrot": {
        "label": "🧠 Steal a Brainrot",
        "url": "https://progameguides.com/roblox/steal-a-brainrot-codes/",
    },
    "anime_expeditions": {
        "label": "🗺️ Anime Expeditions",
        "url": "https://progameguides.com/roblox/anime-expeditions-codes/",
    },
}

CODE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
}



async def get_manual_codes(game_key: str) -> list[tuple[str, str]]:
    doc = await manual_codes_col.find_one({"_id": game_key})
    entries = doc.get("entries", []) if doc else []
    return [(e.get("code", ""), e.get("desc", "")) for e in entries if e.get("code")]


async def add_manual_code(game_key: str, code: str, desc: str):
    doc = await manual_codes_col.find_one({"_id": game_key})
    entries = doc.get("entries", []) if doc else []
    for e in entries:
        if e.get("code", "").lower() == code.lower():
            e["desc"] = desc
            await manual_codes_col.update_one({"_id": game_key}, {"$set": {"entries": entries}}, upsert=True)
            return
    entries.append({"code": code, "desc": desc})
    await manual_codes_col.update_one({"_id": game_key}, {"$set": {"entries": entries}}, upsert=True)


async def remove_manual_code(game_key: str, code: str) -> bool:
    doc = await manual_codes_col.find_one({"_id": game_key})
    entries = doc.get("entries", []) if doc else []
    new_entries = [e for e in entries if e.get("code", "").lower() != code.lower()]
    if len(new_entries) == len(entries):
        return False
    await manual_codes_col.update_one({"_id": game_key}, {"$set": {"entries": new_entries}}, upsert=True)
    return True


# --- 📢 การประกาศโค้ดใหม่อัตโนมัติ (ตั้งค่าห้องแยกต่อเกม/ต่อเซิร์ฟ) ---
async def get_announce_channel(guild_id: int, game_key: str):
    doc = await code_announce_col.find_one({"_id": guild_id})
    return doc.get("channels", {}).get(game_key) if doc else None

async def set_announce_channel(guild_id: int, game_key: str, channel_id: int):
    await code_announce_col.update_one({"_id": guild_id}, {"$set": {f"channels.{game_key}": channel_id}}, upsert=True)

async def unset_announce_channel(guild_id: int, game_key: str):
    await code_announce_col.update_one({"_id": guild_id}, {"$unset": {f"channels.{game_key}": ""}}, upsert=True)

async def get_all_announce_configs(game_key: str) -> list:
    return [doc async for doc in code_announce_col.find({f"channels.{game_key}": {"$exists": True}})]


# --- 🆕 ตัวติดตามโค้ดที่เคยเห็นแล้ว (baseline ระดับเกม ใช้ร่วมกันทุกเซิร์ฟ) ---
async def get_known_codes(game_key: str):
    """คืนค่า set ของโค้ดที่เคยเห็นแล้ว หรือ None ถ้ายังไม่เคยเก็บ baseline มาก่อนเลย"""
    doc = await known_codes_col.find_one({"_id": game_key})
    if not doc:
        return None
    return set(doc.get("codes", []))

async def save_known_codes(game_key: str, codes: list):
    await known_codes_col.update_one({"_id": game_key}, {"$set": {"codes": codes}}, upsert=True)


def parse_codes_from_html(html: str) -> list[tuple[str, str]]:
    """แกะรายชื่อโค้ด + คำอธิบาย ออกจากตาราง 'Active Codes' ในหน้าเว็บ"""
    soup = BeautifulSoup(html, "html.parser")
    codes: list[tuple[str, str]] = []

    active_heading = None
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if "active code" in heading.get_text(strip=True).lower():
            active_heading = heading
            break

    table = active_heading.find_next("table") if active_heading else soup.find("table")
    if not table:
        return codes

    for row in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c and c.lower() != "copy"]
        if len(cells) >= 2 and cells[0].lower() not in ("code", ""):
            code, desc = cells[0], cells[1]
            codes.append((code, desc))
        elif len(cells) == 1 and cells[0].lower() not in ("code", ""):
            codes.append((cells[0], ""))

    return codes


async def fetch_game_codes(url: str) -> list[tuple[str, str]]:
    async with aiohttp.ClientSession(headers=CODE_FETCH_HEADERS) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            html = await resp.text()
    return parse_codes_from_html(html)


def build_codes_embed(game_label: str, source_url: str, codes: list[tuple[str, str]], from_manual: bool = False) -> discord.Embed:
    if not codes:
        embed = discord.Embed(
            title=f"📭 {game_label} — ยังไม่มีโค้ดที่ใช้งานได้ตอนนี้",
            description=f"ลองเช็กอีกทีทีหลังนะคะ หรือดูที่ [แหล่งข้อมูล]({source_url})",
            color=0xFFB6C1,
        )
        return embed

    lines = []
    for code, desc in codes[:20]:
        if desc:
            lines.append(f"`{code}` — {desc}")
        else:
            lines.append(f"`{code}`")

    embed = discord.Embed(
        title=f"🎁 โค้ดที่ใช้งานได้ตอนนี้ — {game_label}",
        description="\n".join(lines),
        color=0x77DD77,
    )
    footer = f"ทั้งหมด {len(codes)} โค้ด"
    footer += " • มาจากรายการที่แอดมินอัปเดตไว้ (ดึงจากเว็บไม่ได้ตอนนี้)" if from_manual else " • อัปเดตล่าสุดจาก progameguides.com"
    embed.set_footer(text=footer)
    return embed


class GameCodeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=info["label"], value=key)
            for key, info in GAME_CODE_SOURCES.items()
        ]
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการดูโค้ด...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        game_key = self.values[0]
        info = GAME_CODE_SOURCES[game_key]

        codes: list[tuple[str, str]] = []
        from_manual = False
        try:
            codes = await fetch_game_codes(info["url"])
            if not codes:
                raise ValueError("no codes parsed from page")
        except Exception as e:
            error_detail = f"{type(e).__name__}: {e}"
            logger.warning(f"fetch_game_codes failed for {game_key}: {error_detail}")
            print(f"[CODE FETCH ERROR] {game_key}: {error_detail}", flush=True)
            codes = await get_manual_codes(game_key)
            from_manual = True

        embed = build_codes_embed(info["label"], info["url"], codes, from_manual=from_manual)
        new_view = GameCodeResultView(codes[:20])

        try:
            await interaction.message.edit(embed=embed, view=new_view)
        except Exception as e:
            edit_error = f"{type(e).__name__}: {e}"
            logger.warning(f"message.edit failed for {game_key}: {edit_error}")
            print(f"[MESSAGE EDIT ERROR] {game_key}: {edit_error}", flush=True)
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass


class CodeCopyButton(discord.ui.Button):
    """ปุ่มคัดลอกโค้ด กดแล้วบอทจะส่งโค้ดนั้นมาเป็นข้อความ ephemeral ให้กดคัดลอกได้ทันที"""
    def __init__(self, code: str, row: int):
        super().__init__(label=f"📋 {code}"[:80], style=discord.ButtonStyle.secondary, row=row)
        self.code = code

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"📋 คัดลอกโค้ดนี้ได้เลยค่ะ:\n`{self.code}`", ephemeral=True)


class GameCodeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameCodeSelect())

    @discord.ui.button(label="เพิ่มโค้ด", style=discord.ButtonStyle.success, emoji="➕", row=3)
    async def add_code_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะเพิ่มโค้ดได้ค่ะ", ephemeral=True)
        await interaction.response.send_message(
            "เลือกเกมที่จะเพิ่มโค้ดให้ค่ะ:", view=AddCodeAdminView(), ephemeral=True
        )

    @discord.ui.button(label="ลบโค้ด", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)
    async def remove_code_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะลบโค้ดได้ค่ะ", ephemeral=True)
        await interaction.response.send_message(
            "เลือกเกมที่จะลบโค้ดออกค่ะ:", view=RemoveCodeAdminView(), ephemeral=True
        )

    @discord.ui.button(label="ตั้งห้องประกาศโค้ดใหม่", style=discord.ButtonStyle.primary, emoji="📢", row=3)
    async def announce_setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะตั้งค่านี้ได้ค่ะ", ephemeral=True)
        await interaction.response.send_message(
            "ตั้งค่าห้องประกาศเมื่อมีโค้ดใหม่ออกได้ที่นี่ค่ะ:", view=CodeAnnounceConfigView(interaction.guild), ephemeral=True
        )


class GameCodeResultView(GameCodeView):
    """เหมือน GameCodeView แต่เพิ่มปุ่มคัดลอกโค้ดแยกทีละปุ่ม เมื่อมีโค้ดให้เลือกแล้ว"""
    def __init__(self, codes: list[tuple[str, str]]):
        super().__init__()
        # แสดงปุ่มคัดลอกได้สูงสุด 10 โค้ด (แถวละ 5 ปุ่ม x 2 แถว) ที่เหลือยังดูได้จากข้อความ embed ด้านบน
        for idx, (code, _desc) in enumerate(codes[:10]):
            row = 1 + (idx // 5)  # แถว 1 และ 2
            self.add_item(CodeCopyButton(code, row))


# ------------------------------------------
# 🛠️ ADMIN UI: เพิ่ม/ลบโค้ดสำรอง (แทนการพิมพ์คำสั่ง)
# ------------------------------------------
class AddCodeModal(discord.ui.Modal):
    def __init__(self, game_key: str, game_label: str):
        super().__init__(title=f"เพิ่มโค้ด — {game_label}"[:45])
        self.game_key = game_key
        self.codes_input = discord.ui.TextInput(
            label="โค้ด (ใส่ได้หลายบรรทัด บรรทัดละ 1 โค้ด)",
            placeholder="CODE1 - คำอธิบาย\nCODE2 - คำอธิบาย\nCODE3",
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True,
        )
        self.add_item(self.codes_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw_lines = str(self.codes_input.value).splitlines()
        added = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            # รองรับตัวคั่นทั้ง " - ", " : ", " — " ระหว่างโค้ดกับคำอธิบาย
            code, desc = line, ""
            for sep in (" - ", " — ", " : ", "-", ":"):
                if sep in line:
                    code, desc = line.split(sep, 1)
                    break
            code, desc = code.strip(), desc.strip()
            if not code:
                continue
            await add_manual_code(self.game_key, code, desc)
            added.append(code)

        if not added:
            return await interaction.response.send_message("❌ ไม่พบโค้ดที่ใส่มาเลยค่ะ ลองใหม่อีกครั้งน้าา", ephemeral=True)

        code_list = ", ".join(f"`{c}`" for c in added)
        await interaction.response.send_message(
            f"✅ เพิ่ม {len(added)} โค้ด ให้เกม **{GAME_CODE_SOURCES[self.game_key]['label']}** เรียบร้อยค๊าา!\n{code_list}",
            ephemeral=True,
        )


class AddCodeGameSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=info["label"], value=key)
            for key, info in GAME_CODE_SOURCES.items()
        ]
        super().__init__(placeholder="🎮 เลือกเกมที่จะเพิ่มโค้ดให้...", options=options)

    async def callback(self, interaction: discord.Interaction):
        game_key = self.values[0]
        info = GAME_CODE_SOURCES[game_key]
        await interaction.response.send_modal(AddCodeModal(game_key, info["label"]))


class AddCodeAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(AddCodeGameSelect())


class RemoveCodeGameSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=info["label"], value=key)
            for key, info in GAME_CODE_SOURCES.items()
        ]
        super().__init__(placeholder="🎮 เลือกเกมที่จะลบโค้ด...", options=options)

    async def callback(self, interaction: discord.Interaction):
        game_key = self.values[0]
        info = GAME_CODE_SOURCES[game_key]
        entries = await get_manual_codes(game_key)
        if not entries:
            return await interaction.response.send_message(
                f"📭 เกม **{info['label']}** ยังไม่มีโค้ดสำรองเก็บไว้เลยค่ะ", ephemeral=True
            )
        await interaction.response.edit_message(
            content=f"เลือกโค้ดที่จะลบออกจาก **{info['label']}**:",
            view=RemoveCodePickView(game_key, entries),
        )


class RemoveCodePicker(discord.ui.Select):
    def __init__(self, game_key: str, entries: list[tuple[str, str]]):
        self.game_key = game_key
        options = [discord.SelectOption(label=code[:100], description=desc[:100] or None) for code, desc in entries[:25]]
        super().__init__(placeholder="🗑️ เลือกโค้ดที่จะลบ...", options=options)

    async def callback(self, interaction: discord.Interaction):
        code = self.values[0]
        await remove_manual_code(self.game_key, code)
        await interaction.response.edit_message(content=f"🗑️ ลบโค้ด `{code}` แล้วค่ะ", view=None)


class RemoveCodePickView(discord.ui.View):
    def __init__(self, game_key: str, entries: list[tuple[str, str]]):
        super().__init__(timeout=120)
        self.add_item(RemoveCodePicker(game_key, entries))


class RemoveCodeAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(RemoveCodeGameSelect())


# ------------------------------------------
# 📢 ADMIN UI: ตั้งค่าห้องประกาศโค้ดใหม่อัตโนมัติ (แยกห้องต่อเกม/ต่อเซิร์ฟ)
# ------------------------------------------
class CodeAnnounceGameSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=info["label"], value=key)
            for key, info in GAME_CODE_SOURCES.items()
        ]
        super().__init__(placeholder="🎮 1. เลือกเกมที่จะตั้งห้องประกาศ...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: CodeAnnounceConfigView = self.view
        view.selected_game = self.values[0]
        info = GAME_CODE_SOURCES[self.values[0]]
        cur_channel_id = await get_announce_channel(interaction.guild.id, self.values[0])
        channel = interaction.guild.get_channel(cur_channel_id) if cur_channel_id else None
        await interaction.response.send_message(
            f"เลือกเกม **{info['label']}** แล้วค่ะ (ห้องที่ตั้งไว้ตอนนี้: {channel.mention if channel else '*ยังไม่ได้ตั้ง*'})\n"
            "เลือกห้องใหม่จากเมนูด้านล่าง หรือกดปิดประกาศได้เลยค่ะ",
            ephemeral=True,
        )


class CodeAnnounceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📢 2. เลือกห้องที่จะประกาศโค้ดใหม่...", channel_types=[discord.ChannelType.text], row=1)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะตั้งค่านี้ได้ค่ะ", ephemeral=True)
        view: CodeAnnounceConfigView = self.view
        if not view.selected_game:
            return await interaction.response.send_message("❌ กรุณาเลือกเกมจากเมนูด้านบนก่อนค่ะ", ephemeral=True)
        channel = self.values[0]
        await set_announce_channel(interaction.guild.id, view.selected_game, channel.id)
        info = GAME_CODE_SOURCES[view.selected_game]
        await interaction.response.send_message(
            f"✅ ตั้งห้องประกาศโค้ดใหม่ของ **{info['label']}** เป็น {channel.mention} แล้วค่ะ พอมีโค้ดใหม่ออกหนูจะรีบมาบอกทันทีน้าา~", ephemeral=True,
        )


class CodeAnnounceConfigView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=120)
        self.guild = guild
        self.selected_game = None
        self.add_item(CodeAnnounceGameSelect())
        self.add_item(CodeAnnounceChannelSelect())

    @discord.ui.button(label="ปิดประกาศของเกมที่เลือก", style=discord.ButtonStyle.danger, emoji="🚫", row=2)
    async def disable_announce(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ต้องมีสิทธิ์ Manage Server ถึงจะตั้งค่านี้ได้ค่ะ", ephemeral=True)
        if not self.selected_game:
            return await interaction.response.send_message("❌ กรุณาเลือกเกมจากเมนูด้านบนก่อนค่ะ", ephemeral=True)
        await unset_announce_channel(self.guild.id, self.selected_game)
        info = GAME_CODE_SOURCES[self.selected_game]
        await interaction.response.send_message(f"🚫 ปิดประกาศโค้ดใหม่อัตโนมัติของ **{info['label']}** แล้วค่ะ", ephemeral=True)


# ==========================================
# ⚙️ CORE EVENTS & COMMANDS MAIN LOGIC
# ==========================================
@bot.event
async def on_ready(): 
    global refresh_main_menu_msg
    async def _refresh(guild_id, channel):
        try:
            async for msg in channel.history(limit=20):
                if msg.author.id == bot.user.id and msg.embeds and "Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก" in str(msg.embeds[0].title):
                    await msg.edit(embed=generate_main_menu_embed(channel.guild), view=BotControlMenuView(channel.guild))
                    break
        except:
            pass
    refresh_main_menu_msg = _refresh
    bot.add_view(DynamicGroupJoinView(role_id=0, emoji_str="🌸"))
    if not check_reminders.is_running():
        check_reminders.start()
    if not check_new_game_codes.is_running():
        check_new_game_codes.start()
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.warning(f"Slash command sync failed: {type(e).__name__}: {e}")
    logger.info(f"Doro COMPLETELY SUPER POWERED IS RUNNING AS {bot.user}")


@bot.tree.command(name="menu", description="เปิดแผงควบคุมระบบ UI ของน้อน Doro")
async def slash_menu(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=generate_main_menu_embed(interaction.guild),
        view=BotControlMenuView(interaction.guild),
    )


@bot.event
async def on_member_join(member: discord.Member):
    cfg = await get_welcome_config(member.guild.id)
    if not cfg:
        return
    channel = member.guild.get_channel(cfg.get("channel_id")) if cfg.get("channel_id") else None
    if channel:
        embed = discord.Embed(
            title="🎉 มีเพื่อนใหม่เข้ามาในเซิร์ฟแล้วค่าา!",
            description=f"ยินดีต้อนรับ {member.mention} เข้าสู่ **{member.guild.name}** น้าา~ 💕\nฝากเนื้อฝากตัวกันด้วยนะค๊าา",
            color=0x2ECC71,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"welcome message failed: {type(e).__name__}: {e}")
    autorole_id = cfg.get("autorole_id")
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role, reason="Auto-role on join")
            except Exception as e:
                logger.warning(f"autorole failed: {type(e).__name__}: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    cfg = await get_welcome_config(member.guild.id)
    if not cfg:
        return
    channel = member.guild.get_channel(cfg.get("channel_id")) if cfg.get("channel_id") else None
    if channel:
        embed = discord.Embed(
            title="💔 มีคนออกจากเซิร์ฟไปแล้วง้อ...",
            description=f"**{member.display_name}** ออกจากเซิร์ฟไปแล้วค่ะ ขอบคุณที่เคยอยู่ด้วยกันน้าา 🥺",
            color=0xE74C3C,
        )
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"goodbye message failed: {type(e).__name__}: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    msg = message.content.strip()
    lower_msg = msg.lower()
    parts = msg.split()

    # --- 💤 ระบบ AFK ---
    if lower_msg == "doro afk" or lower_msg.startswith("doro afk "):
        reason = msg[len("doro afk"):].strip() or "ไปทำธุระก่อนน้าา"
        await set_afk(message.author.id, reason)
        await message.channel.send(f"💤 ตั้งสถานะ AFK ให้ **{message.author.display_name}** แล้วค่ะ: _{reason}_", delete_after=8)
        return
    if await get_afk(message.author.id) is not None:
        await clear_afk(message.author.id)
        await message.channel.send(f"👋 ยินดีต้อนรับกลับมาค่ะ **{message.author.display_name}** ปลด AFK ให้แล้วน้าา~", delete_after=5)
    if message.mentions:
        afk_lines = []
        for m in message.mentions:
            if m.id == message.author.id:
                continue
            reason = await get_afk(m.id)
            if reason is not None:
                afk_lines.append(f"💤 **{m.display_name}** กำลัง AFK อยู่ค่ะ: _{reason}_")
        if afk_lines:
            await message.channel.send("\n".join(afk_lines), delete_after=8)

    # --- 📌 ระบบ Sticky Message (ตั้งค่า/ปิด) ---
    if lower_msg.startswith("doro sticky "):
        if not message.author.guild_permissions.manage_messages:
            return await message.channel.send("❌ ต้องมีสิทธิ์ Manage Messages ถึงจะตั้ง sticky ได้ค่ะ")
        content = msg[len("doro sticky "):].strip()
        if content.lower() in ("off", "ปิด"):
            old = await delete_sticky(message.channel.id)
            if old:
                try:
                    old_msg = await message.channel.fetch_message(old["message_id"])
                    await old_msg.delete()
                except Exception:
                    pass
            return await message.channel.send("📌 ปิดข้อความปักหมุดของห้องนี้แล้วค่ะ", delete_after=5)
        sent = await message.channel.send(f"📌 **ข้อความปักหมุด:**\n{content}")
        await set_sticky(message.channel.id, content, sent.id)
        return

    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
        return
    if message.guild:
        dynamic_responses = await get_custom_responses(message.guild.id)
        if lower_msg in dynamic_responses:
            await message.channel.send(dynamic_responses[lower_msg])
            return
    if any(f"doro {k}" in lower_msg or f"doro{k}" in lower_msg for k in ["เมนู", "menu", "คำสั่งเพลง", "music"]):
        try: 
            await message.delete()
        except: 
            pass
        await message.channel.send(embed=generate_main_menu_embed(message.guild), view=BotControlMenuView(message.guild))
        return
    if any(f"doro {k}" in lower_msg or f"doro{k}" in lower_msg for k in ["ให้ยศ", "addrole"]):
        if not message.author.guild_permissions.manage_roles: return
        try: 
            await message.delete()
        except: 
            pass
        await message.channel.send(embed=discord.Embed(title="🛡️ ระบบมอบยศกลุ่มอัจฉริยะค๊าาา ", color=0xFFB6C1), view=MultiRoleManagementView(message.guild))
        return

    if lower_msg in ("doro โค้ด", "doro code", "doro โคด"):
        embed = discord.Embed(
            title="🎮 ระบบเช็คโค้ดเกม Roblox",
            description="เลือกเกมจากเมนูด้านล่างเลยค่ะ หนูจะไปหาโค้ดล่าสุดมาให้น้าา~ 🔍",
            color=0xFFB6C1,
        )
        await message.channel.send(embed=embed, view=GameCodeView())
        return

    if lower_msg.startswith("doro เพิ่มโค้ด "):
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("❌ ต้องมีสิทธิ์ Manage Server ถึงจะเพิ่มโค้ดได้ค่ะ")
        args = msg.split(maxsplit=3)[1:]  # ตัด "doro" ออก -> [เพิ่มโค้ด, game_key, code, desc...]
        if len(args) < 3:
            game_list = ", ".join(f"`{k}`" for k in GAME_CODE_SOURCES)
            return await message.channel.send(
                f"❌ รูปแบบ: `doro เพิ่มโค้ด <game_key> <โค้ด> <คำอธิบาย>`\nเกมที่มีตอนนี้: {game_list}\n"
                f"หรือพิมพ์ `doro โค้ด` แล้วกดปุ่ม ➕ เพิ่มโค้ด แทนก็ได้ค่ะ"
            )
        game_key, code, desc = args[0], args[1], args[2]
        if game_key not in GAME_CODE_SOURCES:
            game_list = ", ".join(f"`{k}`" for k in GAME_CODE_SOURCES)
            return await message.channel.send(f"❌ ไม่รู้จักเกม `{game_key}` ค่ะ ใช้ได้แค่: {game_list}")
        await add_manual_code(game_key, code, desc)
        await message.channel.send(f"✅ เพิ่มโค้ด `{code}` ให้เกม `{game_key}` เรียบร้อยค๊าา (ใช้เป็นสำรองตอนดึงเว็บไม่ได้)")
        return


    if lower_msg.startswith("doro ลบโค้ด "):
        if not message.author.guild_permissions.manage_guild:
            return await message.channel.send("❌ ต้องมีสิทธิ์ Manage Server ถึงจะลบโค้ดได้ค่ะ")
        args = msg.split(maxsplit=3)[1:]  # [ลบโค้ด, game_key, code]
        if len(args) < 2:
            return await message.channel.send("❌ รูปแบบ: `doro ลบโค้ด <game_key> <โค้ด>` หรือพิมพ์ `doro โค้ด` แล้วกดปุ่ม 🗑️ ลบโค้ด แทนก็ได้ค่ะ")
        game_key, code = args[0], args[1]
        if await remove_manual_code(game_key, code):
            await message.channel.send(f"🗑️ ลบโค้ด `{code}` ออกจากเกม `{game_key}` แล้วค่ะ")
        else:
            await message.channel.send(f"❌ หาโค้ด `{code}` ในเกม `{game_key}` ไม่เจอค่ะ")
        return

    if (f"doro ลบข้อความ" in lower_msg or f"doro clear" in lower_msg) and len(parts) >= 3:
        if not message.author.guild_permissions.manage_messages: return
        try: 
            deleted = await message.channel.purge(limit=int(parts[2]) + 1)
        except: 
            pass
        return

    if lower_msg == "doro สร้างปุ่มรับยศ":
        if not message.author.guild_permissions.manage_roles: return
        try:
            await message.delete() 
        except:
            pass
        admin_setup_embed = discord.Embed(
            title="🛠️ แผงควบคุมตั้งค่ากล่องรับยศเข้ากลุ่ม (แอดมินโหมด)",
            description="กรุณาเลือกยศที่ต้องการแจกและหน้าตาปุ่มอิโมจิด้านล่างให้ครบถ้วน จากนั้นกดปุ่มยืนยันเพื่อเสกกล่องแมวทมิฬสีดำลงช่องแชทค๊าา! ✨",
            color=0x000000
        )
        await message.channel.send(embed=admin_setup_embed, view=RoleSetupAdminView(message.guild), delete_after=60)
        return

    if lower_msg.startswith("doro เล่น ") or lower_msg.startswith("doro play "):
        query = " ".join(parts[2:])
        if not query: 
            return await message.channel.send("❌ โปรดระบุชื่อเพลงหรือลิงก์ให้หนูด้วยค๊าา")
        if not message.author.voice:
            return await message.channel.send("❌ คุณพี่ต้องเข้ามาอยู่ในห้องคุยเสียงก่อนสั่งหนูเปิดเพลงนะค๊าางึมมม")
        await message.channel.send(f"🔍 น้อน Doro กำลังดำน้ำไปงมหาเพลง **'{query}'** บน YouTube แป๊บน้าน้าา...", delete_after=5)
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ytdl:
            try:
                info = ytdl.extract_info(query, download=False)
                if 'entries' in info: 
                    info = info['entries'][0]
                song_data = {
                    'url': info['url'],
                    'title': info['title'],
                    'webpage_url': info['webpage_url'],
                    'thumbnail': info.get('thumbnail'),
                    'requester': message.author.display_name
                }
            except Exception as e:
                return await message.channel.send("❌ งื้อออ หนูหาเพลงนี้ไม่เจอหรือติดบล็อกจาก YouTube ค๊าา ลองเปลี่ยนชื่อเพลงดูน้าา")

        guild_id = message.guild.id
        vc = message.guild.voice_client

        if not vc:
            vc = await message.author.voice.channel.connect()
        if guild_id not in music_queues: 
            music_queues[guild_id] = []
        if vc.is_playing() or vc.is_paused():
            music_queues[guild_id].append(song_data)
            await message.channel.send(f"📋 เพิ่มเพลง **{song_data['title']}** เข้าสู่คิวเรียบร้อยแล้วค๊าา!", delete_after=5)
        else:
            current_songs[guild_id] = song_data
            source = discord.FFmpegPCMAudio(song_data['url'], **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next_song(guild_id, vc, message.channel))
            await message.channel.send(embed=generate_main_menu_embed(message.guild), view=MusicControlView(message.guild))
        return

    # --- 📌 บั๊มปักหมุดข้อความ sticky ให้ลอยอยู่ล่างสุดของห้องเสมอ ---
    sticky = await get_sticky(message.channel.id)
    if sticky:
        try:
            old_msg = await message.channel.fetch_message(sticky["message_id"])
            await old_msg.delete()
        except Exception:
            pass
        try:
            new_msg = await message.channel.send(f"📌 **ข้อความปักหมุด:**\n{sticky['content']}")
            await set_sticky(message.channel.id, sticky["content"], new_msg.id)
        except Exception as e:
            logger.warning(f"sticky repost failed: {type(e).__name__}: {e}")

bot.run(DISCORD_TOKEN)
