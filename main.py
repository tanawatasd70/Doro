import os
import json
import logging
import discord
from discord.ext import commands
import yt_dlp
from flask import Flask
from threading import Thread

# ==========================================
# ⚙️ INITIALIZATION & LOGGING SETUP
# ==========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DoroBot')

# Flask Server for 24/7 Hosting uptime (UptimeRobot friendly)
app = Flask('')

@app.route('/')
def home():
    return "Doro Bot is Alive and Flying!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# Initialize Discord Bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="doro ", intents=intents, help_command=None)

# ==========================================
# 💾 GLOBAL DATABASE / MEMORY BACKPLANE
# ==========================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
ROBLOX_DATA_FILE = "roblox_servers.json"

music_queues = {}
current_songs = {}
vote_records = {}
brainstorm_polls = {}  # ระบบจัดเก็บโพลระดมสมองแบบ Dynamic Memory

custom_responses = {
    "ดอโร่": "ค๊าาา? มีอะไรให้จัดแจงเรียกใช้น้อน Doro ได้เลยน้าา! 🌸",
    "doro": "ค๊าาา? มีอะไรให้จัดแจงเรียกใช้น้อน Doro ได้เลยน้าา! 🌸",
    "หนูโง่": "งื้อออ ไม่เอาหนูไม่พูดคำนี้กันน้าา ทุกคนเก่งในแบบของตัวเองค๊าา! ✨",
    "รักดอโร่": "งื้อออ เขินจังเยย น้อน Doro ก็รักคุณพี่ที่สุดในโลกค๊าา! ❤️",
    "ไอ้ดอโร่": "เรียกหนูเพราะ ๆ สิค๊าา ไม่งั้นหนูจะงอนแล้วน้าา! 🥺"
}

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'nonetwork': 'False',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'nocheckcertificate': True,
    'proxy': '',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Data Storage Helpers
