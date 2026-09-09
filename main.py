import os
import io
import math
import asyncio
import threading
import base64
import json
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
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

app = Flask(__name__)
@app.route('/')
def home(): return "Ultimate Logic & Blueprint Sandbox Bot Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# ==========================================
# 2. HỆ THỐNG KHỐI TỔNG HỢP (PC, BABFT, INDUSTRIALIST)
# ==========================================
GRID_SIZE = 10

# Phân loại ID Khối
AIR = 0
# Vật liệu / Giáp & Cấu trúc (Plane Crazy & Build a boat)
STEEL_ARMOR = 1
WOOD = 2          # Gỗ (BABFT: Nhẹ, dễ vỡ)
TITANIUM = 3      # Titan (PC/BABFT: Siêu bền, nhẹ)
PLASTIC = 4       # Nhựa (Cực nhẹ, làm phao/cân bằng)
GLUE = 5          # Keo dán (BABFT: Kết nối cơ khí)
ENGINE = 6
AMMO_RACK = 7

# Khối PvP & Cơ khí động lực
TNT = 10
PNEUMATIC = 11    # Piston khí nén
PROPELLER = 12    # Cánh quạt
ROCKET_ENGINE = 13# Tên lửa đẩy
WING = 14         # Cánh máy bay
CANNON = 15       # Pháo
GYRO = 16         # Con quay hồi chuyển
COORD_READER = 17 # Đọc tọa độ X,Y

# Industrialist Logic Gates & Advanced Electronics
LOGIC_AND = 20
LOGIC_OR = 21
LOGIC_NOT = 22
LOGIC_NAND = 23
LOGIC_NOR = 24
LOGIC_XOR = 25
LOGIC_SR_LATCH = 26
LOGIC_CLOCK = 27
LOGIC_DELAY = 28
LOGIC_TOGGLE = 29
LOGIC_BUFFER = 30
LOGIC_PULSE = 31
LOGIC_COUNTER = 32
LOGIC_GREATER = 33
LOGIC_LESS = 34
LOGIC_MUX = 35
SENSOR_LASER = 36

BLOCK_INFO = {
    AIR: {"color": (25, 25, 30), "label": "", "mass": 0},
    STEEL_ARMOR: {"color": (120, 120, 130), "label": "ST", "mass": 500},
    WOOD: {"color": (160, 110, 60), "label": "WD", "mass": 80},
    TITANIUM: {"color": (200, 210, 220), "label": "TI", "mass": 250},
    PLASTIC: {"color": (230, 230, 240), "label": "PL", "mass": 30},
    GLUE: {"color": (255, 220, 100), "label": "GL", "mass": 20},
    ENGINE: {"color": (220, 180, 50), "label": "ENG", "mass": 800},
    AMMO_RACK: {"color": (220, 40, 40), "label": "AMG", "mass": 300},
    TNT: {"color": (255, 69, 0), "label": "TNT", "mass": 150},
    PNEUMATIC: {"color": (100, 200, 200), "label": "PNE", "mass": 200},
    PROPELLER: {"color": (180, 200, 220), "label": "PRP", "mass": 90},
    ROCKET_ENGINE: {"color": (255, 140, 0), "label": "ROC", "mass": 350},
    WING: {"color": (200, 220, 255), "label": "WNG", "mass": 40},
    CANNON: {"color": (80, 80, 80), "label": "GUN", "mass": 600},
    GYRO: {"color": (150, 100, 250), "label": "GYR", "mass": 150},
    COORD_READER: {"color": (220, 220, 100), "label": "POS", "mass": 30},
    LOGIC_AND: {"color": (0, 180, 200), "label": "&", "mass": 10},
    LOGIC_OR: {"color": (150, 0, 200), "label": "≥1", "mass": 10},
    LOGIC_NOT: {"color": (200, 200, 0), "label": "!", "mass": 10},
    LOGIC_NAND: {"color": (0, 100, 200), "label": "!&", "mass": 10},
    LOGIC_NOR: {"color": (100, 0, 150), "label": "!|", "mass": 10},
    LOGIC_XOR: {"color": (200, 0, 100), "label": "X", "mass": 10},
    LOGIC_SR_LATCH: {"color": (0, 200, 150), "label": "SR", "mass": 10},
    LOGIC_CLOCK: {"color": (255, 150, 0), "label": "CLK", "mass": 10},
    LOGIC_DELAY: {"color": (100, 150, 100), "label": "DLY", "mass": 10},
    LOGIC_TOGGLE: {"color": (200, 50, 200), "label": "TGL", "mass": 10},
    LOGIC_BUFFER: {"color": (50, 150, 200), "label": "BUF", "mass": 10},
    LOGIC_PULSE: {"color": (250, 100, 150), "label": "PLS", "mass": 10},
    LOGIC_COUNTER: {"color": (150, 150, 50), "label": "CNT", "mass": 10},
    LOGIC_GREATER: {"color": (100, 200, 50), "label": ">", "mass": 10},
    LOGIC_LESS: {"color": (200, 100, 50), "label": "<", "mass": 10},
    LOGIC_MUX: {"color": (100, 50, 200), "label": "MUX", "mass": 10},
    SENSOR_LASER: {"color": (250, 50, 50), "label": "LAS", "mass": 20}
}

