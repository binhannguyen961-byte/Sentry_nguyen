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
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

app = Flask(__name__)
@app.route('/')
def home(): return "Industrial Logic Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

GRID_SIZE = 100 

# ID Khối Cơ Bản & Logic
AIR, SWITCH, BUTTON, CLOCK, DISPLAY_PIX = 0, 1, 2, 3, 4
AND, OR, NOT, NAND, NOR, XOR, XNOR = 10, 11, 12, 13, 14, 15, 16
D_FLIP_FLOP, T_FLIP_FLOP, SR_LATCH, RAM_CELL = 20, 21, 22, 23
MUX, DEMUX, HALF_ADDER, ALU_BLOCK, ROM_BLOCK, REGISTER = 30, 31, 32, 33, 34, 35

# ID Khối Công Nghiệp & Khai Thác (Industrial Blocks)
DRILL = 40        # Máy khoan than (Tạo ra Than + Tiền)
PUMPJACK = 41     # Giàn khoan dầu mỏ
PIPE = 42         # Ống dẫn chất lỏng/dầu
CONVEYOR = 43     # Băng tải vận chuyển tài nguyên
TRUCK_DEPOT = 44  # Trạm xe chở hàng (Đổi tài nguyên lấy Tiền)

BLOCK_INFO = {
    AIR: {"color": (20, 25, 30), "label": "", "price": 0, "tech": None},
    SWITCH: {"color": (50, 150, 50), "label": "SW", "price": 10, "tech": None},
    BUTTON: {"color": (150, 50, 50), "label": "BTN", "price": 10, "tech": None},
    CLOCK: {"color": (255, 150, 0), "label": "CLK", "price": 50, "tech": None},
    DISPLAY_PIX: {"color": (30, 30, 40), "label": "PIX", "price": 20, "tech": None},
    
    AND: {"color": (0, 150, 200), "label": "AND", "price": 30, "tech": None},
    OR: {"color": (150, 0, 200), "label": "OR", "price": 30, "tech": None},
    NOT: {"color": (200, 200, 0), "label": "NOT", "price": 20, "tech": None},
    NAND: {"color": (0, 100, 150), "label": "NAND", "price": 40, "tech": None},
    NOR: {"color": (100, 0, 150), "label": "NOR", "price": 40, "tech": None},
    XOR: {"color": (200, 0, 100), "label": "XOR", "price": 50, "tech": "logic_tier1"},
    XNOR: {"color": (150, 0, 50), "label": "XNOR", "price": 50, "tech": "logic_tier1"},
    
    D_FLIP_FLOP: {"color": (0, 200, 100), "label": "D-FF", "price": 100, "tech": "logic_tier1"},
    T_FLIP_FLOP: {"color": (50, 200, 150), "label": "T-FF", "price": 100, "tech": "logic_tier1"},
    SR_LATCH: {"color": (0, 150, 100), "label": "SR", "price": 80, "tech": "logic_tier1"},
    RAM_CELL: {"color": (255, 200, 0), "label": "RAM", "price": 150, "tech": "logic_tier2"},
    
    MUX: {"color": (100, 50, 200), "label": "MUX", "price": 120, "tech": "logic_tier1"},
    DEMUX: {"color": (120, 70, 220), "label": "DMX", "price": 120, "tech": "logic_tier1"},
    HALF_ADDER: {"color": (50, 50, 200), "label": "ADD", "price": 150, "tech": "logic_tier2"},
    ALU_BLOCK: {"color": (220, 100, 50), "label": "ALU", "price": 500, "tech": "logic_tier2"},
    ROM_BLOCK: {"color": (180, 50, 220), "label": "ROM", "price": 400, "tech": "logic_tier2"},
    REGISTER: {"color": (50, 180, 220), "label": "REG", "price": 300, "tech": "logic_tier2"},

    # Các khối công nghiệp
    DRILL: {"color": (120, 90, 60), "label": "DRILL", "price": 200, "tech": "ind_tier1"},
    PUMPJACK: {"color": (70, 70, 90), "label": "PUMP", "price": 400, "tech": "ind_tier2"},
    PIPE: {"color": (50, 120, 180), "label": "PIPE", "price": 15, "tech": "ind_tier2"},
    CONVEYOR: {"color": (100, 100, 100), "label": "CONV", "price": 15, "tech": "ind_tier1"},
    TRUCK_DEPOT: {"color": (210, 140, 30), "label": "TRUCK", "price": 300, "tech": "ind_tier1"}
}

