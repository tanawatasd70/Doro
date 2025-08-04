import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
from youtubesearchpython import VideosSearch
import yt_dlp
import os
import asyncio
from datetime import datetime
import pytz
from myserver import server_on

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

custom_responses = {
    "bot ชื่ออะไร": "ผมชื่อ doro ค่ะ 🤖",
    "doro ช่วยอะไรได้บ้าง": "ฉันตอบคำถามทั่วไป และเปิดเพลงให้คุณได้ด้วยนะ!",
    "doro สวัสดี": "สวัสดีค่ะ ยินดีที่ได้คุยด้วยนะ!",
}

user_contexts = {}
queue = {}

ROLE_OPTIONS = [
    {"label": "จักพรรดิสวรรค์", "value": "จักพรรดิสวรรค์", "emoji": "🌸"},
    {"label": "ผู้คุมกฎ", "value": "ผู้คุมกฎ", "emoji": "✍️"},
    {"label": "สวรรค์และโลก", "value": "สวรรค์และโลก", "emoji": "🟧"},
    {"label": "เซียน", "value": "เซียน", "emoji": "🪛"},
]

# Role classes

class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=r["label"], value=r["value"], emoji=r["emoji"])
            for r in ROLE_OPTIONS
        ]
        super().__init__(placeholder="เลือกยศของคุณ (เลือกได้หลายยศ)", min_values=1, max_values=len(options), options=options)

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
            if discord.utils.get(guild_roles, name=r["value"]) in interaction.user.roles
            and r["value"] not in selected_roles
        ]
        try:
            await interaction.user.remove_roles(*roles_to_remove)
            await interaction.user.add_roles(*selected_role_objs)
            await interaction.response.send_message("✅ ยศของคุณถูกอัปเดตเรียบร้อยแล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์จัดการยศ", ephemeral=True)

class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศทั้งหมด", style=discord.ButtonStyle.danger, emoji="🗑️")

    async def callback(self, interaction: discord.Interaction):
        roles_to_remove = [
            discord.utils.get(interaction.guild.roles, name=r["value"])
            for r in ROLE_OPTIONS
            if discord.utils.get(interaction.guild.roles, name=r["value"]) in interaction.user.roles
        ]
        try:
            await interaction.user.remove_roles(*roles_to_remove)
            await interaction.response.send_message("🧹 ยศของคุณถูกลบทั้งหมดแล้ว", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ บอทไม่มีสิทธิ์ลบยศ", ephemeral=True)

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
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())  # เมนูเลือกยศ (เลือกหลายยศได้)
        self.add_item(RequestRoleButton())
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())


QUESTION_CHOICES = {
    "เอา / ไม่เอา / ไม่แน่ใจ": ["เอา", "ไม่เอา", "ไม่แน่ใจ"],
    "เล่น / ไม่เล่น": ["เล่น", "ไม่เล่น"],
    "ใช่ / ไม่ใช่": ["ใช่", "ไม่ใช่"],
}

# เก็บโหวต: message_id -> { user_id: answer, ... }
vote_records = {}