def load_roblox_data():
    if os.path.exists(ROBLOX_DATA_FILE):
        try:
            with open(ROBLOX_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_roblox_data(data):
    with open(ROBLOX_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ==========================================
# 🗺️ EMBED GENERATION SYSTEM
# ==========================================
def generate_main_menu_embed(guild: discord.Guild):
    embed = discord.Embed(
        title="🐈 Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก",
        description="ยินดีต้อนรับเข้าสู่ศูนย์กลางการจัดสรรระบบของบอท Doro ค๊าา! คุณพี่ต้องการสั่งการระบบใด จิ้มเลือกผ่านปุ่ม UI สแกนง่ายด้านล่างได้ทันทีเลยน้าา! ✨",
        color=0xFFB6C1
    )
    embed.add_field(name="🌐 ชื่อเซิร์ฟเวอร์", value=f"**{guild.name}**", inline=True)
    embed.add_field(name="👥 ประชากรมนุษย์", value=f"**{guild.member_count}** คน", inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3I4N2I5M2M5MmE0MDRmYjllNWE2ZGNmMDFlNTAwYjRjYmU0Zjg2ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hog2UAsK791U1mZ5r9/giphy.gif")
    embed.set_footer(text="💡 Tip: ใช้คำสั่ง 'doro เมนู' เพื่อเสกแผงควบคุมหลักนี้ออกมาได้ตลอดเวลาค๊าา!")
    return embed

# ==========================================
# 🎛️ CORE INTERACTIVE UI VIEWS
# ==========================================
class BotControlMenuView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="🎵 ระบบคลังเพลง", style=discord.ButtonStyle.primary, emoji="🎶", row=0)
    async def music_system(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="🎵 ระบบควบคุมมิวสิคบอร์ดบ็อกซ์", description="กดปุ่มเพื่อข้าม หรือปิดเสียงได้ตามใจชอบเลยค๊าา", color=0x9B59B6)
        await interaction.message.edit(embed=embed, view=MusicControlView(self.guild))

    @discord.ui.button(label="🧹 เคลียร์ห้องแชท", style=discord.ButtonStyle.secondary, emoji="🧼", row=0)
    async def clear_chat(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="🧹 ระบบล้างแชทขยะและความสะอาดช่องแชท", description="กรุณาเลือกจำนวนข้อความที่ต้องการเคลียร์ทิ้งค๊าา", color=0x3498DB)
        await interaction.message.edit(embed=embed, view=ClearChannelView(self.guild))

    @discord.ui.button(label="📊 สถิติ & ข้อมูลเซิร์ฟ", style=discord.ButtonStyle.success, emoji="📈", row=0)
    async def analytics(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="📈 เมนูตรวจสอบข้อมูลทางสถิติประชากร", description="กรุณากดเลือกข้อมูลที่ต้องการเรียกดูค๊าา", color=0x2ECC71)
        await interaction.message.edit(embed=embed, view=MemberAnalyticsView(self.guild))

    @discord.ui.button(label="🎮 ลิงก์คลัง Roblox", style=discord.ButtonStyle.secondary, emoji="🚀", row=1)
    async def roblox_vault(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="🎮 ระบบคลังแสง Private Server (Roblox)", description="เลือกเกมที่คุณพี่ชอบด้านล่างเพื่อวาร์ปเข้าเล่นเซิร์ฟเวอร์วีได้ทันทีค๊าา!", color=0xE67E22)
        await interaction.message.edit(embed=embed, view=RobloxServerView(self.guild))

    @discord.ui.button(label="🛡️ ระบบยศ & บทบาท", style=discord.ButtonStyle.primary, emoji="👑", row=1)
    async def role_menu(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="🛡️ ศูนย์รับและจัดการบทบาทสมาชิก", description="เลือกยศที่ต้องการติดตัว หรือกดขอรับยศกรณีพิเศษอ้อนๆ แอดมินได้เลยค๊าา", color=0xF1C40F)
        await interaction.message.edit(embed=embed, view=RequestRoleView(self.guild))

    @discord.ui.button(label="🗳️ เปิดโพลล์ถามตอบ", style=discord.ButtonStyle.success, emoji="📊", row=1)
    async def poll_menu(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="🗳️ ระบบตั้งค่าเปิดโพลล์ประชามติ", description="ตั้งค่าห้องแชทและกรอกหัวข้อเพื่อเริ่มกระบวนการโหวตส่งคะแนนค๊าา", color=0xE91E63)
        await interaction.message.edit(embed=embed, view=AskQuestionView(self.guild))

    @discord.ui.button(label="🚫 ศาลเตี้ยโหวตเตะ", style=discord.ButtonStyle.danger, emoji="🔨", row=2)
    async def vote_kick_menu(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        embed = discord.Embed(title="🔨 ระบบศาลเตี้ยประชาธิปไตยโหวตดีดสมาชิก", description="กรุณาเลือกสมาชิกที่ไม่น่ารักเพื่อเริ่มนับแต้มโหวตขับไล่ค๊าา!", color=0x95A5A6)
        await interaction.message.edit(embed=embed, view=MemberSelectView(self.guild))

# ==========================================
# 🎵 MUSIC CONTROL LOGIC & VIEW
# ==========================================
class MusicControlView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="⏭️ ข้ามเพลง", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, btn):
        vc = self.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ น้อน Doro เตะข้ามเพลงให้แล้วค๊าา!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ตอนนี้ไม่มีเพลงเล่นอยู่เลยน้าา", ephemeral=True)

    @discord.ui.button(label="🛑 ปิดเสียง/หยุดเล่น", style=discord.ButtonStyle.danger)
    async def stop_music(self, interaction: discord.Interaction, btn):
        vc = self.guild.voice_client
        if vc:
            if self.guild.id in music_queues:
                music_queues[self.guild.id].clear()
            vc.stop()
            await vc.disconnect()
            await interaction.response.send_message("🛑 น้อน Doro ล้างคิวและบินออกจากห้องเสียงเรียบร้อยแล้วค๊าา!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ บอทไม่ได้อยู่ในห้องคุยเสียงค๊าา", ephemeral=True)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))

def play_next_song(guild_id, vc, channel):
    if guild_id in music_queues and music_queues[guild_id]:
        next_song = music_queues[guild_id].pop(0)
        current_songs[guild_id] = next_song
        source = discord.FFmpegPCMAudio(next_song['url'], **FFMPEG_OPTIONS)
        vc.play(source, after=lambda e: play_next_song(guild_id, vc, channel))
        bot.loop.create_task(channel.send(f"🎶 กำลังเล่นเพลงถัดไปค๊าา: **{next_song['title']}**"))
    else:
        if guild_id in current_songs:
            del current_songs[guild_id]
        bot.loop.create_task(vc.disconnect())

