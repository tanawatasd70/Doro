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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doro")

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
JSON_FILE = "roblox_servers.json"

def load_roblox_data():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f: 
            return json.load(f)
    except FileNotFoundError:
        default_data = {"blox_fruits": {"name": "🏴‍☠️ Blox Fruits", "url": "https://www.roblox.com/"}}
        save_roblox_data(default_data)
        return default_data

def save_roblox_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)


# ==========================================
# 🎵 MUSIC SYSTEM ENGINE
# ==========================================
music_queues = {}  
current_songs = {} 
loop_status = {}   

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

        status_msg = await interaction.channel.send(f"🔍 น้อน Doro กำลังดำน้ำไปงมหาเพลง **'{query}'** บน YouTube แป๊บน้าน้าา...", delete_after=5)
        
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
# 🏗️ MODAL & UI สำหรับสร้างห้องแชทแบบจัดเต็ม
# ==========================================

class MultiChannelModal(discord.ui.Modal, title="🏗️ สร้างห้องแชทหลายห้องพร้อมกัน"):
    def __init__(self, category=None):
        super().__init__()
        self.category = category
        self.channel_names = discord.ui.TextInput(
            label="ชื่อห้อง (คั่นด้วยเครื่องหมาย ,)",
            placeholder="คุยเล่น, ฟังเพลง, ปาร์ตี้เกม",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.channel_names)

    async def on_submit(self, interaction: discord.Interaction):
        names = [n.strip() for n in self.channel_names.value.split(",") if n.strip()]
        created_count = 0
        
        await interaction.response.defer(ephemeral=True)
        
        for name in names:
            try:
                await interaction.guild.create_text_channel(name, category=self.category)
                created_count += 1
            except:
                continue
        
        await interaction.followup.send(f"✨ สร้างห้องให้แล้วทั้งหมด {created_count} ห้องในหมวด **{self.category.name if self.category else 'ทั่วไป'}** เรียบร้อยค๊าา! 🎀", ephemeral=True)

class MultiChannelSetupView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        
        # Dropdown เลือกหมวดหมู่
        self.category_select = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.category],
            placeholder="📂 เลือกหมวดหมู่ที่อยากให้ห้องไปอยู่...",
            min_values=1, max_values=1
        )
        self.category_select.callback = self.select_category
        self.add_item(self.category_select)

    async def select_category(self, interaction: discord.Interaction):
        # เมื่อเลือกหมวดหมู่แล้ว ให้เด้ง Modal ให้พิมพ์ชื่อห้อง
        category = interaction.data['resolved']['channels'][self.category_select.values[0]]
        cat_obj = self.guild.get_channel(int(self.category_select.values[0]))
        
        await interaction.response.send_modal(MultiChannelInputModal(cat_obj))

class MultiChannelInputModal(discord.ui.Modal, title="🏗️ ระบุชื่อห้อง (คั่นด้วย ,)"):
    def __init__(self, category):
        super().__init__()
        self.category = category
        self.channel_names = discord.ui.TextInput(
            label="ชื่อห้องแชท",
            placeholder="ห้อง 1, ห้อง 2, ห้อง 3",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.channel_names)

    async def on_submit(self, interaction: discord.Interaction):
        names = [n.strip() for n in self.channel_names.value.split(",") if n.strip()]
        await interaction.response.defer(ephemeral=True)
        
        count = 0
        for name in names:
            try:
                await interaction.guild.create_text_channel(name, category=self.category)
                count += 1
            except: continue
        await interaction.followup.send(f"✅ สร้างให้แล้ว {count} ห้อง ในหมวดหมู่ **{self.category.name}** ค๊าา!", ephemeral=True)

