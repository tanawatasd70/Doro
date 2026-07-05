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
    raise RuntimeError("DISCORD_TOKEN not found in environment. ใส่ token ใน .env ด้วยนะค๊าา")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("doro")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.presences = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Global Data (ปรับคำพูดน้อน Doro สุดคิ้วท์) ---
custom_responses = {
    "bot ชื่ออะไร": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักของทุกคนน~ 🤖💕",
    "doro ช่วยอะไรได้บ้าง": "หนูช่วยตอบคำถามทั่วไป เปิดเพลงเพราะ ๆ ให้ฟัง แล้วก็ช่วยดูแลเซิร์ฟเวอร์ได้ด้วยนะค๊าา! 🎵✨",
    "doro สวัสดี": "งื้อออ สวัสดีค่าา! ยินดีที่ได้คุยด้วยนะคะ วันนี้มีอะไรให้หนูช่วยไหมเอ่ย? 🌸",
}

user_contexts = {}
vote_records = {}  
poll_result_messages = {} 
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
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศสุดน่ารัก", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="สร้างโพลน่ารัก ๆ เพื่อโหวตเลือกคำตอบกันเถอะ", value="setup_poll"),
            discord.SelectOption(label="🚫 เริ่มวาระโหวตเตะสมาชิก", description="เลือกคนที่ทำตัวไม่น่ารักเพื่อเริ่มโหวตเตะกันค่ะ!", value="setup_kick"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูคู่มือการสั่งงานน้อน Doro ทั้งหมดกันงับ", value="show_commands")
        ]
        super().__init__(placeholder="🎛️ เลือกโหมดคำสั่งที่ต้องการให้น้อน Doro ทำงาน...", min_values=1, max_values=1, options=options)
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        
        if value == "setup_roles":
            embed = discord.Embed(
                title="🛡️ ระบบจัดการยศอัตโนมัติค๊าา",
                description="คุณชอบยศไหนเลือกรับจากเมนูด้านล่างได้เลยนะค๊าา หรือจะกดปุ่มขอยศพิเศษพร้อมส่งเหตุผลอ้อน ๆ มาให้แอดมินดูก็ได้น้าา~ ✨",
                color=0xFFB6C1
            )
            view = RequestRoleView(interaction.guild)
            await interaction.response.send_message(embed=embed, view=view)
            
        elif value == "setup_poll":
            view = AskQuestionView(interaction.guild)
            await interaction.response.send_message("📋 **ตั้งค่าระบบโพลคำถามน้าา:** โปรดเลือกห้องแชทและกรอกข้อมูลคำถามให้ครบถ้วนก่อนน้อน Doro จะปล่อยโพลนะค๊าา", view=view, ephemeral=True)
            
        elif value == "setup_kick":
            embed = discord.Embed(
                title="🚫 ระบบโหวตเตะสมาชิก (โหมด Doro เอาจริง!)",
                description="โปรดเลือกรายชื่อคนที่ไม่น่ารักที่คุณต้องการเริ่มโหวตลงมติเตะด้านล่างนี้ได้เลยค่ะงึมมม",
                color=discord.Color.red()
            )
            view = MemberSelectView(interaction.guild)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif value == "show_commands":
            embed = discord.Embed(
                title="📘 สมุดคู่มือของน้อน Doro 🤖✨",
                description=(
                    "**🔹 bot ชื่ออะไร** / **doro ช่วยอะไรได้บ้าง** / **doro สวัสดี**\n"
                    "**🔹 doro เมนู** : เปิดแผงควบคุม UI น่ารัก ๆ สำหรับขอยศ สร้างโพล หรือโหวตเตะ\n"
                    "**🔹 doro ค้นหา <ชื่อคลิป>** : ค้นหาคลิปวิดีโอให้คุณ\n"
                    "**🔹 doro สมาชิกทั้งหมด** : ดูสถิติคนในเซิร์ฟเวอร์แบบตะมุตะมิ\n"
                    "**🔹 doro เวลา** : เช็กเวลาปัจจุบัน\n"
                    "**🔹 doro โหวตเตะ** : เรียกหน้าต่าง UI แปะป้ายคนไม่น่ารัก\n"
                    "**🔹 doroส่งข้อความ <ช่อง_id> <ข้อความ>** *(คุณแอดมิน)*\n"
                    "**🔹 doro ลบข้อความ <จำนวน>** *(คุณผู้จัดการข้อความ)*\n"
                    "**🔹 doro รีเซ็ตchannel** : ชุบชีวิตห้องแชทใหม่\n"
                    "**🔹 doro คำสั่งเพลง** : ดูชุดคำสั่งเสียงดนตรี !play !skip !stop ทั้งหมดเจ้าค่ะ"
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
        super().__init__(placeholder="🎨 เลือกรับยศสุดเลิศของคุณที่นี่เลยน้าา...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.values[0]))
        if role is None:
            return await interaction.response.send_message("❌ งื้ออ ไม่พบยศนี้ในเซิร์ฟเวอร์เลยค่ะ", ephemeral=True)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ เย้! ยินดีด้วยน้าา คุณได้รับยศ **{role.name}** เรียบร้อยแล้วค่ะ! 🎉", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ น้อน Doro ไม่มีสิทธิ์ให้ยศนี้ง่าา (รบกวนคุณแอดมินช่วยตรวจสิทธิ์ Manage Roles และลำดับยศของหนูหน่อยน้าา)", ephemeral=True)

class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศทั่วไปทั้งหมดออกเยย", style=discord.ButtonStyle.danger, emoji="🗑️")

    async def callback(self, interaction: discord.Interaction):
        roles_to_remove = [r for r in interaction.user.roles if r.name != "@everyone" and not r.managed]
        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)
            await interaction.response.send_message("🧹 ฟู่ๆๆ~ ลบยศทั่วไปออกจากตัวให้เรียบร้อยแล้วค๊าา ตัวเบาหวิวเยย!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ งื้ออ หนูลบยศให้ไม่ได้ง่าา พลังของหนูไม่พอ", ephemeral=True)

class TextInputModal(discord.ui.Modal, title="📝 ส่งเหตุผลอ้อน ๆ เพื่อขอยศพิเศษ"):
    reason = discord.ui.TextInput(label="เหตุผล/ชื่อยศพิเศษที่อยากได้ค๊าา", style=discord.TextStyle.paragraph, placeholder="เช่น หนูขอเข้าห้องลับกลุ่มนักพัฒนาหน่อยน้าาคนดี...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"📨 ส่งคำขอยศให้แล้วนะค๊าา! ข้อความของคุณ: {self.reason.value}", ephemeral=True)

class TextInputButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📝 ส่งคำขอยศพิเศษ (เขียนเหตุผลอ้อนแอดมิน)", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextInputModal())

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(guild))
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())


