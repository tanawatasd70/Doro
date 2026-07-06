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
# 🔓 UPDATED: DYNAMIC GROUP ROLE VIEW (💕 SUPER SWEET FEMALE STYLE)
# ==========================================
class DynamicGroupJoinView(discord.ui.View):
    def __init__(self, role_id: int, emoji_str: str):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.emoji_str = emoji_str
        
        # ตั้งชื่อปุ่มตามอิโมจิที่แอดมินเลือกค๊าา
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
        # 🤫 ข้อความเด้งแล้วหายไปเอง เห็นเฉพาะคนกดตามภาพ image_d2b326.png เลยค๊าา
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.followup.send("❌ งื้อออ น้อนหาตัวยศนี้ในเซิร์ฟไม่เจอ แอดมินจ๋าแอบลบยศไปหรือเปล่านะคะ? 🥺", ephemeral=True)

        if role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(role)
                return await interaction.followup.send(f"🏃‍♂️ ถอนยศ **{role.name}** และออกจากกลุ่มเรียบร้อยแล้วน้าา ไว้แวะมาหาหนูใหม่นะคะคนดี~ 💕", ephemeral=True)
            except discord.Forbidden:
                return await interaction.followup.send("❌ งื้อออ น้อนไม่มีสิทธิ์ถอนยศนี้ให้เลยค๊าา ขอโทษน้าา 🥺", ephemeral=True)

        # 👑 จังหวะกดรับยศสำเร็จ -> หวานเจี๊ยบและขึ้นแบบชั่วคราวเห็นคนเดียวแล้วหายไป!
        try:
            await interaction.user.add_roles(role)
            await interaction.followup.send("🎉 ยินดีต้อนรับเข้าสู่กลุ่มค๊าา! มอบยศ M͟͞E͟͞M͟͞B͟͞E͟͞R͟͞ 💀 ให้เรียบร้อย ตอนนี้ห้องลับเปิดให้เข้าแล้วน้าา~ 💕", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ น้อน Doro ไม่มีสิทธิ์แจกยศนี้ รบกวนแอดมินลากยศของน้อนให้สูงกว่ายศที่จะแจกในตั้งค่าเซิร์ฟเวอร์หน่อยน้าค๊าา จุ๊บ ๆ 🥺🎀", ephemeral=True)

# แผงตั้งค่า UI สำหรับแอดมิน
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
        asyncio.run_coroutine_threadsafe(channel.send("🎵 คิวเพลงหมดแล้วค๊าา หนูขอตัวออกจากห้องเสียงก่อนน้าา บ๊ายบายระคะ~ 🎀"), bot.loop)
        return

    source = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
    vc.play(source, after=lambda e: play_next_song(guild_id, vc, channel))

async def update_music_menu_embed(message, guild):
    try:
        if message:
            await message.edit(embed=generate_main_menu_embed(guild), view=MusicControlView(guild))
    except Exception as e:
        logger.error(f"Error updating music menu: {e}")


# ==========================================
# 🔍 MUSIC SEARCH MODAL
# ==========================================
class MusicSearchModal(discord.ui.Modal, title="🎵 ค้นหาและเพิ่มเพลงลงคิว"):
    def __init__(self, current_msg=None):
        super().__init__()
        self.current_msg = current_msg
        self.song_query = discord.ui.TextInput(
            label="พิมพ์ชื่อเพลง หรือ ลิงก์ YouTube ได้เลยค๊าา", 
            placeholder="เช่น ฝนตกไหม - Three Man Down",
            required=True
        )
        self.add_item(self.song_query)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = self.song_query.value.strip()
        guild = interaction.guild
        
        if not interaction.user.voice:
            await interaction.channel.send("❌ คุณพี่ต้องเข้ามาอยู่ในห้องคุยเสียงก่อนสั่งหนูเปิดเพลงนะค๊าา งึมมม 🥺", delete_after=5)
            return

        await interaction.channel.send(f"🔍 น้อน Doro กำลังดำน้ำไปงมหาเพลง **'{query}'** ให้คุณพี่อยู่น้าา รอแป๊บนึงนะคะ...", delete_after=5)
        
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
                await interaction.channel.send("❌ งื้อออ หนูหาเพลงนี้ไม่เจอเลยค่ะ ลองเปลี่ยนชื่อเพลงดูอีกทีน้าา 🥺", delete_after=5)
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
            discord.SelectOption(label="🎵 เปิดระบบควบคุมและเล่นเพลง", description="เข้าสู่หน้าต่างควบคุมมิวสิคบอร์ด เปิดเพลง/เลือกเพลงค๊าา", value="setup_music"),
            discord.SelectOption(label="🧹 เปิดระบบล้างข้อความแชท", description="ลบข้อความขยะ/รีเซ็ตล้างห้องแชทให้เกลี้ยงในพริบตา", value="setup_clear"),
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศสุดน่ารัก", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="สร้างโพลน่ารัก ๆ เพื่อโหวตเลือกคำตอบกันเถอะ", value="setup_poll"),
            discord.SelectOption(label="🎮 รวมลิงก์ Private Server Roblox", description="คลังแสงลิงก์เซิร์ฟเวอร์วีเกมต่าง ๆ ของชาว Robloxค๊าา", value="roblox_servers"),
            discord.SelectOption(label="🚫 เริ่มวาระโหวตเตะสมาชิก", description="เลือกคนที่ทำตัวไม่น่ารักเพื่อเริ่มโหวตเตะกันค่ะ!", value="setup_kick"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูคู่มือการสั่งงานและบันทึกความสามารถน้อน Doro กันงับ", value="show_commands")
        ]
        super().__init__(placeholder="🎛️ หรือเลือกโหมดทำงานอื่น ๆ ของน้อน Doro ที่นี่ได้เลยค๊าา...", min_values=1, max_values=1, options=options, custom_id="doro_main_control_select", row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        value = self.values[0]
        current_guild = interaction.guild

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
                            "⚠️ **รีเซ็ตห้องแชท (Nuke)**: ทำการโคลนและลบห้องเดิมทิ้งทันที เพื่อล้างประวัติแชททั้งหมดให้โล่ง 100% ค๊าา!", 
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
                description="งื้อออ สวัสดีค่าา! หนูคือ **Doro** ยัยบอทสุดน่ารักที่จะมาช่วยดูแลและสร้างสีสันให้เซิร์ฟเวอร์ของทุกคนค๊าา 💕 หนูทำอะไรได้เยอะแยะเลยนะ ลองมาดูกันเยย!",
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
        description="ยินดีต้อนรับค๊าา! ปรับหน้าต่างควบคุมผ่าน Dropdown ด้านล่าง เลือกโหมดใช้งานน้อนได้เลยนะคะคนดี ✨", 
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
    else:
        embed.add_field(
            name="🎵 สถานะการเล่นเพลงปัจจุบัน",
            value="❌ ยังไม่ได้เปิดเพลง หรือน้อน Doro ยังไม่ได้เข้าห้องคุยเสียงเลยค๊าา",
            inline=False
        )
        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        
    return embed


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
                await interaction.channel.send(f"📥 น้อน Doro วิ่งดุ๊กๆ เข้าห้อง **{interaction.user.voice.channel.name}** ตามคำขอแล้วค๊าา!", delete_after=3)
            else:
                await vc.move_to(interaction.user.voice.channel)
        else:
            await interaction.channel.send("❌ คุณพี่ต้องเข้าห้องเสียงก่อนน้าา หนูจะได้ตามไปถูกห้องงับ 🥺", delete_after=3)
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
        self.amount_input = discord.ui.TextInput(label="ต้องการลบกี่ข้อความดีค๊าา? (ใส่ตัวเลข 1-100)", placeholder="เช่น 35", required=True)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ คุณพี่ไม่มีสิทธิ์จัดการข้อความน้าา", ephemeral=True)
        try:
            amt = int(self.amount_input.value.strip())
            await interaction.response.defer()
            deleted = await interaction.channel.purge(limit=amt)
            await interaction.channel.send(f"🧹 น้อน Doro เคลียร์ข้อความขยะออกไปให้แล้ว {len(deleted)} ข้อความค๊าา! ✨", delete_after=4)
        except ValueError:
            await interaction.response.send_message("❌ กรุณากรอกตัวเลขด้วยน้าา", ephemeral=True)

class ClearChannelView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="🧹 ลบ 5 แชท", style=discord.ButtonStyle.secondary, row=0)
    async def clear_5(self, interaction: discord.Interaction, btn):
        await interaction.channel.purge(limit=5)
        await interaction.response.send_message("🧹 ลบเรียบร้อยค๊าา!", ephemeral=True)

    @discord.ui.button(label="🚨 Nuke Channel", style=discord.ButtonStyle.danger, emoji="💥", row=1)
    async def nuke_channel_btn(self, interaction: discord.Interaction, btn):
        if not interaction.user.guild_permissions.manage_channels: return
        await interaction.response.defer()
        current_channel = interaction.channel
        new_channel = await current_channel.clone()
        await new_channel.edit(position=current_channel.position)
        await current_channel.delete()
        await new_channel.send("💥 รีเซ็ตห้องแชทให้สะอาดเอี่ยมเรียบร้อยแล้วค๊าา!", delete_after=5)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.success, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🎮 ROBLOX PRIVATE SERVERS SYSTEM
# ==========================================
class AddRobloxServerModal(discord.ui.Modal, title="🎮 กรอกรายละเอียดเซิร์ฟเวอร์วี"):
    def __init__(self, selected_emoji: str):
        super().__init__()
        self.selected_emoji = selected_emoji
        self.game_id = discord.ui.TextInput(label="รหัสเกม (อังกฤษตัวพิมพ์เล็ก ห้ามเว้นวรรค)", placeholder="เช่น blox_fruits")
        self.game_name = discord.ui.TextInput(label="ชื่อเกมที่จะแสดงบนเมนู", placeholder="เช่น Blox Fruits")
        self.game_url = discord.ui.TextInput(label="ลิงก์ Private Server (Roblox URL)")
        self.add_item(self.game_id)
        self.add_item(self.game_name)
        self.add_item(self.game_url)
        
    async def on_submit(self, interaction: discord.Interaction):
        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        full_display_name = f"{self.selected_emoji} {self.game_name.value.strip()}"
        current_data = load_roblox_data()
        current_data[g_id] = {"name": full_display_name, "url": self.game_url.value.strip()}
        save_roblox_data(current_data)
        await interaction.response.send_message(f"✅ บันทึกเกม **{full_display_name}** เรียบร้อยค๊าาแอดมินสุดหล่อ!", ephemeral=True)

class RobloxServerSelect(discord.ui.Select):
    def __init__(self):
        current_data = load_roblox_data()
        options = [discord.SelectOption(label=data["name"][:90], value=key) for key, data in current_data.items()] if current_data else [discord.SelectOption(label="ยังไม่มีเกมในคลัง", value="none")]
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", options=options)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        game_data = load_roblox_data().get(self.values[0])
        if game_data:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="👉 กดตรงนี้เพื่อวาปไปเล่นเลยค๊าา!", url=game_data['url']))
            await interaction.response.send_message(f"🚀 เตรียมตัววาปไปเล่นเกม {game_data['name']} กันเลยน้าา~", view=view, ephemeral=True)

