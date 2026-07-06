import os
import json
import random
import asyncio
import pytz
import logging
import discord
import yt_dlp
from datetime import datetime
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from youtubesearchpython import VideosSearch

# ==========================================
# 🌐 WEB SERVER FOR RENDER (KEEPALIVE)
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
# ⚙️ GLOBAL CONFIG & LOGGING SETUP
# ==========================================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in environment configuration.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doro_bot")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.presences = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# คลังคำพูดหวาน ๆ ประจำตัวน้อน Doro
custom_responses = {
    "bot ชื่ออะไร": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักประจำเซิร์ฟของคุณพี่น้าา~ 🤖💕",
    "whats your name": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักประจำเซิร์ฟของคุณพี่น้าา~ 🤖💕",
    "doro ช่วยอะไรได้บ้าง": "หนูช่วยเปิดเพลงเพราะ ๆ ให้ฟัง ล้างแชทขยะ ทำโพล โหวตเตะคนดื้อ แล้วก็แจกยศเข้ากลุ่มได้ด้วยนะค๊าา! 🎵✨",
    "doro สวัสดี": "งื้อออ สวัสดีค่าา! ดีใจจังเลยที่ได้คุยกัน วันนี้มีอะไรให้หนูรับใช้ไหมเอ่ย? 🌸",
}

# 🗃️ Global Storage
vote_records = {}  
poll_result_messages = {} 
JSON_FILE = "roblox_servers.json"

def load_roblox_data():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f: 
            return json.load(f)
    except FileNotFoundError:
        default_data = {
            "blox_fruits": {"name": "🏴‍☠️ Blox Fruits", "url": "https://www.roblox.com/"},
            "king_legacy": {"name": "👑 King Legacy", "url": "https://www.roblox.com/"}
        }
        save_roblox_data(default_data)
        return default_data

def save_roblox_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)


# ==========================================
# 🔓 DYNAMIC GROUP ROLE VIEW (Ephemeral หายเอง 100%)
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
            return await interaction.followup.send("❌ งื้อออ น้อนหาตัวยศนี้ในเซิร์ฟไม่เจอ แอดมินจ๋าแอบลบยศไปหรือเปล่านะคะ? 🥺", ephemeral=True)

        if role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(role)
                return await interaction.followup.send(f"🏃‍♂️ ถอนยศ **{role.name}** และออกจากกลุ่มเรียบร้อยแล้วน้าา ไว้แวะมาหาหนูใหม่นะคะคนดี~ 💕", ephemeral=True)
            except discord.Forbidden:
                return await interaction.followup.send("❌ งื้อออ น้อนไม่มีสิทธิ์ถอนยศนี้ให้เลยค๊าา ระดับยศหนูต่ำเกินไป ขอโทษน้าา 🥺", ephemeral=True)

        try:
            await interaction.user.add_roles(role)
            await interaction.followup.send("🎉 ยินดีต้อนรับเข้าสู่กลุ่มค๊าา! มอบยศ M͟͞E͟͞M͟͞B͟͞E͟͞R͟͞ 💀 ให้เรียบร้อย ตอนนี้ห้องลับเปิดให้เข้าแล้วน้าา~ 💕", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ น้อน Doro ไม่มีสิทธิ์แจกยศนี้ รบกวนแอดมินลากยศของน้อนให้สูงกว่ายศที่จะแจกในตั้งค่าเซิร์ฟเวอร์หน่อยน้าค๊าา จุ๊บ ๆ 🥺🎀", ephemeral=True)


# ตั้งค่าระบบสร้างปุ่มของแอดมิน
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
        
        # ป้องกัน Dropdown ว่างเปล่าสำหรับเครื่องมือแอดมิน
        if not role_options:
            role_options = [discord.SelectOption(label="❌ ไม่มีสิทธิ์สร้างยศใดๆ ในเซิร์ฟนี้", value="none")]

        self.role_select = discord.ui.Select(placeholder="🎨 1. เลือกยศที่จะให้คนกดรับนะคะ...", options=role_options, row=0)
        self.role_select.callback = self.role_callback
        self.add_item(self.role_select)

        emoji_options = [
            discord.SelectOption(label="🌸 ดอกไม้ซากุระ (แบบในรูป)", value="🌸", emoji="🌸"),
            discord.SelectOption(label="🔓 กุญแจปลดล็อกห้อง", value="🔓", emoji="🔓"),
            discord.SelectOption(label="⚔️ ดาบไขว้สายบวก", value="⚔️", emoji="⚔️"),
            discord.SelectOption(label="🔥 ไฟบรรลัยกัลป์", value="🔥", emoji="🔥")
        ]
        self.emoji_select = discord.ui.Select(placeholder="✨ 2. เลือกอิโมจิประจำปุ่มกดเลยค๊าา...", options=emoji_options, row=1)
        self.emoji_select.callback = self.emoji_callback
        self.add_item(self.emoji_select)

    async def role_callback(self, interaction: discord.Interaction):
        if self.role_select.values[0] == "none": return
        self.selected_role_id = int(self.role_select.values[0])
        await interaction.response.defer()

    async def emoji_callback(self, interaction: discord.Interaction):
        self.selected_emoji = self.emoji_select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="🚀 ยืนยันและสร้างแผงรับยศเลยค๊าา!", style=discord.ButtonStyle.success, row=2)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_role_id:
            return await interaction.response.send_message("❌ คุณพี่ลืมเลือกยศหรือเปล่าเอ่ย? โปรดเลือกยศก่อนน้าาคนดี 🥺", ephemeral=True)

        await interaction.response.defer()
        role = self.guild.get_role(self.selected_role_id)
        
        embed = discord.Embed(
            title="ยินดีต้อนรับสู่โลกแห่งเซียน", 
            description=f"### ยินดีต้อนรับครับ ✋\n### กดอิโมจิ {self.selected_emoji} เพื่อยืนยันครับ👇\n\n**แมวทมิฬ FAMILY 🐈‍⬛🖤**!",
            color=0x000000
        )
        embed.set_thumbnail(url="https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?q=80&w=500") 
        embed.set_image(url=random.choice(self.group_images))

        await interaction.channel.send(embed=embed, view=DynamicGroupJoinView(self.selected_role_id, self.selected_emoji))
        await interaction.delete_original_response()