# --- 📊 NEW Poll UI System ---
class AskQuestionTextModal(discord.ui.Modal, title="✍️ รายละเอียดคำถามโพลแสนสนุก"):
    question = discord.ui.TextInput(label="หัวข้อคำถามโพลนี้คืออะไรเอ่ย?", style=discord.TextStyle.short, placeholder="เช่น เย็นนี้ไปกินชาบูกันไหมค๊าา?")
    choices_input = discord.ui.TextInput(
        label="ตัวเลือกคำตอบ (แยกด้วยเครื่องหมายจุลภาค , น้าา)", 
        style=discord.TextStyle.paragraph, 
        placeholder="เช่น ไปเซ่, ไม่ว่างง่ะ, ชวนคนอื่นเถอะ"
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value
        parsed_choices = [c.strip() for c in self.choices_input.value.split(",") if c.strip()]
        
        if len(parsed_choices) < 2:
            return await interaction.response.send_message("❗ โธ่.. ใส่ตัวเลือกให้น้อน Doro อย่างน้อย 2 ช้อยส์สิคะงับ (เช่น ช้อยส์1, ช้อยส์2)", ephemeral=True)
        if len(parsed_choices) > 25:
            return await interaction.response.send_message("❗ ช้อยส์เยอะเกินไปแล้วว หนูกลืนไม่เข้า! รองรับสูงสุด 25 ตัวเลือกน้าา", ephemeral=True)
            
        self.parent_view.poll_choices = parsed_choices
        await interaction.response.send_message(f"✏️ น้อน Doro จำคำถามและตัวเลือก ({len(parsed_choices)} ช้อยส์) ลงสมุดโน้ตชั่วคราวให้แล้วค่ะ!", ephemeral=True)

class OpenQuestionModalButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="✏️ กรอกคำถามและตัวเลือกโพล", style=discord.ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AskQuestionTextModal(self.parent_view))

class SubmitQuestionButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="🚀 ยืนยันปล่อยโพลเลยค๊าา", style=discord.ButtonStyle.success)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.submit_question(interaction)

class VoteSelect(discord.ui.Select):
    def __init__(self, choices, result_channel_id, all_choices_list):
        opts = [discord.SelectOption(label=opt[:100]) for opt in choices]
        super().__init__(placeholder="🗳️ กดตรงนี้เพื่อโหวตเลือกคำตอบที่คุณชอบเลยน้าา...", options=opts, min_values=1, max_values=1)
        self.result_channel_id = result_channel_id
        self.all_choices_list = all_choices_list  

    async def callback(self, interaction2: discord.Interaction):
        user = interaction2.user
        poll_msg_id = interaction2.message.id
        
        user_votes = vote_records.setdefault(poll_msg_id, {})
        user_votes[user.id] = self.values[0]

        guild = interaction2.guild
        
        summary = {ans: [] for ans in self.all_choices_list}
        for uid, ans in user_votes.items():
            member = guild.get_member(uid) if guild else None
            if member: 
                summary.setdefault(ans, []).append(member.display_name)
            else: 
                summary.setdefault(ans, []).append(f"<@{uid}>")

        summary_text = ""
        for ans in summary:
            voters = summary[ans]
            summary_text += f"**{ans}**: {len(voters)} คะแนนเสียงน้าา\n"
            if voters: summary_text += "   ↳ " + ", ".join(voters) + "\n"

        result_channel = guild.get_channel(self.result_channel_id) if guild else None
        
        if result_channel:
            embed_res = discord.Embed(
                title="📊 ผลโหวตเรียลไทม์ (น้อน Doro อัปเดตให้เรื่อย ๆ เยย)", 
                description=f"ผลสรุปของคำถาม: **{interaction2.message.embeds[0].fields[0].value if interaction2.message.embeds else 'โพล'}**\n\n{summary_text}", 
                color=0x87CEEB
            )
            
            res_msg_id = poll_result_messages.get(poll_msg_id)
            if res_msg_id:
                try:
                    old_msg = await result_channel.fetch_message(res_msg_id)
                    await old_msg.edit(embed=embed_res)
                except discord.NotFound:
                    new_res_msg = await result_channel.send(embed=embed_res)
                    poll_result_messages[poll_msg_id] = new_res_msg.id
            else:
                new_res_msg = await result_channel.send(embed=embed_res)
                poll_result_messages[poll_msg_id] = new_res_msg.id

        await interaction2.response.send_message(f"✅ น้อน Doro กาหัวใจและบันทึกคะแนนให้เรียบร้อยแล้วค่ะ!", ephemeral=True, delete_after=2)

