import os, io, asyncio, threading, json, random, textwrap
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
from discord.ui import Button, View
import google.generativeai as genai

# --- CẤU HÌNH 2 MÃ API DỰ PHÒNG ---
api_keys = []
if os.environ.get("GEMINI_API_KEY"):
    api_keys.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"):
    api_keys.append(os.environ.get("GEMINI_API_KEY_2"))

current_key_idx = 0

def get_next_ai_model():
    """Hàm lấy model AI theo cơ chế xoay vòng giữa các API Key"""
    global current_key_idx
    if not api_keys:
        return None
    
    # Lấy key hiện tại cấu hình
    active_key = api_keys[current_key_idx]
    genai.configure(api_key=active_key)
    
    # Chuyển sang key tiếp theo cho lần gọi sau (xoay vòng tròn)
    current_key_idx = (current_key_idx + 1) % len(api_keys)
    
    return genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

ASSETS_DIR = "assets"

def get_asset(filename):
    base_path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(base_path):
        return base_path
    name_root, ext = os.path.splitext(filename)
    variants = [ext.lower(), ext.upper(), ".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG"]
    for v in variants:
        alt_path = os.path.join(ASSETS_DIR, name_root + v)
        if os.path.exists(alt_path):
            return alt_path
    return base_path

# Flask Server giữ Bot sống 24/7 trên hosting
app = Flask(__name__)
@app.route('/')
def home(): return "DDLC Open World Engine (Dual API Keys) Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# --- CƠ SỞ DỮ LIỆU MINIGAME ---
POEM_WORDS = {
    "Sayori": ["Nắng", "Hạnh phúc", "Cầu vồng", "Ấm áp", "Bạn bè", "Nụ cười", "Mây"],
    "Yuri": ["Bí ẩn", "U tối", "Sâu thẳm", "Triết học", "Đam mê", "Trà", "Đêm"],
    "Natsuki": ["Kẹo", "Dễ thương", "Hồng", "Bánh kem", "Manga", "Ngọt ngào"],
    "Monika": ["Tương lai", "Thực tại", "Tình yêu", "Lập trình", "Tự do", "Vĩnh cửu"]
}

CHAR_MINIGAMES = {
    "Sayori": {
        "title": "🌈 Đuổi Bắt Cảm Xúc (Sayori)",
        "choices": ["Ôm ấp động viên", "Kể chuyện cười", "Tặng kẹo ngọt", "Lắng nghe tâm sự"],
        "correct": 0
    },
    "Yuri": {
        "title": "📖 Giải Mã Triết Học (Yuri)",
        "choices": ["Vũ trụ và ý thức", "Bản ngã con người", "Thời gian vô tận", "Bóng tối tâm hồn"],
        "correct": 2
    },
    "Natsuki": {
        "title": "🧁 Nướng Cupcake (Natsuki)",
        "choices": ["Thêm đường bột", "Đánh bông kem", "Trang trí dâu tây", "Nướng lò 180°C"],
        "correct": 2
    },
    "Monika": {
        "title": "💻 Gỡ Lỗi Python (Monika)",
        "choices": ["import love", "print(Y/N)", "while True: run()", "os.remove(barriers)"],
        "correct": 3
    }
}

class GameState:
    def __init__(self):
        self.game_active = False
        self.mode = "STORY"
        self.speaker = "Monika"
        self.user_name = "Y/N"
        self.text = "Chào mừng Y/N trở lại! Hãy nói chuyện hoặc chọn hành động nhé!"
        self.bg_image = "club_monika.JPEG"
        self.scores = {"Sayori": 0, "Yuri": 0, "Natsuki": 0, "Monika": 0}
        
        self.poem_words = []
        self.poem_idx = 0
        self.poem_count = 5
        
        self.char_game_idx = 0
        self.last_msg = None
        self.voice_client = None