# ==========================================
# 🎵 COMPLETE MUSIC SYSTEM ENGINE
# ==========================================
music_queues = {}  
current_songs = {} 
loop_status = {}   
volume_levels = {} 

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
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
        asyncio.run_coroutine_threadsafe(channel.send("🎵 คิวเพลงหมดลงแล้วค๊าา หนูขอตัวออกจากห้องเสียงก่อนน้าา บ๊ายบายระคะคุณพี่~ 🎀"), bot.loop)
        return

    vol = volume_levels.get(guild_id, 1.0)
    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS), volume=vol)
    vc.play(source, after=lambda e: play_next_song(guild_id, vc, channel))

async def update_music_menu_embed(message, guild, author):
    try:
        if message:
            await message.edit(embed=generate_main_menu_embed(guild), view=MusicControlView(guild, author))
    except Exception as e:
        logger.error(f"Error refreshing music embed interface: {e}")


# 🔍 ค้นหาเพลงผ่านกล่องข้อความพิมพ์ข้อความ
class MusicSearchModal(discord.ui.Modal, title="🎵 ค้นหาและเพิ่มเพลงลงคิว"):
    def __init__(self, author, current_msg=None):
        super().__init__()
        self.author = author
        self.current_msg = current_msg
        self.song_query = discord.ui.TextInput(
            label="พิมพ์ชื่อเพลง หรือ วางลิงก์ YouTube ที่นี่ค๊าา", 
            placeholder="เช่น โต๊ะริม - NONT TANONT",
            required=True
        )
        self.add_item(self.song_query)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = self.song_query.value.strip()
        guild = interaction.guild
        
        if not interaction.user.voice:
            await interaction.channel.send("❌ คุณพี่ต้องเข้ามานั่งในห้องคุยเสียงก่อนสั่งหนูเปิดเพลงนะค๊าา งึมมม 🥺", delete_after=5)
            return

        await interaction.channel.send(f"🔍 น้อน Doro กำลังดำน้ำลึกไปงมหาเพลง **'{query}'** ให้คุณพี่อยู่น้าา รอแป๊บนึงนะคะ...", delete_after=5)
        
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
                await interaction.channel.send("❌ งื้อออ หนูค้นหาเพลงนี้ไม่เจอเลยค่ะ ลองเปลี่ยนคีย์เวิร์ดดูอีกทีน้าา 🥺", delete_after=5)
                return

        guild_id = guild.id
        vc = guild.voice_client

        if not vc:
            vc = await interaction.user.voice.channel.connect()

        if guild_id not in music_queues: 
            music_queues[guild_id] = []

        if vc.is_playing() or vc.is_paused():
            music_queues[guild_id].append(song_data)
            await interaction.channel.send(f"📋 เพิ่มเพลง **{song_data['title']}** เข้าสู่คิวหวาน ๆ เรียบร้อยแล้วค๊าา!", delete_after=5)
        else:
            current_songs[guild_id] = song_data
            vol = volume_levels.get(guild_id, 1.0)
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song_data['url'], **FFMPEG_OPTIONS), volume=vol)
            vc.play(source, after=lambda e: play_next_song(guild_id, vc, interaction.channel))

        target_msg = self.current_msg if self.current_msg else interaction.message
        await update_music_menu_embed(target_msg, guild, self.author)