class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = None
        self.poll_choices = []

        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        channel_options = [discord.SelectOption(label=f"#{ch.name}", value=str(ch.id)) for ch in channels[:25]]
        
        self.select_question_channel = discord.ui.Select(placeholder="📢 1. เลือกห้องที่จะให้น้อน Doro ไปปล่อยโพลค่ะ", options=channel_options)
        self.select_question_channel.callback = self.on_select_channel
        self.add_item(self.select_question_channel)

        self.select_result_channel = discord.ui.Select(placeholder="📊 2. เลือกห้องที่จะให้สรุปคะแนนโหวตโชว์ค่ะ", options=channel_options)
        self.select_result_channel.callback = self.on_select_channel
        self.add_item(self.select_result_channel)

        self.add_item(OpenQuestionModalButton(self))
        self.add_item(SubmitQuestionButton(self))

    async def on_select_channel(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()  
        except Exception:
            pass

    async def submit_question(self, interaction: discord.Interaction):
        if not self.question_text or not self.poll_choices:
            return await interaction.response.send_message("❗ งื้ออ อย่าเพิ่งใจร้อนสิคะ! กรอกคำถามและช้อยส์ผ่านปุ่มก่อนน้าา", ephemeral=True)
            
        q_ch_id = int(self.select_question_channel.values[0]) if self.select_question_channel.values else None
        r_ch_id = int(self.select_result_channel.values[0]) if self.select_result_channel.values else None

        if not (q_ch_id and r_ch_id):
            return await interaction.response.send_message("❗ ลืมเลือกห้องหรือเปล่าเอ่ย? เลือกห้องปล่อยคำถามกับห้องสรุปผลด้วยน้าา", ephemeral=True)

        q_channel = self.guild.get_channel(q_ch_id)
        
        embed = discord.Embed(title="📢 น้อน Doro ขอเชิญชวนทุกคนมาร่วมลงประชามติกันค๊าา~", color=discord.Color.pink())
        embed.add_field(name="❓ หัวข้อคำถามโพล", value=self.question_text, inline=False)
        
        choices_desc = "\n".join([f"🔹 {c}" for c in self.poll_choices])
        embed.add_field(name="📦 รายการตัวเลือก", value=choices_desc, inline=False)
        
        vote_view = discord.ui.View(timeout=None)
        vote_view.add_item(VoteSelect(self.poll_choices, r_ch_id, self.poll_choices))
        
        sent_msg = await q_channel.send(embed=embed, view=vote_view)
        vote_records[sent_msg.id] = {}
        
        await interaction.response.send_message(f"✅ บินไปปล่อยโพลเรียบร้อยแล้วที่ห้อง {q_channel.mention} น้าา ฟิ้วว~", ephemeral=True)
        self.question_text = None
        self.poll_choices = []


# --- Vote Kick UI System ---
class MemberSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 จิ้มเลือกคนที่ไม่น่ารักตรงนี้เลยงับ...", min_values=1, max_values=1)
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        target_member = self.values[0]
        
        if target_member.id == interaction.user.id:
            return await interaction.response.send_message("เอ๋.. จะโหวตเตะตัวเองทำไมค๊าาเนี่ยย น้อน Doro งงนะ! 😂❤️", ephemeral=True)
        if target_member.bot:
            return await interaction.response.send_message("บอทอย่างหนูและผองเพื่อนมีเกราะมนตราอมตะ โหวตเตะไม่ได้หรอกน้าา 🤖🛡️", ephemeral=True)

        member_obj = interaction.guild.get_member(target_member.id)
        if not member_obj:
            return await interaction.response.send_message("❌ งื้ออ ไม่เจอคนคนนี้ในเซิร์ฟเวอร์เลยค่ะ", ephemeral=True)

        online_members = [m for m in self.guild.members if m.status != discord.Status.offline and not m.bot]
        required_votes = max(2, len(online_members) // 2 + 1)

        view = VoteKickTypeView(member_obj, required_votes)
        
        embed = discord.Embed(
            title="🛠️ ตั้งค่าศาลเตี้ยประชามติโหวตลงทัณฑ์",
            description=f"เป้าหมาย: {member_obj.mention}\nโปรดกดเลือกบทลงโทษที่อยากให้น้อน Doro ลงมือทำด้านล่างนี้ได้เลยค่ะ!",
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class MemberSelectView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=60)
        self.add_item(MemberSelect(guild))

class KickTypeButton(discord.ui.Button):
    def __init__(self, target: discord.Member, kick_type: str, required_votes: int):
        label_str = "🔊 เตะบินออกจากห้องเสียง" if kick_type == "voice" else "💥 ดีดเปรี้ยงออกจากเซิร์ฟเวอร์"
        style = discord.ButtonStyle.primary if kick_type == "voice" else discord.ButtonStyle.danger
        super().__init__(label=label_str, style=style)
        self.target = target
        self.kick_type = kick_type
        self.required_votes = required_votes

    async def callback(self, interaction: discord.Interaction):
        view = VoteProgressView(self.target, self.kick_type, self.required_votes)
        embed = discord.Embed(
            title=f"🚨 เปิดวาระลงคะแนนโหวตขับไล่ขั้นเด็ดขาด!",
            description=f"เป้าหมาย: {self.target.mention}\nบทลงโทษ: **{self.label}**\nเกณฑ์คะแนนเสียงที่ต้องการ: **{self.required_votes}** โหวตจากคนตื่นอยู่",
            color=discord.Color.red()
        )
        embed.add_field(name="ตารางคะแนนในขณะนี้งับ", value=f"🟢 เห็นด้วย (Vote): 0/{self.required_votes}")
        
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

    @discord.ui.button(label="🟢 เห็นด้วย ลุยเยย! (Vote)", style=discord.ButtonStyle.success, emoji="👍")
    async def vote_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters:
            return await interaction.response.send_message("คุณใช้สิทธิ์ไปแล้วน้าา ห้ามกดซ้ำสิระคะ!", ephemeral=True)
        if interaction.user.id == self.target.id:
            return await interaction.response.send_message("จะกดเห็นด้วยเพื่อเตะตัวเองไม่ได้น้าาา ใจเย็น ๆ ก่อน! 🤣", ephemeral=True)

        self.voters.add(interaction.user.id)
        current_votes = len(self.voters)

        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="ตารางคะแนนในขณะนี้งับ", value=f"🟢 เห็นด้วย (Vote): {current_votes}/{self.required_votes}")

        if current_votes >= self.required_votes:
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)

            try:
                if self.kick_type == "voice":
                    if self.target.voice and self.target.voice.channel:
                        await self.target.move_to(None, reason="มติโหวตเห็นด้วยให้เตะแยกย้ายจากเสียง")
                        await interaction.channel.send(f"🔨 ปัง! มติเป็นเอกฉันท์ค๊าา น้อน Doro ตัดสายดึงปลั๊กย้าย {self.target.mention} ออกจากห้องเสียงเรียบร้อย!")
                    else:
                        await interaction.channel.send(f"⚠️ ผลโหวตชนะแล้วน้าา แต่เป้าหมาย {self.target.mention} แอบถอดหูฟังวิ่งหนีออกจากห้องเสียงไปก่อนแล้วง่ะ")
                elif self.kick_type == "server":
                    await self.target.kick(reason="ผลโหวตลงมติเตะออกจากเซิร์ฟเวอร์โดยผู้ใช้งาน")
                    await interaction.channel.send(f"💥 บูม! ประชามติเห็นพ้องต้องกัน น้อน Doro ดีดนิ้วธานอสส่ง {self.target.mention} ปลิวหายไปจากเซิร์ฟเวอร์แล้วค๊าา บ๊ายบายย~")
            except discord.Forbidden:
                await interaction.channel.send(f"❌ แงง ระบบไม่ทำงาน: ยศของหนูต่ำกว่าเป้าหมาย หรือหนูขาดสิทธิ์ดึงคน/เตะคน (คุณแอดมินช่วยเช็คลำดับสิทธิ์ยศให้หนูหน่อยน้าา)")
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
        if lower_msg == "doro เมนู":
            embed = discord.Embed(
                title="⚙️ Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก (UI Mode)",
                description="ยินดีต้อนรับสู่ดินแดนแห่งความน่ารักค๊าา! เลือกเมนูด้านล่างนี้เพื่อเปิดใช้งานฟังก์ชันรับยศ ส่งโพล หรือโหวตเตะได้ตามใจชอบเลยนะค๊าา ✨",
                color=0x3498DB
            )
            view = BotControlMenuView(message.guild)
            await message.channel.send(embed=embed, view=view)
            return

        if lower_msg == "doro โหวตเตะ":
            embed = discord.Embed(
                title="🚫 เริ่มวาระโหวตเตะสมาชิกคนไม่ดี (UI Mode)",
                description="โปรดเลือกรายชื่อสมาชิกที่คุณต้องการเริ่มโหวตลงมติเตะจากเมนูด้านล่างนี้ได้เลยค่ะงึมมม",
                color=discord.Color.red()
            )
            view = MemberSelectView(message.guild)
            await message.channel.send(embed=embed, view=view)
            return

        if lower_msg == "doro สมาชิกทั้งหมด":
            guild = message.guild
            if guild is None: return
            
            online = sum(1 for m in guild.members if m.status == discord.Status.online)
            idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
            dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
            offline = sum(1 for m in guild.members if m.status == discord.Status.offline)
            bots = sum(1 for m in guild.members if m.bot)
            
            embed = discord.Embed(
                title=f"📊 สรุปสถิติชาวประชากรในบ้าน [{guild.name}]",
                color=0x3498DB
            )
            embed.add_field(name="👥 สมาชิกทั้งหมดในบ้าน", value=f"**{guild.member_count}** ท่านค๊าา", inline=False)
            embed.add_field(name="🟢 ตื่นอยู่และพร้อมคุย", value=f"{online} คน", inline=True)
            embed.add_field(name="🌙 กำลังแอบอู้/ว่างอยู่", value=f"{idle} คน", inline=True)
            embed.add_field(name="🔴 ห้ามกวนเค้านะ", value=f"{dnd} คน", inline=True)
            embed.add_field(name="⚪ แอบไปนอนออฟไลน์", value=f"{offline} คน", inline=True)
            embed.add_field(name="🤖 เผ่าพันธุ์บอทเพื่อนหนู", value=f"{bots} ตัว", inline=True)
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            
            await message.channel.send(embed=embed)
            return

        if lower_msg == "doro เวลา":
            now = datetime.now(pytz.timezone('Asia/Bangkok'))
            await message.channel.send(f"🕒 นาฬิกาของน้อน Doro บอกว่าตอนนี้เวลา: {now.strftime('%Y-%m-%d %H:%M:%S')} แล้วค๊าา")
            return

        if lower_msg.startswith("doro ค้นหา"):
            search_term = msg[len("doro ค้นหา"):].strip()
            if not search_term: return
            results = VideosSearch(search_term, limit=1).result()
            if not results.get("result"): return
            await message.channel.send(f"🎵 น้อน Doro ไปงมคลิปนี้มาให้แล้วค๊าา: **{results['result'][0]['title']}**\n🔗 {results['result'][0]['link']}")
            return

        if lower_msg.startswith("doroส่งข้อความ") or lower_msg.startswith("doro ส่งข้อความ"):
            if not message.author.guild_permissions.administrator: return
            content = msg[len("doroส่งข้อความ" if lower_msg.startswith("doroส่งข้อความ") else "doro ส่งข้อความ"):].strip().split(maxsplit=1)
            if len(content) >= 2:
                ch = bot.get_channel(int(content[0]))
                if ch: await ch.send(f"@everyone {content[1]}")
            return

        if lower_msg.startswith("doroลบข้อความ") or lower_msg.startswith("doro ลบข้อความ"):
            if not message.author.guild_permissions.manage_messages: return
            count_str = msg[len("doroล้างข้อความ" if lower_msg.startswith("doroลบข้อความ") else "doro ลบข้อความ"):].strip()
            try:
                deleted = await message.channel.purge(limit=int(count_str) + 1)
                await message.channel.send(f"🧹 น้อน Doro กวาดบ้านและลบข้อความให้แล้วจำนวน {len(deleted)-1} ข้อความนะค๊าา ขยันสุด ๆ เยย!", delete_after=3)
            except Exception: pass
            return

        if lower_msg == "doro รีเซ็ตchannel":
            if not message.author.guild_permissions.manage_channels: return
            old_channel = message.channel
            new_channel = await old_channel.clone()
            await old_channel.delete()
            await new_channel.send("💣 บู๊มมม!! เสกเวทมนตร์รีเซ็ตห้องใหม่เอี่ยมอ่องเรียบร้อยแล้วค๊าา~ ✨", delete_after=3)
            return
            
        if lower_msg == "doro คำสั่งเพลง":
            embed = discord.Embed(title="🎧 เมนูดนตรีของน้อน Doro (!คำสั่ง)", description="**!join** (เรียกหนูเข้าห้อง) / **!leave** (ไล่หนูไปพัก) / **!play <ชื่อเพลง>** (เปิดเพลงคิ้วท์ ๆ) / **!skip** (ข้ามเพลงเบื่อ) / **!stop** (ปิดวิทยุ) / **!pause** (หยุดแป๊บ) / **!resume** (เล่นต่อเลย) / **!queue** (ส่องคิวเพลง) / **!nowplaying** (เพลงที่กำลังเต้นอยู่)", color=discord.Color.red())
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
    await ctx.send(f"✅ บินเข้าห้องเสียง: **{ch.name}** มาอยู่กับทุกคนแล้วค๊าา~")