game_session = {}
def get_session(guild_id):
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- HÀM VẼ GIAO DIỆN ---
def render_screen(state):
    img_w, img_h = 600, 400
    
    font_file = get_asset("font_regular.ttf")
    try:
        if os.path.exists(font_file):
            font_name = ImageFont.truetype(font_file, 24)
            font_text = ImageFont.truetype(font_file, 20)
        else:
            font_name = font_text = ImageFont.load_default()
    except:
        font_name = font_text = ImageFont.load_default()

    if state.mode == "POEM":
        img = Image.new("RGB", (img_w, img_h), (25, 20, 35))
        draw = ImageDraw.Draw(img)
        draw.rectangle([40, 20, 560, 380], fill=(20, 15, 30), outline=(255, 100, 180), width=2)
        draw.text((160, 35), f"📝 POEM MINIGAME ({state.poem_count} từ)", fill=(255, 150, 200), font=font_name)
        
        for idx, item in enumerate(state.poem_words):
            cy = 90 + idx * 55
            color = (255, 100, 180) if idx == state.poem_idx else (50, 35, 65)
            draw.rectangle([80, cy, 520, cy + 45], fill=color, outline=(255, 180, 220), width=1)
            draw.text((100, cy + 10), f"{idx+1}. {item['word']}", fill=(255, 255, 255), font=font_text)
            
    elif state.mode == "CHAR_GAME":
        img = Image.new("RGB", (img_w, img_h), (30, 20, 40))
        draw = ImageDraw.Draw(img)
        game_info = CHAR_MINIGAMES.get(state.speaker, CHAR_MINIGAMES["Monika"])
        
        draw.rectangle([40, 20, 560, 380], fill=(20, 15, 30), outline=(100, 200, 255), width=2)
        draw.text((130, 35), game_info["title"], fill=(150, 220, 255), font=font_name)
        
        for idx, choice_text in enumerate(game_info["choices"]):
            cy = 90 + idx * 65
            color = (80, 140, 200) if idx == state.char_game_idx else (40, 30, 60)
            draw.rectangle([80, cy, 520, cy + 50], fill=color, outline=(150, 200, 255), width=1)
            draw.text((100, cy + 12), f"• {choice_text}", fill=(255, 255, 255), font=font_text)
    else:
        bg_path = get_asset(state.bg_image)
        if os.path.exists(bg_path):
            try:
                img = Image.open(bg_path).convert("RGB")
                img = img.resize((img_w, img_h))
            except Exception as e:
                print(f"Lỗi load ảnh {state.bg_image}: {e}")
                img = Image.new("RGB", (img_w, img_h), (35, 25, 45))
        else:
            img = Image.new("RGB", (img_w, img_h), (35, 25, 45))

        draw = ImageDraw.Draw(img)
            
        box_y1 = 250
        draw.rectangle([15, box_y1, 585, 385], fill=(20, 15, 30), outline=(255, 100, 180), width=3)
        draw.rectangle([25, box_y1 - 18, 180, box_y1 + 15], fill=(255, 100, 180))
        draw.text((35, box_y1 - 14), state.speaker, fill=(255, 255, 255), font=font_name)
        
        wrapped = textwrap.fill(state.text, width=42)
        draw.text((30, box_y1 + 22), wrapped, fill=(245, 245, 245), font=font_text)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

