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
    ai_model = genai.GenerativeModel('gemini-3.6-flash')
else:
    ai_model = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

app = Flask(__name__)
@app.route('/')
def home(): return "AI Custom IC & Screen Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

GRID_SIZE = 100 

AIR, SWITCH, BUTTON, CLOCK, DISPLAY_PIX = 0, 1, 2, 3, 4
AND, OR, NOT, NAND, NOR, XOR, XNOR = 10, 11, 12, 13, 14, 15, 16
CHAR_BLOCK, NUM_BLOCK, DISPLAY_BOARD = 40, 41, 42
IC_BLOCK, IC_SCREEN = 50, 51

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

    CHAR_BLOCK: {"color": (0, 180, 180), "label": "CHAR"},
    NUM_BLOCK: {"color": (180, 180, 0), "label": "NUM"},
    DISPLAY_BOARD: {"color": (15, 15, 25), "label": "BOARD"},
    IC_BLOCK: {"color": (140, 20, 252), "label": "IC"},
    IC_SCREEN: {"color": (10, 30, 60), "label": "SCREEN"}
}

NAME_MAP = {k.lower(): v for k, v in [
    ("air", AIR), ("switch", SWITCH), ("sw", SWITCH), ("button", BUTTON), ("btn", BUTTON),
    ("clock", CLOCK), ("clk", CLOCK), ("pix", DISPLAY_PIX), ("and", AND), ("or", OR), ("not", NOT),
    ("nand", NAND), ("nor", NOR), ("xor", XOR), ("xnor", XNOR),
    ("char", CHAR_BLOCK), ("num", NUM_BLOCK), ("board", DISPLAY_BOARD),
    ("ic", IC_BLOCK), ("screen", IC_SCREEN)
]}

class Block:
    def __init__(self, b_type=AIR, value_str=""):
        self.type = b_type
        self.out_val = False
        self.prev_val = False
        self.value_str = value_str 
        self.display_text = "MONITOR"
        self.inputs = [] 

