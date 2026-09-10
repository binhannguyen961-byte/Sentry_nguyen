import os, io, asyncio, threading, json
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
def home(): return "Mini Game Engine & Fixed Monitor Console Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

class GameConsole:
    def __init__(self):
        self.current_game = None
        self.game_state = {}
        self.screen_matrix = [[" " for _ in range(16)] for _ in range(10)] # Màn hình 16x10 pixel
        self.buttons = {
            "UP": (2, 6), "DOWN": (2, 8), "LEFT": (1, 7), "RIGHT": (3, 7),
            "A": (6, 7), "B": (8, 7), "START": (5, 9)
        }
        self.last_message = None

    def render_console(self):
        # Kích thước khung ảnh chính
        img_w, img_h = 600, 700
        img = Image.new("RGB", (img_w, img_h), (18, 20, 26))
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 16)
            font_pixel = ImageFont.truetype("arial.ttf", 20)
            font_btn = ImageFont.truetype("arial.ttf", 14)
        except:
            font_title = font_pixel = font_btn = ImageFont.load_default()

        # -------------------------------------------------------------
        # 1. MÀN HÌNH MÁY TÍNH CỐ ĐỊNH PHÍA TRÊN (FIXED SCREEN / MONITOR)
        # -------------------------------------------------------------
        screen_x1, screen_y1, screen_x2, screen_y2 = 30, 40, 570, 360
        # Viền màn hình Monitor
        draw.rectangle([screen_x1 - 10, screen_y1 - 10, screen_x2 + 10, screen_y2 + 10], fill=(40, 44, 52), outline=(70, 75, 88), width=3)
        # Vùng hiển thị hiển thị chính (Bên trong)
        draw.rectangle([screen_x1, screen_y1, screen_x2, screen_y2], fill=(10, 15, 20))

        # Tiêu đề Màn hình
        game_title = f"🖥️ MONITOR - GAME: {self.current_game.upper() if self.current_game else 'NO GAME LOADED'}"
        draw.text((screen_x1 + 10, screen_y1 - 30), game_title, fill=(0, 255, 200), font=font_title)

        # Render các điểm pixel/ký tự trong game lên màn hình máy tính
        cell_w = (screen_x2 - screen_x1) / 16
        cell_h = (screen_y2 - screen_y1) / 10

        for r in range(10):
            for c in range(16):
                char = self.screen_matrix[r][c]
                px = screen_x1 + c * cell_w + cell_w / 4
                py = screen_y1 + r * cell_h + cell_h / 6

                if char == "S": # Snake / Player
                    draw.rectangle([screen_x1 + c * cell_w + 2, screen_y1 + r * cell_h + 2,
                                    screen_x1 + (c + 1) * cell_w - 2, screen_y1 + (r + 1) * cell_h - 2], fill=(0, 255, 120))
                elif char == "F": # Food / Target
                    draw.rectangle([screen_x1 + c * cell_w + 2, screen_y1 + r * cell_h + 2,
                                    screen_x1 + (c + 1) * cell_w - 2, screen_y1 + (r + 1) * cell_h - 2], fill=(255, 60, 60))
                elif char == "#": # Wall / Barrier
                    draw.rectangle([screen_x1 + c * cell_w + 1, screen_y1 + r * cell_h + 1,
                                    screen_x1 + (c + 1) * cell_w - 1, screen_y1 + (r + 1) * cell_h - 1], fill=(100, 100, 120))
                elif char != " ":
                    draw.text((px, py), char, fill=(255, 255, 255), font=font_pixel)

        # -------------------------------------------------------------
        # 2. KHU VỰC BẢNG ĐIỀU KHIỂN & NÚT BẤM PHÍA DƯỚI (CONTROLLER GRID)
        # -------------------------------------------------------------
        ctrl_y1 = 390
        draw.text((30, ctrl_y1), "🎮 CONTROLLER PANEL (Dùng !press <nút>)", fill=(200, 200, 200), font=font_title)

        # Vẽ lưới các nút bấm
        btn_grid_x, btn_grid_y = 30, ctrl_y1 + 30
        grid_cols, grid_rows = 10, 5
        btn_size = 50

        for r in range(grid_rows):
            for c in range(grid_cols):
                bx = btn_grid_x + c * (btn_size + 5)
                by = btn_grid_y + r * (btn_size + 5)
                
                # Nút mặc định ô trống
                btn_name = ""
                btn_color = (30, 35, 45)
                
                # Gán tên cho nút dựa vào vị trí
                for b_key, (b_col, b_row) in self.buttons.items():
                    if b_col == c and b_row == r + 5: # Offset row
                        btn_name = b_key
                        btn_color = (220, 50, 70) if b_key in ("A", "B") else (60, 120, 210)

                draw.rectangle([bx, by, bx + btn_size, by + btn_size], fill=btn_color, outline=(60, 65, 80))
                if btn_name:
                    draw.text((bx + 8, by + 15), btn_name, fill=(255, 255, 255), font=font_btn)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

