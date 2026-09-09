import os
import io
import math
import asyncio
import threading
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
from discord.ui import Button, View
import google.generativeai as genai

# ==========================================
# 1. TÍCH HỢP GEMINI AI & DISCORD SETUP
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-3.6-flash')
else:
    ai_model = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

# Web Server giữ Bot 24/7 (Deploy Render/Heroku)
app = Flask(__name__)
@app.route('/')
def home(): return "Discord Military & Logic Engine Bot Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# ==========================================
# 2. KHUÔN MẪU HỆ THỐNG LOGIC & GIÁP (ENGINE)
# ==========================================
GRID_SIZE = 10

# Khai báo loại khối (Block Types)
AIR = 0
STEEL_ARMOR = 1       # Giáp thép (100mm)
COMPOSITE_ARMOR = 2   # Giáp phức hợp (250mm)
ERA_ARMOR = 3         # Giáp phản ứng nổ ERA (Chống đạn HEAT)
ENGINE = 4            # Động cơ xe
AMMO_RACK = 5         # Hầm đạn (Trúng là nổ)

# Cổng Logic Nâng Cấp
LOGIC_AND = 10
LOGIC_OR = 11
LOGIC_NOT = 12
LOGIC_NAND = 13
LOGIC_NOR = 14
LOGIC_XOR = 15
LOGIC_SR_LATCH = 16   # Chốt SR (Lưu giữ trạng thái)
SENSOR_LASER = 20     # Cảm biến Laser

COLOR_MAP = {
    AIR: (30, 30, 35),
    STEEL_ARMOR: (120, 120, 130),
    COMPOSITE_ARMOR: (70, 100, 140),
    ERA_ARMOR: (200, 100, 30),
    ENGINE: (220, 180, 50),
    AMMO_RACK: (220, 40, 40),
    LOGIC_AND: (0, 180, 200),
    LOGIC_OR: (150, 0, 200),
    LOGIC_NOT: (200, 200, 0),
    LOGIC_NAND: (0, 100, 200),
    LOGIC_NOR: (100, 0, 150),
    LOGIC_XOR: (200, 0, 100),
    LOGIC_SR_LATCH: (0, 200, 150),
    SENSOR_LASER: (250, 50, 50)
}

class Block:
    def __init__(self, b_type=AIR):
        self.type = b_type
        self.thickness_mm = 100 if b_type == STEEL_ARMOR else (250 if b_type == COMPOSITE_ARMOR else 0)
        self.output_signal = False
        self.latch_state = False  # Dùng riêng cho SR-Latch
        self.health = 100

