import os
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

from myserver import server_on

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN not found in environment. ใส่ token ใน .env ด้วย")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doro")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.presences = True # เพื่อให้บอทเช็กสถานะออนไลน์สำหรับการคำนวณโหวตเตะ

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Global Data ---
custom_responses = {
    "bot ชื่ออะไร": "ผมชื่อ doro ค่ะ 🤖",
    "doro ช่วยอะไรได้บ้าง": "ฉันตอบคำถามทั่วไป และเปิดเพลงให้คุณได้ด้วยนะ!",
    "doro สวัสดี": "สวัสดีค่ะ ยินดีที่ได้คุยด้วยนะ!",
}

QUESTION_CHOICES = {
    "เอา / ไม่เอา / ไม่แน่ใจ": ["เอา", "ไม่เอา", "ไม่แน่ใจ"],
    "เล่น / ไม่เล่น": ["เล่น", "ไม่เล่น"],
    "ใช่ / ไม่ใช่": ["ใช่", "ไม่ใช่"],
}

user_contexts = {}
vote_records = {}  
music_queues = {}  
now_playing = {}   

ytdl_format_options = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "extract_flat": "in_playlist",
    "no_warnings": True,
    "default_search": "ytsearch",
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}

async def ytdl_extract(query: str):
    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if "entries" in info:
            info = info["entries"][0]
        return {"title": info.get("title"), "url": info.get("url"), "webpage_url": info.get("webpage_url")}
    except Exception as e:
        logger.exception("yt_dlp error")
        return None

def ensure_queue(guild_id: int):
    if guild_id not in music_queues:
        music_queues[guild_id] = []

async def play_next_in_queue(guild: discord.Guild):
    guild_id = guild.id
    ensure_queue(guild_id)
    queue = music_queues[guild_id]
    voice_client = discord.utils.get(bot.voice_clients, guild=guild)
    if not voice_client: return
    if voice_client.is_playing() or voice_client.is_paused(): return
    if not queue:
        now_playing.pop(guild_id, None)
        return
    track = queue.pop(0)
    now_playing[guild_id] = track
    source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
    def after_play(error):
        if error: logger.error(f"Error while playing: {error}")
        fut = asyncio.run_coroutine_threadsafe(play_next_in_queue(guild), bot.loop)
        try: fut.result()
        except Exception: logger.exception("Error scheduling next track")
    voice_client.play(source, after=after_play)