guild_consoles = {}
def get_console(guild_id):
    if guild_id not in guild_consoles:
        guild_consoles[guild_id] = GameConsole()
    return guild_consoles[guild_id]

async def safe_delete(ctx):
    try: await ctx.message.delete()
    except: pass

async def update_console_board(ctx, console):
    buf = console.render_console()
    file = discord.File(fp=buf, filename="console.png")
    embed = discord.Embed(
        title="🕹️ AI MINI GAME CONSOLE", 
        description=f"🎮 **Game Đang Chạy:** `{console.current_game or 'Chưa mở game'}`\n"
                    f"👉 **Lệnh điều khiển:** `!press <UP/DOWN/LEFT/RIGHT/A/B/START>`", 
        color=0x00ffaa
    )
    embed.set_image(url="attachment://console.png")
    
    if console.last_message:
        try: await console.last_message.edit(embed=embed, attachments=[file])
        except: console.last_message = await ctx.send(embed=embed, file=file)
    else:
        console.last_message = await ctx.send(embed=embed, file=file)

# ==========================================
# CÁC LỆNH ĐIỀU KHIỂN CONSOLE & MINI GAME
# ==========================================

@bot.command(name="opengame")
async def open_game(ctx, *, game_name: str = None):
    """Lệnh mở game: AI sẽ tra cứu độ phức tạp và nạp game lên màn hình máy tính"""
    await safe_delete(ctx)
    if not game_name:
        msg = await ctx.send("❌ Vui lòng nhập tên game! Cú pháp: `!opengame <tên_game>`")
        await asyncio.sleep(5)
        return await msg.delete()

    console = get_console(ctx.guild.id)
    
    if not ai_model:
        msg = await ctx.send("❌ Chưa cấu hình GEMINI_API_KEY!")
        await asyncio.sleep(5)
        return await msg.delete()

    # Nhờ AI tra cứu độ phức tạp
    prompt = f"""
    Phân tích tựa game: '{game_name}'.
    Yêu cầu trả về JSON chính xác theo dạng:
    {{
        "is_executable": true/false,
        "reason": "Lý do ngắn gọn nếu không thể chạy (do game quá phức tạp) hoặc xác nhận chạy được nếu là mini game đơn giản",
        "game_type": "snake / pong / tictactoe / flappy / space_invaders / custom"
    }}
    Lưu ý: Chỉ chấp nhận các mini game 2D đơn giản (Snake, Pong, Tic-Tac-Toe, Flappy Bird, Tetris, Brick Breaker...). 
    Từ chối các game 3D, game thế giới mở hoặc quá phức tạp (như GTA, Genshin, CoD...).
    """
    
    try:
        res = ai_model.generate_content(prompt)
        text_res = res.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_res)

        if not data.get("is_executable"):
            embed = discord.Embed(
                title="🚫 KHÔNG THỂ CHẠY GAME",
                description=f"**Game:** {game_name}\n**Lý do:** {data.get('reason')}\n\n💡 *Gợi ý: Hãy thử các game đơn giản như: `snake`, `pong`, `tictactoe`, `flappy bird`, `tetris`...*",
                color=0xff5555
            )
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(10)
            return await msg.delete()

        # Khởi tạo Mini Game lên Màn Hình Máy Tính
        g_type = data.get("game_type", "snake")
        console.current_game = game_name
        console.screen_matrix = [[" " for _ in range(16)] for _ in range(10)]

        if "snake" in g_type or "rắn" in game_name.lower():
            console.game_state = {"snake": [(5, 5), (5, 4)], "dir": "RIGHT", "food": (3, 10)}
            for r, c in console.game_state["snake"]: console.screen_matrix[r][c] = "S"
            fr, fc = console.game_state["food"]
            console.screen_matrix[fr][fc] = "F"
        elif "pong" in g_type:
            console.game_state = {"p1": 4, "p2": 4, "ball": (4, 8)}
            for r in range(10):
                console.screen_matrix[r][0] = "|" if abs(r - 4) <= 1 else " "
                console.screen_matrix[r][15] = "|" if abs(r - 4) <= 1 else " "
            console.screen_matrix[4][8] = "O"
        else:
            # Khởi tạo mặc định
            console.screen_matrix[4][7] = "A"
            console.screen_matrix[4][8] = "I"

        msg = await ctx.send(f"✅ AI đã nạp thành công **{game_name.upper()}** lên Màn hình Máy tính!")
        await asyncio.sleep(4)
        await msg.delete()
        await update_console_board(ctx, console)

    except Exception as e:
        msg = await ctx.send(f"Lỗi khi tra cứu game từ AI: {e}")
        await asyncio.sleep(5)
        await msg.delete()

