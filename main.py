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

# ==========================================
# 🌐 WEB SERVER FOR RENDER (แก้ปัญหา Port ดับค๊าา)
# ==========================================
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home():
    return "🤖 Doro Bot UI Engine is Fully Active and Online! ✨"

def run_server():
    # ดึงพอร์ตจาก Render มาใช้โดยอัตโนมัติ ถ้าไม่มีจะใช้ 8080 งับ
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def server_on():
    t = Thread(target=run_server)
    t.start()

# เรียกใช้งาน Web Server ทันทีเมื่อรันโค้ด
server_on()


# ==========================================
# ⚙️ CONFIG & BOT SETUP
# ==========================================
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
    "whats your name": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักของทุกคนน~ 🤖💕",
    "what is your name": "หนูชื่อ Doro ค่ะ! เป็นยัยบอทสุดน่ารักของทุกคนน~ 🤖💕",
    "doro ช่วยอะไรได้บ้าง": "หนูช่วยตอบคำถามทั่วไป เปิดเพลงเพราะ ๆ ให้ฟัง แล้วก็ช่วยดูแลเซิร์ฟเวอร์ได้ด้วยนะค๊าา! 🎵✨",
    "doro help": "หนูช่วยตอบคำถามทั่วไป เปิดเพลงเพราะ ๆ ให้ฟัง แล้วก็ช่วยดูแลเซิร์ฟเวอร์ได้ด้วยนะค๊าา! 🎵✨",
    "doro สวัสดี": "งื้อออ สวัสดีค่าา! ยินดีที่ได้คุยด้วยนะคะ วันนี้มีอะไรให้หนูช่วยไหมเอ่ย? 🌸",
    "doro hello": "งื้อออ สวัสดีค่าา! ยินดีที่ได้คุยด้วยนะคะ วันนี้มีอะไรให้หนูช่วยไหมเอ่ย? 🌸",
    "doro hi": "งื้อออ สวัสดีค่าา! ยินดีที่ได้คุยด้วยนะคะ วันนี้มีอะไรให้หนูช่วยไหมเอ่ย? 🌸",
}