class AskQuestionModal(discord.ui.Modal, title="กรอกคำถาม"):
    question = discord.ui.TextInput(label="คำถามของคุณ", style=discord.TextStyle.paragraph)

    def __init__(self, choice_set_name, question_channel_id, result_channel_id):
        super().__init__()
        self.choice_set_name = choice_set_name
        self.question_channel_id = question_channel_id
        self.result_channel_id = result_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        question_channel = guild.get_channel(self.question_channel_id)
        result_channel = guild.get_channel(self.result_channel_id)

        if question_channel is None or result_channel is None:
            await interaction.response.send_message("❌ ไม่พบช่องเป้าหมายหรือช่องผลโหวต", ephemeral=True)
            return

        choices = QUESTION_CHOICES.get(self.choice_set_name)
        if not choices:
            await interaction.response.send_message("❌ ชุดคำตอบไม่ถูกต้อง", ephemeral=True)
            return

        embed = discord.Embed(
            title="📢 คำถามจากผู้ดูแล",
            description=self.question.value,
            color=0xFFB6C1
        )
        embed.set_footer(text=f"เลือกตอบโดยใช้เมนูด้านล่าง | ชุดคำตอบ: {self.choice_set_name}")

        class AnswerSelect(discord.ui.Select):
            def __init__(self):
                opts = [discord.SelectOption(label=opt) for opt in choices]
                super().__init__(placeholder="โปรดเลือกคำตอบของคุณ", options=opts, min_values=1, max_values=1)

            async def callback(self, interaction2: discord.Interaction):
                user = interaction2.user
                msg_id = interaction2.message.id
                user_votes = vote_records.setdefault(msg_id, {})
                user_votes[user.id] = self.values[0]

                # สรุปผลโหวต
                summary = {}
                for ans in choices:
                    summary[ans] = []

                for uid, ans in user_votes.items():
                    member = guild.get_member(uid)
                    if member:
                        summary[ans].append(member.display_name)

                # สร้างข้อความสรุป
                summary_text = ""
                for ans in choices:
                    voters = summary[ans]
                    summary_text += f"**{ans}**: {len(voters)} โหวต\n"
                    if voters:
                        summary_text += ", ".join(voters) + "\n"

                # ส่งสรุปไปช่องผลโหวต
                await result_channel.send(
                    embed=discord.Embed(
                        title="📊 ผลโหวตล่าสุด",
                        description=summary_text,
                        color=0x87CEEB
                    )
                )

                await interaction2.response.send_message(f"คุณเลือก: {self.values[0]}", ephemeral=True)

        view = discord.ui.View()
        view.add_item(AnswerSelect())

        sent_msg = await question_channel.send(embed=embed, view=view)
        vote_records[sent_msg.id] = {}  # เตรียมเก็บโหวต

        await interaction.response.send_message(f"ส่งคำถามไปที่ช่อง {question_channel.mention} เรียบร้อยแล้ว\nสรุปผลโหวตที่ช่อง {result_channel.mention}", ephemeral=True)


def disable_all_items(view: discord.ui.View):
    for item in view.children:
        item.disabled = True


class AskQuestionView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        self.guild = guild

        # Dropdown เลือกชุดคำตอบ
        options = [discord.SelectOption(label=name, value=name) for name in QUESTION_CHOICES.keys()]
        self.select_choices = discord.ui.Select(placeholder="เลือกชุดคำตอบ", options=options)
        self.add_item(self.select_choices)

        # Dropdown เลือกช่องที่จะส่งคำถาม
        channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        channel_options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in channels]
        self.select_question_channel = discord.ui.Select(placeholder="เลือกช่องที่จะส่งคำถาม", options=channel_options)
        self.add_item(self.select_question_channel)

        # Dropdown เลือกช่องที่จะสรุปผลโหวต
        self.select_result_channel = discord.ui.Select(placeholder="เลือกช่องสำหรับสรุปผลโหวต", options=channel_options)
        self.add_item(self.select_result_channel)

        # ปุ่มเปิด modal กรอกคำถาม
        self.add_item(discord.ui.Button(label="กรอกคำถาม", style=discord.ButtonStyle.primary, custom_id="open_question_modal"))

        # ปุ่มยืนยันส่งคำถาม
        self.add_item(discord.ui.Button(label="ยืนยันส่งคำถาม", style=discord.ButtonStyle.success, custom_id="submit_question"))

    @discord.ui.button(label="ปุ่มสำรอง", style=discord.ButtonStyle.secondary, custom_id="dummy_button")
    async def dummy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass  # ไม่ได้ใช้จริง

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data.get("custom_id")

        if custom_id == "open_question_modal":
            # เปิด modal ให้กรอกคำถาม
            choice_set_name = self.select_choices.values[0] if self.select_choices.values else None
            question_channel_id = int(self.select_question_channel.values[0]) if self.select_question_channel.values else None
            result_channel_id = int(self.select_result_channel.values[0]) if self.select_result_channel.values else None

            if not choice_set_name or not question_channel_id or not result_channel_id:
                await interaction.response.send_message("❗ กรุณาเลือกชุดคำตอบ ช่องส่งคำถาม และช่องสรุปผลโหวตก่อน", ephemeral=True)
                return False

            modal = AskQuestionModal(choice_set_name, question_channel_id, result_channel_id)
            await interaction.response.send_modal(modal)
            return False

