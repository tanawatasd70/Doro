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
audio_lock = asyncio.Lock()

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
    """Return dict with title and url for audio stream (not webpage)."""
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
    if not voice_client:
        return
    if voice_client.is_playing() or voice_client.is_paused():
        return
    if not queue:
        now_playing.pop(guild_id, None)
        return
    track = queue.pop(0)
    now_playing[guild_id] = track
    source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
    def after_play(error):
        if error:
            logger.error(f"Error while playing: {error}")
        fut = asyncio.run_coroutine_threadsafe(play_next_in_queue(guild), bot.loop)
        try:
            fut.result()
        except Exception as e:
            logger.exception("Error scheduling next track")

    voice_client.play(source, after=after_play)

def disable_all_items(view: discord.ui.View):
    for item in view.children:
        item.disabled = True

# === Dynamic Role System (Patched) ===
class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [
            r for r in guild.roles
            if r.name != "@everyone" and not r.managed
        ]
        options = [
            discord.SelectOption(label=r.name, value=str(r.id))
            for r in roles[:25]  # Discord กำหนดให้มีเมนู Select สูงสุดได้ 25 ตัวเลือก
        ]
        super().__init__(
            placeholder="เลือกยศของคุณ",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.values[0]))
        if role is None:
            return await interaction.response.send_message("ไม่พบยศนี้ในเซิร์ฟเวอร์", ephemeral=True)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ ได้รับยศ **{role.name}** เรียบร้อยแล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์ให้ยศนี้ (โปรดตรวจสอบสิทธิ์ Manage Roles และลำดับความสูงของยศบอท)", ephemeral=True)

class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศทั้งหมด", style=discord.ButtonStyle.danger, emoji="🗑️")

    async def callback(self, interaction: discord.Interaction):
        # ดึงยศทั้งหมดของเซิร์ฟเวอร์ที่ไม่ใช่ยศระบบ เพื่อนำมาเช็คและลบออกจากตัวผู้ใช้
        roles_to_remove = [
            r for r in interaction.user.roles
            if r.name != "@everyone" and not r.managed
        ]
        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)
            await interaction.response.send_message("🧹 ยศทั่วไปของคุณถูกลบทั้งหมดแล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์ลบยศ", ephemeral=True)

class RequestRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ขอยศด้วยปุ่ม", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("คุณกดปุ่มขอยศแล้ว!", ephemeral=True)

class TextInputModal(discord.ui.Modal, title="กรอกเหตุผลขอยศ"):
    reason = discord.ui.TextInput(label="กรุณาใส่เหตุผลที่ต้องการขอยศ", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"ขอบคุณสำหรับเหตุผล: {self.reason}", ephemeral=True)

class TextInputButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="กรอกเหตุผลขอยศ", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        modal = TextInputModal()
        await interaction.response.send_modal(modal)

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(guild))
        self.add_item(RequestRoleButton())
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())

# --- Poll UI ---
class AskQuestionTextModal(discord.ui.Modal, title="กรอกคำถาม"):
    question = discord.ui.TextInput(label="คำถามของคุณ", style=discord.TextStyle.paragraph)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value
        await interaction.response.send_message("✏️ บันทึกคำถามเรียบร้อยแล้ว", ephemeral=True)

class OpenQuestionModalButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="📝 กรอกคำถาม", style=discord.ButtonStyle.primary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        modal = AskQuestionTextModal(self.parent_view)
        await interaction.response.send_modal(modal)

class SubmitQuestionButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="✅ ยืนยันส่งคำถาม", style=discord.ButtonStyle.success)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.submit_question(interaction)