@bot.command(name="leave")
async def leave_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc: 
        await vc.disconnect()
        await ctx.send("🏃‍♀️ หนูขอตัวไปพักกินขนมก่อนนะคะ บ๊ายบายค๊าา~")

@bot.command(name="play")
async def play_cmd(ctx, *, query: str = None):
    if not query or not ctx.author.voice: return
    guild_id = ctx.guild.id
    ensure_queue(guild_id)
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc is None: 
        await ctx.author.voice.channel.connect()
        vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    await ctx.send("🔎 น้อน Doro กำลังกางแว่นขยายค้นหาเพลงให้อยู่นะค๊าา แป๊บนึงน้าา...")
    info = await ytdl_extract(query)
    if info:
        track = {"title": info["title"], "url": info["url"], "requester": ctx.author.display_name}
        music_queues[guild_id].append(track)
        await ctx.send(f"✅ โยนใส่คิวเพลงให้แล้วค๊าา: **{track['title']}** ✨")
        if vc and not vc.is_playing() and not vc.is_paused():
            await play_next_in_queue(ctx.guild)

@bot.command(name="skip")
async def skip_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and (vc.is_playing() or vc.is_paused()): 
        vc.stop()
        await ctx.send("⏭️ เปลี่ยนเพลงฟิ้วว~ ข้ามเพลงเก่าไปเยยเจ้าค่ะ")