# ==========================================
# 🎛️ NEW UI COMMAND MODE (เมนูหลักควบคุมคำสั่ง)
# ==========================================
class BotCommandControlSelect(discord.ui.Select):
    def __init__(self, guild):
        options = [
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศ", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="เรียกเมนูตั้งค่าโพล โหวตเลือกคำตอบ", value="setup_poll"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="แสดงรายละเอียดคำสั่งตัวอักษรของบอท", value="show_commands")
        ]
        super().__init__(placeholder="🎛️ เลือกโหมดคำสั่งที่ต้องการใช้งาน...", min_values=1, max_values=1, options=options)
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        
        if value == "setup_roles":
            embed = discord.Embed(
                title="🛡️ ระบบจัดการยศอัตโนมัติ",
                description="นายสามารถเลือกรับยศที่ต้องการจากเมนูด้านล่าง หรือกดปุ่มขอยศพร้อมส่งเหตุผลได้เลยนะ!",
                color=0xFFB6C1
            )
            view = RequestRoleView(interaction.guild)
            await interaction.response.send_message(embed=embed, view=view)
            
        elif value == "setup_poll":
            view = AskQuestionView(interaction.guild)
            await interaction.response.send_message("📋 **ตั้งค่าระบบโพลคำถาม:** โปรดเลือกเงื่อนไขด้านล่างให้ครบถ้วนก่อนส่งคำถาม", view=view, ephemeral=True)
            
        elif value == "show_commands":
            embed = discord.Embed(
                title="📘 คำสั่งของ Doro 🤖",
                description=(
                    "**🔹 bot ชื่ออะไร** / **doro ช่วยอะไรได้บ้าง** / **doro สวัสดี**\n"
                    "**🔹 doro เมนู** : เปิดแผงควบคุม UI สำหรับขอยศ สร้างโพลคำถาม\n"
                    "**🔹 doro ค้นหา <ชื่อคลิป>**\n"
                    "**🔹 doro สมาชิกทั้งหมด**\n"
                    "**🔹 doro เวลา**\n"
                    "**🔹 doro โหวตเตะ <@ชื่อ>** : โหวตเตะคนออกจากเซิร์ฟเวอร์/ห้องเสียง\n"
                    "**🔹 doroส่งข้อความ <ช่อง_id> <ข้อความ>** *(แอดมิน)*\n"
                    "**🔹 doro ล้างข้อความ <จำนวน>** *(ผู้จัดการข้อความ)*\n"
                    "**🔹 doro รีเซ็ตchannel**\n"
                    "**🔹 doro คำสั่งเพลง** : ดูชุดคำสั่ง !play !skip !stop ทั้งหมด"
                ),
                color=discord.Color.magenta()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class BotControlMenuView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(BotCommandControlSelect(guild))


# === Dynamic Role System ===
class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🎨 เลือกรับยศของคุณที่นี่...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.values[0]))
        if role is None:
            return await interaction.response.send_message("❌ ไม่พบยศนี้ในเซิร์ฟเวอร์", ephemeral=True)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ คุณได้รับยศ **{role.name}** เรียบร้อยแล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์ให้ยศนี้ (โปรดตรวจสอบสิทธิ์ Manage Roles และลำดับยศของบอท)", ephemeral=True)

class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศทั่วไปทั้งหมด", style=discord.ButtonStyle.danger, emoji="🗑️")

    async def callback(self, interaction: discord.Interaction):
        roles_to_remove = [r for r in interaction.user.roles if r.name != "@everyone" and not r.managed]
        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)
            await interaction.response.send_message("🧹 ลบยศทั่วไปของคุณออกจากตัวเรียบร้อยแล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์ลบยศของคุณ", ephemeral=True)

class TextInputModal(discord.ui.Modal, title="📝 กรอกเหตุผลคำขอยศพิเศษ"):
    reason = discord.ui.TextInput(label="เหตุผล/ชื่อยศพิเศษที่ต้องการขอ", style=discord.TextStyle.paragraph, placeholder="เช่น ขอเข้าห้องแชทลับกลุ่มนักพัฒนา...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"📨 ส่งคำขอยศสำเร็จแล้ว! เหตุผลของคุณ: {self.reason.value}", ephemeral=True)

class TextInputButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📝 ส่งคำขอยศพิเศษ (เขียนเหตุผล)", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextInputModal())

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(guild))
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())


# --- Poll UI System ---
class AskQuestionTextModal(discord.ui.Modal, title="✍️ กรอกรายละเอียดคำถาม"):
    question = discord.ui.TextInput(label="หัวข้อคำถามโพลของคุณ", style=discord.TextStyle.paragraph)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value
        await interaction.response.send_message("✏️ บันทึกคำถามลงในระบบชั่วคราวแล้ว", ephemeral=True)

class OpenQuestionModalButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="✏️ กรอกคำถาม", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AskQuestionTextModal(self.parent_view))

class SubmitQuestionButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="🚀 ยืนยันปล่อยโพลคำถาม", style=discord.ButtonStyle.success)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.submit_question(interaction)

