import os, io, math, asyncio, threading, base64, json
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
import google.generativeai as genai

# Cấu hình AI & Discord
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
def home(): return "Educational Logic Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# ==========================================
# HỆ THỐNG KIẾN TRÚC MÁY TÍNH (COMPUTER ARCHITECTURE)
# ==========================================
GRID_SIZE = 100 # Không gian mạch cực lớn

# ID Khối Logic Học Thuật
AIR = 0
SWITCH = 1        # Công tắc I/O (Bật/Tắt vĩnh viễn)
BUTTON = 2        # Nút bấm (Pulse 1 tick)
CLOCK = 3         # Bộ dao động (Oscillator)
DISPLAY_PIX = 4   # Điểm ảnh (Phát sáng nếu có tín hiệu, dùng tạo video)

# Cổng Logic Cơ Bản & Phức Tạp
AND, OR, NOT = 10, 11, 12
NAND, NOR, XOR, XNOR = 13, 14, 15, 16

# Tuần tự & Nhớ (Sequential & Memory)
D_FLIP_FLOP = 20  # Lưu trạng thái theo Clock
T_FLIP_FLOP = 21  # Đảo trạng thái theo Clock
SR_LATCH = 22     # Chốt Set/Reset
RAM_CELL = 23     # Ô nhớ RAM 1-bit

# Phân luồng dữ liệu
MUX, DEMUX = 30, 31
HALF_ADDER = 32   # Bộ cộng bán phần

BLOCK_INFO = {
    AIR: {"color": (20, 25, 30), "label": ""},
    SWITCH: {"color": (50, 150, 50), "label": "SW"},
    BUTTON: {"color": (150, 50, 50), "label": "BTN"},
    CLOCK: {"color": (255, 150, 0), "label": "CLK"},
    DISPLAY_PIX: {"color": (30, 30, 40), "label": "PIX"}, # Sáng khi output=True
    AND: {"color": (0, 150, 200), "label": "AND"},
    OR: {"color": (150, 0, 200), "label": "OR"},
    NOT: {"color": (200, 200, 0), "label": "NOT"},
    NAND: {"color": (0, 100, 150), "label": "NAND"},
    NOR: {"color": (100, 0, 150), "label": "NOR"},
    XOR: {"color": (200, 0, 100), "label": "XOR"},
    XNOR: {"color": (150, 0, 50), "label": "XNOR"},
    D_FLIP_FLOP: {"color": (0, 200, 100), "label": "D-FF"},
    T_FLIP_FLOP: {"color": (50, 200, 150), "label": "T-FF"},
    SR_LATCH: {"color": (0, 150, 100), "label": "SR"},
    RAM_CELL: {"color": (255, 200, 0), "label": "RAM"},
    MUX: {"color": (100, 50, 200), "label": "MUX"},
    DEMUX: {"color": (120, 70, 220), "label": "DMX"},
    HALF_ADDER: {"color": (50, 50, 200), "label": "ADD"}
}

NAME_MAP = {k.lower(): v for k, v in [
    ("air", AIR), ("xoa", AIR), ("switch", SWITCH), ("button", BUTTON), ("clock", CLOCK),
    ("pix", DISPLAY_PIX), ("and", AND), ("or", OR), ("not", NOT), ("nand", NAND),
    ("nor", NOR), ("xor", XOR), ("xnor", XNOR), ("dff", D_FLIP_FLOP), ("tff", T_FLIP_FLOP),
    ("sr", SR_LATCH), ("ram", RAM_CELL), ("mux", MUX), ("demux", DEMUX), ("add", HALF_ADDER)
]}

class Block:
    def __init__(self, b_type=AIR):
        self.type = b_type
        self.out_val = False
        self.prev_val = False
        self.mem_state = False # Dùng cho FF, RAM

