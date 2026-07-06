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
    def __init__(self):
        super().__init__()
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

        await update_main_menu_embed(interaction.message, guild)


# ==========================================
# 🎛️ MAIN UI COMMAND MENU (WITH ALL-IN-ONE MUSIC CONTROLLER)
# ==========================================
class BotCommandControlSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🏠 หน้าแรก / เคลียร์เมนูย่อย", description="กลับสู่หน้าจอเริ่มต้น ล้างหน้าต่างการทำงานด้านล่าง", value="main_menu"),
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศสุดน่ารัก", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="สร้างโพลน่ารัก ๆ เพื่อโหวตเลือกคำตอบกันเถอะ", value="setup_poll"),
            discord.SelectOption(label="🎮 รวมลิงก์ Private Server Roblox", description="คลังแสงลิงก์เซิร์ฟเวอร์วีเกมต่าง ๆ ของชาว Robloxค๊าา", value="roblox_servers"),
            discord.SelectOption(label="🚫 เริ่มวาระโหวตเตะสมาชิก", description="เลือกคนที่ทำตัวไม่น่ารักเพื่อเริ่มโหวตเตะกันค่ะ!", value="setup_kick"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูคู่มือการสั่งงานและบันทึกความสามารถน้อน Doro กันงับ", value="show_commands")
        ]
        super().__init__(placeholder="🎛️ หรือเลือกโหมดทำงานอื่น ๆ ของน้อน Doro ที่นี่...", min_values=1, max_values=1, options=options, custom_id="doro_main_control_select", row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        value = self.values[0]
        current_guild = interaction.guild

        # สร้าง View หลักขึ้นมาก่อนเสมอ เพื่อรักษาปุ่มเพลงและ Dropdown ไว้ด้านบน
        view = BotControlMenuView(current_guild)

        if value == "main_menu":
            embed = generate_main_menu_embed(current_guild)
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "setup_roles":
            embed = generate_main_menu_embed(current_guild)
            embed.add_field(name="🛡️ [ระบบจัดการยศอัตโนมัติ]", value="คุณชอบยศไหนเลือกรับจากเมนูด้านล่างนี้ได้เลยนะค๊าา หรือจะกดปุ่มขอยศพิเศษส่งเหตุผลหาแอดมินก็ได้น้าา~ ✨", inline=False)
            
            # โคลนเอาปุ่มและ Select ของระบบยศมาฝังต่อท้าย View หลัก
            view.add_item(RoleSelect(current_guild))
            view.add_item(RequestRoleButton())
            view.add_item(RemoveAllRolesButton())
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "setup_poll":
            embed = generate_main_menu_embed(current_guild)
            embed.add_field(name="📊 [ระบบสร้างคำถามโพล]", value="กรุณากรอกหัวข้อคำถาม และเลือกช่องทางปล่อยโพลให้ครบถ้วนด้านล่างนี้เลยน้าา~ ✨", inline=False)
            
            poll_view = AskQuestionView(current_guild)
            view.add_item(poll_view.s1)
            view.add_item(poll_view.s2)
            view.add_item(PollInputButton(poll_view))
            view.add_item(PollSendButton(poll_view))
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "roblox_servers":
            embed = generate_main_menu_embed(current_guild)
            embed.add_field(name="🎮 [คลังแสง Private Server Roblox]", value="อยากไปฟาร์ม ไปเวล หรือไปตึงเกมไหน เลือกชื่อเกมจากเมนูด้านล่างนี้ได้เลยค๊าา\n(สำหรับแอดมินกดปุ่มเพื่อ เพิ่ม/ลบ เกมได้เลยนะค๊าา) ✨", inline=False)
            
            view.add_item(RobloxServerSelect())
            view.add_item(RobloxAddButton())
            view.add_item(RobloxDelButton())
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "setup_kick":
            embed = generate_main_menu_embed(current_guild)
            embed.add_field(name="🚫 [ระบบโหวตเตะสมาชิก]", value="โปรดเลือกรายชื่อคนที่ไม่น่ารักที่คุณต้องการเริ่มโหวตลงมติเตะด้านล่างนี้ได้เลยค่ะงึมมม", inline=False)
            
            view.add_item(MemberSelect(current_guild))
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "show_commands":
            embed = generate_main_menu_embed(current_guild)
            embed.add_field(
                name="📘 สมุดคู่มือและบันทึกความสามารถของน้อน Doro 🤖✨",
                value=(
                    "**🌸 ฟังก์ชันเด่น:**\n"
                    "* **🎛️ แผงควบคุม UI**: สั่งงานผ่านปุ่มและเมนู Dropdown ค๊าา\n"
                    "* **🛡️ ระบบแจกและขอยศ**: เลือกรับยศเอง หรือส่งคำขออ้อน ๆ มาขอยศพิเศษก็ได้น้าา\n"
                    "* **📊 โพลระดมความคิด**: สร้างคำถามระดมโหวตแบบเรียลไทม์สุดล้ำ\n"
                    "* **🎮 คลังแสงเซิร์ฟ Roblox**: รวมลิงก์ตั๋วเข้า Private Server เกมโปรด\n"
                    "* **🚫 ศาลเตี้ยโหวตเตะ**: เปิดวาระโหวตลงมติเพื่อดีดออกจากห้องเสียงหรือเซิร์ฟเวอร์\n"
                    "* **🧹 เคลียร์แชท**: ลบข้อความขยะได้ในพริบตาเดียวเลยงับ\n\n"
                    "**✍️ สรุปคำสั่งพิมพ์ด่วน:**\n"
                    "🔹 `doro เมนู` / `menu` : เปิดแผงควบคุม UI มิวสิคบอร์ด\n"
                    "🔹 `doro ให้ยศ` / `addrole` : บอร์ดแอดมินแจกยศกลุ่มความเร็วสูง\n"
                    "🔹 `doro ลบข้อความ <จำนวน>` : สั่งเคลียร์ข้อความขยะ\n"
                    "🔹 `doro เล่น <ชื่อเพลง/ลิงก์>` : สั่งเปิดเพลงค๊าา 🎵"
                ),
                inline=False
            )
            await interaction.message.edit(embed=embed, view=view)

class BotControlMenuView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(BotCommandControlSelect())

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
        await update_main_menu_embed(interaction.message, self.guild)

    @discord.ui.button(label="🔍 พิมพ์ชื่อเพลง (Play)", style=discord.ButtonStyle.success, emoji="🎵", row=0)
    async def search_play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MusicSearchModal())

    @discord.ui.button(label="⏭️ ข้ามเพลง (Skip)", style=discord.ButtonStyle.secondary, emoji="⏩", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            loop_status[self.guild.id] = False
            vc.stop()
            await interaction.channel.send("⏭️ น้อน Doro สะบัดมือข้ามเพลงให้แล้วค๊าา!", delete_after=3)
        await update_main_menu_embed(interaction.message, self.guild)

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
        await update_main_menu_embed(interaction.message, self.guild)

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
        description="ยินดีต้อนรับค๊าา! ตอนนี้ระบบมิวสิคบอร์ดและคำสั่งทั้งหมดถูกรวมไว้ที่นี่แล้วค๊าา กดปุ่มสั่งงานน้อนได้เลยน้าา ✨", 
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

async def update_main_menu_embed(message, guild):
    try:
        if message:
            await message.edit(embed=generate_main_menu_embed(guild), view=BotControlMenuView(guild))
    except Exception as e:
        logger.error(f"Error updating embed menu: {e}")

async def return_to_main_menu(interaction: discord.Interaction):
    try:
        await interaction.message.edit(embed=generate_main_menu_embed(interaction.guild), view=BotControlMenuView(interaction.guild))
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")


# ==========================================
# 🎮 ROBLOX WRAPPED COMPONENTS
# ==========================================
class RobloxServerSelect(discord.ui.Select):
    def __init__(self):
        current_data = load_roblox_data()
        if current_data:
            options = [discord.SelectOption(label=data["name"][:90], value=key) for key, data in current_data.items()]
        else:
            options = [discord.SelectOption(label="ไม่มีเกมในคลังแสง", value="none")]
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", options=options, row=3)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        game_data = load_roblox_data().get(self.values[0])
        if game_data:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="👉 เข้าเซิร์ฟเวอร์วีที่นี่", url=game_data['url']))
            await interaction.response.send_message(f"🚀 ลิงก์เข้าเกม **{game_data['name']}**", view=view, ephemeral=True)

class RobloxAddButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="➕ เพิ่มเกม", style=discord.ButtonStyle.primary, row=4)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddRobloxServerModal())

class RobloxDelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🗑️ ลบเกม", style=discord.ButtonStyle.danger, row=4)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DeleteRobloxServerModal())

class AddRobloxServerModal(discord.ui.Modal, title="🎮 เพิ่ม/แก้ไข ลิงก์เซิร์ฟเวอร์วี"):
    def __init__(self):
        super().__init__()
        self.game_id = discord.ui.TextInput(label="รหัสเกม (อังกฤษตัวพิมพ์เล็ก ห้ามเว้นวรรค)", placeholder="เช่น blox_fruits")
        self.game_name = discord.ui.TextInput(label="ชื่อเกมที่จะแสดงบนเมนู (ใส่ อีโมจิ ได้)", placeholder="เช่น 🏴‍☠️ Blox Fruits")
        self.game_url = discord.ui.TextInput(label="ลิงก์ Private Server (Roblox URL)")
        self.add_item(self.game_id)
        self.add_item(self.game_name)
        self.add_item(self.game_url)
        
    async def on_submit(self, interaction: discord.Interaction):
        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        current_data = load_roblox_data()
        current_data[g_id] = {"name": self.game_name.value.strip(), "url": self.game_url.value.strip()}
        save_roblox_data(current_data)
        await interaction.response.send_message("✅ บันทึกเกมเรียบร้อยค๊าา!", ephemeral=True)