if custom_id == "open_question_modal":
    # เปิด modal ให้กรอกคำถาม
    choice_set_name = self.select_choices.values[0] if self.select_choices.values else None
    question_channel_id = int(self.select_question_channel.values[0]) if self.select_question_channel.values else None
    result_channel_id = int(self.select_result_channel.values[0]) if self.select_result_channel.values else None

    if not choice_set_name or not question_channel_id or not result_channel_id:
        await interaction.response.send_message("❗ กรุณาเลือกชุดคำตอบ ช่องส่งคำถาม และช่องสรุปผลโหวตก่อน", ephemeral=True)
        return False

    modal = AskQuestionModal(choice_set_name, question_channel_id, result_channel_id)
    modal.view_ref = self  # ✅ บรรทัดที่เพิ่ม
    await interaction.response.send_modal(modal)
    return False

            # ต้องเก็บคำถามจาก modal ก่อน ถึงส่งได้ (ปกติจะได้จาก modal)
            # แต่ถ้าไม่มีคำถาม เราจะเตือน (ที่นี้เราต้องเก็บไว้ใน object นี้)
            # เพิ่ม attribute เก็บคำถามไว้ (ซึ่งอาจต้องดัดแปลงโค้ดอีกที)

            # สำหรับกรณีนี้ ให้เตือนก่อนว่าต้องกรอกคำถามผ่าน modal ก่อน
            if not hasattr(self, "question_text") or not self.question_text:
                await interaction.response.send_message("❗ กรุณากรอกคำถามก่อนผ่านปุ่ม 'กรอกคำถาม' ก่อน", ephemeral=True)
                return False

            guild = self.guild
            question_channel = guild.get_channel(question_channel_id)
            result_channel = guild.get_channel(result_channel_id)

            if question_channel is None or result_channel is None:
                await interaction.response.send_message("❌ ไม่พบช่องเป้าหมายหรือช่องผลโหวต", ephemeral=True)
                return False

            choices = QUESTION_CHOICES.get(choice_set_name)
            if not choices:
                await interaction.response.send_message("❌ ชุดคำตอบไม่ถูกต้อง", ephemeral=True)
                return False

            embed = discord.Embed(
                title="📢 คำถามจากผู้ดูแล",
                description=self.question_text,
                color=0xFFB6C1
            )
            embed.set_footer(text=f"เลือกตอบโดยใช้เมนูด้านล่าง | ชุดคำตอบ: {choice_set_name}")

            class AnswerSelect(discord.ui.Select):
                def __init__(self):
                    opts = [discord.SelectOption(label=opt) for opt in choices]
                    super().__init__(placeholder="โปรดเลือกคำตอบของคุณ", options=opts, min_values=1, max_values=1)

                async def callback(self, interaction2: discord.Interaction):
                    user = interaction2.user
                    msg_id = interaction2.message.id
                    user_votes = vote_records.setdefault(msg_id, {})
                    user_votes[user.id] = self.values[0]

                    # สรุปผลโหวต
                    summary = {}
                    for ans in choices:
                        summary[ans] = []

                    for uid, ans in user_votes.items():
                        member = guild.get_member(uid)
                        if member:
                            summary[ans].append(member.display_name)

                    # สร้างข้อความสรุป
                    summary_text = ""
                    for ans in choices:
                        voters = summary[ans]
                        summary_text += f"**{ans}**: {len(voters)} โหวต\n"
                        if voters:
                            summary_text += ", ".join(voters) + "\n"

                    # ส่งสรุปไปช่องผลโหวต
                    await result_channel.send(
                        embed=discord.Embed(
                            title="📊 ผลโหวตล่าสุด",
                            description=summary_text,
                            color=0x87CEEB
                        )
                    )

                    await interaction2.response.send_message(f"คุณเลือก: {self.values[0]}", ephemeral=True)

            view = discord.ui.View()
            view.add_item(AnswerSelect())

            sent_msg = await question_channel.send(embed=embed, view=view)
            vote_records[sent_msg.id] = {}  # เตรียมเก็บโหวต

            # ปิด view ต้นทาง (disable ปุ่มและเมนู)
            disable_all_items(self)
            await interaction.message.edit(view=self)

            await interaction.response.send_message(
                f"ส่งคำถามไปที่ช่อง {question_channel.mention} เรียบร้อยแล้ว\nสรุปผลโหวตที่ช่อง {result_channel.mention}",
                ephemeral=True
            )
            return False

        return True

    async def on_modal_submit(self, modal: discord.ui.Modal):
        # ฟังก์ชันนี้ไม่มีในตัว discord.py ต้องจัดการเองผ่าน on_modal_submit หรือ callback ของ modal
        pass