# ==========================================
# 🐈 BLACK CAT MULTI-ROLE DISPATCHER (แจกยศแมวทมิฬ)
# ==========================================
class DynamicGroupJoinView(discord.ui.View):
    def __init__(self, role_id: int, emoji_str: str):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.add_item(discord.ui.Button(label="🐈 กดเพื่อรับยศเข้ากลุ่มแมวทมิฬ", style=discord.ButtonStyle.secondary, emoji=emoji_str, custom_id=f"join_group_role_{role_id}"))

class RoleSetupAdminView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=120)
        self.guild = guild
        self.chosen_role = None
        self.chosen_emoji = "🐈"

        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        
        self.role_select = discord.ui.Select(placeholder="🐱 ขั้นตอนที่ 1: เลือกยศที่จะบรรจุลงปุ่มกด", options=options, row=0)
        self.role_select.callback = self.role_callback
        self.add_item(self.role_select)

        emojis = [
            discord.SelectOption(label="🐈 แมวดำทมิฬ", value="🐈"),
            discord.SelectOption(label="🌸 ซากุระชมพู", value="🌸"),
            discord.SelectOption(label="🔥 ไฟอัคคี", value="🔥"),
            discord.SelectOption(label="💫 ละอองดาว", value="💫")
        ]
        self.emoji_select = discord.ui.Select(placeholder="🎨 ขั้นตอนที่ 2: เลือกไอคอนอิโมจิประดับปุ่ม", options=emojis, row=1)
        self.emoji_select.callback = self.emoji_callback
        self.add_item(self.emoji_select)

    async def role_callback(self, interaction: discord.Interaction):
        self.chosen_role = interaction.guild.get_role(int(self.role_select.values[0]))
        await interaction.response.send_message(f"🔒 ล็อคเป้าหมายยศ: **{self.chosen_role.name}** เรียบร้อยค๊าา!", ephemeral=True)

    async def emoji_callback(self, interaction: discord.Interaction):
        self.chosen_emoji = self.emoji_select.values[0]
        await interaction.response.send_message(f"🎨 เลือกใช้ดีไซน์อิโมจิ: {self.chosen_emoji} เรียบร้อยค๊าา!", ephemeral=True)

    @discord.ui.button(label="✨ เสกปุ่มรับยศถาวรลงแชทนี้เลย!", style=discord.ButtonStyle.success, emoji="🚀", row=2)
    async def deploy_btn(self, interaction: discord.Interaction, btn):
        if not self.chosen_role:
            return await interaction.response.send_message("❌ คุณพี่ลืมเลือกยศในกล่องข้อ 1 หรือเปล่าน้าา?", ephemeral=True)

        await interaction.response.defer()
        embed = discord.Embed(
            title="🐈 ศูนย์รับบทบาทสมาชิกกลุ่มแมวทมิฬ (Black Cat Vault)",
            description=f"กดปุ่มด้านล่างเพื่อรับยศติดตัวเข้ากลุ่ม **{self.chosen_role.mention}** ได้ด้วยตนเองทันทีค๊าา!\n\n*ไม่ต้องง้อแอดมินให้เสียเวลา ลุยเยย! ✨*",
            color=0x000000
        )
        embed.set_image(url="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3I4N2I5M2M5MmE0MDRmYjllNWE2ZGNmMDFlNTAwYjRjYmU0Zjg2ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hog2UAsK791U1mZ5r9/giphy.gif")
        
        deployed_view = discord.ui.View(timeout=None)
        btn_item = discord.ui.Button(label=f"กดเพื่อรับยศ {self.chosen_role.name}", style=discord.ButtonStyle.success, emoji=self.chosen_emoji, custom_id=f"dynamic_custom_role_claim_{self.chosen_role.id}")
        
        async def claim_callback(inter: discord.Interaction):
            await inter.response.defer(ephemeral=True)
            try:
                if self.chosen_role in inter.user.roles:
                    await inter.user.remove_roles(self.chosen_role)
                    await inter.followup.send(f"🧹 ถอดยศ **{self.chosen_role.name}** ออกจากตัวเรียบร้อยค๊าา!", ephemeral=True)
                else:
                    await inter.user.add_roles(self.chosen_role)
                    await inter.followup.send(f"🎉 บรรจุยศ **{self.chosen_role.name}** เข้าสู่โปรไฟล์คุณพี่เรียบร้อยค๊าา เลิศมาก!", ephemeral=True)
            except:
                await inter.followup.send("❌ น้อน Doro ยศอยู่ต่ำกว่าบทบาทนี้ เลยดึงยศให้คุณพี่ไม่ได้ค๊าางึมม", ephemeral=True)

        btn_item.callback = claim_callback
        deployed_view.add_item(btn_item)
        
        await interaction.channel.send(embed=embed, view=deployed_view)
        await interaction.message.delete()