class VoteSelect(discord.ui.Select):
    def __init__(self, choices, result_channel_id):
        opts = [discord.SelectOption(label=opt) for opt in choices]
        super().__init__(placeholder="โปรดเลือกคำตอบของคุณ", options=opts, min_values=1, max_values=1)
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
            if parts:
                choice_set_name = parts[0]

        choices = QUESTION_CHOICES.get(choice_set_name, [])
        guild = interaction2.guild

        summary = {ans: [] for ans in choices}
        for uid, ans in user_votes.items():
            member = guild.get_member(uid) if guild else None
            if member:
                summary.setdefault(ans, []).append(member.display_name)
            else:
                summary.setdefault(ans, []).append(f"<@{uid}>")

        summary_text = ""
        for ans in summary:
            voters = summary[ans]
            summary_text += f"**{ans}**: {len(voters)} โหวต\n"
            if voters:
                summary_text += ", ".join(voters) + "\n"

        result_channel = guild.get_channel(self.result_channel_id) if guild else None
        if result_channel:
            await result_channel.send(
                embed=discord.Embed(
                    title="📊 ผลโหวตล่าสุด",
                    description=summary_text,
                    color=0x87CEEB
                )
            )
        await interaction2.response.send_message(f"คุณเลือก: {self.values[0]}", ephemeral=True)