vote_records = {}  
poll_result_messages = {} 

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
            discord.SelectOption(label="📖 ดูคู่มือคำสั่งบอททั้งหมด", description="มาดูคู่มือการสั่งงานและบันทึกความสามารถน้อน Doro กันงับ", value="show_commands")
        ]
        super().__init__(
            placeholder="🎛️ เลือกโหมดคำสั่งที่ต้องการให้น้อน Doro ทำงาน...", 
            min_values=1, 
            max_values=1, 
            options=options,
            custom_id="doro_main_control_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        value = self.values[0]
        current_guild = interaction.guild

        if value == "setup_roles":
            embed = discord.Embed(
                title="🛡️ ระบบจัดการยศอัตโนมัติค๊าา",
                description="คุณชอบยศไหนเลือกรับจากเมนูด้านล่างนี้ได้เลยนะค๊าา หรือจะกดปุ่มขอยศพิเศษพร้อมส่งเหตุผลอ้อน ๆ มาให้แอดมินดูก็ได้น้าา~ ✨",
                color=0xFFB6C1
            )
            view = RequestRoleView(current_guild)
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "setup_poll":
            embed = discord.Embed(
                title="📊 ระบบสร้างคำถามโพลระดมความคิดค๊าา",
                description="กรุณากรอกหัวข้อคำถาม และเลือกช่องทางปล่อยโพลให้ครบถ้วนด้านล่างนี้เลยน้าา~ ✨",
                color=0x9B59B6
            )
            view = AskQuestionView(current_guild)
            await interaction.message.edit(embed=embed, view=view)
            
        elif value == "roblox_servers":
            embed = discord.Embed(
                title="🎮 คลังแสง Private Server ของแก๊งเรา! 🚀",
                description="อยากไปฟาร์ม ไปเวล หรือไปตึงเกมไหน เลือกชื่อเกมจากเมนูด้านล่างนี้ได้เลยค๊าา\n(สำหรับแอดมินสามารถกดปุ่มเพื่อเพิ่มหรือลบเกมได้เลยนะค๊าา) ✨",
                color=0x00E5FF
            )
            view = RobloxServerView()
            await interaction.message.edit(embed=embed, view=view)

        elif value == "setup_kick":
            embed = discord.Embed(
                title="🚫 ระบบโหวตเตะสมาชิก (โหมด Doro เอาจริง!)",
                description="โปรดเลือกรายชื่อคนที่ไม่น่ารักที่คุณต้องการเริ่มโหวตลงมติเตะด้านล่างนี้ได้เลยค่ะงึมมม",
                color=discord.Color.red()
            )
            view = MemberSelectView(current_guild)
            await interaction.message.edit(embed=embed, view=view)

        elif value == "show_commands":
            embed = discord.Embed(
                title="📘 สมุดคู่มือและบันทึกความสามารถของน้อน Doro 🤖✨",
                description=(
                    "งื้อออ สวัสดีค่าา! หนูคือ **Doro** ยัยบอทสุดน่ารักที่จะมาช่วยดูแลและสร้างสีสันให้เซิร์ฟเวอร์ของทุกคนค๊าา 💕 หนูทำอะไรได้เยอะแยะเลยนะ ลองมาดูกันเยย! \n\n"
                    "**🌸 ความสามารถหลักของหนู (ฟังก์ชันเด่น):**\n"
                    "* **🎛️ แผงควบคุม UI อัจฉริยะ**: กดสั่งงานง่าย ๆ ผ่านปุ่มและเมนู Dropdown ไม่ต้องพิมพ์คำสั่งให้เหนื่อยค๊าา\n"
                    "* **🛡️ ระบบแจกและขอยศสุดตึง**: แอดมินสามารถแจกยศกลุ่มให้เพื่อน ๆ ได้พร้อมกันหลายคนในไม่กี่วินาที! หรือสมาชิกจะกดเลือกรับยศเอง และส่งคำขออ้อน ๆ มาขอยศพิเศษก็ได้น้าา\n"
                    "* **📊 โพลระดมความคิด**: สร้างคำถามและตัวเลือกส่งไปห้องที่ต้องการ พร้อมระบบนับคะแนนและแสดงผลโหวตแบบเรียลไทม์สุดล้ำ\n"
                    "* **🎮 คลังแสงเซิร์ฟเวอร์วี Roblox**: รวมลิงก์ตั๋วเข้า Private Server เกมโปรดของแก๊งเราไว้ที่เดียว แอดมินกดเพิ่ม/ลบเกมจากหน้า UI ได้เลยค๊าา\n"
                    "* **🚫 ศาลเตี้ยโหวตเตะ**: ถ้าเจอคนทำตัวไม่น่ารัก สมาชิกสามารถเปิดวาระโหวตลงมติเพื่อดีดออกจากห้องเสียงหรือเตะออกจากเซิร์ฟเวอร์ร่วมกันได้ค่ะงึมมม!\n"
                    "* **🧹 จัดการห้องแชทความเร็วสูง**: ลบข้อความขยะ หรือสั่งรีเซ็ตชุบชีวิตห้องแชทใหม่ได้ในพริบตาเดียวเลยงับ\n\n"
                    "--------------------------------------------------\n"
                    "**✍️ สรุปคำสั่งพิมพ์ด่วน (Quick Commands):**\n"
                    "🔹 **`doro เมนู` / `doro menu`** : เรียกเปิดแผงควบคุมระบบ UI ทั้งหมดค๊าา\n"
                    "🔹 **`doro ให้ยศ` / `doro addrole`** : หน้าต่างด่วนสำหรับแอดมินแจกยศกลุ่มความเร็วสูง\n"
                    "🔹 **`doro ลบข้อความ <จำนวน>`** : สั่งเคลียร์ข้อความขยะในห้องแชท\n"
                    "🔹 **`doro ค้นหา <ข้อความ>`** : ให้หนูดำน้ำไปหาคลิปบน YouTube มาให้\n"
                    "🔹 **`doro คำสั่งเพลง`** : เปิดดูคู่มือการสั่งเปิดเพลงเพราะ ๆ ฟังกันงับ"
                ),
                color=discord.Color.magenta()
            )
            view = BackToMainOnlyView()
            await interaction.message.edit(embed=embed, view=view)

class BotControlMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BotCommandControlSelect())

    @discord.ui.button(label="ยกเลิก / ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="doro_main_cancel_btn", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except Exception: pass

# 🔄 ฟังก์ชันช่วยพากลับหน้าเมนูหลัก
async def return_to_main_menu(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚙️ Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก (UI Mode)", 
        description="ยินดีต้อนรับสู่ดินแดนแห่งความน่ารักค๊าา! เลือกเมนูด้านล่างนี้เพื่อเปิดใช้งานฟังก์ชันได้ตามใจชอบเลยนะค๊าา ✨", 
        color=0x3498DB
    )
    await interaction.message.edit(embed=embed, view=BotControlMenuView())

class BackToMainOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await return_to_main_menu(interaction)


# ==========================================
# 🎮 ROBLOX UI COMPONENTS
# ==========================================
class AddRobloxServerModal(discord.ui.Modal, title="🎮 เพิ่ม/แก้ไข ลิงก์เซิร์ฟเวอร์วี"):
    def __init__(self):
        super().__init__()
        self.game_id = discord.ui.TextInput(label="รหัสเกม (อังกฤษตัวพิมพ์เล็ก ห้ามเว้นวรรค)", placeholder="เช่น blox_fruits", style=discord.TextStyle.short, required=True)
        self.game_name = discord.ui.TextInput(label="ชื่อเกมที่จะแสดงบนเมนู (ใส่ อีโมจิ ได้)", placeholder="เช่น 🏴‍☠️ Blox Fruits", style=discord.TextStyle.short, required=True)
        self.game_url = discord.ui.TextInput(label="ลิงก์ Private Server (Roblox URL)", placeholder="https://www.roblox.com/...", style=discord.TextStyle.short, required=True)
        self.add_item(self.game_id)
        self.add_item(self.game_name)
        self.add_item(self.game_url)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ คุณไม่มีสิทธิ์จัดการเซิร์ฟเวอร์ค๊าา", ephemeral=True)
        g_id = self.game_id.value.strip().lower().replace(" ", "_")
        current_data = load_roblox_data()
        current_data[g_id] = {"name": self.game_name.value.strip(), "url": self.game_url.value.strip()}
        save_roblox_data(current_data)
        await interaction.response.send_message(f"✅ บันทึกเกมเรียบร้อยค๊าา! กรุณากดเมนูใหม่อีกครั้งเพื่อรีเฟรชรายชื่อนะค๊าา", ephemeral=True)

class DeleteRobloxServerModal(discord.ui.Modal, title="🗑️ ลบลิงก์เซิร์ฟเวอร์วี"):
    def __init__(self):
        super().__init__()
        self.game_id = discord.ui.TextInput(label="พิมพ์รหัสเกมที่ต้องการลบ", placeholder="เช่น blox_fruits", style=discord.TextStyle.short, required=True)
        self.add_item(self.game_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ สิทธิ์ไม่พอค๊าา", ephemeral=True)
        g_id = self.game_id.value.strip().lower()
        current_data = load_roblox_data()
        if g_id in current_data:
            del current_data[g_id]
            save_roblox_data(current_data)
            await interaction.response.send_message("🗑️ ลบลิงก์เกมเรียบร้อยแล้วค๊าา!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่พบรหัสเกมนี้ค๊าา", ephemeral=True)

class RobloxServerSelect(discord.ui.Select):
    def __init__(self):
        current_data = load_roblox_data()
        options = []
        if not current_data:
            options.append(discord.SelectOption(label="ไม่มีเกมในคลังแสง", value="none"))
        else:
            for key, data in current_data.items():
                options.append(discord.SelectOption(label=data["name"][:90], value=key))
        super().__init__(placeholder="🎮 เลือกเกมที่ต้องการเข้าเล่นได้เลยค๊าา...", options=options, custom_id="roblox_select_menu")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        game_data = load_roblox_data().get(self.values[0])
        if game_data:
            embed = discord.Embed(title=f"🚀 ลิงก์เข้าเกม {game_data['name']}", description=f"🔗 ลิงก์: {game_data['url']}", color=0x00FFCC)
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="👉 เข้าเซิร์ฟเวอร์วีที่นี่", url=game_data['url'], style=discord.ButtonStyle.link))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RobloxServerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RobloxServerSelect())
        
    @discord.ui.button(label="➕ เพิ่มเกม", style=discord.ButtonStyle.primary, custom_id="roblox_add_btn", row=1)
    async def add_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddRobloxServerModal())
        
    @discord.ui.button(label="🗑️ ลบเกม", style=discord.ButtonStyle.danger, custom_id="roblox_del_btn", row=1)
    async def delete_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteRobloxServerModal())

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="roblox_back_btn", row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await return_to_main_menu(interaction)

    @discord.ui.button(label="ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="roblox_cancel_btn", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except Exception: pass


# ==========================================
# 🛡️ ROLE SYSTEM & MULTI-ROLE UI
# ==========================================
class RoleSelect(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🎨 เลือกรับยศสุดเลิศของคุณที่นี่เลยน้าา...", options=options, custom_id="role_select_dropdown")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        role = interaction.guild.get_role(int(self.values[0]))
        if role is None: return
        try:
            await interaction.user.add_roles(role)
            await interaction.channel.send(f"✅ ยินดีด้วยน้าา คุณ **{interaction.user.display_name}** ได้รับยศ **{role.name}** เรียบร้อยแล้วค่ะ! 🎉", delete_after=5)
        except discord.Forbidden:
            await interaction.channel.send("❌ น้อน Doro ไม่มีสิทธิ์ให้ยศนี้ง่าา", delete_after=5)

class RemoveRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบยศออกให้หมดเยย", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="role_remove_btn", row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        roles_to_remove = [r for r in interaction.user.roles if r.name != "@everyone" and not r.managed]
        try:
            if roles_to_remove:
                await interaction.user.remove_roles(*roles_to_remove)
            await interaction.channel.send(f"🧹 ลบยศออกจากตัวคุณ **{interaction.user.display_name}** เรียบร้อยแล้วค๊าา!", delete_after=5)
        except discord.Forbidden:
            await interaction.channel.send("❌ หนูลบยศให้ไม่ได้ง่าา", delete_after=5)

class TextInputModal(discord.ui.Modal, title="📝 ส่งเหตุผลอ้อน ๆ เพื่อขอยศพิเศษ"):
    def __init__(self):
        super().__init__()
        self.reason = discord.ui.TextInput(label="เหตุผล/ชื่อยศพิเศษที่อยากได้ค๊าา", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"📨 ส่งคำขอยศพิเศษให้แอดมินพิจารณาแล้วนะค๊าา!", ephemeral=True)

class TextInputButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📝 ส่งคำขอยศพิเศษ", style=discord.ButtonStyle.primary, custom_id="role_request_special_btn", row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TextInputModal())

class RequestRoleView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(guild))
        self.add_item(TextInputButton())
        self.add_item(RemoveRolesButton())

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="role_back_btn", row=2)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await return_to_main_menu(interaction)

    @discord.ui.button(label="ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="role_cancel_btn", row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except Exception: pass

# --- ระบบแจกยศกลุ่มผ่านคำสั่ง doro ให้ยศ ---
class MultiRoleSelectDropdown(discord.ui.Select):
    def __init__(self, guild):
        roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
        options = [discord.SelectOption(label=r.name[:90], value=str(r.id)) for r in roles[:25]]
        super().__init__(placeholder="🛡️ ขั้นตอนที่ 1: เลือกยศที่ต้องการแจก...", options=options, custom_id="multi_role_dropdown")
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_role_id = int(self.values[0])
        await interaction.response.defer()

class MultiMemberSelectDropdown(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="👥 ขั้นตอนที่ 2: เลือกสมาชิกที่ต้องการมอบยศให้ (เลือกได้หลายคน)...", min_values=1, max_values=25, custom_id="multi_member_dropdown")
    async def callback(self, interaction: discord.Interaction):
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
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_role_id or not self.selected_members:
            return await interaction.response.send_message("❌ กรุณาเลือกยศและรายชื่อคนให้ครบก่อนค๊าา!", ephemeral=True)
        await interaction.response.defer()
        target_role = self.guild.get_role(self.selected_role_id)
        if not target_role: return
        success, failed = 0, 0
        for user in self.selected_members:
            m = self.guild.get_member(user.id)
            if m:
                try:
                    await m.add_roles(target_role)
                    success += 1
                except: failed += 1
        embed_res = discord.Embed(title="🛡️ ผลการแจกยศกลุ่มสำเร็จค๊าา", description=f"มอบยศ {target_role.mention} เรียบร้อย!", color=0x2ECC71)
        embed_res.add_field(name="🟢 สำเร็จ", value=f"{success} คน")
        if failed > 0: embed_res.add_field(name="🔴 ล้มเหลว", value=f"{failed} คน")
        try: await interaction.message.delete()
        except: pass
        await interaction.channel.send(embed=embed_res, delete_after=15)
        self.stop()

    @discord.ui.button(label="ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except: pass
        self.stop()


# ==========================================
# 📊 POLL UI SYSTEM
# ==========================================
class AskQuestionTextModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="✍️ รายละเอียดคำถามโพลแสนสนุก")
        self.parent_view = parent_view
        self.question = discord.ui.TextInput(label="หัวข้อคำถามโพลนี้คืออะไรเอ่ย?", style=discord.TextStyle.short, required=True)
        self.choices_input = discord.ui.TextInput(label="ตัวเลือกคำตอบ (แยกด้วยเครื่องหมาย , น้าา)", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.question)
        self.add_item(self.choices_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.question_text = self.question.value.strip()
        self.parent_view.poll_choices = [c.strip() for c in self.choices_input.value.split(",") if c.strip()]
        await interaction.response.send_message(f"✏️ บันทึกคำถามและตัวเลือกเรียบร้อยแล้วค่ะ!", ephemeral=True)

class OpenQuestionModalButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="✏️ กรอกคำถามและตัวเลือกโพล", style=discord.ButtonStyle.primary, custom_id="poll_open_modal_btn", row=2)
        self.parent_view = parent_view
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AskQuestionTextModal(self.parent_view))

class SubmitQuestionButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="🚀 ยืนยันปล่อยโพลเลยค๊าา", style=discord.ButtonStyle.success, custom_id="poll_submit_btn", row=2)
        self.parent_view = parent_view
    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.submit_question(interaction)

class VoteSelect(discord.ui.Select):
    def __init__(self, choices, result_channel_id, all_choices_list):
        opts = [discord.SelectOption(label=opt[:90]) for opt in choices]
        super().__init__(placeholder="🗳️ กดตรงนี้เพื่อโหวตเลือกคำตอบที่คุณชอบเลยน้าา...", options=opts, custom_id="poll_vote_select")
        self.result_channel_id = result_channel_id
        self.all_choices_list = all_choices_list  

    async def callback(self, interaction2: discord.Interaction):
        user = interaction2.user
        poll_msg_id = interaction2.message.id
        user_votes = vote_records.setdefault(poll_msg_id, {})
        user_votes[user.id] = self.values[0]
        
        summary_text = ""
        for ans in self.all_choices_list:
            voters = [interaction2.guild.get_member(uid).display_name for uid, a in user_votes.items() if a == ans and interaction2.guild.get_member(uid)]
            summary_text += f"**{ans}**: {len(voters)} คะแนนเสียง\n"
            if voters: summary_text += "     ↳ " + ", ".join(voters) + "\n"

        result_channel = interaction2.guild.get_channel(self.result_channel_id)
        if result_channel:
            embed_res = discord.Embed(title="📊 ผลโหวตเรียลไทม์", description=summary_text, color=0x87CEEB)
            res_msg_id = poll_result_messages.get(poll_msg_id)
            if res_msg_id:
                try:
                    old_msg = await result_channel.fetch_message(res_msg_id)
                    await old_msg.edit(embed=embed_res)
                except:
                    new_res_msg = await result_channel.send(embed=embed_res)
                    poll_result_messages[poll_msg_id] = new_res_msg.id
            else:
                new_res_msg = await result_channel.send(embed=embed_res)
                poll_result_messages[poll_msg_id] = new_res_msg.id
        await interaction2.response.send_message("✅ บันทึกคะแนนเสียงแล้วค่ะ!", ephemeral=True, delete_after=2)

class DeletePublicPollButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="ลบโพลนี้ทิ้ง (แอดมิน)", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="poll_delete_public_btn")
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if interaction.user.guild_permissions.manage_messages:
            try: await interaction.message.delete()
            except: pass

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
        
        self.select_question_channel = discord.ui.Select(placeholder="📢 1. เลือกห้องที่จะปล่อยโพล", options=channel_options, custom_id="poll_select_target_channel", row=0)
        self.select_question_channel.callback = self.on_select_target_channel
        self.add_item(self.select_question_channel)

        self.select_result_channel = discord.ui.Select(placeholder="📊 2. เลือกห้องที่จะให้สรุปคะแนน", options=channel_options, custom_id="poll_select_result_channel", row=1)
        self.select_result_channel.callback = self.on_select_result_channel
        self.add_item(self.select_result_channel)

        self.add_item(OpenQuestionModalButton(self))
        self.add_item(SubmitQuestionButton(self))

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="poll_back_btn", row=3)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await return_to_main_menu(interaction)

    @discord.ui.button(label="ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="poll_cancel_btn", row=3)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except Exception: pass

    async def on_select_target_channel(self, interaction: discord.Interaction):
        self.target_channel_id = int(self.select_question_channel.values[0])
        await interaction.response.defer()  
    async def on_select_result_channel(self, interaction: discord.Interaction):
        self.result_channel_id = int(self.select_result_channel.values[0])
        await interaction.response.defer()

    async def submit_question(self, interaction: discord.Interaction):
        if not self.question_text or not self.poll_choices or not self.target_channel_id or not self.result_channel_id:
            return await interaction.response.send_message("❗ กรอกข้อมูลให้ครบถ้วนก่อนน้าา", ephemeral=True)
        q_channel = self.guild.get_channel(self.target_channel_id)
        if q_channel:
            embed = discord.Embed(title=f"❓ โพล: {self.question_text}", color=discord.Color.pink())
            vote_view = discord.ui.View(timeout=None)
            vote_view.add_item(VoteSelect(self.poll_choices, self.result_channel_id, self.poll_choices))
            vote_view.add_item(DeletePublicPollButton())
            sent_msg = await q_channel.send(embed=embed, view=vote_view)
            vote_records[sent_msg.id] = {}
            await interaction.response.send_message("✅ ปล่อยโพลเรียบร้อย!", ephemeral=True)


# ==========================================
# 🚫 VOTE KICK SYSTEM 
# ==========================================
class MemberSelect(discord.ui.UserSelect):
    def __init__(self, guild):
        super().__init__(placeholder="👤 จิ้มเลือกคนที่ไม่น่ารักตรงนี้เลยงับ...", min_values=1, max_values=1, custom_id="kick_member_select")
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        target_member = self.values[0]
        if target_member.id == interaction.user.id or target_member.bot:
            return await interaction.followup.send("❌ เลือกโหวตเตะคนนี้ไม่ได้ค๊าา!", ephemeral=True)

        member_obj = interaction.guild.get_member(target_member.id)
        if not member_obj: return

        online_members = [m for m in self.guild.members if m.status != discord.Status.offline and not m.bot]
        required_votes = max(2, len(online_members) // 2 + 1)
        view = VoteKickTypeView(member_obj, required_votes)
        
        embed = discord.Embed(
            title="🛠️ ตั้งค่าบทลงทัณฑ์ศาลเตี้ย",
            description=f"เป้าหมาย: {member_obj.mention}\nโปรดเลือกประเภทบทลงโทษด้านล่างนี้เลยค๊าา!",
            color=0xF1C40F
        )
        await interaction.message.edit(embed=embed, view=view)

class MemberSelectView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=60)
        self.add_item(MemberSelect(guild))

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="kick_select_back_btn", row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await return_to_main_menu(interaction)

    @discord.ui.button(label="ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="kick_select_cancel_btn", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except Exception: pass

class KickTypeButton(discord.ui.Button):
    def __init__(self, target: discord.Member, kick_type: str, required_votes: int):
        label_str = "🔊 เตะออกจากห้องเสียง" if kick_type == "voice" else "💥 ดีดออกจากเซิร์ฟเวอร์"
        style = discord.ButtonStyle.primary if kick_type == "voice" else discord.ButtonStyle.danger
        super().__init__(label=label_str[:45], style=style, custom_id=f"kick_btn_{kick_type}_{target.id}")
        self.target = target
        self.kick_type = kick_type
        self.required_votes = required_votes

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except: pass
        view = VoteProgressView(self.target, self.kick_type, self.required_votes)
        embed = discord.Embed(
            title=f"🚨 เปิดวาระลงคะแนนโหวตขับไล่ขั้นเด็ดขาด!",
            description=f"เป้าหมาย: {self.target.mention}\nบทลงโทษ: **{self.label}**\nเกณฑ์คะแนนเสียงที่ต้องการ: **{self.required_votes}** โหวต",
            color=discord.Color.red()
        )
        embed.add_field(name="ตารางคะแนนในขณะนี้งับ", value=f"🟢 เห็นด้วย (Vote): 0/{self.required_votes}")
        await interaction.channel.send(embed=embed, view=view)

class VoteKickTypeView(discord.ui.View):
    def __init__(self, target: discord.Member, required_votes: int):
        super().__init__(timeout=60)
        self.add_item(KickTypeButton(target, "voice", required_votes))
        self.add_item(KickTypeButton(target, "server", required_votes))

    @discord.ui.button(label="🔙 ย้อนกลับ", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await return_to_main_menu(interaction)

    @discord.ui.button(label="ปิดเมนู", style=discord.ButtonStyle.danger, emoji="🔴", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try: await interaction.message.delete()
        except Exception: pass

class VoteProgressView(discord.ui.View):
    def __init__(self, target: discord.Member, kick_type: str, required_votes: int):
        super().__init__(timeout=120)
        self.target = target
        self.kick_type = kick_type
        self.required_votes = required_votes
        self.voters = set()

    @discord.ui.button(label="🟢 เห็นด้วย ลุยเยย! (Vote)", style=discord.ButtonStyle.success, emoji="👍")
    async def vote_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters or interaction.user.id == self.target.id:
            return await interaction.response.send_message("❌ ไม่สามารถใช้สิทธิ์โหวตได้ค๊าา!", ephemeral=True)
        self.voters.add(interaction.user.id)
        current_votes = len(self.voters)
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="ตารางคะแนนในขณะนี้งับ", value=f"🟢 เห็นด้วย (Vote): {current_votes}/{self.required_votes}")

        if current_votes >= self.required_votes:
            try: await interaction.message.delete()
            except: pass
            try:
                if self.kick_type == "voice" and self.target.voice and self.target.voice.channel:
                    await self.target.move_to(None)
                    await interaction.channel.send(f"🔨 มติเสียงส่วนใหญ่ ดีดสาย {self.target.mention} ออกจากห้องเสียงแล้วค๊าา!")
                elif self.kick_type == "server":
                    await self.target.kick(reason="ผลโหวตเตะ")
                    await interaction.channel.send(f"💥 ประชามติเห็นพ้อง ดีด {self.target.mention} ปลิวออกจากเซิร์ฟแล้วค๊าา~")
            except: await interaction.channel.send("❌ หนูขาดสิทธิ์ในการเตะสมาชิกคนนี้ค่ะ")
            self.stop()
        else:
            await interaction.response.edit_message(embed=embed, view=self)


# ==========================================
# ⚙️ SYSTEM CORE & EVENTS
# ==========================================
@bot.event
async def on_ready():
    logger.info(f"Doro COMPLETE UI ENGINE IS ACTIVE AS {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    msg = message.content.strip()
    lower_msg = msg.lower()
    parts = msg.split()

    if lower_msg in custom_responses:
        await message.channel.send(custom_responses[lower_msg])
        return

    # คำสั่งเรียกแผงควบคุม UI หลัก
    is_menu_cmd = False
    for keyword in ["เมนู", "เมณู", "เเมนู", "menu", "munu"]:
        if f"doro {keyword}" in lower_msg or f"doro{keyword}" in lower_msg:
            is_menu_cmd = True
            break
    if is_menu_cmd:
        try: await message.delete() 
        except: pass
        embed = discord.Embed(title="⚙️ Doro แผงควบคุมระบบอัจฉริยะสุดน่ารัก (UI Mode)", description="ยินดีต้อนรับสู่ดินแดนแห่งความน่ารักค๊าา! เลือกเมนูด้านล่างนี้เพื่อทำงานได้เลยงับ ✨", color=0x3498DB)
        await message.channel.send(embed=embed, view=BotControlMenuView())
        return

    # คำสั่งด่วน: แจกยศกลุ่มด้วย UI
    is_add_role_cmd = False
    for keyword in ["ให้ยศ", "แจกยศ", "addrole"]:
        if f"doro {keyword}" in lower_msg or f"doro{keyword}" in lower_msg:
            is_add_role_cmd = True
            break
    if is_add_role_cmd:
        try: await message.delete()
        except: pass
        if not (message.author.guild_permissions.manage_roles or message.author.guild_permissions.administrator):
            return await message.channel.send("❌ สิทธิ์ของคุณไม่พอที่จะใช้ระบบแจกยศกลุ่มค๊าา", delete_after=5)
        embed = discord.Embed(title="🛡️ ระบบมอบยศกลุ่มอัจฉริยะ (UI High-Speed)", description="โปรดเลือกยศและสมาชิกที่ต้องการมอบยศให้ได้เลยค๊าา เมนูจะหายไปหลังใช้เสร็จค่ะ ✨", color=0x2ECC71)
        await message.channel.send(embed=embed, view=MultiRoleManagementView(message.guild))
        return

    # ฟังก์ชันลบข้อความด่วน
    if (f"doro ลบข้อความ" in lower_msg or f"doro clear" in lower_msg) and len(parts) >= 3:
        if not message.author.guild_permissions.manage_messages: return
        try:
            deleted = await message.channel.purge(limit=int(parts[2]) + 1)
            await message.channel.send(f"🧹 เสกข้อความหายวับไป {len(deleted)-1} ข้อความแล้วค่ะ!", delete_after=3)
        except: pass
        return

bot.run(DISCORD_TOKEN)