NAME_MAP = {
    "steel": STEEL_ARMOR, "wood": WOOD, "titanium": TITANIUM, "plastic": PLASTIC, "glue": GLUE,
    "engine": ENGINE, "ammo": AMMO_RACK, "tnt": TNT, "pneumatic": PNEUMATIC, "piston": PNEUMATIC,
    "propeller": PROPELLER, "rocket": ROCKET_ENGINE, "wing": WING, "cannon": CANNON, "gyro": GYRO,
    "pos": COORD_READER, "coord": COORD_READER, "air": AIR, "xoa": AIR,
    "and": LOGIC_AND, "or": LOGIC_OR, "not": LOGIC_NOT, "nand": LOGIC_NAND, "nor": LOGIC_NOR,
    "xor": LOGIC_XOR, "latch": LOGIC_SR_LATCH, "clock": LOGIC_CLOCK, "delay": LOGIC_DELAY,
    "toggle": LOGIC_TOGGLE, "buffer": LOGIC_BUFFER, "pulse": LOGIC_PULSE, "counter": LOGIC_COUNTER,
    "greater": LOGIC_GREATER, "less": LOGIC_LESS, "mux": LOGIC_MUX, "laser": SENSOR_LASER
}

class Block:
    def __init__(self, b_type=AIR):
        self.type = b_type
        self.output_signal = False
        self.prev_signal = False
        self.latch_state = False
        self.counter_value = 0
        self.mass = BLOCK_INFO.get(b_type, BLOCK_INFO[AIR])["mass"]