class VoteSelect(discord.ui.Select):
    def __init__(self, choices, result_channel_id):
        opts = [discord.SelectOption(label=opt) for opt in choices]
        super().__init__(placeholder="🗳️ กดเพื่อโหวตคำตอบของคุณ...", options=opts, min_values=1, max_values=1)
        self.result_channel_id = result_channel_id

    async def callback(self, interaction2: discord.Interaction):
        user = interaction2.user
        msg_id = interaction2.message.id
        user_votes = vote_records.setdefault(msg_id, {})
        user_votes[user.id] = self.values[0]

        embed = interaction2.message.embeds[0] if interaction2.message.embeds else None
        choice_set_name = None
        if embed and embed.description:
            parts = embed.description.split('\n')
            if parts: choice_set_name = parts[0]

        choices = QUESTION_CHOICES.get(choice_set_name, [])
        guild = interaction2.guild

        summary = {ans: [] for ans in choices}
        for uid, ans in user_votes.items():
            member = guild.get_member(uid) if guild else None
            if member: summary.setdefault(ans, []).append(member.display_name)
            else: summary.setdefault(ans, []).append(f"<@{uid}>")

        summary_text = ""
        for ans in summary:
            voters = summary[ans]
            summary_text += f"**{ans}**: {len(voters)} โหวต\n"
            if voters: summary_text += "  ↳ " + ", ".join(voters) + "\n"

        result_channel = guild.get_channel(self.result_channel_id) if guild else None
        if result_channel:
            await result_channel.send(embed=discord.Embed(title="📊 ผลโหวตล่าสุดอัปเดตแล้ว", description=summary_text, color=0x87CEEB))
        await interaction2.response.send_message(f"✅ บันทึกคะแนนโหวตโพลคำตอบ [{self.values[0]}] ของคุณแล้ว", ephemeral=True)

class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = None

        self.select_choices = discord.ui.Select(
            placeholder="📦 1. เลือกชุดคำตอบของโพล",
            options=[discord.SelectOption(label=key, value=key) for key in QUESTION_CHOICES.keys()]
        )
        self.add_item(self.select_choices)

        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        channel_options = [discord.SelectOption(label=f"#{ch.name}", value=str(ch.id)) for ch in channels[:25]]
        
        self.select_question_channel = discord.ui.Select(placeholder="📢 2. เลือกห้องที่จะปล่อยคำถาม", options=channel_options)
        self.add_item(self.select_question_channel)

        self.select_result_channel = discord.ui.Select(placeholder="📊 3. เลือกห้องสรุปคะแนนโหวต", options=channel_options)
        self.add_item(self.select_result_channel)

        self.add_item(OpenQuestionModalButton(self))
        self.add_item(SubmitQuestionButton(self))

    async def submit_question(self, interaction: discord.Interaction):
        if not self.question_text:
            return await interaction.response.send_message("❗ กรุณากรอกหัวข้อคำถามผ่านปุ่ม 'กรอกคำถาม' ก่อนส่ง", ephemeral=True)
        choice_set_name = self.select_choices.values[0] if self.select_choices.values else None
        q_ch_id = int(self.select_question_channel.values[0]) if self.select_question_channel.values else None
        r_ch_id = int(self.select_result_channel.values[0]) if self.select_result_channel.values else None

        if not (choice_set_name and q_ch_id and r_ch_id):
            return await interaction.response.send_message("❗ โปรดเลือกชุดคำตอบ ช่องส่งคำถาม และห้องสรุปคะแนนให้ครบถ้วนก่อน", ephemeral=True)

        choices = QUESTION_CHOICES.get(choice_set_name)
        q_channel = self.guild.get_channel(q_ch_id)
        
        embed = discord.Embed(title="📢 โพลคำถามจากสมาชิกในเซิร์ฟเวอร์", description=f"{choice_set_name}\n\n**คำถาม:** {self.question_text}", color=discord.Color.pink())
        vote_view = discord.ui.View(timeout=None)
        vote_view.add_item(VoteSelect(choices, r_ch_id))
        
        sent_msg = await q_channel.send(embed=embed, view=vote_view)
        vote_records[sent_msg.id] = {}
        await interaction.response.send_message(f"✅ ปล่อยโพลเรียบร้อยแล้วที่ห้อง {q_channel.mention}", ephemeral=True)
        self.question_text = None


