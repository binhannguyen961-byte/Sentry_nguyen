import os, io, math, asyncio, threading, json
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
import google.generativeai as genai

# Cấu hình AI & Discord
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
def home(): return "Pure Logic & Display Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

GRID_SIZE = 100 

# ID Các loại Block Logic & Hiển thị
AIR, SWITCH, BUTTON, CLOCK, DISPLAY_PIX = 0, 1, 2, 3, 4
AND, OR, NOT, NAND, NOR, XOR, XNOR = 10, 11, 12, 13, 14, 15, 16
D_FLIP_FLOP, T_FLIP_FLOP, SR_LATCH, RAM_CELL = 20, 21, 22, 23
MUX, DEMUX, HALF_ADDER, ALU_BLOCK, ROM_BLOCK, REGISTER = 30, 31, 32, 33, 34, 35

# ID Khối Ký Tự, Số & Bảng Điện Tử
CHAR_BLOCK = 40      # Khối chứa ký tự Chữ (A-Z)
NUM_BLOCK = 41       # Khối chứa Số (0-9)
DISPLAY_BOARD = 42   # Bảng điện tử hiển thị Chữ / Số

BLOCK_INFO = {
    AIR: {"color": (20, 25, 30), "label": ""},
    SWITCH: {"color": (50, 150, 50), "label": "SW"},
    BUTTON: {"color": (150, 50, 50), "label": "BTN"},
    CLOCK: {"color": (255, 150, 0), "label": "CLK"},
    DISPLAY_PIX: {"color": (40, 40, 50), "label": "PIX"},
    
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
    HALF_ADDER: {"color": (50, 50, 200), "label": "ADD"},
    ALU_BLOCK: {"color": (220, 100, 50), "label": "ALU"},
    ROM_BLOCK: {"color": (180, 50, 220), "label": "ROM"},
    REGISTER: {"color": (50, 180, 220), "label": "REG"},

    CHAR_BLOCK: {"color": (0, 180, 180), "label": "CHAR"},
    NUM_BLOCK: {"color": (180, 180, 0), "label": "NUM"},
    DISPLAY_BOARD: {"color": (15, 15, 25), "label": "BOARD"}
}

NAME_MAP = {k.lower(): v for k, v in [
    ("air", AIR), ("xoa", AIR), ("switch", SWITCH), ("sw", SWITCH), ("button", BUTTON), ("btn", BUTTON),
    ("clock", CLOCK), ("clk", CLOCK), ("pix", DISPLAY_PIX), ("and", AND), ("or", OR), ("not", NOT),
    ("nand", NAND), ("nor", NOR), ("xor", XOR), ("xnor", XNOR), ("dff", D_FLIP_FLOP), ("tff", T_FLIP_FLOP),
    ("sr", SR_LATCH), ("ram", RAM_CELL), ("mux", MUX), ("demux", DEMUX), ("add", HALF_ADDER),
    ("alu", ALU_BLOCK), ("rom", ROM_BLOCK), ("reg", REGISTER),
    ("char", CHAR_BLOCK), ("num", NUM_BLOCK), ("board", DISPLAY_BOARD)
]}

# Danh sách Blueprint tự động lắp đặt hoàn toàn miễn phí
BLUEPRINTS = {
    "adder_1bit": {
        "name": "Bộ cộng logic 1-Bit",
        "desc": "Kết nối các cổng XOR, AND, OR tạo thành bộ cộng full adder.",
        "blocks": [
            ("xor", 0, 0, ""), ("xor", 2, 0, ""), ("and", 0, 1, ""), ("and", 2, 1, ""), ("or", 1, 2, "")
        ],
        "connections": [
            ((0, 0), (2, 0)), ((0, 0), (2, 1)), ((0, 1), (1, 2)), ((2, 1), (1, 2))
        ]
    },
    "counter_display": {
        "name": "Bảng Điện Tử Hiển Thị Ký Tự",
        "desc": "Switch kích hoạt tín hiệu truyền qua khối CHAR 'N' và hiển thị lên Màn hình Bảng điện tử.",
        "blocks": [
            ("sw", 0, 0, ""), ("char", 1, 0, "N"), ("board", 2, 0, "")
        ],
        "connections": [
            ((0, 0), (1, 0)), ((1, 0), (2, 0))
        ]
    }
}

class Block:
    def __init__(self, b_type=AIR, value_str=""):
        self.type = b_type
        self.out_val = False
        self.prev_val = False
        self.mem_state = False 
        self.value_str = value_str # Lưu giá trị ký tự/số (ví dụ 'A', '8', 'Nam')
        self.display_text = "___"  # Nội dung hiển thị trên Bảng Điện Tử
        self.rom_data = [True, False, True, True, False]
        self.inputs = [] 