class RobloxServerView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(RobloxServerSelect())
    @discord.ui.button(label=" ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🛡️ ROLE REQUEST BACKPLANE
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
            await interaction.user.add_roles(role)

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(RoleSelect(guild))
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 📊 POLL SYSTEM COMPONENTS
# ==========================================
class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=3)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🚫 VOTE KICK SYSTEM COMPONENTS
# ==========================================
class MemberSelectView(discord.ui.View):
    def __init__(self, guild): 
        super().__init__(timeout=60)
        self.guild = guild
    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# ==========================================
# 🛡️ BACKPLANE HIGH SPEED MULTI-ROLE
# ==========================================
class MultiRoleManagementView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=180)
        self.guild = guild


# ==========================================
# ⚙️ CORE EVENTS & COMMANDS MAIN LOGIC
# ==========================================
@bot.event
async def on_ready(): 
    bot.add_view(DynamicGroupJoinView(role_id=0, emoji_str="🌸"))
    logger.info(f"Doro FEMALE SWEET MODE IS RUNNING AS {bot.user}")

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
        await message.channel.send(embed=generate_main_menu_embed(message.guild), view=BotControlMenuView(message.guild))
        return

    # 🐈‍⬛ แผงเสกรับยศสไตล์ แมวทมิฬ (สีดำดุดัน แต่คนแจกหวานเจี๊ยบ)
    if lower_msg == "doro สร้างปุ่มรับยศ":
        if not message.author.guild_permissions.manage_roles: return
        try: await message.delete()
        except: pass
            
        admin_setup_embed = discord.Embed(
            title="🛠️ แผงควบคุมตั้งค่ากล่องรับยศเข้ากลุ่ม (แอดมินโหมดคะคนดี)",
            description="กรุณาเลือกยศที่ต้องการแจกและหน้าตาปุ่มอิโมจิด้านล่างให้ครบถ้วน จากนั้นกดปุ่มยืนยันเพื่อเสกกล่องแมวทมิฬสีดำสุดเท่ลงช่องแชทได้เลยค๊าา! ✨",
            color=0x000000
        )
        await message.channel.send(embed=admin_setup_embed, view=RoleSetupAdminView(message.guild), delete_after=60)
        return

bot.run(DISCORD_TOKEN)
