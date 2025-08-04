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

# ====== ระบบถามคำถามแบบมี Dropdown ======
class AskQuestionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

        self.select_choices = discord.ui.Select(
            placeholder="เลือกคำตอบของคุณ",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="เอา", value="accept", emoji="👍"),
                discord.SelectOption(label="ไม่เอา", value="reject", emoji="👎"),
                discord.SelectOption(label="ไม่แน่ใจ", value="unsure", emoji="❓"),
            ]
        )
        self.select_choices.callback = self.select_callback
        self.add_item(self.select_choices)

    async def select_callback(self, interaction: discord.Interaction):
        choice_set_name = self.select_choices.values[0] if self.select_choices.values else None
        await interaction.response.send_message(f"คุณเลือก: {choice_set_name}", ephemeral=True)

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

    if lower_msg.startswith("doro ถาม "):
        question = msg[10:].strip()

        embed = discord.Embed(
            title="📋 คำถามจาก Doro",
            description=f"{question}\n\nกรุณาเลือกคำตอบของคุณจากเมนูด้านล่าง ⬇️",
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"ถามโดย {message.author.display_name}", icon_url=message.author.display_avatar)

        view = AskQuestionView(message.guild)
        await message.channel.send(embed=embed, view=view)

# ====== ฟีเจอร์อื่น (ตัวอย่างจากระบบค้นหา) ======
@bot.command()
async def ค้นหา(ctx, *, keyword):
    search = VideosSearch(keyword, limit=1)
    result = search.result()
    if result["result"]:
        video = result["result"][0]
        await ctx.send(f"🔍 เจอวิดีโอ: {video['title']}\n{video['link']}")
    else:
        await ctx.send("❌ ไม่พบวิดีโอ")

# ====== บูต Server (Render) ======
server_on()
bot.run(DISCORD_TOKEN)