class AcademicWorld:
    def __init__(self):
        self.grid = [[Block(AIR) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.tick_count = 0
        self.view_x = 0
        self.view_y = 0
        self.zoom = 10 
        self.last_message = None 

    def logic_step(self):
        self.tick_count += 1
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                self.grid[x][y].prev_val = self.grid[x][y].out_val

        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                b = self.grid[x][y]
                if b.type == AIR: continue
                
                input_blocks = []
                for ix, iy in b.inputs:
                    if 0 <= ix < GRID_SIZE and 0 <= iy < GRID_SIZE:
                        input_blocks.append(self.grid[ix][iy])

                in1 = input_blocks[0].prev_val if len(input_blocks) > 0 else (self.grid[x-1][y].prev_val if x > 0 else False)
                in2 = input_blocks[1].prev_val if len(input_blocks) > 1 else (self.grid[x][y-1].prev_val if y > 0 else False)
                clk_pulse = input_blocks[2].prev_val if len(input_blocks) > 2 else (self.grid[x+1][y].prev_val if x < GRID_SIZE-1 else False)

                if b.type == CLOCK: b.out_val = (self.tick_count % 2 == 0)
                elif b.type == SWITCH: pass 
                elif b.type == BUTTON: pass # Giữ trạng thái do người dùng trigger
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
                elif b.type == ALU_BLOCK:
                    b.out_val = (in1 != in2) if clk_pulse else (in1 and in2)
                elif b.type == ROM_BLOCK:
                    b.out_val = b.rom_data[self.tick_count % len(b.rom_data)]
                elif b.type == DISPLAY_PIX: 
                    b.out_val = in1
                elif b.type in (CHAR_BLOCK, NUM_BLOCK):
                    b.out_val = in1 # Dẫn truyền tín hiệu kích hoạt từ Switch/Button
                elif b.type == DISPLAY_BOARD:
                    # Bảng điện tử: Kiểm tra tín hiệu từ khối CHAR / NUM kết nối vào nó
                    active_text = []
                    is_active = False
                    for inp in input_blocks:
                        if inp.prev_val:
                            is_active = True
                            if inp.type in (CHAR_BLOCK, NUM_BLOCK) and inp.value_str:
                                active_text.append(inp.value_str)
                    
                    b.out_val = is_active
                    b.display_text = "".join(active_text) if active_text else ("ON" if is_active else "OFF")

    def render_view(self):
        cell_sz = max(20, 600 // self.zoom)
        img_sz = self.zoom * cell_sz
        img = Image.new("RGB", (img_sz, img_sz), (15, 18, 22))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("arial.ttf", max(10, cell_sz//3))
        except: font = ImageFont.load_default()

        # Vẽ đường kết nối dây tín hiệu
        for vx in range(self.zoom):
            for vy in range(self.zoom):
                gx, gy = self.view_x + vx, self.view_y + vy
                if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                    b = self.grid[gx][gy]
                    for ix, iy in b.inputs:
                        if self.view_x <= ix < self.view_x + self.zoom and self.view_y <= iy < self.view_y + self.zoom:
                            start_p = ((ix - self.view_x) * cell_sz + cell_sz // 2, (iy - self.view_y) * cell_sz + cell_sz // 2)
                            end_p = (vx * cell_sz + cell_sz // 2, vy * cell_sz + cell_sz // 2)
                            line_color = (0, 255, 150) if self.grid[ix][iy].out_val else (80, 80, 100)
                            draw.line([start_p, end_p], fill=line_color, width=2)

        # Vẽ các Block trên lưới
        for vx in range(self.zoom):
            for vy in range(self.zoom):
                gx, gy = self.view_x + vx, self.view_y + vy
                if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                    b = self.grid[gx][gy]
                    info = BLOCK_INFO.get(b.type, BLOCK_INFO[AIR])
                    color = info["color"]
                    
                    # Khi được kích hoạt tín hiệu (High Output)
                    if b.out_val: 
                        if b.type == DISPLAY_PIX:
                            color = (255, 255, 255) # Pixels sáng trắng rực rỡ
                        elif b.type == DISPLAY_BOARD:
                            color = (10, 40, 80)    # Màn hình sáng đèn nền xanh
                        else:
                            color = (min(255, color[0]+100), min(255, color[1]+100), min(255, color[2]+100))

                    rx, ry = vx * cell_sz, vy * cell_sz
                    draw.rectangle([rx+1, ry+1, rx+cell_sz-2, ry+cell_sz-2], fill=color, outline=(40, 45, 50))
                    
                    # Nhãn hiển thị tên & Giá trị khối
                    if info["label"] and cell_sz >= 20:
                        text_c = (255, 255, 255) if not (b.type == DISPLAY_PIX and b.out_val) else (0, 0, 0)
                        
                        if b.type in (CHAR_BLOCK, NUM_BLOCK):
                            disp_lbl = f"{info['label']}:{b.value_str}" if b.value_str else info['label']
                        elif b.type == DISPLAY_BOARD:
                            disp_lbl = f"[{b.display_text}]" if b.out_val else "[OFF]"
                            text_c = (0, 255, 200) if b.out_val else (100, 100, 100)
                        else:
                            disp_lbl = info["label"]

                        draw.text((rx + cell_sz*0.08, ry + cell_sz*0.3), disp_lbl, fill=text_c, font=font)
        
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
    embed = discord.Embed(
        title="🖥️ LOGIC & DISPLAY SIMULATOR", 
        description=f"⏱️ **Tick Hệ Thống:** {env.tick_count}\n"
                    f"🔍 **Khu vực quan sát:** X({env.view_x}→{env.view_x+env.zoom}), Y({env.view_y}→{env.view_y+env.zoom})", 
        color=0x00ffaa
    )
    embed.set_image(url="attachment://logic.png")
    
    if env.last_message:
        try: await env.last_message.edit(embed=embed, attachments=[file])
        except: env.last_message = await ctx.send(embed=embed, file=file)
    else:
        env.last_message = await ctx.send(embed=embed, file=file)

# ==========================================
# CÁC LỆNH ĐIỀU KHIỂN & TƯƠNG TÁC
# ==========================================
@bot.command(name="map")
async def show_map(ctx):
    await safe_delete(ctx)
    await update_board(ctx, get_env(ctx.guild.id))

@bot.command(name="set")
async def set_block(ctx, block: str = None, val_or_x = None, x_or_y = None, y_val = None):
    """Lệnh đặt block đa năng:
    - Đặt block thường: !set and 2 3
    - Đặt chữ/số: !set char A 2 3  hoặc !set num 9 4 5
    """
    await safe_delete(ctx)
    if not block: return
    env = get_env(ctx.guild.id)
    b_name = block.lower()
    
    if b_name not in NAME_MAP: return
    b_type = NAME_MAP[b_name]
    
    # Xử lý tham số linh hoạt cho khối CHAR/NUM
    if b_type in (CHAR_BLOCK, NUM_BLOCK):
        val_str = str(val_or_x) if val_or_x is not None else "A"
        x, y = int(x_or_y), int(y_val)
    else:
        val_str = ""
        x, y = int(val_or_x), int(x_or_y)

    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        env.grid[x][y] = Block(b_type, value_str=val_str)
        await update_board(ctx, env)

@bot.command(name="autobuild", aliases=["ab"])
async def auto_build(ctx, bp_id: str = None, x: int = None, y: int = None):
    """Auto Build các cấu trúc logic & hiển thị từ Blueprint mẫu"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    
    if not bp_id or bp_id.lower() not in BLUEPRINTS or x is None or y is None:
        desc_list = "\n".join([f"• `{k}`: **{v['name']}**\n  _{v['desc']}_" for k, v in BLUEPRINTS.items()])
        embed = discord.Embed(title="🏗️ BẢN THIẾT KẾ AUTO BUILD", description=desc_list, color=0xe67e22)
        embed.set_footer(text="Cú pháp: !autobuild <tên_mẫu> <x> <y>")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(15)
        return await msg.delete()
        
    bp = BLUEPRINTS[bp_id.lower()]
    
    # Đặt block & giá trị
    for b_name, dx, dy, val in bp["blocks"]:
        bx, by = x + dx, y + dy
        if 0 <= bx < GRID_SIZE and 0 <= by < GRID_SIZE:
            env.grid[bx][by] = Block(NAME_MAP[b_name], value_str=val)
            
    # Tự động nối dây
    for (src_dx, src_dy), (dst_dx, dst_dy) in bp["connections"]:
        sx, sy = x + src_dx, y + src_dy
        dx, dy = x + dst_dx, y + dst_dy
        if 0 <= sx < GRID_SIZE and 0 <= sy < GRID_SIZE and 0 <= dx < GRID_SIZE and 0 <= dy < GRID_SIZE:
            env.grid[dx][dy].inputs.append((sx, sy))
            
    await update_board(ctx, env)

@bot.command(name="connect", aliases=["con"])
async def connect_nodes(ctx, *args):
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    args_lower = [a.lower() for a in args]
    if "to" not in args_lower: return
    
    to_idx = args_lower.index("to")
    part1, part2 = args_lower[:to_idx], args_lower[to_idx+1:]
    
    try:
        x1, y1 = int(part1[-2]), int(part1[-1])
        x2, y2 = int(part2[-2]), int(part2[-1])
        if 0 <= x1 < GRID_SIZE and 0 <= y1 < GRID_SIZE and 0 <= x2 < GRID_SIZE and 0 <= y2 < GRID_SIZE:
            if (x1, y1) not in env.grid[x2][y2].inputs:
                env.grid[x2][y2].inputs.append((x1, y1))
            await update_board(ctx, env)
    except (ValueError, IndexError): pass

@bot.command(name="trigger", aliases=["press", "click"])
async def trigger_io(ctx, x: int, y: int):
    """Bật / Tắt trạng thái của Button hoặc Switch"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    b = env.grid[x][y]
    if b.type in (SWITCH, BUTTON):
        b.out_val = not b.out_val
    await update_board(ctx, env)

@bot.command(name="zoom")
async def zoom_view(ctx, action: str = "in", amount: int = 5):
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    if action == "in": env.zoom = max(5, env.zoom - amount)
    elif action == "out": env.zoom = min(GRID_SIZE, env.zoom + amount)
    await update_board(ctx, env)

@bot.command(name="pan")
async def pan_view(ctx, x: int, y: int):
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

@bot.command(name="ai_analyze", aliases=["aia"])
async def ai_analyze_circuit(ctx):
    await safe_delete(ctx)
    if not ai_model:
        msg = await ctx.send("❌ Chưa cấu hình GEMINI_API_KEY!")
        await asyncio.sleep(5)
        return await msg.delete()
        
    env = get_env(ctx.guild.id)
    placed_blocks = []
    
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            b = env.grid[x][y]
            if b.type != AIR:
                info = BLOCK_INFO.get(b.type, {})
                placed_blocks.append(f"- Block {info.get('label')}({b.value_str}) tại ({x},{y}), Inputs: {b.inputs}")
                
    if not placed_blocks:
        prompt = "Mạch hiện tại đang trống. Hướng dẫn thiết kế mạch hiển thị bảng điện tử với nút bấm đơn giản."
    else:
        circuit_desc = "\n".join(placed_blocks[:30])
        prompt = f"Phân tích mạch logic và hệ thống hiển thị sau:\n{circuit_desc}"

    try:
        response = ai_model.generate_content(prompt)
        embed = discord.Embed(title="🤖 GEMINI AI - PHÂN TÍCH NGUYÊN LÝ MẠCH", description=response.text[:2000], color=0x9b59b6)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(30)
        await msg.delete()
    except Exception as e:
        msg = await ctx.send(f"Lỗi AI: {e}")
        await asyncio.sleep(5)
        await msg.delete()

@bot.command(name="help", aliases=["trogiup", "h"])
async def help_cmd(ctx):
    await safe_delete(ctx)
    embed = discord.Embed(title="📚 BẢNG HƯỚNG DẪN CÁC LỆNH LOGIC & DISPLAY", color=0x00ff7f)
    
    embed.add_field(
        name="🔤 TẠO CHỮ, SỐ & BẢNG ĐIỆN TỬ",
        value="`!set char <chữ> <x> <y>` : Đặt khối chứa chữ (ví dụ: `!set char A 1 0`).\n"
              "`!set num <số> <x> <y>` : Đặt khối chứa số (ví dụ: `!set num 9 2 0`).\n"
              "`!set board <x> <y>` : Đặt Màn hình Bảng Điện Tử.\n"
              "`!trigger <x> <y>` : Nhấn Nút/Switch kích hoạt truyền dữ liệu chữ/số lên Bảng Điện Tử.",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ XÂY DỰNG & AUTO BUILD",
        value="`!set <tên_block> <x> <y>` : Đặt block logic tùy ý.\n"
              "`!autobuild counter_display 0 0` : Tự động dựng mô hình bảng điện tử mẫu.\n"
              "`!connect <x1> <y1> to <x2> <y2>` : Nối dây tín hiệu.",
        inline=False
    )
    
    embed.add_field(
        name="⚡ VẬN HÀNH LOGIC",
        value="`!step [số_tick]` : Chạy xung nhịp mạch.\n"
              "`!ai_analyze` : Nhờ AI Gemini phân tích mạch.",
        inline=False
    )

    msg = await ctx.send(embed=embed)
    await asyncio.sleep(20)
    try: await msg.delete()
    except: pass

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
