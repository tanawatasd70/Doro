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

# -------------------------
# (คลาสและโค้ดจัดการยศ / คำถาม / โหวต เหมือนเดิม)
# -------------------------

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
            await message.channel.send(f"🧹 ลบข้อความจำนวน {len(deleted)-1} ข้อความแล้ว", delete_after=3)
        except Exception as e:
            await message.channel.send(f"⚠️ อะไรกันลบไม่สำเร็จ: {e}")
        return

    if lower_msg == "doro รีเซ็ตchannel":
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("❌ นายไม่มีสิทธิ์จัดการช่องนี้นะ")
            return
        try:
            old_channel = message.channel
            new_channel = await old_channel.clone(reason="ทำการรีเซ็ตห้องใหม่แล้ว")
            await old_channel.delete()
            await new_channel.send("💣 ห้องนี้ถูกรีเซ็ตใหม่แล้ว!")
        except Exception as e:
            await message.channel.send(f"⚠️ เกิดข้อผิดพลาด: {e}")
        return

    # custom_responses
    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
        return

    # เก็บ context
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    user_contexts[user_id].append((user_id, username, msg))
    if len(user_contexts[user_id]) > 5:
        user_contexts[user_id].pop(0)

    if msg.startswith("!"):
        await bot.process_commands(message)


@bot.command()
async def คำสั่ง(ctx):
    embed = discord.Embed(
        title="📖 คำสั่งทั้งหมดของ Doro",
        description="รวมคำสั่งที่สามารถใช้งานได้",
        color=discord.Color.pink()
    )

    embed.set_thumbnail(url="<IMAGE_URL>")  # ใส่ลิงก์รูปภาพโลโก้ที่คุณอัปโหลด

    embed.add_field(name="🎵 เพลง", value="`doro play <ชื่อเพลง/ลิงก์>` - เล่นเพลงจาก YouTube\n`doro stop` - หยุดเพลง", inline=False)
    embed.add_field(name="📊 โหวต", value="`doro โหวต <ชื่อเกม>` - สร้างโหวตแข่งขัน", inline=False)
    embed.add_field(name="❓ ถาม", value="`doro ถาม` - เปิด Modal เพื่อสร้างคำถาม", inline=False)
    embed.add_field(name="⚙️ อื่นๆ", value="`doro คำสั่ง` - แสดงรายการคำสั่งทั้งหมด", inline=False)

    embed.set_footer(text="Doro Bot ✨ ใช้เพื่อความสนุกในดิสคอร์ด!")

    await ctx.send(embed=embed)


server_on()
bot.run(DISCORD_TOKEN)