class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = None

        self.select_choices = discord.ui.Select(
            placeholder="เลือกชุดคำตอบ",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=key, value=key) for key in QUESTION_CHOICES.keys()],
            custom_id="select_choices"
        )
        self.add_item(self.select_choices)

        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        channel_options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in channels[:25]]
        self.select_question_channel = discord.ui.Select(
            placeholder="📢 เลือกห้องส่งคำถาม",
            options=channel_options,
            custom_id="select_question_channel"
        )
        self.add_item(self.select_question_channel)

        self.select_result_channel = discord.ui.Select(
            placeholder="📊 เลือกห้องสรุปผล",
            options=channel_options,
            custom_id="select_result_channel"
        )
        self.add_item(self.select_result_channel)

        self.add_item(OpenQuestionModalButton(self))
        self.add_item(SubmitQuestionButton(self))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logger.exception("Interaction error", exc_info=error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("เกิดข้อผิดพลาดขึ้น! โปรดลองอีกครั้งในภายหลัง", ephemeral=True)
            else:
                await interaction.followup.send("เกิดข้อผิดพลาดขึ้น! โปรดลองอีกครั้งในภายหลัง", ephemeral=True)
        except Exception:
            pass

    async def submit_question(self, interaction: discord.Interaction):
        if not self.question_text:
            await interaction.response.send_message("❗ กรุณากรอกคำถามก่อนผ่านปุ่ม 'กรอกคำถาม'", ephemeral=True)
            return

        choice_set_name = self.select_choices.values[0] if self.select_choices.values else None
        question_channel_id = int(self.select_question_channel.values[0]) if self.select_question_channel.values else None
        result_channel_id = int(self.select_result_channel.values[0]) if self.select_result_channel.values else None

        guild = self.guild
        question_channel = guild.get_channel(question_channel_id) if question_channel_id else None
        result_channel = guild.get_channel(result_channel_id) if result_channel_id else None

        if not (choice_set_name and question_channel and result_channel):
            await interaction.response.send_message("❗ กรุณาเลือกชุดคำตอบ ช่องส่งคำถาม และช่องสรุปผลโหวตก่อน", ephemeral=True)
            return

        choices = QUESTION_CHOICES.get(choice_set_name)
        if not choices:
            await interaction.response.send_message("❌ ชุดคำตอบไม่ถูกต้อง", ephemeral=True)
            return

        embed = discord.Embed(
            title="📢 คำถามสำหรับทุกคน",
            description=f"{choice_set_name}\n{self.question_text}",
            color=discord.Color.pink()
        )

        vote_view = discord.ui.View()
        vote_view.add_item(VoteSelect(choices, result_channel_id))
        sent_msg = await question_channel.send(embed=embed, view=vote_view)
        vote_records[sent_msg.id] = {}

        await interaction.response.send_message(f"✅ ส่งคำถามไปที่ {question_channel.mention} เรียบร้อยแล้ว\nสรุปผลโหวตที่ช่อง {result_channel.mention}", ephemeral=True)
        self.question_text = None

# --- Events & Message Handling ---
@bot.event
async def on_ready():
    logger.info(f"Doro ready as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name
    msg = message.content.strip()
    lower_msg = msg.lower()

    user_contexts.setdefault(user_id, []).append((user_id, username, msg))
    if len(user_contexts[user_id]) > 5:
        user_contexts[user_id].pop(0)

    try:
        if lower_msg == "doro ขอยศ":
            embed = discord.Embed(
                title="ขอยศ",
                description="นายเลือกยศจากเมนูด้านล่าง หรือกดปุ่มเพื่อกรอกเหตุผลขอยศนี้ได้นะ",
                color=0xFFB6C1
            )
            view = RequestRoleView(message.guild)
            await message.channel.send(embed=embed, view=view)
            return

        if lower_msg.startswith("doro ถาม"):
            view = AskQuestionView(message.guild)
            await message.reply("📋 กดปุ่มด้านล่างเพื่อสร้างคำถาม", view=view)
            return

        if lower_msg == "doro เวลา":
            now = datetime.now(pytz.timezone('Asia/Bangkok'))
            await message.channel.send(f"🕒 เวลาปัจจุบัน: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            return

        if lower_msg == "doro สมาชิกทั้งหมด":
            guild = message.guild
            if guild is None:
                await message.channel.send("❌ คำสั่งนี้ใช้ได้ในเซิร์ฟเวอร์เท่านั้น")
                return
            members = guild.members
            total = guild.member_count
            lines = [f"{m.display_name} - {str(m.status)}" for m in members]
            for i in range(0, len(lines), 20):
                chunk = lines[i:i+20]
                await message.channel.send(f"👥 สมาชิกทั้งหมด ({total} คน):\n" + "\n".join(chunk))
            return

        if lower_msg.startswith("doro ค้นหา"):
            search_term = msg[len("doro ค้นหา"):].strip()
            if not search_term:
                await message.channel.send("❗ โปรดระบุชื่อคลิปที่ต้องการค้นหา")
                return
            results = VideosSearch(search_term, limit=1).result()
            if not results.get("result"):
                await message.channel.send("❌ ไม่พบคลิปที่ค้นหา")
                return
            info = results["result"][0]
            await message.channel.send(f"🎵 พบคลิป: **{info['title']}**\n🔗 {info['link']}")
            return

        if lower_msg.startswith("doroส่งข้อความ") or lower_msg.startswith("doro ส่งข้อความ"):
            if not message.author.guild_permissions.administrator:
                await message.channel.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้")
                return
            if lower_msg.startswith("doroส่งข้อความ"):
                content = msg[len("doroส่งข้อความ"):].strip()
            else:
                content = msg[len("doro ส่งข้อความ"):].strip()
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send("❗ รูปแบบที่ถูกต้อง: doroส่งข้อความ <channel_id> <ข้อความ>")
                return
            try:
                channel_id = int(parts[0])
                text = parts[1]
                channel = bot.get_channel(channel_id)
                if channel is None:
                    await message.channel.send("❌ ไม่พบช่อง ID นั้นนะ")
                    return
                await channel.send(f"@everyone {text}")
                await message.channel.send(f"✅ ทำการส่งข้อความไปที่ {channel.name} เรียบร้อยแล้ว")
            except Exception as e:
                await message.channel.send(f"⚠️ เกิดข้อผิดพลาด: {e}")
            return

        if lower_msg.startswith("doroล้างข้อความ") or lower_msg.startswith("doro ล้างข้อความ"):
            if not message.author.guild_permissions.manage_messages:
                await message.channel.send("❌ คุณไม่มีสิทธิ์จัดการข้อความนี้นะ")
                return
            if lower_msg.startswith("doroล้างข้อความ"):
                count_str = lower_msg[len("doroล้างข้อความ"):].strip()
            else:
                count_str = lower_msg[len("doro ล้างข้อความ"):].strip()
            try:
                count = int(count_str)
                deleted = await message.channel.purge(limit=count + 1)
                await message.channel.send(f"🧹 อืม...ลบข้อความจำนวน {len(deleted)-1} ข้อความแล้ว", delete_after=3)
            except Exception as e:
                await message.channel.send(f"⚠️ อะไรกันลบไม่สำเร็จ: {e}")
            return

        if lower_msg == "doro รีเซ็ตchannel":
            if not message.author.guild_permissions.manage_channels:
                await message.channel.send("❌ นายไม่มีสิทธิ์จัดการช่องนี้นะเจ้าบื่อ")
                return
            try:
                old_channel = message.channel
                new_channel = await old_channel.clone(reason="ทำการรีเซ็ตห้องใหม่แล้วอิๆ")
                await old_channel.delete()
                await new_channel.send("💣 ห้องนี้ถูกระเบิดเป็นจุนไปแล้ว ฮ่าฮ่าๆ!")
            except Exception as e:
                await message.channel.send(f"⚠️ อะไรกันเกิดอะไรขึ้น: {e}")
            return

        if lower_msg == "doro คำสั่ง":
            embed = discord.Embed(
                title="📘 คำสั่งของ Doro 🤖",
                description=(
                    "**🔹 bot ชื่ออะไร**\n"
                    "**🔹 doro ช่วยอะไรได้บ้าง**\n"
                    "**🔹 doro สวัสดี**\n"
                    "**🔹 doro ค้นหา <ชื่อคลิป>**\n"
                    "**🔹 doro สมาชิกทั้งหมด**\n"
                    "**🔹 doro เวลา**\n"
                    "**🔹 doroส่งข้อความ <channel_id> <ข้อความ>**\n"
                    "**🔹 doro ล้างข้อความ<จำนวน>**\n"
                    "**🔹 doro รีเซ็ตchannel**\n"
                    "**🔹 doro ถาม**\n"
                    "**🔹 doro ขอยศ (เมนูเลือกยศ)**\n"
                    "**🔹 doro คำสั่งเพลง**\n"
                    "**🔹 !join / !play / !skip / !stop / !queue**"
                ),
                color=discord.Color.magenta()
            )
            await message.channel.send(embed=embed)
            return

        if lower_msg == "doro คำสั่งเพลง":
            embed = discord.Embed(
                title="🎧 คำสั่งที่ใช้ในการควบคุมบอทเพลง",
                description=(
                    "**!join**\t: ให้บอทเข้าห้องเสียงของคุณ\n"
                    "**!leave**\t: ให้บอทออกจากห้องเสียง\n"
                    "**!volume** <0-100>\t: ปรับระดับเสียง\n"
                    "**!remove** <หมายเลขคิว>\t: ลบเพลงจากคิว\n"
                    "**!clear**\t: ล้างคิวเพลงทั้งหมด\n"
                    "**!play** <ชื่อเพลง/URL>\t: เล่นเพลงจาก YouTube\n"
                    "**!skip**\t: ข้ามเพลงปัจจุบัน\n"
                    "**!pause**\t: หยุดชั่วคราว\n"
                    "**!resume**\t: เล่นต่อจากที่หยุด\n"
                    "**!stop**\t: หยุดเล่นทั้งหมดและล้างคิว\n"
                    "**!queue**\t: แสดงรายการเพลงในคิว\n"
                    "**!nowplaying**\t: แสดงเพลงที่กำลังเล่น\n"
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        if lower_msg in custom_responses:
            await message.channel.send(custom_responses[lower_msg])
            return

    except Exception:
        logger.exception("Error while handling text triggers")

    await bot.process_commands(message)

# --- Music commands (commands.Bot style) ---
@bot.command(name="join")
async def join_cmd(ctx: commands.Context):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("❌ คุณต้องอยู่ในห้องเสียงก่อนที่จะให้บอทเข้าร่วมห้อง")
        return
    channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    try:
        if voice_client is None:
            await channel.connect()
        else:
            await voice_client.move_to(channel)
        await ctx.send(f"✅ เข้าห้อง: **{channel.name}**")
    except Exception as e:
        await ctx.send(f"❌ ไม่สามารถเข้าห้องได้: {e}")

@bot.command(name="leave")
async def leave_cmd(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("👋 ออกจากห้องเสียงเรียบร้อยแล้ว")
    else:
        await ctx.send("❌ บอทไม่ได้อยู่ในห้องเสียง")

@bot.command(name="play")
async def play_cmd(ctx: commands.Context, *, query: str = None):
    if query is None:
        await ctx.send("❗ กรุณาระบุชื่อเพลงหรือ URL")
        return
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("❌ คุณต้องอยู่ในห้องเสียงเพื่อสั่งเล่นเพลง")
        return
    guild_id = ctx.guild.id
    ensure_queue(guild_id)
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client is None or not voice_client.is_connected():
        try:
            await ctx.author.voice.channel.connect()
            voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        except Exception as e:
            await ctx.send(f"❌ ไม่สามารถเชื่อมต่อห้องเสียง: {e}")
            return

    await ctx.send("🔎 กำลังค้นหาเพลง...")
    info = await ytdl_extract(query)
    if not info:
        await ctx.send("❌ ไม่พบเพลงหรือเกิดข้อผิดพลาดขณะค้นหา")
        return

    track = {"title": info["title"], "url": info["url"], "webpage_url": info.get("webpage_url"), "requester": ctx.author.display_name}
    music_queues[guild_id].append(track)
    await ctx.send(f"✅ เพิ่มเพลง **{track['title']}** ลงในคิว โดย {track['requester']}")

    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and not voice_client.is_playing() and not voice_client.is_paused():
        await play_next_in_queue(ctx.guild)

@bot.command(name="skip")
async def skip_cmd(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not (voice_client.is_playing() or voice_client.is_paused()):
        await ctx.send("❌ ไม่มีเพลงกำลังเล่น")
        return
    voice_client.stop()
    await ctx.send("⏭️ ข้ามเพลงเรียบร้อยแล้ว")

@bot.command(name="stop")
async def stop_cmd(ctx: commands.Context):
    guild_id = ctx.guild.id
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        voice_client.stop()
        music_queues[guild_id] = []
        now_playing.pop(guild_id, None)
        await ctx.send("⏹️ หยุดเล่นและล้างคิวเรียบร้อยแล้ว")
    else:
        await ctx.send("❌ บอทไม่ได้อยู่ในห้องเสียง")

@bot.command(name="pause")
async def pause_cmd(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ หยุดชั่วคราว")
    else:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่น")

@bot.command(name="resume")
async def resume_cmd(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ เล่นต่อแล้ว")
    else:
        await ctx.send("❌ ไม่มีเพลงที่ถูกหยุดไว้")

@bot.command(name="queue")
async def queue_cmd(ctx: commands.Context):
    guild_id = ctx.guild.id
    ensure_queue(guild_id)
    q = music_queues[guild_id]
    if not q:
        await ctx.send("🎶 คิวว่างอยู่")
        return
    lines = [f"{i+1}. {t['title']} - โดย {t.get('requester','ไม่ทราบ')}" for i, t in enumerate(q)]
    for i in range(0, len(lines), 10):
        await ctx.send("\n".join(lines[i:i+10]))

@bot.command(name="nowplaying")
async def nowplaying_cmd(ctx: commands.Context):
    track = now_playing.get(ctx.guild.id)
    if not track:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่นตอนนี้")
        return
    await ctx.send(f"🎵 กำลังเล่น: **{track['title']}** - ขอโดย {track.get('requester','ไม่ทราบ')}")

@bot.command(name="volume")
@commands.has_permissions(manage_guild=True)
async def volume_cmd(ctx: commands.Context, vol: int):
    if vol < 0 or vol > 100:
        await ctx.send("❗ โปรดระบุค่า volume 0-100")
        return
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.source:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่น")
        return
    await ctx.send("⚠️ ปรับเสียงแบบละเอียดยังไม่รองรับในระบบนี้ (ต้องใช้ PCMVolumeTransformer).")

if __name__ == "__main__":
    try:
        server_on()
    except Exception:
        logger.exception("Error starting server_on() (may be fine if not needed)")
    bot.run(DISCORD_TOKEN)