# --- Vote Kick UI System ---
class KickTypeButton(discord.ui.Button):
    def __init__(self, target: discord.Member, kick_type: str, required_votes: int):
        label_str = "🔊 เตะออกจากห้องเสียง" if kick_type == "voice" else "💥 เตะออกจากเซิร์ฟเวอร์"
        style = discord.ButtonStyle.primary if kick_type == "voice" else discord.ButtonStyle.danger
        super().__init__(label=label_str, style=style)
        self.target = target
        self.kick_type = kick_type
        self.required_votes = required_votes

    async def callback(self, interaction: discord.Interaction):
        view = VoteProgressView(self.target, self.kick_type, self.required_votes)
        embed = discord.Embed(
            title=f"🚨 เริ่มวาระการลงมติโหวตเตะผู้ใช้",
            description=f"เป้าหมาย: {self.target.mention}\nมาตรการการลงทัณฑ์: **{self.label}**\nเกณฑ์คะแนนเสียงฉลุย: **{self.required_votes}** โหวตจากคนออนไลน์",
            color=discord.Color.red()
        )
        embed.add_field(name="เกณฑ์ผลการลงคะแนนในขณะนี้", value=f"🟢 เห็นด้วย (Vote): 0/{self.required_votes}")
        if self.view:
            for item in self.view.children: item.disabled = True
            await interaction.response.edit_message(view=self.view)
        await interaction.channel.send(embed=embed, view=view)

class VoteKickTypeView(discord.ui.View):
    def __init__(self, target: discord.Member, required_votes: int):
        super().__init__(timeout=60)
        self.add_item(KickTypeButton(target, "voice", required_votes))
        self.add_item(KickTypeButton(target, "server", required_votes))

class VoteProgressView(discord.ui.View):
    def __init__(self, target: discord.Member, kick_type: str, required_votes: int):
        super().__init__(timeout=120)
        self.target = target
        self.kick_type = kick_type
        self.required_votes = required_votes
        self.voters = set()

    @discord.ui.button(label="🟢 เห็นด้วย (Vote)", style=discord.ButtonStyle.success, emoji="👍")
    async def vote_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters:
            return await interaction.response.send_message("คุณใช้สิทธิ์ลงคะแนนไปแล้ว ไม่สามารถโหวตซ้ำได้!", ephemeral=True)
        if interaction.user.id == self.target.id:
            return await interaction.response.send_message("คุณจะกดเห็นด้วยเพื่อเตะตัวเองไม่ได้นะเฮ้ย! 🤣", ephemeral=True)

        self.voters.add(interaction.user.id)
        current_votes = len(self.voters)

        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="เกณฑ์ผลการลงคะแนนในขณะนี้", value=f"🟢 เห็นด้วย (Vote): {current_votes}/{self.required_votes}")

        if current_votes >= self.required_votes:
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)

            try:
                if self.kick_type == "voice":
                    if self.target.voice and self.target.voice.channel:
                        await self.target.move_to(None, reason="มติโหวตเห็นด้วยให้เตะแยกย้ายจากเสียง")
                        await interaction.channel.send(f"🔨 มติคะแนนเสียงเป็นเอกฉันท์! ตัดสายย้าย {self.target.mention} ออกจากห้องเสียงแล้ว")
                    else:
                        await interaction.channel.send(f"⚠️ ผลโหวตชนะเรียบร้อย แต่ตัวเป้าหมาย {self.target.mention} ดึงสายออกหนีไปก่อนหน้าแล้ว")
                elif self.kick_type == "server":
                    await self.target.kick(reason="ผลโหวตลงมติเตะออกจากเซิร์ฟเวอร์โดยผู้ใช้งาน")
                    await interaction.channel.send(f"💥 บูม! ประชามติเห็นพ้องต้องกัน ทำการดีด {self.target.mention} ปลิวออกจากเซิร์ฟเวอร์ถาวรเรียบร้อย!")
            except discord.Forbidden:
                await interaction.channel.send(f"❌ ระบบไม่ทำงาน: ยศของบอทต่ำกว่าเป้าหมาย หรือบอทขาดสิทธิ์จัดการดึงคน/เตะคน (โปรดเช็คลำดับสิทธิ์ยศ)")
            self.stop()
        else:
            await interaction.response.edit_message(embed=embed, view=self)