# ==========================================
# 🎛️ CORE CENTRAL MANAGEMENT CONTROL INTERFACE (🔒 ล็อกสิทธิ์)
# ==========================================
class BotCommandControlSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🏠 หน้าแรก / เคลียร์เมนูย่อย", description="กลับสู่หน้าจอหลัก ล้างหน้าต่างปุ่มกดเสริมด้านล่าง", value="main_menu"),
            discord.SelectOption(label="🎵 เปิดระบบควบคุมและเล่นเพลง", description="เข้าสู่หน้าต่างแผงควบคุมมิวสิคบอร์ด มิกซ์เพลง/เลือกเพลงค๊าา", value="setup_music"),
            discord.SelectOption(label="🧹 เปิดระบบล้างข้อความแชท", description="ลบข้อความขยะ/รีเซ็ตล้างห้องแชทให้โล่งเตียนในพริบตา", value="setup_clear"),
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มส่งคำขอยศพิเศษ", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="สร้างแบบสอบถามโพลน่ารัก ๆ เพื่อโหวตเลือกมติของแก๊งเรา", value="setup_poll"),
            discord.SelectOption(label="🎮 รวมลิงก์ Private Server Roblox", description="คลังแสงวาปลิงก์เซิร์ฟเวอร์วีเกมต่าง ๆ ของชาวแก๊งเราค๊าา", value="roblox_servers"),
            discord.SelectOption(label="🚫 เริ่มวาระโหวตเตะสมาชิก", description="เลือกรายชื่อคนนิสัยไม่ดีเพื่อเปิดสภาโหวตขับออกจากเซิร์ฟ", value="setup_kick"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูบันทึกขีดความสามารถและไกด์สอนสั่งงานน้อน Doro กันค๊าา", value="show_commands")
        ]
        super().__init__(placeholder="🎛️ เลือกโหมดทำงานต่าง ๆ ของน้อน Doro ที่นี่ได้เลยค๊าา...", min_values=1, max_values=1, options=options, custom_id="doro_main_control_select", row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        value = self.values[0]
        current_guild = interaction.guild
        author = self.view.author 

        if value == "main_menu":
            embed = generate_main_menu_embed(current_guild)
            await interaction.message.edit(embed=embed, view=BotControlMenuView(current_guild, author))
            
        elif value == "setup_music":
            embed = generate_main_menu_embed(current_guild)
            await interaction.message.edit(embed=embed, view=MusicControlView(current_guild, author))

        elif value == "setup_clear":
            embed = discord.Embed(
                title="🧹 ระบบจัดการและกวาดล้างข้อความช่องแชท", 
                description="คุณพี่ต้องการให้น้อน Doro ปัดกวาดช่องแชทนี้รูปแบบไหนดีค๊าา?\n\n"
                            "🔹 **เลือกจำนวนลบแชท**: กวาดล้างแชทเก่าออกแบบนุ่มนวลตามจำนวน\n"
                            "⚠️ **Nuke Channel**: โคลนห้องแชทใหม่เอี่ยมถอดด้าม แล้วบอมบ์ห้องเก่าทิ้งทันที ล้างประวัติแชทขยะเกลี้ยง 100% ค๊าา!", 
                color=0x34495E
            )
            await interaction.message.edit(embed=embed, view=ClearChannelView(current_guild, author))

        elif value == "setup_roles":
            embed = discord.Embed(
                title="🛡️ ระบบเมนูกดรับยศอัตโนมัติค๊าา", 
                description="ชอบหรืออยากได้ยศไหน เลือกรับจาก Dropdown ด้านล่างนี้ได้เลยนะค๊าา หรือจะกดปุ่มขอยศพรีเมียมส่งตรงถึงห้องแอดมินก็ได้น้าา~ ✨", 
                color=0xFFB6C1
            )
            await interaction.message.edit(embed=embed, view=RequestRoleView(current_guild, author))

        elif value == "setup_poll":
            embed = discord.Embed(
                title="📊 แผงสร้างโพลสำรวจประชามติสุดคิ้วท์", 
                description="มาช่วยกันตั้งหัวข้อโพลโหวตความคิดเห็นกันเถอะค๊าา! เลือกปุ่มตั้งค่าตัวเลือกโพลด้านล่างนี้เลยน้าา~ ✨", 
                color=0x9B59B6
            )
            await interaction.message.edit(embed=embed, view=AskQuestionView(current_guild, author))

        elif value == "roblox_servers":
            embed = discord.Embed(
                title="🎮 คลังแสงรวมลิงก์ Private Server แก๊งเรา! 🚀", 
                description="จะไปฟาร์มผลไม้ ไปล่าบอส หรือเวลตึง ๆ เกมไหน เลือกเกมจากเมนูด้านล่างได้เลยค๊าา\n*(สำหรับแอดมินสามารถกดปุ่มสีเขียวเพื่อกรอกเพิ่มเซิร์ฟวีลงระบบได้น้าา)* ✨", 
                color=0x00E5FF
            )
            await interaction.message.edit(embed=embed, view=RobloxServerView(current_guild, author))

        elif value == "setup_kick":
            embed = discord.Embed(
                title="🚫 ระบบเปิดสภาโหวตเตะสมาชิก (โหมด Doro เอาจริง!)", 
                description="ใครทำตัวไม่รักดี ดื้อแพ่ง หรือก่อความวุ่นวาย เลือกรายชื่อหนุ่มสาวคนนั้นด้านล่างเพื่อเริ่มกระบวนการประชาทัณฑ์โหวตขับไล่ได้เลยค่ะ!", 
                color=discord.Color.red()
            )
            await interaction.message.edit(embed=embed, view=MemberSelectView(current_guild, author))

        elif value == "show_commands":
            embed = generate_guide_embed()
            await interaction.message.edit(embed=embed, view=BackToMainOnlyView(current_guild, author))

class BotControlMenuView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author
        self.add_item(BotCommandControlSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ อ๊ะ ๆ อย่ามาเนียนค๊าา! เมนูนี้ของคุณพี่ท่านอื่น คนดีไปพิมพ์เรียกของตัวเองน้าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="❌ ปิดหน้าต่างแผงควบคุมนี้", style=discord.ButtonStyle.danger, emoji="🔴", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except: pass

def generate_guide_embed():
    embed = discord.Embed(
        title="📘 สมุดคู่มือและบันทึกความสามารถของน้อน Doro 🤖✨",
        description="งื้อออ สวัสดีค่าา! หนูคือ **Doro** ยัยบอทสุดน่ารักที่จะมาช่วยดูแลและสร้างสีสันให้เซิร์ฟเวอร์ของทุกคนค๊าา หนูทำอะไรได้เยอะแยะเลยนะ ลองมาดูกันเยย!\n\n"
                    "🌟 **ความสามารถหลักของหนู (ฟังก์ชันเด่น):**\n"
                    "📦 **แผงควบคุม UI อัจฉริยะ**: กดสั่งงานง่าย ๆ ผ่านปุ่มและเมนู Dropdown ไม่ต้องพิมพ์คำสั่งให้เหนื่อยค๊าา\n"
                    "🎵 **มิวสิคบอร์ดแยกแท็บ**: เข้าหน้าต่างควบคุมเพลงและคิวได้แบบเป็นสัดส่วนผ่าน Dropdown\n"
                    "🧹 **ระบบล้างแชทและรีเซ็ตห้อง**: สั่งกวาดล้างข้อความขยะ หรือล้างห้องแชทให้ขาวสะอาด 100% ด้วยปุ่ม Nuke\n"
                    "🛡️ **ระบบแจกและขอยศสุดตึง**: เลือกรับยศเอง หรือส่งคำขออ้อน ๆ มาขอยศพิเศษก็ได้น้าา\n"
                    "📊 **โพลระดมความคิด**: สร้างคำถามและส่งไปห้องที่ต้องการ พร้อมระบบนับคะแนนเรียลไทม์\n"
                    "🎮 **คลังแสงเซิร์ฟ Roblox**: รวมลิงก์ตั๋วเข้า Private Server เกมโปรดของแก๊งเราไว้ที่เดียว\n"
                    "🚫 **ศาลเตี้ยโหวตเตะ**: เปิดวาระโหวตลงมติเพื่อดีดออกจากห้องเสียงหรือเซิร์ฟเวอร์\n\n"
                    "--------------------------------------------------\n\n"
                    "📌 **สรุปคำสั่งพิมพ์ด่วน (Quick Commands):**\n"
                    "`doro เมนู` / `doro menu` / `doro คำสั่งเพลง` : เรียกเปิดแผงควบคุมระบบ UI ทั้งหมดค๊าา\n"
                    "`doro ให้ยศ` / `doro addrole` : หน้าต่างด่วนสำหรับแอดมินแจกยศกลุ่มความเร็วสูง\n"
                    "`doro ลบข้อความ <จำนวน>` : สั่งเคลียร์ข้อความขยะในห้องแชท\n"
                    "`doro เล่น <ชื่อเพลง/ลิงก์>` : สั่งน้อน Doro ดำน้ำไปเปิดเพลงค๊าา\n"
                    "`doro สร้างปุ่มรับยศ` : สร้างกล่องกดรับยศเข้ากลุ่มลับอัจฉริยะแบบแอดมิน",
        color=discord.Color.magenta()
    )
    return embed

def generate_main_menu_embed(guild):
    guild_id = guild.id
    song = current_songs.get(guild_id)
    vc = guild.voice_client

    embed = discord.Embed(
        title="⚙️ Doro แผงควบคุมระบบอัจฉริยะ (All-in-One UI Mode)", 
        description="งื้อออ สวัสดีค่าา! หนูคือ **Doro** ยัยบอทสุดน่ารักที่จะมาช่วยดูแลและสร้างสีสันให้เซิร์ฟเวอร์ของทุกคนค๊าา หนูทำอะไรได้เยอะแยะเลยนะ ลองมาดูกันเยย! เลือกเปลี่ยนฟังก์ชันใช้งานน้อนได้ผ่านแถบ Dropdown เมนูด้านล่างนี้เลยน้าา ✨", 
        color=0x3498DB
    )
    
    if vc and vc.is_connected() and song:
        status_str = "🟢 กำลังขับขานเสียงเพลงอย่างมีความสุข" if not vc.is_paused() else "⏸️ พักเบรกเสียงเพลงชั่วคราว"
        embed.add_field(
            name="🎵 แทร็กเพลงที่กำลังเล่นอยู่ตอนนี้",
            value=f"**ชื่อเพลง:** [{song['title']}]({song['webpage_url']})\n**ดีเจผู้ขอคิว:** {song['requester']}\n**สถานะ:** {status_str}",
            inline=False
        )
        if song.get('thumbnail'):
            embed.set_thumbnail(url=song['thumbnail'])
    else:
        embed.add_field(
            name="🎵 แทร็กเพลงที่กำลังเล่นอยู่ตอนนี้",
            value="❌ แผงเล่นเพลงปิดอยู่ หรือหนูยังไม่ได้เข้าห้องเสียงเลยค๊าาคุณพี่",
            inline=False
        )
        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        
    return embed


# ==========================================
# 🎵 MUSIC DETAILED CONTROLS (🔒 ล็อกสิทธิ์)
# ==========================================
class MusicControlView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ อ๊ะ ๆ อย่ามาเนียนค๊าา! แผงควบคุมมิวสิคนี้ของคุณพี่ท่านอื่นน้าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📥 วาร์ปเข้าห้องเสียง", style=discord.ButtonStyle.primary, emoji="🎙️", row=0)
    async def join_vc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user.voice:
            vc = interaction.guild.voice_client
            if not vc:
                await interaction.user.voice.channel.connect()
                await interaction.channel.send(f"📥 หนูซอยเท้าดุ๊กๆ เข้าห้อง **{interaction.user.voice.channel.name}** ตามเสียงเรียกคุณพี่แล้วค๊าา!", delete_after=3)
            else:
                await vc.move_to(interaction.user.voice.channel)
        else:
            await interaction.channel.send("❌ คุณพี่ต้องเอาตัวเองเข้าห้องคุยเสียงก่อนน้าา หนูจะได้ตามไปสิงสถิตถูกห้องงับ 🥺", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild, self.author)

    @discord.ui.button(label="🔍 ค้นหาเพลงโปรด (Play)", style=discord.ButtonStyle.success, emoji="🎵", row=0)
    async def search_play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MusicSearchModal(self.author, current_msg=interaction.message))

    @discord.ui.button(label="⏸️ เล่น/หยุดชั่วคราว", style=discord.ButtonStyle.secondary, emoji="⏯️", row=0)
    async def pause_resume_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.pause()
                await interaction.channel.send("⏸️ แอบเบรกหยุดเพลงไว้ชั่วคราวน้าาา", delete_after=3)
            elif vc.is_paused():
                vc.resume()
                await interaction.channel.send("▶️ ลุยลื่นไหลบรรเลงทำนองต่อเลยค๊าา!", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild, self.author)

    @discord.ui.button(label="⏭️ Skip เพลงถัดไป", style=discord.ButtonStyle.secondary, emoji="⏩", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            loop_status[self.guild.id] = False
            vc.stop()
            await interaction.channel.send("⏭️ น้อน Doro ปัดข้ามแทร็กเพลงนี้ให้แล้วค๊าา!", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild, self.author)

    @discord.ui.button(label="🔁 โหมดวนเพลงเดิม", style=discord.ButtonStyle.primary, emoji="🔄", row=1)
    async def loop_toggle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        gid = self.guild.id
        loop_status[gid] = not loop_status.get(gid, False)
        state_text = "เปิดวนลูปเพลงเดิมฉ่ำ ๆ 🔁" if loop_status[gid] else "ปิดการวนลูปแล้วค๊าา ➡️"
        await interaction.channel.send(f"📢 ตอนนี้ระบบทำการ {state_text} เรียบร้อยค๊าา!", delete_after=3)

    @discord.ui.button(label="🔊 เพิ่มเสียง", style=discord.ButtonStyle.secondary, emoji="➕", row=1)
    async def vol_up(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        gid = self.guild.id
        cur_vol = volume_levels.get(gid, 1.0)
        volume_levels[gid] = min(cur_vol + 0.2, 2.0)
        vc = interaction.guild.voice_client
        if vc and vc.source: vc.source.volume = volume_levels[gid]
        await interaction.channel.send(f"🔊 เพิ่มระดับเสียงเบสหนัก ๆ เป็น {int(volume_levels[gid]*100)}% แล้วค๊าา!", delete_after=3)

    @discord.ui.button(label="🔉 ลดเสียง", style=discord.ButtonStyle.secondary, emoji="➖", row=1)
    async def vol_down(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        gid = self.guild.id
        cur_vol = volume_levels.get(gid, 1.0)
        volume_levels[gid] = max(cur_vol - 0.2, 0.0)
        vc = interaction.guild.voice_client
        if vc and vc.source: vc.source.volume = volume_levels[gid]
        await interaction.channel.send(f"🔉 หรี่ลดระดับเสียงถนอมหูเหลือ {int(volume_levels[gid]*100)}% แล้วค๊าา!", delete_after=3)

    @discord.ui.button(label="🛑 Stop & ล้างคิวหมดแผง", style=discord.ButtonStyle.danger, emoji="🛑", row=2)
    async def stop_music_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild_id = self.guild.id
        vc = interaction.guild.voice_client
        music_queues[guild_id] = []
        if guild_id in current_songs: 
            del current_songs[guild_id]
        if vc: 
            await vc.disconnect()
        await interaction.channel.send("🛑 ล้างกระดานคิวเพลงทิ้งเกลี้ยงตับ และตัดสายห้องคุยเสียงแล้วค๊าา!", delete_after=3)
        await update_music_menu_embed(interaction.message, self.guild, self.author)

    @discord.ui.button(label="🔙 ย้อนกลับเมนูหลัก", style=discord.ButtonStyle.success, emoji="⬅️", row=2)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# 🧹 CHANNEL PRUNING & NUKE (🔒 ล็อกสิทธิ์)
# ==========================================
class CustomClearModal(discord.ui.Modal, title="🧹 ระบุจำนวนแชทที่อยากสลาย"):
    def __init__(self):
        super().__init__()
        self.amount_input = discord.ui.TextInput(label="กวาดล้างกี่ข้อความดีค๊าา? (ระบุตัวเลข 1-100)", placeholder="ใส่จำนวน เช่น 40", required=True)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ โถ่คุณพี่.. สิทธิ์จัดการข้อความไม่มี ข้ามหนูน้องไปก่อนน้าา", ephemeral=True)
        try:
            amt = int(self.amount_input.value.strip())
            await interaction.response.defer()
            deleted = await interaction.channel.purge(limit=amt)
            await interaction.channel.send(f"🧹 น้อน Doro บินไปสลายข้อความขยะออกไปให้แล้ว {len(deleted)} ข้อความค๊าา โล่งสบายตาเว่อร์! ✨", delete_after=4)
        except ValueError:
            await interaction.response.send_message("❌ คีย์ตัวเลขมาสิคะคุณพี่ ขอกลม ๆ ไม่เอาตัวหนังสือน้าา", ephemeral=True)

class ClearChannelView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ ห้องแชทนี้เป็นสิทธิ์ปัดกวาดของคุณพี่ท่านอื่นนะค๊าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🧹 ล้าง 5 แชทล่าสุด", style=discord.ButtonStyle.secondary, row=0)
    async def clear_5(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.channel.purge(limit=6) 
        await interaction.channel.send("🧹 ลบเศษขยะแชท 5 แถวให้เรียบร้อยค๊าา!", delete_after=3)

    @discord.ui.button(label="🔢 ระบุจำนวนเอง", style=discord.ButtonStyle.primary, row=0)
    async def clear_custom(self, interaction: discord.Interaction, btn):
        await interaction.response.send_modal(CustomClearModal())

    @discord.ui.button(label="💥 สั่ง Nuke ห้องนี้ทิ้งระเบิดตู้มม!", style=discord.ButtonStyle.danger, emoji="💥", row=1)
    async def nuke_channel_btn(self, interaction: discord.Interaction, btn):
        if not interaction.user.guild_permissions.manage_channels: 
            return await interaction.response.send_message("❌ แอดมินจำแลงปะเนี่ย ไม่มีสิทธิ์ลบห้องนะค๊าา!", ephemeral=True)
        await interaction.response.defer()
        current_channel = interaction.channel
        new_channel = await current_channel.clone()
        await new_channel.edit(position=current_channel.position)
        await current_channel.delete()
        await new_channel.send("💥 ห้องนี้โดนระเบ็ตระเบิดทำลายล้างเรียบร้อยค๊าา! เสกห้องใหม่เอี่ยมอ่องสไลเดอร์ให้แทนแล้วน้าา~ ✨", delete_after=6)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.success, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# 🎮 ROBLOX DATA AND LINK VAULT SYSTEM (🔒 ล็อกสิทธิ์ + 🛡️ คราสการ์ด)
# ==========================================
class AddRobloxServerModal(discord.ui.Modal, title="🎮 แอดมินโหมด: เพิ่มข้อมูลลิงก์เซิร์ฟวี"):
    def __init__(self, selected_emoji: str):
        super().__init__()
        self.selected_emoji = selected_emoji
        self.game_id = discord.ui.TextInput(label="รหัสเกม (อังกฤษพิมพ์เล็ก ติดกันห้ามเว้นวรรค)", placeholder="เช่น blox_fruits", required=True)
        self.game_name = discord.ui.TextInput(label="ชื่อเกมสไตล์ไทยเท่ๆ", placeholder="เช่น บล็อกฟรุ๊ตตึงๆ", required=True)
        self.game_url = discord.ui.TextInput(label="ลิงก์ Private Server จากหน้าเว็บ Roblox", placeholder="https://www.roblox.com/share?...", required=True)
        self.add_item(self.game_id)
        self.add_item(self.game_name)
        self.add_item(self.game_url)
        
    async def on_submit(self, interaction: discord.Interaction):
        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        full_name = f"{self.selected_emoji} {self.game_name.value.strip()}"
        current_data = load_roblox_data()
        current_data[g_id] = {"name": full_name, "url": self.game_url.value.strip()}
        save_roblox_data(current_data)
        await interaction.response.send_message(f"✅ บันทึกเกม **{full_name}** เข้ากรุคลังแสงเรียบร้อยแล้วค๊าา แอดมินสุดหล่อ! 🥰", ephemeral=True)

class RobloxServerSelect(discord.ui.Select):
    def __init__(self):
        current_data = load_roblox_data()
        
        # 🛡️ บั๊กการ์ดคุ้มครอง: ถ้าคลัง JSON ว่างเปล่า ให้สร้างเมนูสำรองป้องกัน Discord แตกหัก!
        if not current_data:
            options = [discord.SelectOption(label="❌ คลังว่างเปล่า ไม่มีลิงก์เซิร์ฟวีในระบบเลยค๊าา", value="none")]
        else:
            options = [discord.SelectOption(label=data["name"][:90], value=key) for key, data in current_data.items()]
            
        super().__init__(placeholder="🎮 เลือกเกมที่แก๊งเราเปิดเซิร์ฟวีไว้เพื่อวาร์ป...", options=options)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": 
            return await interaction.response.send_message("❌ ไม่มีตั๋วลิงก์เซิร์ฟวีเลยค๊าา แอดมินโปรดกดปุ่มด้านล่างเพิ่มเกมก่อนน้าา", ephemeral=True)
        
        game_data = load_roblox_data().get(self.values[0])
        if game_data:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="👉 กดตรงนี้เพื่อวาร์ปไปเล่นกันเยย! 🚀", url=game_data['url']))
            await interaction.response.send_message(f"🚀 เตรียมตัวกระโดดขึ้นยานวาร์ปทะลุมิติไปเกม {game_data['name']} กันเลยน้าา~ ลุยย", view=view, ephemeral=True)

class RobloxServerView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author
        self.add_item(RobloxServerSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ หน้าต่างค้นหาลิงก์วาปอันนี้เป็นของคุณพี่ท่านอื่นค๊าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕ เพิ่มเกมใหม่ (แอดมิน)", style=discord.ButtonStyle.success, row=1)
    async def add_game_btn(self, interaction: discord.Interaction, btn):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ เฉพาะแอดมินระดับสูงสุดเท่านั้นน้าาที่จะเพิ่มลิงก์ได้งับ 🥺", ephemeral=True)
        await interaction.response.send_modal(AddRobloxServerModal("🎮"))

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# 🛡️ INTERIOR MULTI-ROLE & USER REQUESTS (🔒 ล็อกสิทธิ์ + 🛡️ คราสการ์ด)
# ==========================================
class RoleSubmitModal(discord.ui.Modal, title="📝 ส่งคำร้องขอยศพิเศษอ้อนแอดมิน"):
    def __init__(self, role_name: str):
        super().__init__()
        self.role_name = role_name
        self.reason = discord.ui.TextInput(label="ส่งเหตุผลอ้อนหวานๆ ที่อยากได้ยศนี้หน่อยค๊าา", style=discord.TextStyle.paragraph, placeholder="เช่น แอดมินขาา น้อนฟาร์มเวลตันแล้ว ขอยศสายแบกหน่อยน้าาจุ๊บๆ...", required=True)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"💌 น้อน Doro คาบจดหมายคำขอรับยศ **'{self.role_name}'** พร้อมเหตุผลสุดอ้อน บินไปหย่อนใส่โต๊ะทำงานของแอดมินเรียบร้อยแล้วค๊าา รออนุมัติน้าาคนดี~", ephemeral=True)

class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed and r.position < guild.me.top_role.position]
        options = [discord.SelectOption(label=f"ยศ: {r.name[:80]}", value=str(r.id), emoji="✨") for r in roles[:25]]
        
        # 🛡️ บั๊กการ์ดคุ้มครอง: ถ้าเซิร์ฟเวอร์ไม่มียศให้เลือก หรือยศบอทอยู่ต่ำสุด ป้องกันไม่ให้ดิสคอร์ดล่มค๊าา!
        if not options:
            options = [discord.SelectOption(label="❌ ไม่มีสิทธิ์แจกยศใดๆ ในตอนนี้ (บอทยศต่ำสุด)", value="none")]

        super().__init__(placeholder="🎨 เลือกยศทั่วไปที่คุณต้องการกดรับด้วยตัวเอง...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": 
            return await interaction.response.send_message("❌ ไม่สามารถแจกยศได้ค๊าา แอดมินต้องสร้างยศและเลื่อนระดับบอทให้สูงกว่ายศที่อยากแจกก่อนน้าา", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(int(self.values[0]))
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.followup.send(f"ถอดสลายยศ **{role.name}** ออกจากโปรไฟล์แล้วค๊าา ✨", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.followup.send(f"แต่งตั้งมอบยศ **{role.name}** ประดับตัวให้เรียบร้อยจ้าา เลิศเว่อร์! 💕", ephemeral=True)

class RequestRoleView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author
        self.add_item(RoleSelect(guild))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ กล่องเลือกรับยศตรงนี้เป็นเซ็ตส่วนตัวของคุณพี่ท่านอื่นนะค๊าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="👑 ขอยศ VIP ระดับสูง (ส่งตั๋วหาแอดมิน)", style=discord.ButtonStyle.danger, emoji="💖", row=1)
    async def request_vip(self, interaction: discord.Interaction, btn):
        await interaction.response.send_modal(RoleSubmitModal("VIP Elite"))

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# 📊 DECORATED OPINION POLL CONTEXT (🔒 ล็อกสิทธิ์)
# ==========================================
class PollLaunchModal(discord.ui.Modal, title="📊 ตั้งข้อคำถามมติมหาชน"):
    def __init__(self):
        super().__init__()
        self.title_input = discord.ui.TextInput(label="หัวข้อโพลที่จะให้โหวต", placeholder="เช่น เย็นนี้กินชาบูหรือหมูกระทะกันดีค๊าา?", required=True)
        self.opt1 = discord.ui.TextInput(label="ตัวเลือกที่ 1️⃣", placeholder="กินชาบูซุปน้ำดำ", required=True)
        self.opt2 = discord.ui.TextInput(label="ตัวเลือกที่ 2️⃣", placeholder="หมูกระทะเยียวยาจิตใจ", required=True)
        self.add_item(self.title_input)
        self.add_item(self.opt1)
        self.add_item(self.opt2)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title=f"📊 โพลสำรวจ: {self.title_input.value}",
            description=f"คุณพี่สมาชิกร่วมใจกดโหวตมติได้ที่ปุ่มด้านล่างนี้เลยน้าา\n\n1️⃣ **{self.opt1.value}** : 0 เสียง\n2️⃣ **{self.opt2.value}** : 0 เสียง",
            color=0x9B59B6
        )
        poll_id = f"poll_{int(datetime.now().timestamp())}"
        vote_records[poll_id] = {"voters": {}, "title": self.title_input.value, "o1_text": self.opt1.value, "o2_text": self.opt2.value, "o1_count": 0, "o2_count": 0}
        
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label=self.opt1.value[:40], style=discord.ButtonStyle.primary, custom_id=f"{poll_id}_1", emoji="1️⃣"))
        view.add_item(discord.ui.Button(label=self.opt2.value[:40], style=discord.ButtonStyle.success, custom_id=f"{poll_id}_2", emoji="2️⃣"))
        
        poll_msg = await interaction.channel.send(embed=embed, view=view)
        poll_result_messages[poll_id] = poll_msg.id

class AskQuestionView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ เมนูสร้างโพลสำรวจนี้เปิดสิทธิ์ให้เฉพาะคุณพี่ที่พิมพ์เรียกใช้เท่านั้นค๊าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📝 เริ่มสร้างกล่องโพลใหม่ทันที", style=discord.ButtonStyle.primary, emoji="➕", row=0)
    async def create_poll(self, interaction: discord.Interaction, btn):
        await interaction.response.send_modal(PollLaunchModal())

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# 🚫 PARLIAMENT MEMBER VOTE KICK CORE (🔒 ล็อกสิทธิ์)
# ==========================================
class MemberSelectView(discord.ui.View):
    def __init__(self, guild, author): 
        super().__init__(timeout=120)
        self.guild = guild
        self.author = author
        
        members = [m for m in guild.members if not m.bot][:25]
        options = [discord.SelectOption(label=m.display_name, value=str(m.id), description=f"ID: {m.id}", emoji="👤") for m in members] if members else [discord.SelectOption(label="ไม่มีสมาชิกให้เลือก", value="none")]
        
        self.member_select = discord.ui.Select(placeholder="🚫 เลือกรายชื่อคนดื้อที่จะเริ่มประชามติโหวตเตะ...", options=options, row=0)
        self.member_select.callback = self.member_select_callback
        self.add_item(self.member_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ แผงควบคุมเปิดวาระสภานี้ ล็อกสิทธิ์ไว้เฉพาะผู้เรียกใช้ค๊าา 🥺", ephemeral=True)
            return False
        return True

    async def member_select_callback(self, interaction: discord.Interaction):
        if self.member_select.values[0] == "none": return
        await interaction.response.defer()
        target_member = self.guild.get_member(int(self.member_select.values[0]))
        
        if not target_member: return
        
        kick_id = f"kick_{target_member.id}"
        vote_records[kick_id] = {"target": target_member.id, "voters": [], "needed": 3} 
        
        embed = discord.Embed(
            title="🚨 วาระสภาประชาชน: โหวตขับไล่สมาชิกออกจากเมือง!",
            description=f"ผู้ถูกเสนอชื่อขับไล่: {target_member.mention}\nต้องการเสียงสนับสนุนทั้งหมด: **3 เสียง** เพื่อเตะออก!\n\n**รายชื่อผู้ลงมติเห็นพ้อง:** ยังไม่มีคนกดยืนยัน",
            color=discord.Color.red()
        )
        
        view = discord.ui.View(timeout=None)
        btn = discord.ui.Button(label="🔨 กดยืนยันร่วมโหวตเตะ!", style=discord.ButtonStyle.danger, custom_id=f"execute_{kick_id}", emoji="👎")
        view.add_item(btn)
        
        await interaction.channel.send(embed=embed, view=view)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# 📘 AUXILIARY BACK INTERFACES (🔒 ล็อกสิทธิ์)
# ==========================================
class BackToMainOnlyView(discord.ui.View):
    def __init__(self, guild, author):
        super().__init__(timeout=None)
        self.guild = guild
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ ปุ่มย้อนกลับนี้ล็อกสิทธิ์ไว้ส่วนตัวค๊าา 🥺", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔙 ย้อนกลับสู่แผงควบคุมหน้าแรกค๊าา", style=discord.ButtonStyle.success, emoji="🏠")
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild, self.author))


