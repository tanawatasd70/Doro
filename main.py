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

# เก็บโหวต: message_id -> { user_id: answer, ... }
vote_records = {}

QUESTION_CHOICES = {
    "เอา / ไม่เอา / ไม่แน่ใจ": ["เอา", "ไม่เอา", "ไม่แน่ใจ"],
    "เล่น / ไม่เล่น": ["เล่น", "ไม่เล่น"],
    "ใช่ / ไม่ใช่": ["ใช่", "ไม่ใช่"],
}

class AskQuestionView(discord.ui.View):
    def __init__(self, guild, question_text=None):
        super().__init__(timeout=None)
        self.guild = guild
        self.question_text = question_text

        self.select_choices = discord.ui.Select(
            placeholder="เลือกชุดคำตอบ",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="เอา / ไม่เอา / ไม่แน่ใจ", value="เอา / ไม่เอา / ไม่แน่ใจ"),
                discord.SelectOption(label="เล่น / ไม่เล่น", value="เล่น / ไม่เล่น"),
                discord.SelectOption(label="ใช่ / ไม่ใช่", value="ใช่ / ไม่ใช่"),
            ],
        )
        self.add_item(self.select_choices)

        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        channel_options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in channels]
        self.select_question_channel = discord.ui.Select(
            placeholder="เลือกห้องส่งคำถาม",
            options=channel_options
        )
        self.add_item(self.select_question_channel)

        self.select_result_channel = discord.ui.Select(
            placeholder="เลือกห้องสรุปผลโหวต",
            options=channel_options
        )
        self.add_item(self.select_result_channel)

        self.submit_button = discord.ui.Button(label="ส่งคำถาม", style=discord.ButtonStyle.success)
        self.submit_button.callback = self.submit_callback
        self.add_item(self.submit_button)

    async def submit_callback(self, interaction: discord.Interaction):
        if not self.question_text:
            await interaction.response.send_message("กรุณากรอกคำถามก่อน (พิมพ์ `doro ถาม <คำถาม>`)", ephemeral=True)
            return
        choice_set_name = self.select_choices.values[0] if self.select_choices.values else None
        question_channel_id = int(self.select_question_channel.values[0]) if self.select_question_channel.values else None
        result_channel_id = int(self.select_result_channel.values[0]) if self.select_result_channel.values else None

        if not (choice_set_name and question_channel_id and result_channel_id):
            await interaction.response.send_message("โปรดเลือกชุดคำตอบ ห้องส่งคำถาม และห้องสรุปผลให้ครบ", ephemeral=True)
            return

        choices = QUESTION_CHOICES.get(choice_set_name)
        if not choices:
            await interaction.response.send_message("ชุดคำตอบไม่ถูกต้อง", ephemeral=True)
            return

        question_channel = self.guild.get_channel(question_channel_id)
        result_channel = self.guild.get_channel(result_channel_id)
        if not question_channel or not result_channel:
            await interaction.response.send_message("ไม่พบช่องที่เลือก", ephemeral=True)
            return

        embed = discord.Embed(
            title="📢 คำถามจาก Doro",
            description=self.question_text,
            color=discord.Color.pink()
        )

        class VoteSelect(discord.ui.Select):
            def __init__(self):
                opts = [discord.SelectOption(label=opt) for opt in choices]
                super().__init__(placeholder="โปรดเลือกคำตอบของคุณ", options=opts, min_values=1, max_values=1)

            async def callback(self, interaction2: discord.Interaction):
                user = interaction2.user
                msg_id = interaction2.message.id
                user_votes = vote_records.setdefault(msg_id, {})
                user_votes[user.id] = self.values[0]

                summary = {ans: [] for ans in choices}
                for uid, ans in user_votes.items():
                    member = self.view.guild.get_member(uid)
                    if member:
                        summary[ans].append(member.display_name)
                summary_text = ""
                for ans in choices:
                    voters = summary[ans]
                    summary_text += f"**{ans}**: {len(voters)} โหวต\n"
                    if voters:
                        summary_text += ", ".join(voters) + "\n"

                await result_channel.send(embed=discord.Embed(
                    title="📊 ผลโหวตล่าสุด",
                    description=summary_text,
                    color=0x87CEEB
                ))

                await interaction2.response.send_message(f"คุณเลือก: {self.values[0]}", ephemeral=True)

        view = discord.ui.View()
        vote_select = VoteSelect()
        vote_select.view = view
        view.add_item(vote_select)

        sent_msg = await question_channel.send(embed=embed, view=view)
        vote_records[sent_msg.id] = {}

        await interaction.response.send_message(f"ส่งคำถามไปที่ {question_channel.mention} เรียบร้อยแล้ว\nสรุปผลโหวตที่ {result_channel.mention}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg = message.content
    lower_msg = msg.lower()

    # ระบบถามคำถามแบบ dropdown + embed จากโค้ดคุณ
    if lower_msg.startswith("doro ถาม "):
        question = msg[10:].strip()
        embed = discord.Embed(
            title="📋 คำถามจาก Doro",
            description=f"{question}\n\nกรุณาเลือกคำตอบของคุณจากเมนูด้านล่าง ⬇️",
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"ถามโดย {message.author.display_name}", icon_url=message.author.display_avatar.url)
        view = AskQuestionView(message.guild, question_text=question)
        await message.channel.send(embed=embed, view=view)
        return

    await bot.process_commands(message)

@bot.command()
async def ค้นหา(ctx, *, keyword):
    search = VideosSearch(keyword, limit=1)
    result = search.result()
    if result["result"]:
        video = result["result"][0]
        await ctx.send(f"🔍 เจอวิดีโอ: {video['title']}\n{video['link']}")
    else:
        await ctx.send("❌ ไม่พบวิดีโอ")

# เรียกใช้งาน Server (Render)
server_on()

bot.run(DISCORD_TOKEN)