class AcademicWorld:
    def __init__(self):
        self.grid = [[Block(AIR) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.tick_count = 0
        # Zoom view config
        self.view_x = 0
        self.view_y = 0
        self.zoom = 10 # Kích thước vùng hiển thị (10x10)
        self.last_message = None # Dùng để edit tin nhắn

    def logic_step(self):
        self.tick_count += 1
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                self.grid[x][y].prev_val = self.grid[x][y].out_val

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                b = self.grid[x][y]
                if b.type == AIR: continue
                
                in1 = self.grid[x-1][y].prev_val if x > 0 else False
                in2 = self.grid[x][y-1].prev_val if y > 0 else False # Phức tạp hóa luồng dữ liệu 2 chiều
                clk_pulse = self.grid[x+1][y].prev_val if x < GRID_SIZE-1 else False

                if b.type == CLOCK: b.out_val = (self.tick_count % 2 == 0)
                elif b.type == SWITCH: pass # Giữ nguyên trạng thái qua lệnh bot
                elif b.type == BUTTON: b.out_val = False # Pulse kết thúc sau 1 tick
                elif b.type == AND: b.out_val = in1 and in2
                elif b.type == OR: b.out_val = in1 or in2
                elif b.type == NOT: b.out_val = not in1
                elif b.type == NAND: b.out_val = not (in1 and in2)
                elif b.type == NOR: b.out_val = not (in1 or in2)
                elif b.type == XOR: b.out_val = in1 != in2
                elif b.type == XNOR: b.out_val = in1 == in2
                elif b.type == D_FLIP_FLOP:
                    if clk_pulse: b.mem_state = in1
                    b.out_val = b.mem_state
                elif b.type == T_FLIP_FLOP:
                    if clk_pulse and in1: b.mem_state = not b.mem_state
                    b.out_val = b.mem_state
                elif b.type == DISPLAY_PIX: b.out_val = in1

    def render_view(self):
        cell_sz = max(20, 600 // self.zoom)
        img_sz = self.zoom * cell_sz
        img = Image.new("RGB", (img_sz, img_sz), (15, 18, 22))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("arial.ttf", max(10, cell_sz//3))
        except: font = ImageFont.load_default()

        for vx in range(self.zoom):
            for vy in range(self.zoom):
                gx, gy = self.view_x + vx, self.view_y + vy
                if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                    b = self.grid[gx][gy]
                    info = BLOCK_INFO.get(b.type, BLOCK_INFO[AIR])
                    color = info["color"]
                    
                    if b.out_val: # Phát sáng khi logic=TRUE
                        color = (min(255, color[0]+120), min(255, color[1]+120), min(255, color[2]+120))
                        if b.type == DISPLAY_PIX: color = (200, 255, 200) # Pixel sáng rực

                    rx, ry = vx * cell_sz, vy * cell_sz
                    draw.rectangle([rx+1, ry+1, rx+cell_sz-2, ry+cell_sz-2], fill=color, outline=(40, 45, 50))
                    
                    if info["label"] and cell_sz >= 20:
                        text_c = (255,255,255) if not b.out_val else (0,0,0)
                        draw.text((rx + cell_sz*0.1, ry + cell_sz*0.3), info["label"], fill=text_c, font=font)
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

guild_envs = {}
def get_env(guild_id):
    if guild_id not in guild_envs: guild_envs[guild_id] = AcademicWorld()
    return guild_envs[guild_id]

async def safe_delete(ctx):
    try: await ctx.message.delete()
    except: pass

async def update_board(ctx, env):
    buf = env.render_view()
    file = discord.File(fp=buf, filename="logic.png")
    embed = discord.Embed(title="💻 ACADEMIC LOGIC SIMULATOR", description=f"Khu vực hiển thị: X({env.view_x}→{env.view_x+env.zoom}), Y({env.view_y}→{env.view_y+env.zoom})\nTick hệ thống: {env.tick_count}", color=0x2b2d31)
    embed.set_image(url="attachment://logic.png")
    
    if env.last_message:
        try:
            await env.last_message.edit(embed=embed, attachments=[file])
        except:
            env.last_message = await ctx.send(embed=embed, file=file)
    else:
        env.last_message = await ctx.send(embed=embed, file=file)

# ==========================================
# LỆNH ĐIỀU KHIỂN & HỌC THUẬT
# ==========================================
@bot.command(name="map")
async def show_map(ctx):
    await safe_delete(ctx)
    await update_board(ctx, get_env(ctx.guild.id))

@bot.command(name="set")
async def set_block(ctx, block: str = None, x: int = None, y: int = None):
    await safe_delete(ctx)
    if not block or x is None or y is None: return
    env = get_env(ctx.guild.id)
    if block.lower() in NAME_MAP and 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        env.grid[x][y] = Block(NAME_MAP[block.lower()])
        await update_board(ctx, env)

@bot.command(name="trigger")
async def trigger_io(ctx, x: int, y: int):
    """Bật/tắt các khối đầu vào (Switch/Button)"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    b = env.grid[x][y]
    if b.type == SWITCH: b.out_val = not b.out_val
    elif b.type == BUTTON: b.out_val = True
    await update_board(ctx, env)

@bot.command(name="zoom")
async def zoom_view(ctx, action: str = "in", amount: int = 5):
    """!zoom in/out để thu phóng khung nhìn hiển thị mạch"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    if action == "in": env.zoom = max(5, env.zoom - amount)
    elif action == "out": env.zoom = min(GRID_SIZE, env.zoom + amount)
    await update_board(ctx, env)

@bot.command(name="pan")
async def pan_view(ctx, x: int, y: int):
    """Di chuyển camera hiển thị mạch"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    env.view_x = max(0, min(GRID_SIZE - env.zoom, x))
    env.view_y = max(0, min(GRID_SIZE - env.zoom, y))
    await update_board(ctx, env)

@bot.command(name="step", aliases=["tick", "run"])
async def run_step(ctx, steps: int = 1):
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    for _ in range(min(steps, 100)): env.logic_step()
    await update_board(ctx, env)

@bot.command(name="edu")
async def edu_info(ctx, gate: str):
    await safe_delete(ctx)
    # Lệnh mở rộng kiến thức lý thuyết cho các cổng
    info = {
        "and": "Cổng AND (Y = A • B). Trả về TRUE khi TẤT CẢ đầu vào là TRUE.",
        "xor": "Cổng XOR (Y = A ⊕ B). Trả về TRUE khi đầu vào KHÁC NHAU. Dùng nhiều trong bộ cộng (Adder).",
        "dff": "D Flip-Flop (Data FF). Đồng bộ hóa tín hiệu với xung nhịp (Clock). Chốt dữ liệu đầu vào D khi có sườn lên của Clock.",
        "pix": "Khối hiển thị (Pixel). Bố trí ma trận các khối PIX cùng hệ thống định tuyến (MUX/DEMUX) và ROM để tạo video/hình ảnh động."
    }
    desc = info.get(gate.lower(), "Vui lòng nhập cổng chuẩn: and, xor, dff, pix...")
    msg = await ctx.send(f"📚 **KIẾN THỨC LOGIC:** {desc}")
    await asyncio.sleep(10)
    await msg.delete() # Xóa tin nhắn giáo dục sau 10s để giữ chat sạch

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
