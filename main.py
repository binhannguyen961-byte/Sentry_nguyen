import os
import io
import math
import asyncio
import threading
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
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

app = Flask(__name__)
@app.route('/')
def home(): return "Industrialist & Plane Crazy Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# ==========================================
# 2. HỆ THỐNG KHỐI (BLOCKS & INDUSTRIALIST LOGIC)
# ==========================================
GRID_SIZE = 10

# Khối vật chất & Giáp
AIR = 0
STEEL_ARMOR = 1
COMPOSITE_ARMOR = 2
ERA_ARMOR = 3
ENGINE = 4
AMMO_RACK = 5

# Khối PvP & Cơ khí mới
TNT = 30                # Khối thuốc nổ phát nổ khi nhận điện
PNEUMATIC = 31          # Động cơ khí / Piston đẩy
PROPELLER = 32          # Cánh quạt tạo lực đẩy gió
ROCKET_ENGINE = 33      # Động cơ tên lửa phản lực mạnh

# Khối phụ kiện cũ
WING = 6
CANNON = 7
CAMERA = 8
GYRO = 9
COORD_READER = 35       # Khối đọc tọa độ X, Y của chính nó hoặc truyền vị trí

# Nhóm Logic Gates (Mở rộng chuẩn Industrialist)
LOGIC_AND = 10
LOGIC_OR = 11
LOGIC_NOT = 12
LOGIC_NAND = 13
LOGIC_NOR = 14
LOGIC_XOR = 15
LOGIC_SR_LATCH = 16
LOGIC_CLOCK = 17
LOGIC_DELAY = 18
LOGIC_TOGGLE = 19
LOGIC_BUFFER = 20       # Truyền tín hiệu có trễ định hình
LOGIC_PULSE = 21        # Tạo xung đơn (Edge detector)
LOGIC_COUNTER = 22      # Đếm xung tín hiệu đầu vào
LOGIC_GREATER = 23      # So sánh A > B
LOGIC_LESS = 24         # So sánh A < B
LOGIC_MUX = 25          # Bộ chọn kênh (Multiplexer)
SENSOR_LASER = 26