# ==========================================
# 🎛️ MAIN UI COMMAND MENU 
# ==========================================
class BotCommandControlSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🏠 หน้าแรก / เคลียร์เมนูย่อย", description="กลับสู่หน้าจอเริ่มต้น ล้างหน้าต่างการทำงานด้านล่าง", value="main_menu"),
            discord.SelectOption(label="🎵 เปิดระบบควบคุมและเล่นเพลง", description="เข้าสู่หน้าต่างควบคุมมิวสิคบอร์ด เปิดเพลง/เลือกเพลงค๊าา", value="setup_music"),
            discord.SelectOption(label="🧹 เปิดระบบล้างข้อความแชท", description="ลบข้อความขยะ/รีเซ็ตล้างห้องแชทให้เกลี้ยงในพริบตา", value="setup_clear"),
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศสุดน่ารัก", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="สร้างโพลน่ารัก ๆ เพื่อโหวตเลือกคำตอบกันเถอะ", value="setup_poll"),
            discord.SelectOption(label="🎮 รวมลิงก์ Private Server Roblox", description="คลังแสงลิงก์เซิร์ฟเวอร์วีเกมต่าง ๆ ของชาว Robloxค๊าา", value="roblox_servers"),
            discord.SelectOption(label="🏗️ สร้างห้องแชทหลายห้อง", description="สร้างช่องแชทจำนวนมากในครั้งเดียวค๊าา", value="setup_channels"),
            discord.SelectOption(label="🚫 เริ่มวาระโหวตเตะสมาชิก", description="เลือกคนที่ทำตัวไม่น่ารักเพื่อเริ่มโหวตเตะกันค่ะ!", value="setup_kick"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูคู่มือการสั่งงานและบันทึกความสามารถน้อน Doro กันงับ", value="show_commands")
        ]
        super().__init__(placeholder="🎛️ หรือเลือกโหมดทำงานอื่น ๆ ของน้อน Doro ที่นี่...", min_values=1, max_values=1, options=options, custom_id="doro_main_control_select", row=0)

    async def callback(self, interaction: discord.Interaction):
        # หากเลือกสร้างช่องแชท ให้เปิด Modal โดยไม่ต้อง edit ข้อความ
        async def callback(self, interaction: discord.Interaction):
        # แก้ไขตรงนี้ครับ:
        if self.values[0] == "setup_channels":
            await interaction.response.send_message("📂 กรุณาเลือกหมวดหมู่ที่ต้องการสร้างห้องก่อนนะค๊าา:", view=MultiChannelSetupView(interaction.guild), ephemeral=True)
            return
        
        await interaction.response.defer()
        value = self.values[0]
        current_guild = interaction.guild
        
        # 🏗️ โหมดสร้างห้องแชท
        if value == "setup_channels":
            await interaction.response.send_modal(MultiChannelModal())
            return

        # สำหรับเมนูอื่นๆ
        await interaction.response.defer()
        
        if value == "main_menu":
            embed = generate_main_menu_embed(current_guild)
            await interaction.message.edit(embed=embed, view=BotControlMenuView(current_guild))
            
        elif value == "setup_music":
            embed = generate_main_menu_embed(current_guild)
            await interaction.message.edit(embed=embed, view=MusicControlView(current_guild))

        elif value == "setup_clear":
            embed = discord.Embed(
                title="🧹 ระบบจัดการและล้างข้อความในช่องแชท", 
                description="คุณพี่ต้องการให้น้อน Doro จัดการช่องแชทนี้อย่างไรดีค๊าา?\n\n"
                            "🔹 **ลบตามจำนวนล่าสุด**: กวาดล้างข้อความเก่าออกตามจำนวนที่เลือก\n"
                            "⚠️ **รีเซ็ตห้องแชท (Nuke)**: ทำการโคลนและลบห้องเดิมทิ้งทันที เพื่อล้างประวัติแชททั้งหมดให้โล่ง 100% ค๊าา! *(ต้องการสิทธิ์จัดการช่องแชลเนล)*", 
                color=0x34495E
            )
            await interaction.message.edit(embed=embed, view=ClearChannelView(current_guild))

        elif value == "setup_roles":
            embed = discord.Embed(title="🛡️ ระบบจัดการยศอัตโนมัติค๊าา", description="คุณชอบยศไหนเลือกรับจากเมนูด้านล่างนี้ได้เลยนะค๊าา หรือจะกดปุ่มขอยศพิเศษพร้อมส่งเหตุผลอ้อน ๆ มาให้แอดมินดูก็ได้น้าา~ ✨", color=0xFFB6C1)
            await interaction.message.edit(embed=embed, view=RequestRoleView(current_guild))
            
        elif value == "setup_poll":
            embed = discord.Embed(title="📊 ระบบสร้างคำถามโพลระดมความคิดค๊าา", description="กรุณากรอกหัวข้อคำถาม และเลือกช่องทางปล่อยโพลให้ครบถ้วนด้านล่างนี้เลยน้าา~ ✨", color=0x9B59B6)
            await interaction.message.edit(embed=embed, view=AskQuestionView(current_guild))
            
        elif value == "roblox_servers":
            embed = discord.Embed(title="🎮 คลังแสง Private Server ของแก๊งเรา! 🚀", description="อยากไปฟาร์ม ไปเวล หรือไปตึงเกมไหน เลือกชื่อเกมจากเมนูด้านล่างนี้ได้เลยค๊าา\n(สำหรับแอดมินสามารถกดปุ่มเพื่อเพิ่มหรือลบเกมได้เลยนะค๊าา) ✨", color=0x00E5FF)
            await interaction.message.edit(embed=embed, view=RobloxServerView(current_guild))
            
        elif value == "setup_kick":
            embed = discord.Embed(title="🚫 ระบบโหวตเตะสมาชิก (โหมด Doro เอาจริง!)", description="โปรดเลือกรายชื่อคนที่ไม่น่ารักที่คุณต้องการเริ่มโหวตลงมติเตะด้านล่างนี้ได้เลยค่ะงึมมม", color=discord.Color.red())
            await interaction.message.edit(embed=embed, view=MemberSelectView(current_guild))
            
        elif value == "show_commands":
            embed = discord.Embed(
                title="📘 สมุดคู่มือและบันทึกความสามารถของน้อน Doro 🤖✨",
                description=(
                    "งื้อออ สวัสดีค่าา! หนูคือ **Doro** ยัยบอทสุดน่ารักที่จะมาช่วยดูแลและสร้างสีสันให้เซิร์ฟเวอร์ของทุกคนค๊าา 💕 หนูทำอะไรได้เยอะแยะเลยนะ ลองมาดูกันเยย! \n\n"
                    "**🌸 ความสามารถหลักของหนู (ฟังก์ชันเด่น):**\n"
                    "* **🎛️ แผงควบคุม UI อัจฉริยะ**: กดสั่งงานง่าย ๆ ผ่านปุ่มและเมนู Dropdown ไม่ต้องพิมพ์คำสั่งให้เหนื่อยค๊าา\n"
                    "* **🎵 มิวสิคบอร์ดแยกแท็บ**: เข้าหน้าต่างควบคุมเพลงและคิวได้แบบเป็นสัดส่วนผ่าน Dropdown\n"
                    "* **🧹 ระบบล้างแชทและรีเซ็ตห้อง**: สั่งกวาดล้างข้อความขยะ หรือล้างห้องแชทให้ขาวสะอาด 100% ด้วยปุ่ม Nuke\n"
                    "* **🛡️ ระบบแจกและขอยศสุดตึง**: เลือกรับยศเอง หรือส่งคำขออ้อน ๆ มาขอยศพิเศษก็ได้น้าา\n"
                    "* **📊 โพลระดมความคิด**: สร้างคำถามและส่งไปห้องที่ต้องการ พร้อมระบบนับคะแนนเรียลไทม์\n"
                    "* **🎮 คลังแสงเซิร์ฟ Roblox**: รวมลิงก์ตั๋วเข้า Private Server เกมโปรดของแก๊งเราไว้ที่เดียว\n"
                    "* **🏗️ สร้างห้องแชทหลายห้อง**: สั่งหนูสร้างห้องแชทใหม่พร้อมกันหลายห้องได้ในคลิกเดียว\n"
                    "* **🚫 ศาลเตี้ยโหวตเตะ**: เปิดวาระโหวตลงมติเพื่อดีดออกจากห้องเสียงหรือเซิร์ฟเวอร์\n\n"
                    "--------------------------------------------------\n"
                    "**✍️ สรุปคำสั่งพิมพ์ด่วน (Quick Commands):**\n"
                    "🔹 **`doro เมนู` / `doro menu` / `doro คำสั่งเพลง`** : เรียกเปิดแผงควบคุมระบบ UI ทั้งหมดค๊าา\n"
                    "🔹 **`doro ให้ยศ` / `doro addrole`** : หน้าต่างด่วนสำหรับแอดมินแจกยศกลุ่มความเร็วสูง\n"
                    "🔹 **`doro ลบข้อความ <จำนวน>`** : สั่งเคลียร์ข้อความขยะในห้องแชท\n"
                    "🔹 **`doro เล่น <ชื่อเพลง/ลิงก์>`** : สั่งน้อน Doro ดำน้ำไปเปิดเพลงค๊าา 🎵"
                ),
                color=discord.Color.magenta()
            )
            await interaction.message.edit(embed=embed, view=BackToMainOnlyView(current_guild))