class CustomClearModal(discord.ui.Modal, title="🧹 กำหนดจำนวนข้อความที่ต้องการลบ"):
    amount_input = discord.ui.TextInput(label="ระบุจำนวน (1-100 ข้อความค๊าา)", placeholder="ระบุตัวเลข เช่น 25", required=True)

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
        embed_nuke.set_image(url="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3I4N2I5M2M5MmE0MDRmYjllNWE2ZGNmMDFlNTAwYjRjYmU0Zjg2ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hog2UAsK791U1mZ5r9/giphy.gif")
        await new_channel.send(embed=embed_nuke, delete_after=3)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.success, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


# =====================================================================
# 📊 UPDATE FEATURE: MEMBER ANALYTICS SYSTEM (ระบบเปลี่ยนหน้า ไม่สร้างกล่องแชทใหม่)
# =====================================================================
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

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.danger, emoji="⬅️", row=1)
    async def back(self, interaction: discord.Interaction, btn):
        await interaction.response.defer()
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
        current_data = load_roblox_data()
        current_data[g_id] = {
            "name": full_display_name, 
            "url": self.game_url.value.strip(),
            "image": self.game_image.value.strip() if self.game_image.value else None
        }
        save_roblox_data(current_data)
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
    def __init__(self):
        current_data = load_roblox_data()
        options = [discord.SelectOption(label=data["name"][:90], value=key) for key, data in current_data.items()] if current_data else [discord.SelectOption(label="ยังไม่มีเกมในคลัง", value="none")]
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", options=options)
        
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        game_data = load_roblox_data().get(self.values[0])
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
        current_data = load_roblox_data()
        
        if g_id in current_data:
            deleted_name = current_data[g_id]['name']
            del current_data[g_id]
            save_roblox_data(current_data)
            await interaction.followup.send(f"🗑️ ลบเกม **{deleted_name}** ออกจากคลังแสงเรียบร้อยค๊าา!", ephemeral=True, delete_after=3)
        else: 
            await interaction.followup.send(f"❌ ไม่พบรหัสเกม '{g_id}' ในระบบค๊าา ลองเช็คตัวพิมพ์ดี ๆ น้าา", ephemeral=True, delete_after=3)

class RobloxServerView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(RobloxServerSelect())
    
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