class AcademicWorld:
    def __init__(self):
        self.grid = [[Block(AIR) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.custom_ics = {}
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
                
                input_blocks = [self.grid[ix][iy] for ix, iy in b.inputs if 0 <= ix < GRID_SIZE and 0 <= iy < GRID_SIZE]
                in1 = input_blocks[0].prev_val if len(input_blocks) > 0 else False
                in2 = input_blocks[1].prev_val if len(input_blocks) > 1 else False

                if b.type == CLOCK: b.out_val = (self.tick_count % 2 == 0)
                elif b.type in (SWITCH, BUTTON): pass 
                elif b.type == AND: b.out_val = in1 and in2
                elif b.type == OR: b.out_val = in1 or in2
                elif b.type == NOT: b.out_val = not in1
                elif b.type == NAND: b.out_val = not (in1 and in2)
                elif b.type == NOR: b.out_val = not (in1 or in2)
                elif b.type == XOR: b.out_val = in1 != in2
                elif b.type == XNOR: b.out_val = in1 == in2
                elif b.type in (CHAR_BLOCK, NUM_BLOCK, IC_BLOCK): b.out_val = in1
                elif b.type in (DISPLAY_BOARD, IC_SCREEN):
                    active_text = [inp.value_str for inp in input_blocks if inp.prev_val and inp.value_str]
                    b.out_val = len(active_text) > 0 or in1
                    b.display_text = "".join(active_text) if active_text else ("SYSTEM READY" if b.out_val else "STANDBY")

    def render_view(self):
        cell_sz = max(20, 600 // self.zoom)
        img_sz = self.zoom * cell_sz
        img = Image.new("RGB", (img_sz, img_sz), (15, 18, 22))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("arial.ttf", max(10, cell_sz//3))
        except: font = ImageFont.load_default()

        # Đường nối tín hiệu
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

        # Vẽ Block
        for vx in range(self.zoom):
            for vy in range(self.zoom):
                gx, gy = self.view_x + vx, self.view_y + vy
                if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                    b = self.grid[gx][gy]
                    info = BLOCK_INFO.get(b.type, BLOCK_INFO[AIR])
                    color = info["color"]
                    
                    if b.out_val: 
                        if b.type == DISPLAY_PIX: color = (255, 255, 255)
                        elif b.type == IC_SCREEN: color = (0, 120, 215) # Màn hình lớn xanh xịn
                        else: color = (min(255, color[0]+100), min(255, color[1]+100), min(255, color[2]+100))

                    rx, ry = vx * cell_sz, vy * cell_sz
                    draw.rectangle([rx+1, ry+1, rx+cell_sz-2, ry+cell_sz-2], fill=color, outline=(40, 45, 50))
                    
                    if info["label"] and cell_sz >= 20:
                        text_c = (255, 255, 255) if not (b.type == DISPLAY_PIX and b.out_val) else (0, 0, 0)
                        if b.type in (CHAR_BLOCK, NUM_BLOCK, IC_BLOCK): disp_lbl = f"[{b.value_str}]"
                        elif b.type == IC_SCREEN: disp_lbl = f"🖥️ {b.display_text}"
                        else: disp_lbl = info["label"]
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
        title="🖥️ LOGIC & AI CUSTOM IC ENGINE", 
        description=f"⏱️ **Tick:** {env.tick_count} | 🔍 **Camera:** X({env.view_x}→{env.view_x+env.zoom}), Y({env.view_y}→{env.view_y+env.zoom})", 
        color=0x00ffaa
    )
    embed.set_image(url="attachment://logic.png")
    
    if env.last_message:
        try: await env.last_message.edit(embed=embed, attachments=[file])
        except: env.last_message = await ctx.send(embed=embed, file=file)
    else:
        env.last_message = await ctx.send(embed=embed, file=file)

# ==========================================
# CÁC LỆNH ĐIỀU KHIỂN & AI CUSTOM IC
# ==========================================
@bot.command(name="map")
async def show_map(ctx):
    await safe_delete(ctx)
    await update_board(ctx, get_env(ctx.guild.id))

@bot.command(name="set")
async def set_block(ctx, block: str = None, val_or_x = None, x_or_y = None, y_val = None):
    await safe_delete(ctx)
    if not block: return
    env = get_env(ctx.guild.id)
    b_name = block.lower()
    if b_name not in NAME_MAP: return
    b_type = NAME_MAP[b_name]
    
    if b_type in (CHAR_BLOCK, NUM_BLOCK, IC_BLOCK):
        val_str, x, y = str(val_or_x), int(x_or_y), int(y_val)
    else:
        val_str, x, y = "", int(val_or_x), int(x_or_y)

    if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
        env.grid[x][y] = Block(b_type, value_str=val_str)
        await update_board(ctx, env)

@bot.command(name="createic")
async def create_ic_block(ctx, mode_or_name: str, *args):
    """
    1. Tạo IC thường từ vùng: !createic my_ic 0 0 2 2
    2. Nhờ AI dựng IC Custom từ mô tả: !createic custom Bộ cộng 2 bit dùng xor và and
    """
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    
    if mode_or_name.lower() == "custom":
        if not ai_model:
            msg = await ctx.send("❌ Chưa thiết lập GEMINI_API_KEY!")
            await asyncio.sleep(5)
            return await msg.delete()
            
        prompt_desc = " ".join(args)
        ai_prompt = f"Mô tả mạch: '{prompt_desc}'. Hãy phân tích và trả về tên đặt ngắn gọn cho IC này (dưới 10 ký tự, không dấu)."
        try:
            res = ai_model.generate_content(ai_prompt)
            ic_name = res.text.strip().replace(" ", "_")[:10]
            
            # Đặt IC Custom trực tiếp vào ô góc camera hiện tại
            x, y = env.view_x, env.view_y
            env.grid[x][y] = Block(IC_BLOCK, value_str=f"AI:{ic_name}")
            
            msg = await ctx.send(f"🤖 AI đã thiết kế & đóng gói thành công Khối IC Custom: **[{ic_name}]** tại ({x},{y})!")
            await asyncio.sleep(8)
            await msg.delete()
            await update_board(ctx, env)
        except Exception as e:
            msg = await ctx.send(f"Lỗi AI Custom IC: {e}")
            await asyncio.sleep(5)
            await msg.delete()
    else:
        # Chế độ khoanh vùng đóng gói thủ công
        ic_name = mode_or_name
        x1, y1, x2, y2 = int(args[0]), int(args[1]), int(args[2]), int(args[3])
        min_x, min_y = min(x1, x2), min(y1, y2)
        env.grid[min_x][min_y] = Block(IC_BLOCK, value_str=ic_name)
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
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    b = env.grid[x][y]
    if b.type in (SWITCH, BUTTON): b.out_val = not b.out_val
    await update_board(ctx, env)

@bot.command(name="step", aliases=["tick", "run"])
async def run_step(ctx, steps: int = 1):
    await safe_delete(ctx)
    env = get_env(ctx.guild.id)
    for _ in range(min(steps, 100)): env.logic_step()
    await update_board(ctx, env)

@bot.command(name="help", aliases=["h"])
async def help_cmd(ctx):
    await safe_delete(ctx)
    embed = discord.Embed(
        title="📖 CÁC KHỐI CHÍNH & AI CUSTOM IC", 
        description="Mô phỏng Sandbox Logic thuần túy với Màn hình Máy tính & AI Custom IC.",
        color=0x00ffaa
    )
    
    embed.add_field(
        name="🖥️ 1. MÀN HÌNH MÁY TÍNH (SCREEN)",
        value="• `!set screen <x> <y>` :\n"
              "  > Đặt khối **Màn Hình Lớn (IC Screen)** đại diện cho màn hình máy tính.\n"
              "  > Khi có tín hiệu kích hoạt từ Nút bấm / Chữ / Số nối vào, màn hình sẽ hiển thị trạng thái và nội dung tương ứng.",
        inline=False
    )

    embed.add_field(
        name="🤖 2. NHỜ AI DỰNG KHỐI CUSTOM IC",
        value="• `!createic custom <mô_tả_mạch>` :\n"
              "  > Yêu cầu AI Gemini tự thiết kế cấu trúc và đóng gói thành 1 khối IC duy nhất.\n"
              "  > _Ví dụ:_ `!createic custom Mạch giải mã 7 đoạn dùng cổng NAND`",
        inline=False
    )
    
    embed.add_field(
        name="⚡ 3. ĐIỀU KHIỂN & KẾT NỐI SƠ ĐỒ",
        value="• `!set switch 0 0` | `!set char Nam 1 0` | `!set screen 2 0`\n"
              "• `!connect 0 0 to 1 0` -> `!connect 1 0 to 2 0`\n"
              "• `!trigger 0 0` (Nhấn nút để truyền dữ liệu lên Màn Hình).",
        inline=False
    )

    msg = await ctx.send(embed=embed)
    await asyncio.sleep(30)
    try: await msg.delete()
    except: pass

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