NAME_MAP = {k.lower(): v for k, v in [
    ("air", AIR), ("xoa", AIR), ("switch", SWITCH), ("button", BUTTON), ("clock", CLOCK),
    ("pix", DISPLAY_PIX), ("and", AND), ("or", OR), ("not", NOT), ("nand", NAND),
    ("nor", NOR), ("xor", XOR), ("xnor", XNOR), ("dff", D_FLIP_FLOP), ("tff", T_FLIP_FLOP),
    ("sr", SR_LATCH), ("ram", RAM_CELL), ("mux", MUX), ("demux", DEMUX), ("add", HALF_ADDER),
    ("alu", ALU_BLOCK), ("rom", ROM_BLOCK), ("reg", REGISTER),
    ("drill", DRILL), ("pump", PUMPJACK), ("pipe", PIPE), ("conv", CONVEYOR), ("truck", TRUCK_DEPOT)
]}

# Cây Công Nghệ (Tech Tree)
TECH_TREE = {
    "ind_tier1": {"name": "Khai thác Cơ bản", "cost": 300, "desc": "Mở khóa Máy khoan than (DRILL), Băng tải (CONV), Trạm xe (TRUCK)"},
    "ind_tier2": {"name": "Hóa dầu & Dẫn lưu", "cost": 800, "desc": "Mở khóa Giàn khoan dầu (PUMP), Ống dẫn (PIPE)"},
    "logic_tier1": {"name": "Mạch Tổ hợp Bậc thấp", "cost": 500, "desc": "Mở khóa XOR, XNOR, Flip-Flops, MUX, DEMUX"},
    "logic_tier2": {"name": "Vi xử lý Advanced", "cost": 1500, "desc": "Mở khóa ALU, ROM, Thanh ghi (REG), Bộ cộng (ADD)"}
}

# Bản thiết kế tự động dựng (Auto-Build Schematics)
BLUEPRINTS = {
    "adder_1bit": {
        "name": "Bộ cộng 1-bit (1-Bit Full Adder)",
        "cost": 650,
        "desc": "Mạch cộng logic gồm cổng XOR, AND, OR được kết nối sẵn.",
        "blocks": [
            ("xor", 0, 0), ("xor", 2, 0), ("and", 0, 1), ("and", 2, 1), ("or", 1, 2)
        ],
        "connections": [
            ((0, 0), (2, 0)), ((0, 0), (2, 1)), ((0, 1), (1, 2)), ((2, 1), (1, 2))
        ]
    },
    "coal_factory": {
        "name": "Trạm khai thác & Xuất khẩu Than",
        "cost": 1200,
        "desc": "Hệ thống Tự động hóa: Máy khoan -> Băng tải -> Trạm xe xuất khẩu.",
        "blocks": [
            ("drill", 0, 0), ("clock", 0, 1), ("conv", 1, 0), ("conv", 2, 0), ("truck", 3, 0)
        ],
        "connections": [
            ((0, 1), (0, 0)) # Clock kích hoạt Máy khoan
        ]
    }
}

class Block:
    def __init__(self, b_type=AIR):
        self.type = b_type
        self.out_val = False
        self.prev_val = False
        self.mem_state = False 
        self.rom_data = [True, False, True, True, False]
        self.inputs = [] 

