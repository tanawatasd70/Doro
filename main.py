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

# --- Global Data ---
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

# ==========================================
# 🎮 ROBLOX PRIVATE SERVER DATABASE SYSTEM
# ==========================================
JSON_FILE = "roblox_servers.json"

def load_roblox_data():
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        default_data = {
            "blox_fruits": {"name": "🏴‍☠️ Blox Fruits", "url": "https://www.roblox.com/"},
            "king_legacy": {"name": "👑 King Legacy", "url": "https://www.roblox.com/"}
        }
        save_roblox_data(default_data)
        return default_data

def save_roblox_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ==========================================
# 🎛️ MAIN UI COMMAND MENU
# ==========================================
class BotCommandControlSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛡️ เปิดระบบจัดการ/ขอยศ", description="เรียกเมนู Dropdown เลือกรับยศ และปุ่มขอยศสุดน่ารัก", value="setup_roles"),
            discord.SelectOption(label="📊 เปิดระบบสร้างคำถามโพล", description="สร้างโพลน่ารัก ๆ เพื่อโหวตเลือกคำตอบกันเถอะ", value="setup_poll"),
            discord.SelectOption(label="🎮 รวมลิงก์ Private Server Roblox", description="คลังแสงลิงก์เซิร์ฟเวอร์วีเกมต่าง ๆ ของชาว Robloxค๊าา", value="roblox_servers"),
            discord.SelectOption(label="🚫 เริ่มวาระโหวตเตะสมาชิก", description="เลือกคนที่ทำตัวไม่น่ารักเพื่อเริ่มโหวตเตะกันค่ะ!", value="setup_kick"),
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูคู่มือการสั่งงานน้อน Doro ทั้งหมดกันงับ", value="show_commands")
        ]
        super().__init__(
            placeholder="🎛️ เลือกโหมดคำสั่งที่ต้องการให้น้อน Doro ทำงาน...", 
            min_values=1, 
            max_values=1, 
            options=options,
            custom_id="doro_main_control_select"
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        current_guild = interaction.guild
        
        if value == "setup_roles":
            embed = discord.Embed(
                title="🛡️ ระบบจัดการยศอัตโนมัติค๊าา",
                description="คุณชอบยศไหนเลือกรับจากเมนูด้านล่างนี้ได้เลยนะค๊าา หรือจะกดปุ่มขอยศพิเศษพร้อมส่งเหตุผลอ้อน ๆ มาให้แอดมินดูก็ได้น้าา~ ✨",
                color=0xFFB6C1
            )
            view = RequestRoleView(current_guild)
            await interaction.response.send_message(embed=embed, view=view)
            
        elif value == "setup_poll":
            view = AskQuestionView(current_guild)
            await interaction.response.send_message("📋 **ตั้งค่าระบบโพลคำถามน้าา:** โปรดเลือกห้องแชทและกรอกข้อมูลคำถามให้ครบถ้วนก่อนน้อน Doro จะปล่อยโพลนะค๊าา", view=view, ephemeral=True)
            
        elif value == "roblox_servers":
            embed = discord.Embed(
                title="🎮 คลังแสง Private Server ของแก๊งเรา! 🚀",
                description="อยากไปฟาร์ม ไปเวล หรือไปตึงเกมไหน เลือกชื่อเกมจากเมนูด้านล่างนี้ได้เลยค๊าา\n(สำหรับแอดมินสามารถกดปุ่มเพื่อเพิ่มหรือลบเกมได้เลยนะค๊าา) ✨",
                color=0x00E5FF
            )
            view = RobloxServerView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif value == "setup_kick":
            embed = discord.Embed(
                title="🚫 ระบบโหวตเตะสมาชิก (โหมด Doro เอาจริง!)",
                description="โปรดเลือกรายชื่อคนที่ไม่น่ารักที่คุณต้องการเริ่มโหวตลงมติเตะด้านล่างนี้ได้เลยค่ะงึมมม",
                color=discord.Color.red()
            )
            view = MemberSelectView(current_guild)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        elif value == "show_commands":
            embed = discord.Embed(
                title="📘 สมุดคู่มือของน้อน Doro 🤖✨",
                description=(
                    "**🔹 bot ชื่ออะไร** / **doro ช่วยอะไรได้บ้าง** / **doro สวัสดี**\n"
                    "**🔹 doro เมนู** : เปิดแผงควบคุม UI น่ารัก ๆ สำหรับขอยศ สร้างโพล หรือลิงก์ Roblox\n"
                    "**🔹 doro ค้นหา <ชื่อคลิป>** : ค้นหาคลิปวิดีโอให้คุณ\n"
                    "**🔹 doro สมาชิกทั้งหมด** : ดูสถิติคนในเซิร์ฟเวอร์แบบตะมุตะมิ\n"
                    "**🔹 doro เวลา** : เช็กเวลาปัจจุบัน\n"
                    "**🔹 doro โหวตเตะ** : เรียกหน้าต่าง UI แปะป้ายคนไม่น่ารัก\n"
                    "**🔹 doroส่งข้อความ <ช่อง_id> <ข้อความ>** *(คุณแอดมิน)*\n"
                    "**🔹 doro ลบข้อความ <จำนวน>** *(คุณผู้จัดการข้อความ)*\n"
                    "**🔹 doro รีเซ็ตห้อง** : ชุบชีวิตห้องแชทใหม่\n"
                    "**🔹 doro คำสั่งเพลง** : ดูชุดคำสั่งเสียงดนตรี !play !skip !stop ทั้งหมดเจ้าค่ะ"
                ),
                color=discord.Color.magenta()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class BotControlMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BotCommandControlSelect())


# ==========================================
# 🎮 ROBLOX UI COMPONENTS
# ==========================================
class AddRobloxServerModal(discord.ui.Modal, title="🎮 เพิ่ม/แก้ไข ลิงก์เซิร์ฟเวอร์วี"):
    game_id = discord.ui.TextInput(
        label="รหัสเกม (ภาษาอังกฤษตัวพิมพ์เล็ก ห้ามมีช่องว่าง)", 
        placeholder="เช่น blox_fruits, bedwars",
        style=discord.TextStyle.short
    )
    game_name = discord.ui.TextInput(
        label="ชื่อเกมที่จะให้โชว์บนเมนู (ใส่ อีโมจิ ได้น้าา)", 
        placeholder="เช่น 🏴‍☠️ Blox Fruits (เซิร์ฟหลัก)",
        style=discord.TextStyle.short
    )
    game_url = discord.ui.TextInput(
        label="ลิงก์ Private Server (Roblox Link)", 
        placeholder="https://www.roblox.com/share?code=...",
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ งื้ออ คุณไม่มีสิทธิ์จัดการเซิร์ฟเวอร์ ไม่สามารถเพิ่มลิงก์ได้ค๊าา", ephemeral=True)

        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        g_name = self.game_name.value.strip()
        g_url = self.game_url.value.strip()

        if not g_url.startswith("http"):
            return await interaction.response.send_message("❌ รูปแบบลิงก์ไม่ถูกต้องค๊าา ต้องขึ้นต้นด้วย http หรือ https น้าา", ephemeral=True)

        current_data = load_roblox_data()
        current_data[g_id] = {"name": g_name, "url": g_url}
        save_roblox_data(current_data)
        await interaction.response.send_message(f"✅ บันทึกเกม **{g_name}** เรียบร้อยค๊าา! (รบกวนเปิดเมนูใหม่อีกรอบเพื่ออัปเดตนะค๊าา)", ephemeral=True)

class DeleteRobloxServerModal(discord.ui.Modal, title="🗑️ ลบลิงก์เซิร์ฟเวอร์วี"):
    game_id = discord.ui.TextInput(
        label="พิมพ์รหัสเกมที่ต้องการลบ (ภาษาอังกฤษ)", 
        placeholder="เช่น blox_fruits",
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ สิทธิ์ไม่พอค๊าา", ephemeral=True)

        g_id = self.game_id.value.strip().lower()
        current_data = load_roblox_data()

        if g_id in current_data:
            name = current_data[g_id]['name']
            del current_data[g_id]
            save_roblox_data(current_data)
            await interaction.response.send_message(f"🗑️ ลบลิงก์เกม **{name}** เรียบร้อยแล้วค๊าา!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ ไม่พบรหัสเกม `{g_id}` ในระบบค๊าา", ephemeral=True)

class RobloxServerSelect(discord.ui.Select):
    def __init__(self):
        current_data = load_roblox_data()
        options = []
        if not current_data:
            options.append(discord.SelectOption(label="ไม่มีเกมในคลังแสง", value="none", description="รอกรรมการมาเพิ่มเกมค๊าา"))
        else:
            for key, data in current_data.items():
                short_name = data["name"][:90] if data["name"] else "Unknown Game"
                options.append(discord.SelectOption(label=short_name, value=key, description=f"รหัสอ้างอิง: {key}"[:100]))
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", min_values=1, max_values=1, options=options, custom_id="roblox_select_menu")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ ยังไม่มีเกมในระบบเลยงับบ รอแอดมินมาแอดให้น้าา", ephemeral=True)

        game_key = self.values[0]
        current_data = load_roblox_data()
        game_data = current_data.get(game_key)
        
        if game_data:
            embed = discord.Embed(
                title=f"🚀 ลิงก์เข้า Private Server เกม {game_data['name']}",
                description=f"กดที่ปุ่ม **'👉 เข้าเซิร์ฟเวอร์วีที่นี่'** ด้านล่างเพื่อเข้าเล่นได้ทันทีค๊าา!\n\n🔗 ลิงก์สำรอง: {game_data['url']}",
                color=0x00FFCC
            )
            view = discord.ui.View()
            
            raw_label = f"👉 เข้า {game_data['name']}"
            button_label = raw_label[:45] if len(raw_label) > 0 else "👉 เข้าสู่เซิร์ฟเวอร์วี"
            
            view.add_item(discord.ui.Button(label=button_label, url=game_data['url'], style=discord.ButtonStyle.link))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message("❌ งื้ออ ลิงก์นี้อาจจะโดนลบหรือแก้ไขไปแล้วค๊าา", ephemeral=True)

class RobloxServerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RobloxServerSelect())

    @discord.ui.button(label="➕ เพิ่ม/แก้ไขลิงก์เกม", style=discord.ButtonStyle.primary, custom_id="roblox_add_btn")
    async def add_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ปุ่มนี้เฉพาะคุณแอดมินเท่านั้นน้าาองึมม", ephemeral=True)
        await interaction.response.send_modal(AddRobloxServerModal())

    @discord.ui.button(label="🗑️ ลบลิงก์เกม", style=discord.ButtonStyle.danger, custom_id="roblox_del_btn")
    async def delete_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ ปุ่มนี้เฉพาะแอดมินค๊าา", ephemeral=True)
        await interaction.response.send_modal(DeleteRobloxServerModal())


# ==========================================
# 🛡️ ROLE MANAGEMENT SYSTEM
# ==========================================
class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🎨 เลือกรับยศสุดเลิศของคุณที่นี่เลยน้าา...", min_values=1, max_values=1, options=options, custom_id="role_select_dropdown")

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.values[0]))
        if role is None:
            return await interaction.response.send_message("❌ งื้ออ ไม่พบยศนี้ในเซิร์ฟเวอร์เลยค่ะ", ephemeral=True)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ เย้! ยินดีด้วยน้าา คุณได้รับยศ **{role.name}** เรียบร้อยแล้วค่ะ! 🎉", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ น้อน Doro ไม่มีสิทธิ์ให้ยศนี้ง่าา (รบกวนแอดมินช่วยตรวจลำดับยศของหนูหน่อยน้าา)", ephemeral=True)