class DeleteRobloxServerModal(discord.ui.Modal, title="🗑️ ลบลิงก์เซิร์ฟเวอร์วี"):
    def __init__(self):
        super().__init__()
        self.game_id = discord.ui.TextInput(label="พิมพ์รหัสเกมที่ต้องการลบ")
        self.add_item(self.game_id)
        
    async def on_submit(self, interaction: discord.Interaction):
        g_id = self.game_id.value.strip().lower()
        current_data = load_roblox_data()
        if g_id in current_data:
            del current_data[g_id]
            save_roblox_data(current_data)
            await interaction.response.send_message("🗑️ ลบเรียบร้อยแล้วค๊าา!", ephemeral=True)
        else: 
            await interaction.response.send_message("❌ ไม่พบรหัสเกมนี้ค๊าา", ephemeral=True)


# ==========================================
# 🛡️ ROLE WRAPPED COMPONENTS
# ==========================================
class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🎨 เลือกรับยศสุดเลิศของคุณที่นี่เลยน้าา...", options=options, row=3)
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        role = interaction.guild.get_role(int(self.values[0]))
        if role:
            try: 
                await interaction.user.add_roles(role)
                await interaction.channel.send(f"✅ มอบยศ **{role.name}** ให้คุณเรียบร้อยค๊าา!", delete_after=5)
            except: 
                pass

class RequestRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📝 ส่งคำขอยศพิเศษ", style=discord.ButtonStyle.primary, row=4)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextInputModal())

class RemoveAllRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศออกให้หมดเยย", style=discord.ButtonStyle.danger, row=4)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        roles = [r for r in interaction.user.roles if r.name != "@everyone" and not r.managed]
        if roles: 
            await interaction.user.remove_roles(*roles)
        await interaction.channel.send("🧹 ล้างยศเกลี้ยงตัวแล้วจ้าา!", delete_after=5)

class TextInputModal(discord.ui.Modal, title="📝 ส่งเหตุผลอ้อน ๆ เพื่อขอยศพิเศษ"):
    def __init__(self):
        super().__init__()
        self.reason = discord.ui.TextInput(label="เหตุผล/ชื่อยศพิเศษที่อยากได้ค๊าา", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)
    async def on_submit(self, interaction: discord.Interaction): 
        await interaction.response.send_message("📨 ส่งคำขออ้อน ๆ ให้แอดมินแล้วน้าา!", ephemeral=True)


# ==========================================
# 📊 POLL WRAPPED COMPONENTS
# ==========================================
class AskQuestionView:
    def __init__(self, guild):
        self.guild = guild
        self.question_text = None
        self.poll_choices = []
        self.target_id = None
        self.result_id = None
        channels = [discord.SelectOption(label=f"#{ch.name}"[:40], value=str(ch.id)) for ch in guild.channels if isinstance(ch, discord.TextChannel)][:25]
        
        self.s1 = discord.ui.Select(placeholder="📢 1. เลือกห้องที่จะปล่อยโพล", options=channels, row=3)
        self.s2 = discord.ui.Select(placeholder="📊 2. เลือกห้องที่จะให้สรุปคะแนน", options=channels, row=4)
        self.s1.callback = self.c1
        self.s2.callback = self.c2

    async self.c1(self, interaction): 
        self.target_id = int(self.s1.values[0])
        await interaction.response.defer()
    async self.c2(self, interaction): 
        self.result_id = int(self.s2.values[0])
        await interaction.response.defer()

