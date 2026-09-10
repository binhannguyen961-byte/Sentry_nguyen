import os, io, asyncio, threading, json, random
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
import google.generativeai as genai

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
def home(): return "DDLC Poem Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# Kho từ vựng viết thơ DDLC
POEM_WORDS = {
    "Sayori": ["Nắng", "Hạnh phúc", "Cầu vồng", "Ấm áp", "Bạn bè", "Nụ cười", "Mây", "Cùng nhau"],
    "Yuri": ["Bí ẩn", "U tối", "Sâu thẳm", "Triết học", "Đam mê", "Hỗn loạn", "Đêm", "Tâm hồn"],
    "Natsuki": ["Kẹo", "Dễ thương", "Hồng", "Bánh kem", "Anime", "Ngọt ngào", "Vui vẻ", "Nhỏ bé"],
    "Monika": ["Tương lai", "Thực tại", "Tình yêu", "Định mệnh", "Tự do", "Viết", "Giai điệu", "Vĩnh cửu"]
}

class GameConsole:
    def __init__(self):
        self.current_game = None
        self.game_state = {}
        self.buttons = {
            "UP": (2, 6), "DOWN": (2, 8), "LEFT": (1, 7), "RIGHT": (3, 7),
            "A": (6, 7), "B": (8, 7), "START": (5, 9)
        }
        self.last_message = None

    def generate_poem_words(self):
        # Chọn ngẫu nhiên 4 từ đại diện cho 4 nhân vật
        words = []
        for char, w_list in POEM_WORDS.items():
            words.append({"word": random.choice(w_list), "char": char})
        random.shuffle(words)
        return words

    def render_console(self):
        img_w, img_h = 600, 700
        img = Image.new("RGB", (img_w, img_h), (18, 20, 26))
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 15)
            font_speaker = ImageFont.truetype("arial.ttf", 14)
            font_text = ImageFont.truetype("arial.ttf", 13)
            font_btn = ImageFont.truetype("arial.ttf", 14)
        except:
            font_title = font_speaker = font_text = font_btn = ImageFont.load_default()

        # 1. MÀN HÌNH MONITOR FIX CỐ ĐỊNH
        screen_x1, screen_y1, screen_x2, screen_y2 = 30, 40, 570, 360
        draw.rectangle([screen_x1 - 10, screen_y1 - 10, screen_x2 + 10, screen_y2 + 10], fill=(40, 44, 52), outline=(70, 75, 88), width=3)
        draw.rectangle([screen_x1, screen_y1, screen_x2, screen_y2], fill=(25, 20, 35))

        game_title = f"🖥️ MONITOR - {self.current_game.upper() if self.current_game else 'NO GAME'}"
        draw.text((screen_x1 + 10, screen_y1 - 30), game_title, fill=(255, 150, 200), font=font_title)

        if self.current_game and "doki" in self.current_game.lower():
            mode = self.game_state.get("mode", "STORY")

            # GIAO DIỆN POEM MINIGAME
            if mode == "POEM":
                draw.text((screen_x1 + 150, screen_y1 + 15), "📝 POEM MINIGAME", fill=(255, 100, 180), font=font_title)
                words_left = self.game_state.get("poem_count", 5)
                draw.text((screen_x1 + 20, screen_y1 + 40), f"Số từ còn lại: {words_left}/5", fill=(200, 200, 200), font=font_text)

                words = self.game_state.get("current_words", [])
                selected_idx = self.game_state.get("selected_idx", 0)

                for idx, item in enumerate(words):
                    cy = screen_y1 + 80 + idx * 45
                    bg_color = (255, 100, 180) if idx == selected_idx else (50, 35, 60)
                    draw.rectangle([screen_x1 + 80, cy, screen_x2 - 80, cy + 35], fill=bg_color, outline=(255, 180, 220), width=2)
                    draw.text((screen_x1 + 100, cy + 8), f"{idx+1}. {item['word']}", fill=(255, 255, 255), font=font_text)

                draw.text((screen_x1 + 40, screen_y2 - 25), "Dùng UP/DOWN để chọn từ, bấm A để xác nhận!", fill=(180, 180, 180), font=font_text)

            # GIAO DIỆN VISUAL NOVEL THƯỜNG
            else:
                speaker = self.game_state.get("speaker", "Monika")
                dialogue = self.game_state.get("text", "Chúc mừng bạn đã đến với Câu lạc bộ Văn học!")

                # Render Sprite
                char_x, char_y = 230, 80
                draw.rectangle([char_x, char_y, char_x + 80, char_y + 140], fill=(255, 180, 200), outline=(220, 100, 150), width=2)
                draw.text((char_x + 10, char_y + 50), f"[{speaker[0]}]", fill=(100, 30, 60), font=font_speaker)

                # Dialogue Box
                box_x1, box_y1, box_x2, box_y2 = screen_x1 + 15, screen_y2 - 100, screen_x2 - 15, screen_y2 - 15
                draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(20, 15, 30), outline=(255, 100, 180), width=2)
                
                draw.rectangle([box_x1 + 10, box_y1 - 12, box_x1 + 120, box_y1 + 10], fill=(255, 100, 180))
                draw.text((box_x1 + 15, box_y1 - 10), speaker, fill=(255, 255, 255), font=font_speaker)

                words_list = dialogue.split(" ")
                line1 = " ".join(words_list[:8])
                line2 = " ".join(words_list[8:])
                draw.text((box_x1 + 15, box_y1 + 18), line1, fill=(240, 240, 240), font=font_text)
                if line2:
                    draw.text((box_x1 + 15, box_y1 + 38), line2, fill=(240, 240, 240), font=font_text)

        # 2. CONTROLLER PANEL
        ctrl_y1 = 390
        draw.text((30, ctrl_y1), "🎮 CONTROLLER PANEL", fill=(200, 200, 200), font=font_title)

        btn_grid_x, btn_grid_y = 30, ctrl_y1 + 30
        grid_cols, grid_rows = 10, 5
        btn_size = 50

        for r in range(grid_rows):
            for c in range(grid_cols):
                bx = btn_grid_x + c * (btn_size + 5)
                by = btn_grid_y + r * (btn_size + 5)
                btn_name = ""
                btn_color = (30, 35, 45)
                
                for b_key, (b_col, b_row) in self.buttons.items():
                    if b_col == c and b_row == r + 5:
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
        title="🕹️ DDLC ENGINE & POEM MINIGAME", 
        description=f"🎮 **Game:** `{console.current_game}`\n👉 **Chế độ:** `{console.game_state.get('mode', 'STORY')}`", 
        color=0xff77aa
    )
    embed.set_image(url="attachment://console.png")
    
    if console.last_message:
        try: await console.last_message.edit(embed=embed, attachments=[file])
        except: console.last_message = await ctx.send(embed=embed, file=file)
    else:
        console.last_message = await ctx.send(embed=embed, file=file)