# เราต้องแก้ให้ AskQuestionModal เก็บค่า question แล้วส่งกลับไปที่ view
class AskQuestionModal(discord.ui.Modal, title="กรอกคำถาม"):
    question = discord.ui.TextInput(label="คำถามของคุณ", style=discord.TextStyle.paragraph)

    def __init__(self, choice_set_name, question_channel_id, result_channel_id):
        super().__init__()
        self.choice_set_name = choice_set_name
        self.question_channel_id = question_channel_id
        self.result_channel_id = result_channel_id
        self.view_ref = None  # เก็บ reference ของ view เพื่อส่งข้อมูลกลับ

    async def on_submit(self, interaction: discord.Interaction):
        # เก็บข้อความคำถามกลับไปที่ view (ส่งผ่าน interaction)
        # หา view ที่เปิด modal นี้
        # โดย interaction.message อาจเป็นข้อความก่อนหน้าของ view นั้น

        # ดึง view ผ่าน interaction.message
        # แต่ interaction.message อาจเป็น None ถ้ามาจาก modal -> workaround:

        # เราเก็บ reference view ไว้ตอนเปิด modal
        if self.view_ref:
            self.view_ref.question_text = self.question.value
            await interaction.response.send_message("✅ กรอกคำถามเรียบร้อยแล้ว สามารถกดยืนยันส่งคำถามได้เลย", ephemeral=True)
        else:
            await interaction.response.send_message("❌ เกิดข้อผิดพลาด ไม่พบ view ต้นทาง", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name
    msg = message.content.strip()
    lower_msg = msg.lower()

    if lower_msg.startswith("doro ถาม"):
        view = AskQuestionView(message.guild)
        await message.reply("📋 กดปุ่มด้านล่างเพื่อสร้างคำถาม", view=view)
        return

    if lower_msg == "doro ขอยศ":
        embed = discord.Embed(
            title="ขอยศ",
            description="นายเลือกยศจากเมนูด้านล่าง หรือกดปุ่มเพื่อกรอกเหตุผลขอยศนี้ได้นะ",
            color=0xFFB6C1
        )
        view = RequestRoleView()
        await message.channel.send(embed=embed, view=view)
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
        search_term = msg[10:].strip()
        if not search_term:
            await message.channel.send("❗ โปรดระบุชื่อคลิปที่ต้องการค้นหา")
            return
        results = VideosSearch(search_term, limit=1).result()
        if not results["result"]:
            await message.channel.send("❌ ไม่พบคลิปที่ค้นหา")
            return
        info = results["result"][0]
        await message.channel.send(f"🎵 พบคลิป: **{info['title']}**\n🔗 {info['link']}")
        return

    if lower_msg.startswith("doroส่งข้อความ") or lower_msg.startswith("doro ส่งข้อความ"):
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
            await channel.send(f"@everyone  {text}")
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
                "**🔹 doro ถาม <คำถาม>**\n"
                "**🔹 doro ข้อยศ (เมนูเลือกยศ)**\n"
                "**🔹 !join / !play / !skip / !stop / !queue**"
            ),
            color=discord.Color.magenta()
        )
        await message.channel.send(embed=embed)
        return

    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
        return

    # บันทึกบริบทผู้ใช้
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    user_contexts[user_id].append((user_id, username, msg))
    if len(user_contexts[user_id]) > 5:
        user_contexts[user_id].pop(0)

    if msg.startswith("!"):
        await bot.process_commands(message)


server_on()
bot.run(DISCORD_TOKEN)