@bot.command(name="press", aliases=["btn"])
async def press_button(ctx, button_name: str = None):
    """Lệnh tương tác nút bấm trên tay cầm"""
    await safe_delete(ctx)
    if not button_name: return
    console = get_console(ctx.guild.id)
    btn = button_name.upper()

    if not console.current_game:
        msg = await ctx.send("⚠️ Vui lòng mở game trước bằng lệnh `!opengame <tên_game>`!")
        await asyncio.sleep(5)
        return await msg.delete()

    # Logic xử lý game Snake cơ bản khi bấm nút
    if "snake" in console.current_game.lower() or "rắn" in console.current_game.lower():
        st = console.game_state
        if btn in ("UP", "DOWN", "LEFT", "RIGHT"):
            st["dir"] = btn

        # Di chuyển rắn
        head_r, head_c = st["snake"][0]
        if st["dir"] == "UP": head_r = (head_r - 1) % 10
        elif st["dir"] == "DOWN": head_r = (head_r + 1) % 10
        elif st["dir"] == "LEFT": head_c = (head_c - 1) % 16
        elif st["dir"] == "RIGHT": head_c = (head_c + 1) % 16

        new_head = (head_r, head_c)
        st["snake"].insert(0, new_head)
        
        if new_head == st["food"]:
            # Ăn mồi -> Tạo mồi mới
            st["food"] = ((head_r + 3) % 10, (head_c + 5) % 16)
        else:
            st["snake"].pop()

        # Render lại matrix
        console.screen_matrix = [[" " for _ in range(16)] for _ in range(10)]
        for r, c in st["snake"]: console.screen_matrix[r][c] = "S"
        fr, fc = st["food"]
        console.screen_matrix[fr][fc] = "F"

    await update_console_board(ctx, console)

@bot.command(name="help", aliases=["h"])
async def help_cmd(ctx):
    await safe_delete(ctx)
    embed = discord.Embed(
        title="📖 CẨM NANG AI MINI GAME CONSOLE", 
        description="Chương trình mô phỏng Máy chơi game Mini với Màn hình cố định & AI tra cứu game.",
        color=0x00ffaa
    )
    
    embed.add_field(
        name="🖥️ 1. LỆNH MỞ GAME (!opengame)",
        value="• `!opengame <tên_game>` :\n"
              "  > AI sẽ tự động kiểm tra độ phức tạp của game.\n"
              "  > **Game chạy được:** các game 2D/Mini Game đơn giản (*Snake, Pong, Tic-Tac-Toe, Flappy Bird, Tetris...*)\n"
              "  > **Game từ chối:** các game quá nặng hoặc 3D phức tạp (*GTA V, Genshin Impact, Call of Duty...*)\n"
              "  > _Ví dụ:_ `!opengame Rắn săn mồi` hoặc `!opengame Pong`",
        inline=False
    )

    embed.add_field(
        name="🎮 2. LỆNH BẤM NÚT ĐIỀU KHIỂN (!press)",
        value="• `!press <nút>` :\n"
              "  > Tương tác trực tiếp với bảng nút bấm phía dưới màn hình.\n"
              "  > các nút khả dụng: `UP`, `DOWN`, `LEFT`, `RIGHT`, `A`, `B`, `START`.\n"
              "  > _Ví dụ:_ `!press UP` hoặc `!press A`",
        inline=False
    )

    msg = await ctx.send(embed=embed)
    await asyncio.sleep(25)
    try: await msg.delete()
    except: pass

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
