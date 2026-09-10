import os, io, asyncio, threading, json, random, textwrap
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
from discord.ui import Button, View
import google.generativeai as genai

# --- CẤU HÌNH API & DISCORD ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

# Thư mục chứa asset (hình ảnh ghép sẵn, nhạc, font)
ASSETS_DIR = "assets"

def get_asset(filename):
    return os.path.join(ASSETS_DIR, filename)

# Flask Server giữ Bot sống 24/7 trên hosting
app = Flask(__name__)
@app.route('/')
def home(): return "DDLC Open World Engine (CG Mode) Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# --- CƠ SỞ DỮ LIỆU ---
POEM_WORDS = {
    "Sayori": ["Nắng", "Hạnh phúc", "Cầu vồng", "Ấm áp", "Bạn bè", "Nụ cười", "Mây"],
    "Yuri": ["Bí ẩn", "U tối", "Sâu thẳm", "Triết học", "Đam mê", "Trà", "Đêm"],
    "Natsuki": ["Kẹo", "Dễ thương", "Hồng", "Bánh kem", "Manga", "Ngọt ngào"],
    "Monika": ["Tương lai", "Thực tại", "Tình yêu", "Lập trình", "Tự do", "Vĩnh cửu"]
}

class GameState:
    def __init__(self):
        self.game_active = False
        self.mode = "STORY" # STORY hoặc POEM
        self.speaker = "Monika"
        self.text = "Chào mừng Nam trở lại! Hôm nay chúng ta sẽ làm gì đây? Bấm nút hoặc dùng lệnh !chat nhé!"
        self.bg_image = "club_monika.jpg" # File ảnh ghép sẵn mặc định trong assets
        self.scores = {"Sayori": 0, "Yuri": 0, "Natsuki": 0, "Monika": 0}
        self.poem_words = []
        self.poem_idx = 0
        self.poem_count = 5
        self.last_msg = None
        self.voice_client = None