# Thông số khối (Mass, Color, Label)
BLOCK_INFO = {
    AIR: {"color": (30, 30, 35), "label": "", "mass": 0},
    STEEL_ARMOR: {"color": (120, 120, 130), "label": "ST", "mass": 500},
    COMPOSITE_ARMOR: {"color": (70, 100, 140), "label": "CP", "mass": 200},
    ERA_ARMOR: {"color": (200, 100, 30), "label": "ER", "mass": 100},
    ENGINE: {"color": (220, 180, 50), "label": "ENG", "mass": 800},
    AMMO_RACK: {"color": (220, 40, 40), "label": "AMG", "mass": 300},
    TNT: {"color": (255, 69, 0), "label": "TNT", "mass": 150},
    PNEUMATIC: {"color": (100, 200, 200), "label": "PNE", "mass": 250},
    PROPELLER: {"color": (180, 200, 220), "label": "PRP", "mass": 100},
    ROCKET_ENGINE: {"color": (255, 140, 0), "label": "ROC", "mass": 400},
    WING: {"color": (200, 220, 255), "label": "WNG", "mass": 50},
    CANNON: {"color": (80, 80, 80), "label": "GUN", "mass": 600},
    CAMERA: {"color": (50, 200, 100), "label": "CAM", "mass": 20},
    GYRO: {"color": (150, 100, 250), "label": "GYR", "mass": 150},
    COORD_READER: {"color": (220, 220, 100), "label": "POS", "mass": 40},
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

    def analyze_physics(self):
        total_mass = 0
        total_lift = 0
        total_thrust = 0
        gyro_power = 0
        cm_x, cm_y = 0, 0 

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    b = self.grid[x][y][z]
                    if b.type != AIR:
                        total_mass += b.mass
                        cm_x += x * b.mass
                        cm_y += y * b.mass
                        
                        if b.type == ENGINE: total_thrust += 5000
                        elif b.type == PROPELLER: total_thrust += 2000
                        elif b.type == ROCKET_ENGINE: total_thrust += 12000
                        elif b.type == WING: total_lift += 3000
                        elif b.type == GYRO: gyro_power += 1000

        if total_mass > 0:
            cm_x /= total_mass
            cm_y /= total_mass

        return {
            "mass": total_mass,
            "thrust": total_thrust,
            "lift": total_lift,
            "gyro": gyro_power,
            "cm_x": round(cm_x, 1),
            "cm_y": round(cm_y, 1)
        }

    def update_logic_step(self):
        self.tick_count += 1
        self.logs.clear()

        # Lưu trạng thái cũ
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    self.grid[x][y][z].prev_signal = self.grid[x][y][z].output_signal

        # Tính toán Industrialist Logic Gates & PvP
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                for z in range(GRID_SIZE):
                    b = self.grid[x][y][z]
                    in1 = self.grid[x-1][y][z].prev_signal if x > 0 else False
                    in2 = self.grid[x+1][y][z].prev_signal if x < GRID_SIZE-1 else False

                    if b.type == LOGIC_AND: b.output_signal = in1 and in2
                    elif b.type == LOGIC_OR: b.output_signal = in1 or in2
                    elif b.type == LOGIC_NOT: b.output_signal = not in1
                    elif b.type == LOGIC_XOR: b.output_signal = in1 != in2
                    elif b.type == LOGIC_CLOCK: b.output_signal = (self.tick_count % 2 == 0)
                    elif b.type == LOGIC_DELAY: b.output_signal = in1
                    elif b.type == LOGIC_BUFFER: b.output_signal = in1
                    elif b.type == LOGIC_PULSE:
                        b.output_signal = in1 and not self.grid[x-1][y][z].prev_signal if x > 0 else False
                    elif b.type == LOGIC_COUNTER:
                        if in1 and not self.grid[x-1][y][z].prev_signal if x > 0 else False:
                            b.counter_value = (b.counter_value + 1) % 10
                        b.output_signal = (b.counter_value > 0)
                    elif b.type == LOGIC_GREATER:
                        b.output_signal = int(in1) > int(in2)
                    elif b.type == LOGIC_LESS:
                        b.output_signal = int(in1) < int(in2)
                    elif b.type == LOGIC_MUX:
                        # Nếu có tín hiệu điều khiển, chọn luồng
                        b.output_signal = in2 if in1 else False
                    elif b.type == LOGIC_TOGGLE:
                        curr_in1 = self.grid[x-1][y][z].output_signal if x > 0 else False
                        prev_in1 = self.grid[x-1][y][z].prev_signal if x > 0 else False
                        if curr_in1 and not prev_in1:
                            b.latch_state = not b.latch_state
                        b.output_signal = b.latch_state
                    elif b.type == COORD_READER:
                        # Lấy hai khối đầu tiên (hoặc hiển thị tọa độ X, Y của khối này)
                        b.output_signal = True
                        self.logs.append(f"📍 Tọa độ khối POS tại X={x}, Y={y}, Z={z}")
                    elif b.type == TNT:
                        if in1:
                            self.logs.append(f"💥 TNT phát nổ tại ({x},{y},{z})!")
                            self.grid[x][y][z] = Block(AIR) # Hủy khối TNT
                    elif b.type == CANNON:
                        if in1:
                            self.logs.append(f"🔥 Pháo tại ({x},{y}) khai hỏa!")
                            b.output_signal = True
                        else:
                            b.output_signal = False

    def render_to_image(self):
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

                if b.output_signal and (b.type >= 10 or b.type in [CANNON, COORD_READER]):
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
    buf = world.render_to_image()
    file = discord.File(fp=buf, filename="sandbox.png")
    
    embed = discord.Embed(title="🎮 INDUSTRIALIST & PVP ENGINE", color=0x2b2d31)
    embed.set_image(url="attachment://sandbox.png")
    embed.set_footer(text=f"Tầng Z={world.current_slice} | Tick: {world.tick_count}")
    await ctx.send(embed=embed, file=file)

@bot.command(name="set")
async def set_block_cmd(ctx, block_name: str = None, x: int = None, y: int = None, z: int = None):
    await auto_delete_cmd(ctx)
    if not block_name or x is None or y is None:
        return

    world = get_world(ctx.guild.id)
    target_z = z if z is not None else world.current_slice

    NAME_MAP = {
        "steel": STEEL_ARMOR, "composite": COMPOSITE_ARMOR, "era": ERA_ARMOR,
        "engine": ENGINE, "ammo": AMMO_RACK, "wing": WING, "cannon": CANNON,
        "camera": CAMERA, "gyro": GYRO, "air": AIR,
        "tnt": TNT, "pneumatic": PNEUMATIC, "piston": PNEUMATIC,
        "propeller": propeller := PROPELLER, "rocket": ROCKET_ENGINE,
        "pos": COORD_READER, "coord": COORD_READER,
        "and": LOGIC_AND, "or": LOGIC_OR, "not": LOGIC_NOT, "xor": LOGIC_XOR,
        "clock": LOGIC_CLOCK, "delay": LOGIC_DELAY, "toggle": LOGIC_TOGGLE,
        "buffer": LOGIC_BUFFER, "pulse": LOGIC_PULSE, "counter": LOGIC_COUNTER,
        "greater": LOGIC_GREATER, "less": LOGIC_LESS, "mux": LOGIC_MUX, "laser": SENSOR_LASER
    }

    b_type = NAME_MAP.get(block_name.lower())
    if b_type is not None:
        world.set_block(x, y, target_z, b_type)
        await show_map(ctx)

@bot.command(name="step", aliases=["tick"])
async def step_logic(ctx, steps: int = 1):
    await auto_delete_cmd(ctx)
    world = get_world(ctx.guild.id)
    for _ in range(min(steps, 10)):
        world.update_logic_step()
    
    buf = world.render_to_image()
    file = discord.File(fp=buf, filename="sandbox.png")
    
    desc = "\n".join(world.logs) if world.logs else "Mạch logic industrialist đã xử lý xong nhịp."
    embed = discord.Embed(title=f"⏱️ TICK MẠCH & PVP ({steps} steps)", description=desc, color=0x00ff00)
    embed.set_image(url="attachment://sandbox.png")
    await ctx.send(embed=embed, file=file)

@bot.command(name="physics", aliases=["testflight"])
async def eval_physics(ctx):
    await auto_delete_cmd(ctx)
    world = get_world(ctx.guild.id)
    stats = world.analyze_physics()
    
    embed = discord.Embed(title="📐 BÁO CÁO VẬT LÝ & ĐỘNG CƠ", color=0x3498db)
    embed.add_field(name="⚖️ Khối lượng", value=f"{stats['mass']} kg", inline=True)
    embed.add_field(name="🚀 Lực đẩy tổng (Engine+Prop+Rocket)", value=f"{stats['thrust']} N", inline=True)
    embed.add_field(name="🦅 Lực nâng cánh", value=f"{stats['lift']} N", inline=True)
    embed.add_field(name="🎯 Trọng tâm (CoM)", value=f"X: {stats['cm_x']}, Y: {stats['cm_y']}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="help", aliases=["trogiup"])
async def help_command(ctx):
    await auto_delete_cmd(ctx)
    embed = discord.Embed(title="📖 BẢNG LỆNH INDUSTRIALIST & PVP", color=0x00ff7f)
    embed.add_field(name="🛠️ XÂY DỰNG", value="`!map` `!layer <0-9>` `!set <khối> <x> <y>` `!clear`", inline=False)
    embed.add_field(name="💣 KHỐI PVP & CƠ KHÍ", value="`tnt`, `pneumatic` (Piston), `propeller` (Cánh quạt), `rocket` (Động cơ tên lửa), `pos` (Đọc tọa độ X,Y)", inline=False)
    embed.add_field(name="⚡ INDUSTRIALIST LOGIC", value="`buffer`, `pulse`, `counter`, `greater` (>), `less` (<), `mux`, `clock`, `delay`, `toggle`, `and`, `or`, `not`, `xor`", inline=False)
    embed.add_field(name="🚀 ĐIỀU KHIỂN", value="`!step [số]` : Chạy xung nhịp mạch / Kích hoạt TNT & Pháo\n`!physics` : Kiểm tra thông số lực đẩy động cơ", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ai")
async def ai_chat(ctx, *, prompt: str = None):
    await auto_delete_cmd(ctx)
    if not ai_model or not prompt: return
    async with ctx.typing():
        sys_prompt = f"Bạn là chuyên gia kỹ sư quân sự và thiết kế máy móc logic. Hãy trả lời cực kỳ chuẩn xác và sắc sảo: {prompt}"
        res = await asyncio.to_thread(ai_model.generate_content, sys_prompt)
        embed = discord.Embed(title="🤖 STARK AI", description=res.text, color=discord.Color.blue())
        await ctx.send(embed=embed)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