class BotControlMenuView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(BotCommandControlSelect())

    @discord.ui.button(label="❌ ปิดแผงควบคุม", style=discord.ButtonStyle.danger, emoji="🔴", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except:
            pass

def generate_main_menu_embed(guild):
    guild_id = guild.id
    song = current_songs.get(guild_id)
    vc = guild.voice_client

    embed = discord.Embed(
        title="⚙️ Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก (All-in-One UI Mode)", 
        description="ยินดีต้อนรับค๊าา! ตอนนี้ปุ่มควบคุมเพลงถูกย้ายเข้าไปอยู่ในหัวข้อ **'🎵 เปิดระบบควบคุมและเล่นเพลง'** ใน Dropdown ด้านล่างแล้วนะค๊าา เพื่อความสะอาดตา เลือกโหมดใช้งานน้อนได้เลยน้าา ✨", 
        color=0x3498DB
    )
    
    if vc and vc.is_connected() and song:
        status_str = "🟢 กำลังบรรเลงเพลงอย่างเพลิดเพลิน" if not vc.is_paused() else "⏸️ พักเสียงเพลงชั่วคราว"
        embed.add_field(
            name="🎵 สถานะการเล่นเพลงปัจจุบัน",
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
            name="🎵 สถานะการเล่นเพลงปัจจุบัน",
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
# 🧹 CLEAR CHANNEL COMPONENTS (เพิ่มระบบ Nuke / Reset ห้องแชทที่นี่งับ!)
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

    # 💥 ปุ่มวิเศษสำหรับรีเซ็ตล้างระดานแชลเนลแบบ 100% (Nuke Channel) 
    @discord.ui.button(label="🚨 รีเซ็ตห้องแชท (Nuke Channel)", style=discord.ButtonStyle.danger, emoji="💥", row=1)
    async def nuke_channel_btn(self, interaction: discord.Interaction, btn):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ คุณพี่ต้องมีสิทธิ์ 'จัดการช่องแชลเนล' (Manage Channels) ถึงจะสั่งระเบิดห้องแชทได้นะค๊าางึมมม", ephemeral=True)
        
        await interaction.response.defer()
        current_channel = interaction.channel
        
        # คลอนนิ่งห้องเก่าขึ้นมาใหม่
        new_channel = await current_channel.clone(reason="Doro UI Nuke / Channel Reset Action")
        
        # ย้ายตำแหน่งห้องใหม่ให้ไปอยู่ที่เดียวกับห้องเก่า
        await new_channel.edit(position=current_channel.position)
        
        # ลบห้องเก่าทิ้งทลายประวัติแชทขยะ
        await current_channel.delete(reason="Doro UI Nuke / Channel Reset Action")
        
        # ส่งข้อความต้อนรับในห้องใหม่ และตั้งค่าให้หายไปภายใน 3 วินาที (delete_after=3)
        embed_nuke = discord.Embed(
            title="💥 ห้องแชทนี้ถูกรีเซ็ตเรียบร้อยแล้วค๊าา! (Channel Nuked Successfully)",
            description=f"🧹 น้อน Doro จัดการระเบิดแชทเก่าทิ้ง และกวาดล้างข้อมูลขยะทั้งหมดให้สะอาดเอี่ยมอ่อง 100% แล้วนะค๊าา! พร้อมใช้งานแชทใหม่แบบลื่น ๆ เยยย ✨\n\n*ผู้สั่งรีเซ็ตห้อง: {interaction.user.mention}*",
            color=0xFF3E3E
        )
        embed_nuke.set_image(url="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2I4N2I5M2M5MmE0MDRmYjllNWE2ZGNmMDFlNTAwYjRjYmU0Zjg2ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hog2UAsK791U1mZ5r9/giphy.gif")
        
        # ✨ เพิ่ม delete_after=3 ตรงนี้เพื่อให้ข้อความและ GIF หายวับไปใน 3 วินาทีค๊าา!
        await new_channel.send(embed=embed_nuke, delete_after=3)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.success, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.success, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🎮 ROBLOX MODALS & VIEWS
# ==========================================
# ==========================================
# 🎮 ROBLOX SYSTEM (ฉบับสมบูรณ์ - ใส่รูปได้/ไม่ใส่ก็ได้)
# ==========================================

# 1. หน้าต่างกรอกรายละเอียดเกม (เพิ่มช่องรูปภาพแบบ Optional)
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
        
        current_data = load_roblox_data()
        current_data[g_id] = {
            "name": full_display_name, 
            "url": self.game_url.value.strip(),
            "image": self.game_image.value.strip() if self.game_image.value else None
        }
        save_roblox_data(current_data)
        await interaction.response.send_message(f"✅ บันทึกเกม **{full_display_name}** เรียบร้อยค๊าา!", ephemeral=True)

# 2. เมนูเลือกอิโมจิ
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

# 3. เมนูเลือกเกมและแสดงผล (รองรับรูปภาพ)
class RobloxServerSelect(discord.ui.Select):
    def __init__(self):
        current_data = load_roblox_data()
        options = [discord.SelectOption(label=data["name"][:90], value=key) for key, data in current_data.items()] if current_data else [discord.SelectOption(label="ยังไม่มีเกมในคลัง", value="none")]
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", options=options)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        game_data = load_roblox_data().get(self.values[0])
        if game_data:
            embed = discord.Embed(title=f"🚀 เข้าเล่นเกม {game_data['name']}", color=0x00E5FF)
            # ถ้ามีลิงก์รูป ให้ใส่รูป ถ้าไม่มีให้ข้ามไป
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
        current_data = load_roblox_data()
        
        if g_id in current_data:
            deleted_name = current_data[g_id]['name']
            del current_data[g_id]
            save_roblox_data(current_data)
            
            # ✨ น้อนสั่งให้ข้อความนี้โชว์แค่ 3 วินาทีแล้วหายไปงับ!
            await interaction.followup.send(f"🗑️ ลบเกม **{deleted_name}** ออกจากคลังแสงเรียบร้อยค๊าา!", ephemeral=True, delete_after=3)
        else: 
            # ✨ กรณีหาไม่เจอ ก็ให้หายไปใน 3 วินาทีเหมือนกันค๊าา
            await interaction.followup.send(f"❌ ไม่พบรหัสเกม '{g_id}' ในระบบค๊าา ลองเช็คตัวพิมพ์ดี ๆ น้าา", ephemeral=True, delete_after=3)
# 4. หน้าหลักระบบ Roblox
class RobloxServerView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(RobloxServerSelect())
    
    @discord.ui.button(label="➕ เพิ่มเกม", style=discord.ButtonStyle.primary, emoji="➕", row=1)
    async def add_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_message("🎨 เลือกอิโมจิเพื่อเริ่มตั้งค่าเกมค๊าา:", view=RobloxEmojiSelectView(), ephemeral=True)
        
    @discord.ui.button(label=" ลบเกม", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def del_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_modal(DeleteRobloxServerModal())
        
    @discord.ui.button(label=" ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
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

class VoteSelect(discord.ui.Select):
    def __init__(self, choices, result_channel_id, all_choices):
        super().__init__(placeholder="🗳️ กดโหวตคำตอบที่คุณชอบเลยน้าา...", options=[discord.SelectOption(label=o[:90]) for o in choices])
        self.res_id = result_channel_id
        self.all_choices = all_choices
    async def callback(self, interaction: discord.Interaction):
        p_id = interaction.message.id
        u_votes = vote_records.setdefault(p_id, {})
        u_votes[interaction.user.id] = self.values[0]
        await interaction.response.send_message("✅ โหวตเสสิ้น!", ephemeral=True, delete_after=2)

class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = None
        self.poll_choices = []
        self.target_id = None
        self.result_id = None
        channels = [discord.SelectOption(label=f"#{ch.name}"[:40], value=str(ch.id)) for ch in guild.channels if isinstance(ch, discord.TextChannel)][:25]
        
        self.s1 = discord.ui.Select(placeholder="📢 1. เลือกห้องที่จะปล่อยโพล", options=channels, row=0)
        self.s2 = discord.ui.Select(placeholder="📊 2. เลือกห้องที่จะให้สรุปคะแนน", options=channels, row=1)
        self.s1.callback = self.c1
        self.s2.callback = self.c2
        self.add_item(self.s1)
        self.add_item(self.s2)

    async def c1(self, interaction): 
        self.target_id = int(self.s1.values[0])
        await interaction.response.defer()
    async def c2(self, interaction): 
        self.result_id = int(self.s2.values[0])
        await interaction.response.defer()

    @discord.ui.button(label="✏️ กรอกคำถามโพล", style=discord.ButtonStyle.primary, row=2)
    async def input_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_modal(AskQuestionTextModal(self))
    @discord.ui.button(label="🚀 ยืนยันปล่อยโพลเลย", style=discord.ButtonStyle.success, row=2)
    async def send_btn(self, interaction: discord.Interaction, btn):
        if not self.question_text or not self.poll_choices or not self.target_id or not self.result_id: return
        chan = self.guild.get_channel(self.target_id)
        if chan:
            v_view = discord.ui.View(timeout=None)
            v_view.add_item(VoteSelect(self.poll_choices, self.result_id, self.poll_choices))
            msg = await chan.send(embed=discord.Embed(title=f"❓ โพล: {self.question_text}", color=0xFFC0CB), view=v_view)
            vote_records[msg.id] = {}
            await interaction.response.send_message("✅ ปล่อยโพลสำเร็จค๊าา!", ephemeral=True)
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=3)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🚫 VOTE KICK SYSTEM COMPONENTS
# ==========================================
# 🚫 VOTE KICK SYSTEM COMPONENTS (แก้ไขเพิ่มปุ่มย้อนกลับ)
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
            # เพิ่ม view ใหม่ที่รวมปุ่มย้อนกลับเข้าไปด้วย
            await interaction.message.edit(embed=discord.Embed(title="🛠️ ตั้งค่าศาลเตี้ยโหวตเตะ", description=f"เป้าหมาย: {m_obj.mention}"), view=VoteKickTypeView(m_obj, req, self.guild))

class MemberSelectView(discord.ui.View):
    def __init__(self, guild): 
        super().__init__(timeout=60)
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
    
    # ✨ ปุ่มย้อนกลับหน้าแรกในหน้านี้
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

class VoteProgressView(discord.ui.View):
    def __init__(self, target, k_type, req):
        super().__init__(timeout=120)
        self.target = target
        self.k_type = k_type
        self.req = req
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
# ⚙️ CORE EVENTS & COMMANDS MAIN LOGIC
# ==========================================
@bot.event
async def on_ready(): 
    global refresh_main_menu_msg
    async def _refresh(guild_id, channel):
        try:
            async for msg in channel.history(limit=20):
                if msg.author.id == bot.user.id and msg.embeds and "All-in-One UI Mode" in str(msg.embeds[0].title):
                    await msg.edit(embed=generate_main_menu_embed(channel.guild), view=BotControlMenuView(channel.guild))
                    break
        except:
            pass
    refresh_main_menu_msg = _refresh
    logger.info(f"Doro COMPLETELY SUPER POWERED IS RUNNING AS {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    msg = message.content.strip()
    lower_msg = msg.lower()
    parts = msg.split()

    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
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
        await message.channel.send(embed=discord.Embed(title="🛡️ ระบบมอบยศกลุ่มอัจฉริยะ (UI High-Speed)", color=0x2ECC71), view=MultiRoleManagementView(message.guild))
        return

    if (f"doro ลบข้อความ" in lower_msg or f"doro clear" in lower_msg) and len(parts) >= 3:
        if not message.author.guild_permissions.manage_messages: return
        try: 
            deleted = await message.channel.purge(limit=int(parts[2]) + 1)
        except: 
            pass
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

bot.run(DISCORD_TOKEN)