# ==========================================
# ⚙️ GLOBAL INTERACTION INTERCEPT & GATEKEEPER
# ==========================================
@bot.event
async def on_ready(): 
    bot.add_view(DynamicGroupJoinView(role_id=0, emoji_str="🌸"))
    logger.info(f"✨ Doro Multi-Platform Core Engined Active with Safety Patch! ✨")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    custom_id = interaction.data.get("custom_id", "")
    
    if custom_id.startswith("poll_"):
        await interaction.response.defer(ephemeral=True)
        parts = custom_id.split("_")
        poll_id = f"poll_{parts[1]}"
        choice = parts[2]
        user_id = str(interaction.user.id)
        
        poll_data = vote_records.get(poll_id)
        if not poll_data: return
        
        if user_id in poll_data["voters"]:
            return await interaction.followup.send("❌ คุณพี่เคยลงมติโหวตไปแล้วน้าา อย่าแอบกดซ้ำสิคะ งึมมม 🥺", ephemeral=True)
            
        poll_data["voters"][user_id] = choice
        if choice == "1": poll_data["o1_count"] += 1
        else: poll_data["o2_count"] += 1
        
        await interaction.followup.send("🎉 บันทึกเสียงโหวตของคุณพี่เข้าสู่ระบบเรียบร้อยแล้วค๊าา ขอบคุณน้าา 💕", ephemeral=True)
        
        msg_id = poll_result_messages.get(poll_id)
        if msg_id:
            try:
                msg = await interaction.channel.fetch_message(msg_id)
                new_embed = discord.Embed(
                    title=f"📊 โพลสำรวจ: {poll_data['title']}",
                    description=f"คุณพี่สมาชิกร่วมใจกดโหวตมติได้ที่ปุ่มด้านล่างนี้เลยน้าา\n\n1️⃣ **{poll_data['o1_text']}** : {poll_data['o1_count']} เสียง\n2️⃣ **{poll_data['o2_text']}** : {poll_data['o2_count']} เสียง",
                    color=0x9B59B6
                )
                await msg.edit(embed=new_embed)
            except: pass
        return

    if custom_id.startswith("execute_kick_"):
        await interaction.response.defer(ephemeral=True)
        kick_id = custom_id.replace("execute_", "")
        data = vote_records.get(kick_id)
        if not data: return
        
        uid = interaction.user.id
        if uid in data["voters"]:
            return await interaction.followup.send("❌ โหวตไปแล้วรอบนึงค๊าา รักกันจริงอย่ากดเบิ้ลน้าาคุณพี่ 🥺", ephemeral=True)
            
        data["voters"].append(uid)
        current_votes = len(data["voters"])
        target_user = interaction.guild.get_member(data["target"])
        
        if not target_user: return
        
        names_list = ", ".join([interaction.guild.get_member(v).display_name for v in data["voters"] if interaction.guild.get_member(v)])
        
        if current_votes >= data["needed"]:
            try:
                await target_user.kick(reason="โดนสภาประชาชนร่วมใจโหวตขับไล่ค๊าา")
                embed = discord.Embed(title="🔨 มติสภาโหวตสัมฤทธิ์ผลเตะปลิวเรียบร้อย!", description=f"สมาชิกนาม {target_user.mention} โดนเตะออกจากเซิร์ฟเวอร์ค๊าา!", color=discord.Color.dark_red())
                await interaction.channel.send(embed=embed)
            except discord.Forbidden:
                await interaction.channel.send(f"❌ ยศของน้อน Doro ต่ำกว่าคุณพี่ {target_user.display_name} หนูเลยเตะเค้าออกไม่ได้ค๊าา 🥺")
        else:
            embed = discord.Embed(
                title="🚨 วาระสภาประชาชน: โหวตขับไล่สมาชิกออกจากเมือง!",
                description=f"ผู้ถูกเสนอชื่อขับไล่: {target_user.mention}\nต้องการเสียงสนับสนุนทั้งหมด: **3 เสียง** (ตอนนี้ได้ {current_votes} เสียงค๊าา)\n\n**รายชื่อผู้ร่วมลงมติเห็นพ้อง:**\n`{names_list}`",
                color=discord.Color.red()
            )
            await interaction.message.edit(embed=embed)
        await interaction.followup.send("👉 ลงคะแนนยินยอมให้ขับไล่บุคคลนี้สำเร็จค๊าา!", ephemeral=True)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    msg = message.content.strip()
    lower_msg = msg.lower()

    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
        return

    if any(f"doro {k}" in lower_msg or f"doro{k}" in lower_msg for k in ["เมนู", "menu", "คำสั่งเพลง", "music"]):
        try: await message.delete()
        except: pass
        await message.channel.send(embed=generate_main_menu_embed(message.guild), view=BotControlMenuView(message.guild, message.author))
        return

    if lower_msg == "doro สร้างปุ่มรับยศ":
        if not message.author.guild_permissions.manage_roles: 
            return await message.channel.send("❌ คำสั่งสำหรับคนระยศสูงเท่านั้นนะค๊าาคุณพี่ขาา")
        try: await message.delete()
        except: pass
            
        admin_setup_embed = discord.Embed(
            title="🛠️ แผงควบคุมสร้างปุ่มกล่องรับยศเข้ากลุ่ม (แอดมินโหมดค๊าา)",
            description="รบกวนคุณพี่เลือกยศที่จะแจกและรูปแบบปุ่มกดด้านล่างนี้ให้ครบถ้วนนะคะ จากนั้นกดปุ่มสีเขียวยืนยันเพื่อเสกข้อความสไตล์แมวทมิฬลงห้องแชทได้ทันทีค๊าา! ✨",
            color=0x000000
        )
        await message.channel.send(embed=admin_setup_embed, view=RoleSetupAdminView(message.guild), delete_after=60)
        return

bot.run(DISCORD_TOKEN)