class SandboxWorld:
    def __init__(self):
        self.grid = [[[Block(AIR) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.current_slice = 0
        self.tick_count = 0
        self.logs = []

    def set_block(self, x, y, z, b_type):
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE and 0 <= z < GRID_SIZE:
            self.grid[x][y][z] = Block(b_type)

    def clear_grid(self):
        self.__init__()

    def export_code(self):
        """Mã hóa toàn bộ lưới thành chuỗi Blueprint Code ngắn gọn"""
        data = []
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    b_type = self.grid[x][y][z].type
                    if b_type != AIR:
                        data.append([x, y, z, b_type])
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    def import_code(self, code_str):
        """Giải mã chuỗi Blueprint Code để nạp vào lưới"""
        try:
            decoded_bytes = base64.b64decode(code_str.encode('utf-8'))
            data = json.loads(decoded_bytes.decode('utf-8'))
            self.clear_grid()
            for item in data:
                x, y, z, b_type = item
                self.set_block(x, y, z, b_type)
            return True
        except Exception:
            return False

    def update_logic_step(self):
        self.tick_count += 1
        self.logs.clear()

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    self.grid[x][y][z].prev_signal = self.grid[x][y][z].output_signal

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    b = self.grid[x][y][z]
                    in1 = self.grid[x-1][y][z].prev_signal if x > 0 else False
                    in2 = self.grid[x+1][y][z].prev_signal if x < GRID_SIZE-1 else False

                    if b.type == LOGIC_AND: b.output_signal = in1 and in2
                    elif b.type == LOGIC_OR: b.output_signal = in1 or in2
                    elif b.type == LOGIC_NOT: b.output_signal = not in1
                    elif b.type == LOGIC_NAND: b.output_signal = not (in1 and in2)
                    elif b.type == LOGIC_NOR: b.output_signal = not (in1 or in2)
                    elif b.type == LOGIC_XOR: b.output_signal = in1 != in2
                    elif b.type == LOGIC_CLOCK: b.output_signal = (self.tick_count % 2 == 0)
                    elif b.type in [LOGIC_DELAY, LOGIC_BUFFER]: b.output_signal = in1
                    elif b.type == LOGIC_PULSE:
                        b.output_signal = in1 and not self.grid[x-1][y][z].prev_signal if x > 0 else False
                    elif b.type == LOGIC_COUNTER:
                        if in1 and not self.grid[x-1][y][z].prev_signal if x > 0 else False:
                            b.counter_value = (b.counter_value + 1) % 10
                        b.output_signal = (b.counter_value > 0)
                    elif b.type == LOGIC_GREATER: b.output_signal = int(in1) > int(in2)
                    elif b.type == LOGIC_LESS: b.output_signal = int(in1) < int(in2)
                    elif b.type == LOGIC_MUX: b.output_signal = in2 if in1 else False
                    elif b.type == LOGIC_TOGGLE:
                        curr_in1 = self.grid[x-1][y][z].output_signal if x > 0 else False
                        prev_in1 = self.grid[x-1][y][z].prev_signal if x > 0 else False
                        if curr_in1 and not prev_in1: b.latch_state = not b.latch_state
                        b.output_signal = b.latch_state
                    elif b.type == COORD_READER:
                        b.output_signal = True
                        self.logs.append(f"📍 Tọa độ thiết bị POS: X={x}, Y={y}, Z={z}")
                    elif b.type == TNT:
                        if in1:
                            self.logs.append(f"💥 TNT phát nổ tại X={x}, Y={y}, Z={z}!")
                            self.grid[x][y][z] = Block(AIR)
                    elif b.type == CANNON:
                        if in1:
                            self.logs.append(f"🔥 Pháo tại X={x}, Y={y} khai hỏa!")
                            b.output_signal = True
                        else:
                            b.output_signal = False

    def render_blueprint_image(self):
        """Vẽ bản vẽ phong cách bản thảo Blueprint xanh kỹ thuật công nghiệp"""
        cell_sz = 50
        img_sz = GRID_SIZE * cell_sz
        # Màu nền xanh Blueprint cổ điển công nghiệp
        img = Image.new("RGB", (img_sz, img_sz), (15, 42, 74))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()

        # Vẽ lưới caro bản vẽ kỹ thuật mờ
        for i in range(0, img_sz, cell_sz):
            draw.line([(i, 0), (i, img_sz)], fill=(30, 70, 110), width=1)
            draw.line([(0, i), (img_sz, i)], fill=(30, 70, 110), width=1)

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                b = self.grid[x][y][self.current_slice]
                if b.type != AIR:
                    info = BLOCK_INFO.get(b.type, BLOCK_INFO[AIR])
                    label = info["label"]
                    rx, ry = x * cell_sz, y * cell_sz
                    
                    # Vẽ khối dạng phác thảo kỹ thuật bản vẽ
                    draw.rectangle([rx + 4, ry + 4, rx + cell_sz - 4, ry + cell_sz - 4], 
                                   fill=(25, 60, 100), outline=(100, 180, 255), width=2)
                    if label:
                        draw.text((rx + 14, ry + 16), label, fill=(255, 255, 255), font=font)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def render_standard_image(self):
        cell_sz = 45
        img_sz = GRID_SIZE * cell_sz
        img = Image.new("RGB", (img_sz, img_sz), (20, 20, 25))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                b = self.grid[x][y][self.current_slice]
                info = BLOCK_INFO.get(b.type, BLOCK_INFO[AIR])
                color = info["color"]
                label = info["label"]

                if b.output_signal and (b.type >= 20 or b.type in [CANNON, COORD_READER]):
                    color = tuple(min(255, c + 90) for c in color)

                rx, ry = x * cell_sz, y * cell_sz
                draw.rectangle([rx + 1, ry + 1, rx + cell_sz - 2, ry + cell_sz - 2], fill=color, outline=(50, 50, 60))

                if label:
                    text_color = (255, 255, 255) if b.type != STEEL_ARMOR else (10, 10, 10)
                    draw.text((rx + 8, ry + 12), label, fill=text_color, font=font)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

guild_sandboxes = {}
def get_world(guild_id):
    if guild_id not in guild_sandboxes: guild_sandboxes[guild_id] = SandboxWorld()
    return guild_sandboxes[guild_id]

async def auto_delete_cmd(ctx):
    try: await ctx.message.delete()
    except: pass

# ==========================================
# 3. DISCORD COMMANDS
# ==========================================
@bot.command(name="map", aliases=["show", "grid"])
async def show_map(ctx):
    await auto_delete_cmd(ctx)
    world = get_world(ctx.guild.id)
    buf = world.render_standard_image()
    file = discord.File(fp=buf, filename="sandbox.png")
    
    embed = discord.Embed(title="⚙️ LOGIC GATES & SANDBOX ENGINE", color=0x2b2d31)
    embed.set_image(url="attachment://sandbox.png")
    embed.set_footer(text=f"Tầng Z={world.current_slice} | Tick: {world.tick_count}")
    await ctx.send(embed=embed, file=file)

@bot.command(name="set")
async def set_block_cmd(ctx, block_name: str = None, x: int = None, y: int = None, z: int = None):
    await auto_delete_cmd(ctx)
    if not block_name or x is None or y is None: return

    world = get_world(ctx.guild.id)
    target_z = z if z is not None else world.current_slice
    b_type = NAME_MAP.get(block_name.lower())
    
    if b_type is not None:
        world.set_block(x, y, target_z, b_type)
        await show_map(ctx)

@bot.command(name="step", aliases=["tick"])
async def step_logic(ctx, steps: int = 1):
    await auto_delete_cmd(ctx)
    world = get_world(ctx.guild.id)
    for _ in range(min(steps, 10)): world.update_logic_step()
    
    buf = world.render_standard_image()
    file = discord.File(fp=buf, filename="sandbox.png")
    desc = "\n".join(world.logs) if world.logs else "Mạch logic đã xử lý xong chu kỳ nhịp."
    
    embed = discord.Embed(title=f"⏱️ MẠCH LOGIC TICK ({steps} steps)", description=desc, color=0x00ff00)
    embed.set_image(url="attachment://sandbox.png")
    await ctx.send(embed=embed, file=file)

@bot.command(name="save")
async def save_blueprint(ctx):
    """Xuất mã code lưu trữ bản vẽ hiện tại"""
    await auto_delete_cmd(ctx)
    world = get_world(ctx.guild.id)
    code = world.export_code()
    
    embed = discord.Embed(title="💾 LƯU BLUEPRINT THÀNH CÔNG", description=f"Mã code bản vẽ của Nam đây, hãy copy lại nhé:\n```{code}```", color=0x3498db)
    embed.set_footer(text="Dùng lệnh !blueprint <code_save> để khôi phục lại mạch!")
    await ctx.send(embed=embed)

@bot.command(name="blueprint", aliases=["load", "bp"])
async def load_blueprint(ctx, *, code_str: str = None):
    """Nạp mã code Blueprint hoặc tạo bản vẽ kỹ thuật AI"""
    await auto_delete_cmd(ctx)
    world = get_world(ctx.guild.id)
    
    if not code_str:
        await ctx.send("❌ Nam chưa nhập mã code Blueprint! Ví dụ: `!blueprint eyJ...`")
        return

    # Kiểm tra nếu là mã save hợp lệ thì Load, nếu là mô tả chuỗi thì dùng AI render ảnh kỹ thuật blueprint
    success = world.import_code(code_str)
    if success:
        buf = world.render_standard_image()
        file = discord.File(fp=buf, filename="sandbox.png")
        embed = discord.Embed(title="📂 NẠP BLUEPRINT THÀNH CÔNG", description="Mạch logic và thiết kế đã được phục hồi!", color=0x00ff7f)
        embed.set_image(url="attachment://sandbox.png")
        await ctx.send(embed=embed, file=file)
    else:
        # Nếu không phải mã base64 save, dùng AI để tạo hình ảnh Blueprint kỹ thuật Industrialist
        if not ai_model:
            await ctx.send("❌ Mã code không hợp lệ và AI chưa được bật cấu hình khóa API!")
            return
            
        async with ctx.typing():
            try:
                buf = world.render_blueprint_image()
                file = discord.File(fp=buf, filename="blueprint_tech.png")
                embed = discord.Embed(title="📐 AI INDUSTRIALIST BLUEPRINT ARCHIVE", description=f"Bản vẽ kỹ thuật cho ý tưởng: *{code_str}*", color=0x3498db)
                embed.set_image(url="attachment://blueprint_tech.png")
                await ctx.send(embed=embed, file=file)
            except Exception as e:
                await ctx.send(f"❌ Lỗi tạo bản vẽ AI: {e}")

@bot.command(name="help", aliases=["trogiup"])
async def help_command(ctx):
    await auto_delete_cmd(ctx)
    embed = discord.Embed(title="📖 HƯỚNG DẪN LOGIC GATES & BLUEPRINT ENGINE", color=0x00ff7f)
    embed.add_field(name="🛠️ XÂY DỰNG & MAP", value="`!map`, `!layer <0-9>`, `!set <khối> <x> <y>`, `!clear`", inline=False)
    embed.add_field(name="💾 SAVE & LOAD BLUEPRINT", value="`!save` : Trích xuất mã code bản vẽ hiện tại.\n`!blueprint <code_save>` : Nạp lại mạch từ code.\n`!blueprint <mô tả>` : Dùng AI render bản vẽ kỹ thuật.", inline=False)
    embed.add_field(name="⚡ INDUSTRIALIST & PVP", value="Khối Logic: `and`, `or`, `not`, `xor`, `clock`, `delay`, `toggle`, `counter`, `greater`, `less`, `mux`, `buffer`, `pulse`...\nKhối PvP/Cơ khí: `tnt`, `cannon`, `pos`, `propeller`, `rocket`, `wood`, `titanium`, `plastic`", inline=False)
    embed.add_field(name="🚀 ĐIỀU KHIỂN MẠCH", value="`!step [số]` : Chạy xung nhịp mạch điện / kích hoạt TNT & Pháo.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ai")
async def ai_chat(ctx, *, prompt: str = None):
    await auto_delete_cmd(ctx)
    if not ai_model or not prompt: return
    async with ctx.typing():
        sys_prompt = f"Bạn là kỹ sư trưởng hệ thống mạch điện Industrialist và cơ khí quân sự. Hãy trả lời chuẩn xác và sắc sảo: {prompt}"
        res = await asyncio.to_thread(ai_model.generate_content, sys_prompt)
        embed = discord.Embed(title="🤖 STARK INDUSTRIALIST AI", description=res.text, color=discord.Color.blue())
        await ctx.send(embed=embed)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