@bot.command(name="opengame")
async def open_game(ctx, *, game_name: str = None):
    await safe_delete(ctx)
    if not game_name: return
    console = get_console(ctx.guild.id)
    console.current_game = game_name

    if "doki" in game_name.lower():
        console.game_state = {
            "mode": "STORY",
            "speaker": "Monika",
            "text": "Chào mừng bạn! Hôm nay chúng ta sẽ bắt đầu viết thơ nhé. Bấm START để vào Poem Minigame!",
            "step": 1,
            "scores": {"Sayori": 0, "Yuri": 0, "Natsuki": 0, "Monika": 0}
        }
        msg = await ctx.send("🌸 **DDLC with Poem Minigame** đã sẵn sàng!")
        await asyncio.sleep(3)
        await msg.delete()
        await update_console_board(ctx, console)

@bot.command(name="press", aliases=["btn"])
async def press_button(ctx, button_name: str = None):
    await safe_delete(ctx)
    if not button_name: return
    console = get_console(ctx.guild.id)
    btn = button_name.upper()

    if console.current_game and "doki" in console.current_game.lower():
        st = console.game_state

        # Chuyển đổi sang Chế độ Viết thơ khi bấm START
        if btn == "START" and st["mode"] == "STORY":
            st["mode"] = "POEM"
            st["poem_count"] = 5
            st["selected_idx"] = 0
            st["current_words"] = console.generate_poem_words()

        # Xử lý trong Chế độ Poem Minigame
        elif st["mode"] == "POEM":
            if btn == "UP":
                st["selected_idx"] = (st["selected_idx"] - 1) % 4
            elif btn == "DOWN":
                st["selected_idx"] = (st["selected_idx"] + 1) % 4
            elif btn == "A":
                # Cộng điểm cho nhân vật tương ứng với từ đã chọn
                chosen_item = st["current_words"][st["selected_idx"]]
                char = chosen_item["char"]
                st["scores"][char] = st.get("scores", {}).get(char, 0) + 1
                st["poem_count"] -= 1

                if st["poem_count"] <= 0:
                    # Hoàn thành bài thơ -> Quay lại Story với phản ứng của nhân vật có điểm cao nhất
                    best_char = max(st["scores"], key=st["scores"].get)
                    st["mode"] = "STORY"
                    st["speaker"] = best_char
                    st["text"] = f"Bài thơ của bạn tuyệt quá! Tớ rất thích những từ ngữ bạn chọn!"
                else:
                    st["current_words"] = console.generate_poem_words()
                    st["selected_idx"] = 0

        # Xử lý đọc thoại Story bình thường
        elif st["mode"] == "STORY" and btn == "A":
            st["step"] += 1
            if ai_model:
                prompt = f"""
                Bạn là Game Engine DDLC.
                Tạo câu thoại ngắn gọn tiếp theo (dưới 15 từ). 
                Nhân vật: {st['speaker']}.
                Trả về JSON: {{"speaker": "{st['speaker']}", "text": "Lời thoại"}}
                """
                try:
                    res = ai_model.generate_content(prompt)
                    data = json.loads(res.text.replace("```json", "").replace("```", "").strip())
                    st["text"] = data.get("text", "Cùng tiếp tục trò chuyện nào!")
                except:
                    st["text"] = "Mọi người đang chăm chú đọc bài thơ của bạn."

    await update_console_board(ctx, console)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