class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศทั่วไปทั้งหมดออกเยย", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="role_remove_btn")

    async def callback(self, interaction: discord.Interaction):
        roles_to_remove = [r for r in interaction.user.roles if r.name != "@everyone" and not r.managed]
        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)
            await interaction.response.send_message("🧹 ฟู่ๆๆ~ ลบยศทั่วไปออกจากตัวให้เรียบร้อยแล้วค๊าา ตัวเบาหวิวเยย!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ งื้ออ หนูลบยศให้ไม่ได้ง่าา พลังของหนูไม่พอ", ephemeral=True)

class TextInputModal(discord.ui.Modal, title="📝 ส่งเหตุผลอ้อน ๆ เพื่อขอยศพิเศษ"):
    reason = discord.ui.TextInput(label="เหตุผล/ชื่อยศพิเศษที่อยากได้ค๊าา", style=discord.TextStyle.paragraph, placeholder="หนูขอเข้าห้องลับกลุ่มนักพัฒนาหน่อยน้าา...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"📨 ส่งคำขอยศให้แล้วนะค๊าา! ข้อความของคุณ: {self.reason.value}", ephemeral=True)

class TextInputButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📝 ส่งคำขอยศพิเศษ (เขียนเหตุผลอ้อนแอดมิน)", style=discord.ButtonStyle.primary, custom_id="role_request_special_btn")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextInputModal())

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(guild))
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())