class SandboxWorld:
    def __init__(self):
        self.grid = [[[Block(AIR) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.current_slice = 0

    def set_block(self, x, y, z, b_type):
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE and 0 <= z < GRID_SIZE:
            self.grid[x][y][z] = Block(b_type)

    def update_logic(self):
        """Hệ thống cập nhật tín hiệu vi mạch Logic Gates Nâng Cấp"""
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    b = self.grid[x][y][z]
                    in1 = self.grid[x-1][y][z].output_signal if x > 0 else False
                    in2 = self.grid[x+1][y][z].output_signal if x < GRID_SIZE-1 else False

                    if b.type == LOGIC_AND: b.output_signal = in1 and in2
                    elif b.type == LOGIC_OR: b.output_signal = in1 or in2
                    elif b.type == LOGIC_NOT: b.output_signal = not in1
                    elif b.type == LOGIC_NAND: b.output_signal = not (in1 and in2)
                    elif b.type == LOGIC_NOR: b.output_signal = not (in1 or in2)
                    elif b.type == LOGIC_XOR: b.output_signal = in1 != in2
                    elif b.type == LOGIC_SR_LATCH:
                        # in1 = Set (S), in2 = Reset (R)
                        if in1: b.latch_state = True
                        elif in2: b.latch_state = False
                        b.output_signal = b.latch_state
                    elif b.type == SENSOR_LASER:
                        # Laser quét theo trục X
                        b.output_signal = any(self.grid[sx][y][z].type != AIR for sx in range(x + 1, GRID_SIZE))

    def render_to_image(self):
        """Vẽ Ma trận 2D tầng hiện tại ra Image Buffer để gửi lên Discord"""
        cell_sz = 40
        img_sz = GRID_SIZE * cell_sz
        img = Image.new("RGB", (img_sz, img_sz), (30, 30, 35))
        draw = ImageDraw.Draw(img)

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                b = self.grid[x][y][self.current_slice]
                color = COLOR_MAP.get(b.type, (30, 30, 35))
                
                # Nếu cổng logic đang BẬT -> làm sáng màu lên
                if b.output_signal and b.type >= 10:
                    color = tuple(min(255, c + 80) for c in color)

                rx, ry = x * cell_sz, y * cell_sz
                draw.rectangle([rx, ry, rx + cell_sz - 2, ry + cell_sz - 2], fill=color)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

# Quản lý Sandbox theo Guild ID
guild_sandboxes = {}

# ==========================================
# 3. INTERACTIVE DISCORD UI (UI CONTROLS)
# ==========================================
class SandboxControlView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="➕ Đặt Giáp Thép", style=discord.ButtonStyle.primary, row=0)
    async def add_armor(self, interaction: discord.Interaction, button: Button):
        world = guild_sandboxes[self.guild_id]
        world.set_block(3, 3, world.current_slice, STEEL_ARMOR)
        world.set_block(4, 3, world.current_slice, COMPOSITE_ARMOR)
        world.set_block(5, 3, world.current_slice, ENGINE)
        await self.update_map(interaction, "🛡️ Đã đặt Giáp Thép + Động Cơ mẫu!")

    @discord.ui.button(label="⚡ Đặt Cổng Logic", style=discord.ButtonStyle.success, row=0)
    async def add_logic(self, interaction: discord.Interaction, button: Button):
        world = guild_sandboxes[self.guild_id]
        world.set_block(1, 5, world.current_slice, SENSOR_LASER)
        world.set_block(2, 5, world.current_slice, LOGIC_XOR)
        await self.update_map(interaction, "⚡ Đã đặt Laser + Cổng XOR!")

    @discord.ui.button(label="🚀 Bắn Đạn APFSDS", style=discord.ButtonStyle.danger, row=1)
    async def fire_shell(self, interaction: discord.Interaction, button: Button):
        world = guild_sandboxes[self.guild_id]
        logs = []
        pen = 350
        hit = False

        for x in range(GRID_SIZE):
            b = world.grid[x][3][world.current_slice]
            if b.type != AIR:
                hit = True
                if pen >= b.thickness_mm:
                    pen -= b.thickness_mm
                    b.type = AIR # Phá hủy khối
                    logs.append(f"💥 Xuyên qua giáp tại X={x}! Dư {pen}mm pen.")
                else:
                    logs.append(f"🛡️ Đạn bị cản lại tại X={x}!")
                    break

        msg = "\n".join(logs) if hit else "💨 Đạn bay trật mục tiêu!"
        await self.update_map(interaction, f"**KẾT QUẢ BẮN:**\n{msg}")

    @discord.ui.button(label="🔄 Chuyển Tầng Mặt Cắt", style=discord.ButtonStyle.secondary, row=1)
    async def change_layer(self, interaction: discord.Interaction, button: Button):
        world = guild_sandboxes[self.guild_id]
        world.current_slice = (world.current_slice + 1) % GRID_SIZE
        await self.update_map(interaction, f"🔄 Đã chuyển sang Tầng Z={world.current_slice}")

    async def update_map(self, interaction: discord.Interaction, status_text: str):
        world = guild_sandboxes[self.guild_id]
        world.update_logic()
        buf = world.render_to_image()
        file = discord.File(fp=buf, filename="sandbox.png")

        embed = discord.Embed(title="🎮 SANDBOX MILITARY & LOGIC SIMULATOR", description=status_text, color=0x2b2d31)
        embed.set_image(url="attachment://sandbox.png")
        embed.set_footer(text=f"Tầng mặt cắt hiện tại: Z={world.current_slice} / {GRID_SIZE-1}")

        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

# ==========================================
# 4. BOT COMMANDS & GEMINI AI INTEGRATION
# ==========================================
@bot.command(name="sandbox", aliases=["game", "sim"])
async def start_sandbox(ctx):
    """Khởi tạo Bàn chơi Sandbox tương tác"""
    guild_sandboxes[ctx.guild.id] = SandboxWorld()
    world = guild_sandboxes[ctx.guild.id]

    buf = world.render_to_image()
    file = discord.File(fp=buf, filename="sandbox.png")
    
    embed = discord.Embed(title="🎮 SANDBOX MILITARY & LOGIC SIMULATOR", description="Bấm các nút bên dưới để đặt giáp, lắp mạch logic hoặc thử nghiệm đạn bắn!", color=0x2b2d31)
    embed.set_image(url="attachment://sandbox.png")

    view = SandboxControlView(ctx.guild.id)
    await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="ai", aliases=["ask", "chat"])
async def ai_chat(ctx, *, prompt: str = None):
    """Hỏi đáp AI Gemini về Đạn đạo, Giáp xe tăng & Mạch Logic"""
    if not ai_model:
        await ctx.send("❌ Chưa cấu hình `GEMINI_API_KEY` trong Environment Variables!")
        return

    if not prompt:
        await ctx.send("❌ Nam ơi, cậu hãy nhập câu hỏi! Ví dụ: `!ai So sánh giáp Composite và ERA`")
        return

    async with ctx.typing():
        try:
            sys_prompt = f"Bạn là một chuyên gia quân sự và kỹ sư điện tử lấy cảm hứng từ nhân vật Tony stark và Harry osborn từ spiderman bởi Sam raimi. Hãy trả lời ngắn gọn, chính xác câu hỏi sau: {prompt}"
            response = await asyncio.to_thread(ai_model.generate_content, sys_prompt)
            
            embed = discord.Embed(title="🤖 GEMINI MILITARY AI", description=response.text, color=discord.Color.blue())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Lỗi xử lý AI: {e}")

# ==========================================
# 5. KHỞI CHẠY BOT
# ==========================================
if __name__ == "__main__":
    # Chạy Flask Server trong Thread riêng
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Lỗi: Chưa thiết lập DISCORD_TOKEN!")
