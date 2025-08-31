import os
import random
import asyncio
import discord
import yt_dlp
import pytz

from dotenv import load_dotenv
from datetime import datetime
from discord.ext import commands
from youtubesearchpython import VideosSearch
from myserver import server_on


# โหลดค่า Token
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ====================== Custom Responses ======================
custom_responses = {
    "bot ชื่ออะไร": "ผมชื่อ doro ค่ะ 🤖",
    "doro ช่วยอะไรได้บ้าง": "ฉันตอบคำถามทั่วไป และเปิดเพลงให้คุณได้ด้วยนะ!",
    "doro สวัสดี": "สวัสดีค่ะ ยินดีที่ได้คุยด้วยนะ!",
}

user_contexts = {}
queue = {}

# ====================== Role Options ======================
ROLE_OPTIONS = [
    {"label": "จักพรรดิสวรรค์", "value": "จักพรรดิสวรรค์", "emoji": "🌸"},
    {"label": "ผู้คุมกฎ", "value": "ผู้คุมกฎ", "emoji": "✍️"},
    {"label": "สวรรค์และโลก", "value": "สวรรค์และโลก", "emoji": "🟧"},
    {"label": "เซียน", "value": "เซียน", "emoji": "🪛"},
]


# ====================== Role System ======================
class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=r["label"], value=r["value"], emoji=r["emoji"]
            )
            for r in ROLE_OPTIONS
        ]
        super().__init__(
            placeholder="เลือกยศของคุณ (เลือกได้หลายยศ)",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_roles = self.values
        guild_roles = interaction.guild.roles

        selected_role_objs = [
            discord.utils.get(guild_roles, name=role_name)
            for role_name in selected_roles
            if discord.utils.get(guild_roles, name=role_name)
        ]

        roles_to_remove = [
            discord.utils.get(guild_roles, name=r["value"])
            for r in ROLE_OPTIONS
            if discord.utils.get(guild_roles, name=r["value"])
            in interaction.user.roles
            and r["value"] not in selected_roles
        ]

        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)

            if selected_role_objs:
                await interaction.user.add_roles(*selected_role_objs)

            await interaction.response.send_message(
                "✅ ยศของคุณถูกอัปเดตเรียบร้อยแล้ว", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ บอทไม่มีสิทธิ์จัดการยศ", ephemeral=True
            )


class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="ลบยศทั้งหมด",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
        )

    async def callback(self, interaction: discord.Interaction):
        roles_to_remove = [
            discord.utils.get(interaction.guild.roles, name=r["value"])
            for r in ROLE_OPTIONS
            if discord.utils.get(interaction.guild.roles, name=r["value"])
            in interaction.user.roles
        ]
        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)

            await interaction.response.send_message(
                "🧹 ยศของคุณถูกลบทั้งหมดแล้ว", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ บอทไม่มีสิทธิ์ลบยศ", ephemeral=True
            )


class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())
        self.add_item(RemoveRolesButton())


class RequestRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ขอยศด้วยปุ่ม", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("คุณกดปุ่มขอยศแล้ว!", ephemeral=True)


class TextInputModal(discord.ui.Modal, title="กรอกเหตุผลขอยศ"):
    reason = discord.ui.TextInput(
        label="กรุณาใส่เหตุผลที่ต้องการขอยศ", style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"ขอบคุณสำหรับเหตุผล: {self.reason}", ephemeral=True
        )


class TextInputButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="กรอกเหตุผลขอยศ", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        modal = TextInputModal()
        await interaction.response.send_modal(modal)


class RequestRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())
        self.add_item(RequestRoleButton())
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())


# ====================== Question System ======================
QUESTION_CHOICES = {
    "เอา / ไม่เอา / ไม่แน่ใจ": ["เอา", "ไม่เอา", "ไม่แน่ใจ"],
    "เล่น / ไม่เล่น": ["เล่น", "ไม่เล่น"],
    "ใช่ / ไม่ใช่": ["ใช่", "ไม่ใช่"],
}

vote_records = {}


# ====================== Event: on_message ======================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name
    msg = message.content.strip()
    lower_msg = msg.lower()

    # === ระบบถามคำถาม ===
    if lower_msg.startswith("doro ถาม"):
        view = AskQuestionView(message.guild)
        await message.reply("📋 กดปุ่มด้านล่างเพื่อสร้างคำถาม", view=view)
        return

    # === ระบบขอยศ ===
    if lower_msg == "doro ขอยศ":
        embed = discord.Embed(
            title="ขอยศ",
            description="นายเลือกยศจากเมนูด้านล่าง หรือกดปุ่มเพื่อกรอกเหตุผลขอยศนี้ได้นะ",
            color=0xFFB6C1,
        )
        view = RequestRoleView()
        await message.channel.send(embed=embed, view=view)
        return

    # === เวลา ===
    if lower_msg == "doro เวลา":
        now = datetime.now(pytz.timezone("Asia/Bangkok"))
        await message.channel.send(
            f"🕒 เวลาปัจจุบัน: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return

    # === สมาชิกทั้งหมด ===
    if lower_msg == "doro สมาชิกทั้งหมด":
        guild = message.guild
        if guild is None:
            await message.channel.send("❌ คำสั่งนี้ใช้ได้ในเซิร์ฟเวอร์เท่านั้น")
            return

        members = guild.members
        total = guild.member_count
        lines = [f"{m.display_name} - {str(m.status)}" for m in members]

        for i in range(0, len(lines), 20):
            chunk = lines[i : i + 20]
            await message.channel.send(
                f"👥 สมาชิกทั้งหมด ({total} คน):\n" + "\n".join(chunk)
            )
        return

    # === คำสั่ง ===
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
                "**🔹 doro ถาม **\n"
                "**🔹 doro ข้อยศ (เมนูเลือกยศ)**\n"
                "**🔹 !join / !play / !skip / !stop / !queue**"
            ),
            color=discord.Color.magenta(),
        )
        await message.channel.send(embed=embed)
        return

    # === ตอบ custom responses ===
    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
        return

    # === จัดการ context ของผู้ใช้ ===
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    user_contexts[user_id].append((user_id, username, msg))
    if len(user_contexts[user_id]) > 5:
        user_contexts[user_id].pop(0)

    # === ตรวจสอบ command ที่ขึ้นต้นด้วย ! ===
    if msg.startswith("!"):
        await bot.process_commands(message)


# ====================== Run Server & Bot ======================
server_on()
bot.run(DISCORD_TOKEN)