# ==========================================
# 📊 [FIXED] POLL UI SYSTEM (แก้ไขจุดพังจากรูป)
# ==========================================
class AskQuestionTextModal(discord.ui.Modal):
    def __init__(self, parent_view):
        # แก้ไข: ส่งค่า Title ตรงเข้า Constructor ป้องกันโครงสร้างพังจนขึ้น Interaction Failed
        super().__init__(title="✍️ รายละเอียดคำถามโพลแสนสนุก")
        self.parent_view = parent_view

        # ประกาศช่องข้อความและใช้ add_item เพื่อความเสถียรสูงสุดตาม Discord API
        self.question = discord.ui.TextInput(
            label="หัวข้อคำถามโพลนี้คืออะไรเอ่ย?", 
            style=discord.TextStyle.short, 
            placeholder="เย็นนี้ไปกินชาบูกันไหมค๊าา?",
            required=True
        )
        self.choices_input = discord.ui.TextInput(
            label="ตัวเลือกคำตอบ (แยกด้วยเครื่องหมายจุลภาค , น้าา)", 
            style=discord.TextStyle.paragraph, 
            placeholder="ไปเซ่, ไม่ว่างง่ะ, ชวนคนอื่นเถอะ",
            required=True
        )
        self.add_item(self.question)
        self.add_item(self.choices_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value.strip()
        parsed_choices = [c.strip() for c in self.choices_input.value.split(",") if c.strip()]
        
        if len(parsed_choices) < 2:
            return await interaction.response.send_message("❗ โธ่.. ใส่ตัวเลือกให้น้อน Doro อย่างน้อย 2 ช้อยส์สิคะงับ", ephemeral=True)
        if len(parsed_choices) > 25:
            return await interaction.response.send_message("❗ ช้อยส์เยอะเกินไปแล้วว รองรับสูงสุด 25 ตัวเลือกน้าา", ephemeral=True)
            
        self.parent_view.poll_choices = parsed_choices
        await interaction.response.send_message(f"✏️ น้อน Doro จำคำถามและตัวเลือก ({len(parsed_choices)} ช้อยส์) ลงสมุดโน้ตแล้วค่ะ!", ephemeral=True)

class OpenQuestionModalButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="✏️ กรอกคำถามและตัวเลือกโพล", style=discord.ButtonStyle.secondary, custom_id="poll_open_modal_btn")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # เรียกเปิดหน้าต่างกรอกข้อมูลโพลที่แก้เรียบร้อยแล้ว
        await interaction.response.send_modal(AskQuestionTextModal(self.parent_view))

class SubmitQuestionButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="🚀 ยืนยันปล่อยโพลเลยค๊าา", style=discord.ButtonStyle.success, custom_id="poll_submit_btn")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.submit_question(interaction)

class VoteSelect(discord.ui.Select):
    def __init__(self, choices, result_channel_id, all_choices_list):
        opts = [discord.SelectOption(label=opt[:90] if opt else "ตัวเลือก") for opt in choices]
        super().__init__(placeholder="🗳️ กดตรงนี้เพื่อโหวตเลือกคำตอบที่คุณชอบเลยน้าา...", options=opts, min_values=1, max_values=1, custom_id="poll_vote_select")
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
            summary_text += f"**{ans}**: {len(voters)} คะแนนเสียง\n"
            if voters: summary_text += "     ↳ " + ", ".join(voters) + "\n"

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
        
        self.target_channel_id = None
        self.result_channel_id = None

        channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        channel_options = [discord.SelectOption(label=f"#{ch.name}"[:40], value=str(ch.id)) for ch in channels[:25]]
        
        self.select_question_channel = discord.ui.Select(
            placeholder="📢 1. เลือกห้องที่จะให้น้อน Doro ไปปล่อยโพลค่ะ", 
            options=channel_options,
            custom_id="poll_select_target_channel"
        )
        self.select_question_channel.callback = self.on_select_target_channel
        self.add_item(self.select_question_channel)

        self.select_result_channel = discord.ui.Select(
            placeholder="📊 2. เลือกห้องที่จะให้สรุปคะแนนโหวตโชว์ค่ะ", 
            options=channel_options,
            custom_id="poll_select_result_channel"
        )
        self.select_result_channel.callback = self.on_select_result_channel
        self.add_item(self.select_result_channel)

        self.add_item(OpenQuestionModalButton(self))
        self.add_item(SubmitQuestionButton(self))

    async def on_select_target_channel(self, interaction: discord.Interaction):
        self.target_channel_id = int(self.select_question_channel.values[0])
        await interaction.response.defer()  

    async def on_select_result_channel(self, interaction: discord.Interaction):
        self.result_channel_id = int(self.select_result_channel.values[0])
        await interaction.response.defer()

    async def submit_question(self, interaction: discord.Interaction):
        if not self.question_text or not self.poll_choices:
            return await interaction.response.send_message("❗ งื้ออ อย่าเพิ่งใจร้อนสิคะ! กรอกคำถามและช้อยส์ผ่านปุ่มก่อนน้าา", ephemeral=True)
            
        if not self.target_channel_id or not self.result_channel_id:
            return await interaction.response.send_message("❗ ลืมเลือกห้องปล่อยคำถามหรือห้องสรุปผลด้วยน้าา", ephemeral=True)

        q_channel = self.guild.get_channel(self.target_channel_id)
        if not q_channel:
            return await interaction.response.send_message("❌ ไม่พบห้องแชทที่จะปล่อยโพลค๊าา บอทอาจไม่มีสิทธิ์เข้าถึง", ephemeral=True)

        try:
            embed = discord.Embed(title="📢 น้อน Doro ขอเชิญชวนทุกคนมาร่วมลงประชามติกันค๊าา~", color=discord.Color.pink())
            embed.add_field(name="❓ หัวข้อคำถามโพล", value=self.question_text, inline=False)
            
            choices_desc = "\n".join([f"🔹 {c}" for c in self.poll_choices])
            embed.add_field(name="📦 รายการตัวเลือก", value=choices_desc, inline=False)
            
            vote_view = discord.ui.View(timeout=None)
            vote_view.add_item(VoteSelect(self.poll_choices, self.result_channel_id, self.poll_choices))
            
            sent_msg = await q_channel.send(embed=embed, view=vote_view)
            vote_records[sent_msg.id] = {}
            await interaction.response.send_message(f"✅ บินไปปล่อยโพลเรียบร้อยแล้วที่ห้อง {q_channel.mention} น้าา ฟิ้วว~", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ เกิดข้อผิดพลาดระบบ HTTP: {e}", ephemeral=True)


# ==========================================
# 🚫 VOTE KICK SYSTEM
# ==========================================
class MemberSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 จิ้มเลือกคนที่ไม่น่ารักตรงนี้เลยงับ...", min_values=1, max_values=1, custom_id="kick_member_select")
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
        label_str = "🔊 เตะออกจากห้องเสียง" if kick_type == "voice" else "💥 ดีดออกจากเซิร์ฟเวอร์"
        safe_label = label_str[:45]
        
        style = discord.ButtonStyle.primary if kick_type == "voice" else discord.ButtonStyle.danger
        custom_id_str = f"kick_btn_{kick_type}_{target.id}"
        super().__init__(label=safe_label, style=style, custom_id=custom_id_str[:100])
        self.target = target
        self.kick_type = kick_type
        self.required_votes = required_votes

    async def callback(self, interaction: discord.Interaction):
        view = VoteProgressView(self.target, self.kick_type, self.required_votes)
        embed = discord.Embed(
            title=f"🚨 เปิดวาระลงคะแนนโหวตขับไล่ขั้นเด็ดขาด!",
            description=f"เป้าหมาย: {self.target.mention}\nบทลงโทษ: **{self.label}**\nเกณฑ์คะแนนเสียงที่ต้องการ: **{self.required_votes}** โหวต",
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

    @discord.ui.button(label="🟢 เห็นด้วย ลุยเยย! (Vote)", style=discord.ButtonStyle.success, emoji="👍", custom_id="kick_vote_yes_btn")
    async def vote_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters:
            return await interaction.response.send_message("คุณใช้สิทธิ์ไปแล้วน้าา ห้ามกดซ้ำสิระคะ!", ephemeral=True)
        if interaction.user.id == self.target.id:
            return await interaction.response.send_message("จะกดเห็นด้วยเพื่อเตะตัวเองไม่ได้น้าาา! 🤣", ephemeral=True)

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
                        await interaction.channel.send(f"🔨 มติเป็นเอกฉันท์ค๊าา น้อน Doro ตัดสาย {self.target.mention} ออกจากห้องเสียงเรียบร้อย!")
                    else:
                        await interaction.channel.send(f"⚠️ ผลโหวตชนะแล้วน้าา แต่เป้าหมาย {self.target.mention} แอบวิ่งหนีออกจากห้องเสียงไปก่อนแล้วง่ะ")
                elif self.kick_type == "server":
                    await self.target.kick(reason="ผลโหวตลงมติเตะออกจากเซิร์ฟเวอร์")
                    await interaction.channel.send(f"💥 ประชามติเห็นพ้องต้องกัน น้อน Doro ส่ง {self.target.mention} ปลิวหายไปจากเซิร์ฟเวอร์แล้วค๊าา~")
            except discord.Forbidden:
                await interaction.channel.send(f"❌ ระบบไม่ทำงาน: ยศของหนูต่ำกว่าเป้าหมาย หรือหนูขาดสิทธิ์การเตะคน")
            self.stop()
        else:
            await interaction.response.edit_message(embed=embed, view=self)


# ==========================================
# ⚙️ SYSTEM CORE & EVENTS
# ==========================================
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
                description="ยินดีต้อนรับสู่ดินแดนแห่งความน่ารักค๊าา! เลือกเมนูด้านล่างนี้เพื่อเปิดใช้งานฟังก์ชันได้ตามใจชอบเลยนะค๊าา ✨",
                color=0x3498DB
            )
            view = BotControlMenuView()
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
            
            embed = discord.Embed(
                title="📊 สถิติสมาชิกในเซิร์ฟเวอร์แบบตะมุตะมิ",
                description=f"🟢 ออนไลน์: {online} คน\n🌙 จอฟ้า/ว่าง: {idle} คน\n⛔ ห้ามรบกวน: {dnd} คน\n⚪ ออฟไลน์: {offline} คน",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)
            return
            
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในระบบข้อความ: {e}")

# รันเว็บเซิร์ฟเวอร์เปิดบอทตลอด 24 ชม. และสตาร์ท Discord Bot
server_on()
bot.run(DISCORD_TOKEN)