@bot.command(name="stop")
async def stop_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc:
        vc.stop()
        music_queues[ctx.guild.id] = []
        now_playing.pop(ctx.guild.id, None)
        await ctx.send("⏹️ ปิดวิทยุและล้างคิวเพลงเกลี้ยงตับแล้วค๊าา เงียบกริ๊บเยย~")

@bot.command(name="pause")
async def pause_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_playing(): 
        vc.pause()
        await ctx.send("⏸️ แช่แข็งเพลงไว้แป๊บนึงน้าา...")

@bot.command(name="resume")
async def resume_cmd(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_paused(): 
        vc.resume()
        await ctx.send("▶️ เล่นเพลงต่อความมันส์กันเลยค๊าา ลุยย!")

@bot.command(name="queue")
async def queue_cmd(ctx):
    q = music_queues.get(ctx.guild.id, [])
    if not q: return await ctx.send("🎶 ฮืออ คิวว่างเปล่าไม่มีเพลงเยยเหรอคะ มาเปิดเพลงกันเถอะ")
    lines = [f"{i+1}. {t['title']}" for i, t in enumerate(q)]
    await ctx.send("📋 **รายการคิวเพลงแสนสนุก:**\n" + "\n".join(lines[:10]))

@bot.command(name="nowplaying")
async def nowplaying_cmd(ctx):
    t = now_playing.get(ctx.guild.id)
    if t: await ctx.send(f"🎵 น้อน Doro กำลังบรรเลงเพลงนี้อยู่ค๊าา: **{t['title']}** 💃✨")

if __name__ == "__main__":
    try: server_on()
    except Exception: pass
    bot.run(DISCORD_TOKEN)