# --- Message Handling Events ---
@bot.event
async def on_ready():
    logger.info(f"Doro UI Engine active as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return

    user_id = message.author.id
    msg = message.content.strip()
    lower_msg = msg.lower()

    user_contexts.setdefault(user_id, []).append((user_id, message.author.name, msg))
    if len(user_contexts[user_id]) > 5: user_contexts[user_id].pop(0)

    try:
        # 🎛️ เรียกหน้าเมนูหน้าต่าง UI ควบคุมรวมคำสั่งทั้งหมด
        if lower_msg == "doro เมนู":
            embed = discord.Embed(
                title="⚙️ Doro แผงควบคุมระบบอัจฉริยะ (UI Mode)",
                description="ยินดีต้อนรับสู่โหมด UI! คุณสามารถกดเลือกเมนูด้านล่างนี้เพื่อเปิดใช้งานฟังก์ชันรับยศ, ส่งโพลคำถาม หรือดูคู่มือการใช้งานบอทได้อย่างรวดเร็วครับ",
                color=0x3498DB
            )
            view = BotControlMenuView(message.guild)
            await message.channel.send(embed=embed, view=view)
            return

        if lower_msg.startswith("doro โหวตเตะ"):
            guild = message.guild
            if guild is None: return

            target_member = None
            if message.mentions:
                target_member = message.mentions[0]
            else:
                search_name = msg[len("doro โหวตเตะ"):].strip()
                if search_name:
                    target_member = discord.utils.find(lambda m: search_name in m.display_name or search_name in m.name, guild.members)

            if not target_member:
                await message.channel.send("❗ ระบุเป้าหมายโดย Mention ชื่อ เช่น `doro โหวตเตะ @ชื่อเพื่อน`")
                return
            if target_member.id == message.author.id:
                await message.channel.send("จะโหวตเตะตัวเองไม่ได้นะ! 😂")
                return

            online_members = [m for m in guild.members if m.status != discord.Status.offline and not m.bot]
            required_votes = max(2, len(online_members) // 2 + 1)

            view = VoteKickTypeView(target_member, required_votes)
            await message.channel.send(f"🛠️ โปรดระบุประเภทการโหวตลงโทษ {target_member.mention}:", view=view)
            return

        # --- คำสั่งพื้นฐานเดิม ---
        if lower_msg == "doro เวลา":
            now = datetime.now(pytz.timezone('Asia/Bangkok'))
            await message.channel.send(f"🕒 เวลาปัจจุบัน: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            return

        if lower_msg == "doro สมาชิกทั้งหมด":
            guild = message.guild
            if guild is None: return
            lines = [f"{m.display_name} - {str(m.status)}" for m in guild.members]
            for i in range(0, len(lines), 20):
                await message.channel.send(f"👥 สมาชิก ({guild.member_count} คน):\n" + "\n".join(lines[i:i+20]))
            return

        if lower_msg.startswith("doro ค้นหา"):
            search_term = msg[len("doro ค้นหา"):].strip()
            if not search_term: return
            results = VideosSearch(search_term, limit=1).result()
            if not results.get("result"): return
            await message.channel.send(f"🎵 คลิป: **{results['result'][0]['title']}**\n🔗 {results['result'][0]['link']}")
            return

        if lower_msg.startswith("doroส่งข้อความ") or lower_msg.startswith("doro ส่งข้อความ"):
            if not message.author.guild_permissions.administrator: return
            content = msg[len("doroส่งข้อความ" if lower_msg.startswith("doroส่งข้อความ") else "doro ส่งข้อความ"):].strip().split(maxsplit=1)
            if len(content) >= 2:
                ch = bot.get_channel(int(content[0]))
                if ch: await ch.send(f"@everyone {content[1]}")
            return

        if lower_msg.startswith("doroล้างข้อความ") or lower_msg.startswith("doro ล้างข้อความ"):
            if not message.author.guild_permissions.manage_messages: return
            count_str = msg[len("doroล้างข้อความ" if lower_msg.startswith("doroล้างข้อความ") else "doro ล้างข้อความ"):].strip()
            try:
                deleted = await message.channel.purge(limit=int(count_str) + 1)
                await message.channel.send(f"🧹 ลบข้อความแล้วจำนวน {len(deleted)-1} ข้อความ", delete_after=3)
            except Exception: pass
            return

        if lower_msg == "doro รีเซ็ตchannel":
            if not message.author.guild_permissions.manage_channels: return
            old_channel = message.channel
            new_channel = await old_channel.clone()
            await old_channel.delete()
            await new_channel.send("💣 รีเซ็ตห้องใหม่เรียบร้อย!")
            return

        if lower_msg == "doro คำสั่งเพลง":
            embed = discord.Embed(title="🎧 คำสั่งบอทเพลง (!คำสั่ง)", description="**!join** / **!leave** / **!play <ชื่อเพลง>** / **!skip** / **!stop** / **!pause** / **!resume** / **!queue** / **!nowplaying**", color=discord.Color.red())
            await message.channel.send(embed=embed)
            return

        if lower_msg in custom_responses:
            await message.channel.send(custom_responses[lower_msg])
            return

    except Exception:
        logger.exception("Text handler error")

    await bot.process_commands(message)


# --- Music Commands ---
@bot.command(name="join")
async def join_cmd(ctx):
    if ctx.author.voice is None: return
    ch = ctx.author.voice.channel
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc is None: await ch.connect()
    else: await vc.move_to(ch)
    await ctx.send(f"✅ เข้าห้อง: **{ch.name}**")

@bot.command(name="leave")
async def leave_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc: await vc.disconnect()

@bot.command(name="play")
async def play_cmd(ctx, *, query: str = None):
    if not query or not ctx.author.voice: return
    guild_id = ctx.guild.id
    ensure_queue(guild_id)
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc is None: 
        await ctx.author.voice.channel.connect()
        vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    await ctx.send("🔎 กำลังค้นหาเพลง...")
    info = await ytdl_extract(query)
    if info:
        track = {"title": info["title"], "url": info["url"], "requester": ctx.author.display_name}
        music_queues[guild_id].append(track)
        await ctx.send(f"✅ เพิ่มลงคิว: **{track['title']}**")
        if vc and not vc.is_playing() and not vc.is_paused():
            await play_next_in_queue(ctx.guild)

@bot.command(name="skip")
async def skip_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and (vc.is_playing() or vc.is_paused()): vc.stop()

@bot.command(name="stop")
async def stop_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc:
        vc.stop()
        music_queues[ctx.guild.id] = []
        now_playing.pop(ctx.guild.id, None)

@bot.command(name="pause")
async def pause_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_playing(): vc.pause()

@bot.command(name="resume")
async def resume_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_paused(): vc.resume()

@bot.command(name="queue")
async def queue_cmd(ctx):
    q = music_queues.get(ctx.guild.id, [])
    if not q: return await ctx.send("🎶 คิวว่าง")
    lines = [f"{i+1}. {t['title']}" for i, t in enumerate(q)]
    await ctx.send("\n".join(lines[:10]))

@bot.command(name="nowplaying")
async def nowplaying_cmd(ctx):
    t = now_playing.get(ctx.guild.id)
    if t: await ctx.send(f"🎵 กำลังเล่น: **{t['title']}**")

if __name__ == "__main__":
    try: server_on()
    except Exception: pass
    bot.run(DISCORD_TOKEN)