class PollInputButton(discord.ui.Button):
    def __init__(self, poll_view):
        super().__init__(label="✏️ กรอกคำถามโพล", style=discord.ButtonStyle.primary, row=1)
        self.poll_view = poll_view
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AskQuestionTextModal(self.poll_view))

class PollSendButton(discord.ui.Button):
    def __init__(self, poll_view):
        super().__init__(label="🚀 ยืนยันปล่อยโพลเลย", style=discord.ButtonStyle.success, row=1)
        self.poll_view = poll_view
    async def callback(self, interaction: discord.Interaction):
        pv = self.poll_view
        if not pv.question_text or not pv.poll_choices or not pv.target_id or not pv.result_id: 
            return await interaction.response.send_message("❌ กรุณากรอกคำถามและเลือกห้องให้ครบถ้วนก่อนค๊าา!", ephemeral=True)
        
        chan = pv.guild.get_channel(pv.target_id)
        if chan:
            v_view = discord.ui.View(timeout=None)
            v_view.add_item(VoteSelect(pv.poll_choices, pv.result_id, pv.poll_choices))
            msg = await chan.send(embed=discord.Embed(title=f"❓ โพล: {pv.question_text}", color=0xFFC0CB), view=v_view)
            vote_records[msg.id] = {}
            await interaction.response.send_message("✅ ปล่อยโพลสำเร็จค๊าา!", ephemeral=True)

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
        await interaction.response.send_message("✅ โหวตเสร็จสิ้น!", ephemeral=True, delete_after=2)


# ==========================================
# 🚫 VOTE KICK WRAPPED COMPONENTS
# ==========================================
class MemberSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 จิ้มเลือกคนที่ไม่น่ารักตรงนี้เลยงับ...", row=3)
        self.guild = guild
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        target = self.values[0]
        m_obj = interaction.guild.get_member(target.id)
        if m_obj:
            req = max(2, len([m for m in self.guild.members if m.status != discord.Status.offline and not m.bot]) // 2 + 1)
            # แก้ไขเพื่อให้แสดงตัวเลือกระบบเตะต่อลงมาโดยไม่ล้างหน้าแผงควบคุมหลักออก
            view = BotControlMenuView(self.guild)
            view.add_item(VoteKickTypeButton(m_obj, req, "voice", "🔊 เตะออกจากห้องเสียง"))
            view.add_item(VoteKickTypeButton(m_obj, req, "server", "💥 ดีดออกจากเซิร์ฟเวอร์"))
            
            embed = generate_main_menu_embed(self.guild)
            embed.add_field(name="🚨 [กำลังตั้งค่าศาลเตี้ยโหวตเตะ]", value=f"เป้าหมาย: {m_obj.mention}\nจำนวนแต้มโหวตที่ต้องการ: {req} โหวตค่ะ", inline=False)
            await interaction.message.edit(embed=embed, view=view)

class VoteKickTypeButton(discord.ui.Button):
    def __init__(self, target, req_votes, kick_type, label):
        style = discord.ButtonStyle.primary if kick_type == "voice" else discord.ButtonStyle.danger
        super().__init__(label=label, style=style, row=4)
        self.target = target
        self.req = req_votes
        self.k_type = kick_type
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        title_text = "🚨 เริ่มโหวตดีดสายออกจากห้องเสียง!" if self.k_type == "voice" else "🚨 เริ่มโหวตเตะออกจากเซิร์ฟเวอร์!"
        await interaction.channel.send(embed=discord.Embed(title=title_text, description=f"เป้าหมาย: {self.target.mention}\nต้องการทั้งหมด {self.req} คะแนนโหวตค่ะ"), view=VoteProgressView(self.target, self.k_type, self.req))

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
            
            await message.channel.send(embed=generate_main_menu_embed(message.guild), view=BotControlMenuView(message.guild))

bot.run(DISCORD_TOKEN)