class AcademicWorld:
    def __init__(self):
        self.grid = [[Block(AIR) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.tick_count = 0
        self.money = 1000 # Số tiền ban đầu
        self.unlocked_techs = set() # Các công nghệ đã nghiên cứu
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
                
                input_vals = []
                for ix, iy in b.inputs:
                    if 0 <= ix < GRID_SIZE and 0 <= iy < GRID_SIZE:
                        input_vals.append(self.grid[ix][iy].prev_val)

                in1 = input_vals[0] if len(input_vals) > 0 else (self.grid[x-1][y].prev_val if x > 0 else False)
                in2 = input_vals[1] if len(input_vals) > 1 else (self.grid[x][y-1].prev_val if y > 0 else False)
                clk_pulse = input_vals[2] if len(input_vals) > 2 else (self.grid[x+1][y].prev_val if x < GRID_SIZE-1 else False)

                if b.type == CLOCK: b.out_val = (self.tick_count % 2 == 0)
                elif b.type == SWITCH: pass 
                elif b.type == BUTTON: b.out_val = False 
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
                elif b.type == DISPLAY_PIX: b.out_val = in1
                
                # Logic các khối công nghiệp (Industrial Logic)
                elif b.type == DRILL:
                    # Khi nhận xung Clock/Nguồn, máy khoan sản xuất tài nguyên -> cộng tiền
                    if in1 or clk_pulse:
                        self.money += 15
                        b.out_val = True
                    else: b.out_val = False
                elif b.type == PUMPJACK:
                    if in1 or clk_pulse:
                        self.money += 35
                        b.out_val = True
                    else: b.out_val = False
                elif b.type == CONVEYOR or b.type == PIPE:
                    b.out_val = in1 # Dẫn truyền tín hiệu/vật liệu
                elif b.type == TRUCK_DEPOT:
                    if in1: self.money += 50 # Xuất hàng sinh lợi nhuận cao

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
                    for ix, iy in b.inputs:
                        if self.view_x <= ix < self.view_x + self.zoom and self.view_y <= iy < self.view_y + self.zoom:
                            start_p = ((ix - self.view_x) * cell_sz + cell_sz // 2, (iy - self.view_y) * cell_sz + cell_sz // 2)
                            end_p = (vx * cell_sz + cell_sz // 2, vy * cell_sz + cell_sz // 2)
                            line_color = (0, 255, 150) if self.grid[ix][iy].out_val else (100, 100, 120)
                            draw.line([start_p, end_p], fill=line_color, width=2)

        for vx in range(self.zoom):
            for vy in range(self.zoom):
                gx, gy = self.view_x + vx, self.view_y + vy
                if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                    b = self.grid[gx][gy]
                    info = BLOCK_INFO.get(b.type, BLOCK_INFO[AIR])
                    color = info["color"]
                    
                    if b.out_val: 
                        color = (min(255, color[0]+120), min(255, color[1]+120), min(255, color[2]+120))
                        if b.type == DISPLAY_PIX: color = (200, 255, 200) 

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
    embed = discord.Embed(
        title="🏭 INDUSTRIAL LOGIC ENGINE", 
        description=f"💰 **Tài khoản:** ${env.money:,} | ⏱️ **Tick:** {env.tick_count}\n"
                    f"🔍 **Góc nhìn:** X({env.view_x}→{env.view_x+env.zoom}), Y({env.view_y}→{env.view_y+env.zoom})", 
        color=0x3498db
    )
    embed.set_image(url="attachment://logic.png")
    
    if env.last_message:
        try: await env.last_message.edit(embed=embed, attachments=[file])
        except: env.last_message = await ctx.send(embed=embed, file=file)
    else:
        env.last_message = await ctx.send(embed=embed, file=file)

# ==========================================
# LỆNH ĐIỀU KHIỂN & HỆ THỐNG MỚI
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
    
    b_name = block.lower()
    if b_name in NAME_MAP and 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        b_type = NAME_MAP[b_name]
        info = BLOCK_INFO[b_type]
        
        # Kiểm tra Cây công nghệ
        req_tech = info["tech"]
        if req_tech and req_tech not in env.unlocked_techs:
            msg = await ctx.send(f"🔒 Món này yêu cầu nghiên cứu **{TECH_TREE[req_tech]['name']}** (`!tech` để xem).")
            await asyncio.sleep(5)
            return await msg.delete()
            
        # Kiểm tra Tiền
        cost = info["price"]
        if env.money < cost:
            msg = await ctx.send(f"❌ Không đủ tiền! Cần **${cost}** nhưng bạn chỉ có **${env.money}**.")
            await asyncio.sleep(5)
            return await msg.delete()
            
        env.money -= cost
        env.grid[x][y] = Block(b_type)
        await update_board(ctx, env)

@bot.command(name="autobuild", aliases=["ab"])
async def auto_build(ctx, bp_id: str = None, x: int = None, y: int = None):
    """Lệnh Auto Build mạch/nhà máy theo bản thiết kế mẫu"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    
    if not bp_id or bp_id.lower() not in BLUEPRINTS or x is None or y is None:
        desc_list = "\n".join([f"• `{k}`: {v['name']} - Giá: **${v['cost']}**\n  _{v['desc']}_" for k, v in BLUEPRINTS.items()])
        embed = discord.Embed(title="🏗️ DANH SÁCH BẢN THIẾT KẾ (AUTO BUILD)", description=desc_list, color=0xe67e22)
        embed.set_footer(text="Cú pháp: !autobuild <tên_mẫu> <x> <y>")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(15)
        return await msg.delete()
        
    bp = BLUEPRINTS[bp_id.lower()]
    if env.money < bp["cost"]:
        msg = await ctx.send(f"❌ Không đủ tiền mua bản thiết kế! Cần **${bp['cost']}**.")
        await asyncio.sleep(5)
        return await msg.delete()
        
    env.money -= bp["cost"]
    
    # Đặt các khối theo sơ đồ
    for b_name, dx, dy in bp["blocks"]:
        bx, by = x + dx, y + dy
        if 0 <= bx < GRID_SIZE and 0 <= by < GRID_SIZE:
            env.grid[bx][by] = Block(NAME_MAP[b_name])
            
    # Nối dây truyền tín hiệu tự động
    for (src_dx, src_dy), (dst_dx, dst_dy) in bp["connections"]:
        sx, sy = x + src_dx, y + src_dy
        dx, dy = x + dst_dx, y + dst_dy
        if 0 <= sx < GRID_SIZE and 0 <= sy < GRID_SIZE and 0 <= dx < GRID_SIZE and 0 <= dy < GRID_SIZE:
            env.grid[dx][dy].inputs.append((sx, sy))
            
    await update_board(ctx, env)

@bot.command(name="tech", aliases=["tree", "research"])
async def tech_tree_cmd(ctx, tech_id: str = None):
    """Xem và Nghiên cứu Cây Công Nghệ"""
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    
    if not tech_id:
        lines = []
        for tid, tinfo in TECH_TREE.items():
            status = "✅ Đã mở" if tid in env.unlocked_techs else f"🔒 **${tinfo['cost']}**"
            lines.append(f"• `!research {tid}`: **{tinfo['name']}** ({status})\n  _{tinfo['desc']}_")
        
        embed = discord.Embed(title="🔬 CÂY CÔNG NGHỆ (TECH TREE)", description="\n\n".join(lines), color=0x9b59b6)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(20)
        return await msg.delete()
        
    tid = tech_id.lower()
    if tid in TECH_TREE:
        if tid in env.unlocked_techs:
            msg = await ctx.send("✅ Công nghệ này đã được nghiên cứu từ trước!")
            await asyncio.sleep(4)
            return await msg.delete()
            
        tinfo = TECH_TREE[tid]
        if env.money < tinfo["cost"]:
            msg = await ctx.send(f"❌ Không đủ tiền nghiên cứu! Cần **${tinfo['cost']}**.")
            await asyncio.sleep(4)
            return await msg.delete()
            
        env.money -= tinfo["cost"]
        env.unlocked_techs.add(tid)
        msg = await ctx.send(f"🎉 Đã hoàn tất nghiên cứu **{tinfo['name']}**!")
        await asyncio.sleep(5)
        await msg.delete()
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

@bot.command(name="trigger")
async def trigger_io(ctx, x: int, y: int):
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    b = env.grid[x][y]
    if b.type == SWITCH: b.out_val = not b.out_val
    elif b.type == BUTTON: b.out_val = True
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
                placed_blocks.append(f"- Block {info.get('label')} tại ({x},{y}), Inputs: {b.inputs}")
                
    if not placed_blocks:
        prompt = "Mạch hiện tại đang trống. Gợi ý chiến lược xây dựng nhà máy khai thác hoặc mạch logic đơn giản."
    else:
        circuit_desc = "\n".join(placed_blocks[:30])
        prompt = f"Phân tích hệ thống mạch/nhà máy công nghiệp sau và tối ưu hóa hiệu suất:\n{circuit_desc}"

    try:
        response = ai_model.generate_content(prompt)
        embed = discord.Embed(title="🤖 GEMINI AI - PHÂN TÍCH TỐI ƯU HỆ THỐNG", description=response.text[:2000], color=0x9b59b6)
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
    embed = discord.Embed(title="📚 INDUSTRIAL LOGIC SIMULATOR - HƯỚNG DẪN LỆNH", color=0x00ff7f)
    
    embed.add_field(
        name="🏭 TỰ ĐỘNG HÓA & CÔNG NGHỆ",
        value="`!tech` / `!research <id>` : Xem & Mở khóa Cây Công Nghệ.\n"
              "`!autobuild` (hoặc `!ab`) : Xem danh sách & Xây dựng tự động mạch/nhà máy mẫu (tốn tiền).\n"
              "`!set <tên_khối> <x> <y>` : Mua & Đặt khối đơn lẻ.",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ XÂY DỰNG & KẾT NỐI",
        value="`!connect <x1> <y1> to <x2> <y2>` : Nối dây dẫn/tín hiệu.\n"
              "`!trigger <x> <y>` : Bật/Tắt công tắc (`switch`) hoặc nút bấm (`button`).",
        inline=False
    )
    
    embed.add_field(
        name="⚡ VẬN HÀNH & KINH TẾ",
        value="`!step [số_tick]` : Chạy chu kỳ sản xuất & truyền tín hiệu.\n"
              "`!ai_analyze` : Nhờ Gemini AI đánh giá và tối ưu dây chuyền.",
        inline=False
    )

    embed.add_field(
        name="🔣 CÁC KHỐI CÔNG NGHIỆP MỚI",
        value="• Khai thác: `drill` (máy khoan), `pump` (giàn khoan dầu)\n"
              "• Vận chuyển: `conv` (băng tải), `pipe` (ống dẫn), `truck` (trạm xe xuất hàng)",
        inline=False
    )
    
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(20)
    try: await msg.delete()
    except: pass

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