game_session = {}
def get_session(guild_id):
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- HÀM VẼ GIAO DIỆN VỚI ẢNH GHÉP SẴN ---
def render_screen(state):
    img_w, img_h = 600, 400
    
    # Nạp Font chữ tiếng Việt từ thư mục assets
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
        # Màn hình làm thơ (Dùng nền màu tối cho dễ nhìn chữ)
        img = Image.new("RGB", (img_w, img_h), (25, 20, 35))
        draw = ImageDraw.Draw(img)
        
        draw.rectangle([40, 20, 560, 380], fill=(20, 15, 30), outline=(255, 100, 180), width=2)
        draw.text((180, 35), f"📝 POEM MINIGAME ({state.poem_count} từ)", fill=(255, 150, 200), font=font_name)
        
        for idx, item in enumerate(state.poem_words):
            cy = 90 + idx * 55
            color = (255, 100, 180) if idx == state.poem_idx else (50, 35, 65)
            draw.rectangle([80, cy, 520, cy + 45], fill=color, outline=(255, 180, 220), width=1)
            draw.text((100, cy + 10), f"{idx+1}. {item['word']}", fill=(255, 255, 255), font=font_text)
            
    else:
        # 1. Nạp ảnh ghép sẵn trọn gói (Background + Nhân vật)
        bg_path = get_asset(state.bg_image)
        if os.path.exists(bg_path):
            try:
                img = Image.open(bg_path).convert("RGB")
                img = img.resize((img_w, img_h))
            except Exception as e:
                print(f"Lỗi load ảnh ghép sẵn: {e}")
                img = Image.new("RGB", (img_w, img_h), (35, 25, 45))
        else:
            # Fallback nếu chưa có file ảnh ghép
            img = Image.new("RGB", (img_w, img_h), (35, 25, 45))

        draw = ImageDraw.Draw(img)
            
        # 2. Khung thoại (Dialogue Box) đè lên phía dưới ảnh
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
        embed = discord.Embed(title="🎮 DDLC: THẾ GIỚI MỞ", color=0xff77aa)
        embed.set_image(url="attachment://game.png")
        await interaction.message.edit(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="⬆️ Lên", style=discord.ButtonStyle.blurple, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = (self.state.poem_idx - 1) % 4
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⬇️ Xuống", style=discord.ButtonStyle.blurple, row=0)
    async def btn_down(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = (self.state.poem_idx + 1) % 4
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
                st.text = f"Bài thơ Nam viết tuyệt quá! Tớ rất thích những cảm xúc này."
            else:
                words = []
                for c, w_list in POEM_WORDS.items():
                    words.append({"word": random.choice(w_list), "char": c})
                random.shuffle(words)
                st.poem_words = words
                st.poem_idx = 0
            await self.handle_update(interaction)
        else:
            await process_ai_story(self.ctx, st, "Người chơi ấn tiếp tục cốt truyện.")
            await self.handle_update(interaction)

    @discord.ui.button(label="📝 Viết Thơ", style=discord.ButtonStyle.danger, row=1)
    async def btn_poem(self, interaction: discord.Interaction, button: Button):
        st = self.state
        if st.mode == "STORY":
            st.mode = "POEM"
            st.poem_count = 5
            st.poem_idx = 0
            words = []
            for c, w_list in POEM_WORDS.items():
                words.append({"word": random.choice(w_list), "char": c})
            random.shuffle(words)
            st.poem_words = words
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

# --- XỬ LÝ CỐT TRUYỆN MỞ BẰNG AI ---
async def process_ai_story(ctx, state, user_input):
    if not ai_model:
        state.text = "AI chưa được cấu hình API Key!"
        return
    
    prompt = f"""
    Bạn là Game Engine quản lý thế giới mở DDLC. 
    - Người chơi: Y/N
    - Nhân vật hiện tại: {state.speaker}
    - File ảnh ghép sẵn (background + nhân vật) đang dùng: {state.bg_image}
    - Hành động của Nam: {user_input}
    
    Hãy chọn file ảnh ghép sẵn phù hợp từ danh sách sau dựa theo ngữ cảnh diễn biến:
    - 'club_monika.jpg' (Phòng CLB với Monika)
    - 'club_sayori.jpg' (Phòng CLB với Sayori)
    - 'club_yuri.jpg' (Phòng CLB với Yuri)
    - 'club_natsuki.jpg' (Phòng CLB với Natsuki)
    - 'cafe_date.jpg' (Buổi hẹn hò ở quán cafe)
    - 'park_walk.jpg' (Đi dạo công viên)
    - 'street_sunset.jpg' (Đường phố hoàng hôn)
    
    Trả về định dạng JSON nghiêm ngặt (không kèm markdown khác):
    {{
        "speaker": "Tên nhân vật (Monika, Sayori, Yuri hoặc Natsuki)",
        "text": "Lời thoại ngắn gọn bằng tiếng Việt (tối đa 25 từ).",
        "bg_image": "Tên file ảnh ghép sẵn phù hợp trong danh sách trên",
        "bgm": "club.mp3 hoặc street.mp3 hoặc romance.mp3"
    }}
    """
    try:
        res = ai_model.generate_content(prompt)
        raw_text = res.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_text)
        
        state.speaker = data.get("speaker", state.speaker)
        state.text = data.get("text", "...")
        state.bg_image = data.get("bg_image", state.bg_image)
        
        # Đổi nhạc nền qua Voice Bot nếu có file nhạc tương ứng trong assets
        if "bgm" in data and state.voice_client and state.voice_client.is_connected():
            bgm_file = get_asset(data["bgm"])
            if os.path.exists(bgm_file):
                if state.voice_client.is_playing():
                    state.voice_client.stop()
                state.voice_client.play(discord.FFmpegPCMAudio(bgm_file))
    except Exception as e:
        print(f"Lỗi AI: {e}")
        state.text = "Mọi người đang chăm chú lắng nghe bạn..."

# --- LỆNH CHÍNH ---
@bot.command(name="start")
async def start_game(ctx):
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    state.game_active = True
    
    # Kết nối vào phòng Voice để phát nhạc nền
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
    embed = discord.Embed(title="🎮 DDLC: THẾ GIỚI MỞ", description="Sử dụng các nút bên dưới hoặc gõ lệnh `!chat <nội dung>` để trò chuyện!", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    view = GameControls(ctx, state)
    state.last_msg = await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="chat")
async def player_chat(ctx, *, message: str):
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    if not state.game_active:
        return
    
    await process_ai_story(ctx, state, f"Nam nói/làm: {message}")
    
    buf = render_screen(state)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(title="🎮 DDLC: THẾ GIỚI MỞ", description=f"🗣️ **Nam:** {message}", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    if state.last_msg:
        try:
            await state.last_msg.edit(embed=embed, attachments=[file], view=GameControls(ctx, state))
        except:
            state.last_msg = await ctx.send(embed=embed, file=file, view=GameControls(ctx, state))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