# ==========================================
# 📊 NEW UPDATE FEATURE: BRAINSTORM POLL SYSTEM (3-in-1 แบบไม่บั๊ก)
# ==========================================
class BrainstormVoteButton(discord.ui.Button):
    def __init__(self, label: str, custom_id: str, style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(label=label, style=style, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        poll_id = interaction.message.id
        if poll_id not in brainstorm_polls:
            return await interaction.response.send_message("❌ 不พบข้อมูลโพลนี้ในระบบฐานข้อมูลชั่วคราวค๊าา", ephemeral=True)

        poll_data = brainstorm_polls[poll_id]
        user_id = interaction.user.id
        choice_selected = self.custom_id.replace("poll_choice_", "")

        # บันทึกคะแนนโหวต (1 คน 1 สิทธิ์ สามารถเปลี่ยนใจโหวตใหม่ได้)
        poll_data["voters"][user_id] = choice_selected
        await interaction.response.send_message(f"✅ น้อน Doro บันทึกคะแนนโหวต '{choice_selected}' ของคุณพี่เรียบร้อยค๊าา!", ephemeral=True)
        
        # ทำการอัปเดตผลคะแนนแบบเรียลไทม์บนตัวบอร์ดโพลเดิมทันที!
        await update_poll_display(interaction.message, poll_data)

async def update_poll_display(message: discord.Message, poll_data: dict):
    total_votes = len(poll_data["voters"])
    score_count = {choice: 0 for choice in poll_data["choices"]}
    
    for v_choice in poll_data["voters"].values():
        if v_choice in score_count:
            score_count[v_choice] += 1

    desc_lines = []
    for choice in poll_data["choices"]:
        count = score_count[choice]
        pct = (count / total_votes * 100) if total_votes > 0 else 0
        bar_length = int(pct // 10)
        progress_bar = "🟩" * bar_length + "⬜" * (10 - bar_length)
        desc_lines.append(f"**• {choice}**\n{progress_bar} *{pct:.1f}% ({count} โหวต)*")

    embed_update = discord.Embed(
        title=f"📊 โพลระดมสมอง: {poll_data['question']}",
        description="\n".join(desc_lines) + f"\n\n👥 **ยอดผู้ร่วมโหวตทั้งหมดในปัจจุบัน:** {total_votes} คน",
        color=0xFFC0CB
    )
    embed_update.set_footer(text="💡 คุณพี่สามารถกดเปลี่ยนใจเลือกข้อใหม่ได้ตลอดเวลาจนกว่าแอดมินจะปิดโพลน้าา")
    await message.edit(embed=embed_update)

class ClosePollButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔒 ปิดโพลและสรุปผลคะแนน", style=discord.ButtonStyle.danger, row=4)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ คุณพี่ไม่มีสิทธิ์ในการปิดโพลระดมสมองนี้น้าา", ephemeral=True)
            
        poll_id = interaction.message.id
        if poll_id not in brainstorm_polls:
            return await interaction.response.send_message("❌ ไม่พบข้อมูลโพลนี้แล้วค๊าา", ephemeral=True)

        await interaction.response.defer()
        poll_data = brainstorm_polls[poll_id]
        
        total_votes = len(poll_data["voters"])
        score_count = {choice: 0 for choice in poll_data["choices"]}
        for v_choice in poll_data["voters"].values():
            if v_choice in score_count:
                score_count[v_choice] += 1

        result_channel = interaction.guild.get_channel(poll_data["result_channel_id"])
        if result_channel:
            final_lines = [f"**📍 {ch}:** {amt} โหวต" for ch, amt in score_count.items()]
            embed_res = discord.Embed(
                title=f"🎉 [สรุปผลประชามติ] โพล: {poll_data['question']}",
                description=f"📊 **ผลการลงคะแนนรอบตัดสิน:**\n" + "\n".join(final_lines) + f"\n\n📥 มีผู้เข้าร่วมแสดงวิสัยทัศน์ทั้งหมด {total_votes} คนค๊าา!",
                color=0x2ECC71
            )
            await result_channel.send(embed=embed_res)

        embed_closed = interaction.message.embeds[0]
        embed_closed.title = f"🔒 [ปิดโพลแล้ว] {poll_data['question']}"
        await interaction.message.edit(embed=embed_closed, view=None)
        
        del brainstorm_polls[poll_id]
        await interaction.channel.send("✨ น้อน Doro ปิดระบบลงคะแนน และจัดส่งรายงานเข้าห้องสรุปผลเรียบร้อยค๊าา!", delete_after=5)

class AskQuestionTextModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="✍️ รายละเอียดคำถามโพลแสนสนุก")
        self.parent_view = parent_view
        self.question = discord.ui.TextInput(label="หัวข้อคำถามโพลนี้คืออะไรเอ่ย?", placeholder="เช่น วันนี้กินอะไรกันดีค๊าา?", required=True)
        self.choices_input = discord.ui.TextInput(
            label="ตัวเลือกคำตอบ (แยกด้วยเครื่องหมาย , น้าา)", 
            style=discord.TextStyle.paragraph,
            placeholder="ตัวอย่าง: ชาบู, หมูกระทะ, ส้มตำ, กะเพราไข่ดาว",
            required=True
        )
        self.add_item(self.question)
        self.add_item(self.choices_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value.strip()
        self.parent_view.poll_choices = [c.strip() for c in self.choices_input.value.split(",") if c.strip()]
        
        if len(self.parent_view.poll_choices) < 2:
            return await interaction.response.send_message("❌ โพลระดมสมองต้องระบุตัวเลือกอย่างน้อย 2 ข้อขึ้นไปนะค๊าา!", ephemeral=True)
        if len(self.parent_view.poll_choices) > 20:
            return await interaction.response.send_message("❌ หูยย ตัวเลือกเยอะเกิน 20 ข้อ ระบบปุ่มรองรับไม่ไหวค๊าางึมม", ephemeral=True)
            
        await interaction.response.send_message("✏️ บันทึกคำถามและชอยส์ลงคลังของน้อน Doro เรียบร้อยค๊าา!", ephemeral=True)

class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = None
        self.poll_choices = []
        self.target_id = None
        self.result_id = None
        
        channels = [discord.SelectOption(label=f"#{ch.name}"[:40], value=str(ch.id)) for ch in guild.channels if isinstance(ch, discord.TextChannel)][:25]
        
        self.s1 = discord.ui.Select(placeholder="📢 1. เลือกห้องที่จะปล่อยโพลล์ระดมสมอง", options=channels, row=0)
        self.s2 = discord.ui.Select(placeholder="📊 2. เลือกห้องที่จะให้จัดส่งผลสรุปคะแนน", options=channels, row=1)
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

    @discord.ui.button(label="✏️ กรอกหัวข้อและชอยส์", style=discord.ButtonStyle.primary, row=2)
    async def input_btn(self, interaction: discord.Interaction, btn): 
        await interaction.response.send_modal(AskQuestionTextModal(self))

    @discord.ui.button(label="🚀 อนุมัติยิงโพลล์ออกสู่สากล", style=discord.ButtonStyle.success, row=2)
    async def send_btn(self, interaction: discord.Interaction, btn):
        if not self.question_text or not self.poll_choices or not self.target_id or not self.result_id:
            return await interaction.response.send_message("❌ กรุณากรอกข้อมูลข้อ 1, 2 และตั้งคำถามให้ครบถ้วนก่อนปล่อยโพลนะค๊าา", ephemeral=True)
            
        chan = self.guild.get_channel(self.target_id)
        if chan:
            vote_view = discord.ui.View(timeout=None)
            for choice in self.poll_choices:
                vote_view.add_item(BrainstormVoteButton(label=choice[:80], custom_id=f"poll_choice_{choice}"))
            
            vote_view.add_item(ClosePollButton())

            embed_poll = discord.Embed(
                title=f"📊 โพลระดมสมอง: {self.question_text}",
                description="💡 *ยังไม่มีผู้ลงคะแนนในขณะนี้ มาร่วมเป็นคนแรกกันเลยค๊าา!*",
                color=0xFFC0CB
            )
            msg = await chan.send(embed=embed_poll, view=vote_view)
            
            brainstorm_polls[msg.id] = {
                "question": self.question_text,
                "choices": self.poll_choices,
                "result_channel_id": self.result_id,
                "voters": {}
            }
            await interaction.response.send_message(f"✅ ปล่อยบอร์ดโพลล์อัจฉริยะไปที่ห้อง {chan.mention} สำเร็จแล้วค๊าา!", ephemeral=True)

    @discord.ui.button(label="🔙 ย้อนกลับหน้าแรก", style=discord.ButtonStyle.secondary, emoji="⬅️", row=3)
    async def back(self, interaction: discord.Interaction, btn): 
        await interaction.message.edit(embed=generate_main_menu_embed(self.guild), view=BotControlMenuView(self.guild))


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
        await message.channel.send(embed=discord.Embed(title="🛡️ ระบบมอบยศกลุ่มอัจฉริยะค๊าาา ", color=0xFFB6C1), view=MultiRoleManagementView(message.guild))
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

keep_alive()  # เรียกใช้งานระบบเว็บเซิร์ฟเวอร์คู่ขนานป้องกันเซิร์ฟดับ
bot.run(DISCORD_TOKEN)