# --- DISCORD UI BUTTONS ---
class GameControls(View):
    def __init__(self, ctx, state):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.state = state

    async def handle_update(self, interaction):
        await interaction.response.defer()
        buf = render_screen(self.state)
        file = discord.File(fp=buf, filename="game.png")
        embed = discord.Embed(title=f"🎮 DDLC: THẾ GIỚI MỞ ({self.state.user_name})", color=0xff77aa)
        embed.set_image(url="attachment://game.png")
        await interaction.message.edit(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="⬆️ Lên", style=discord.ButtonStyle.blurple, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = (self.state.poem_idx - 1) % 4
            await self.handle_update(interaction)
        elif self.state.mode == "CHAR_GAME":
            self.state.char_game_idx = (self.state.char_game_idx - 1) % 4
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⬇️ Xuống", style=discord.ButtonStyle.blurple, row=0)
    async def btn_down(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = (self.state.poem_idx + 1) % 4
            await self.handle_update(interaction)
        elif self.state.mode == "CHAR_GAME":
            self.state.char_game_idx = (self.state.char_game_idx + 1) % 4
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="🅰️ Chọn / Tiếp Tục", style=discord.ButtonStyle.green, row=1)
    async def btn_a(self, interaction: discord.Interaction, button: Button):
        st = self.state
        if st.mode == "POEM":
            chosen = st.poem_words[st.poem_idx]
            st.scores[chosen["char"]] += 1
            st.poem_count -= 1
            if st.poem_count <= 0:
                st.mode = "STORY"
                best_char = max(st.scores, key=st.scores.get)
                st.speaker = best_char
                st.text = f"Bài thơ tuyệt vời quá, {st.user_name}!"
            else:
                words = [{"word": random.choice(w_list), "char": c} for c, w_list in POEM_WORDS.items()]
                random.shuffle(words)
                st.poem_words = words
                st.poem_idx = 0
            await self.handle_update(interaction)
            
        elif st.mode == "CHAR_GAME":
            game_info = CHAR_MINIGAMES[st.speaker]
            if st.char_game_idx == game_info["correct"]:
                st.scores[st.speaker] += 2
                st.text = f"Tuyệt đỉnh! {st.user_name} hiểu tớ quá đi mất!"
            else:
                st.text = f"Hơi tiếc một chút, nhưng không sao đâu {st.user_name}!"
            st.mode = "STORY"
            await self.handle_update(interaction)
        else:
            await process_ai_story(self.ctx, st, f"{st.user_name} bấm tiếp tục cốt truyện.")
            await self.handle_update(interaction)

    @discord.ui.button(label="📝 Minigame Riêng", style=discord.ButtonStyle.danger, row=1)
    async def btn_special_game(self, interaction: discord.Interaction, button: Button):
        st = self.state
        if st.mode == "STORY":
            st.mode = "CHAR_GAME"
            st.char_game_idx = 0
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

# --- XỬ LÝ CỐT TRUYỆN MỞ BẰNG AI (XOAY VÒNG 2 API KEY) ---
async def process_ai_story(ctx, state, user_input):
    model = get_next_ai_model()
    if not model:
        state.text = "Chưa cấu hình API Key trên hệ thống!"
        return
    
    prompt = f"""
    Bạn là Game Engine quản lý thế giới mở DDLC. 
    - Tên người chơi: {state.user_name}
    - Nhân vật hiện tại: {state.speaker}
    - Ảnh nền hiện tại: {state.bg_image}
    - Hành động của {state.user_name}: {user_input}
    
    Hãy viết một câu thoại mới phù hợp bằng tiếng Việt cho nhân vật nói với {state.user_name}, đồng thời chọn một file ảnh khớp chính xác 100% từ danh sách sau dựa theo diễn biến:
    - 'club_monika.JPEG' | 'club_sayori.jpg' | 'club_yuri.jpg' | 'club_natsuki.JPEG'
    - 'cafe_monika.JPEG' | 'cafe_sayori.JPEG' | 'cafe_yuri.JPEG' | 'cafe_natsuki.JPEG'
    - 'park_monika.JPEG' | 'park_sayori.JPEG' | 'park_yuri.JPEG' | 'park_natsuki.JPEG'
    - 'street_monika.JPEG' | 'street_sayori.JPEG' | 'street_yuri.JPEG' | 'street_natsuki.JPEG'
    
    Trả về ĐÚNG cấu trúc JSON gồm 3 trường: speaker, text, bg_image.
    """
    
    # Thử gọi API qua key hiện tại, nếu lỗi tự động đổi key còn lại thử lại lần 2
    for attempt in range(len(api_keys) if api_keys else 1):
        try:
            res = model.generate_content(prompt)
            data = json.loads(res.text.strip())
            
            state.speaker = data.get("speaker", state.speaker)
            state.text = data.get("text", state.text)
            state.bg_image = data.get("bg_image", state.bg_image)
            return
        except Exception as e:
            print(f"Lỗi AI với Key hiện tại (Lần thử {attempt+1}): {e}")
            # Lấy model với key tiếp theo để thử lại
            model = get_next_ai_model()

# --- LỆNH CHÍNH ---
@bot.command(name="start")
async def start_game(ctx):
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    state.game_active = True
    
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        try:
            if not state.voice_client or not state.voice_client.is_connected():
                state.voice_client = await channel.connect()
            club_music = get_asset("club.mp3")
            if os.path.exists(club_music) and not state.voice_client.is_playing():
                state.voice_client.play(discord.FFmpegPCMAudio(club_music))
        except Exception as e:
            print(f"Lỗi Voice: {e}")

    buf = render_screen(state)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(title=f"🎮 DDLC: THẾ GIỚI MỞ ({state.user_name})", description="Dùng nút hoặc gõ `!chat <nội dung>` để trò chuyện!", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    view = GameControls(ctx, state)
    state.last_msg = await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="name")
async def set_username(ctx, *, name: str):
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    state.user_name = name.strip()
    await ctx.send(f"✅ Đã đổi tên người chơi thành: **{state.user_name}**", delete_after=5)

@bot.command(name="chat")
async def player_chat(ctx, *, message: str):
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    if not state.game_active:
        return
    
    await process_ai_story(ctx, state, f"{state.user_name} nói/làm: {message}")
    
    buf = render_screen(state)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(title=f"🎮 DDLC: THẾ GIỚI MỞ ({state.user_name})", description=f"🗣️ **{state.user_name}:** {message}", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    if state.last_msg:
        try:
            await state.last_msg.edit(embed=embed, attachments=[file], view=GameControls(ctx, state))
        except:
            state.last_msg = await ctx.send(embed=embed, file=file, view=GameControls(ctx, state))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
