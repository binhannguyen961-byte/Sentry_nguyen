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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

# Flask Server giữ Bot sống 24/7
app = Flask(__name__)
@app.route('/')
def home(): return "DDLC Open World Engine Online!"
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
        self.text = "Chào mừng Nam trở lại! Hôm nay chúng ta sẽ làm gì đây?"
        self.location = "clubroom.jpg" # Bối cảnh mặc định
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

# --- HÀM VẼ GIAO DIỆN (CÓ HÌNH NỀN) ---
def render_screen(state):
    img_w, img_h = 600, 400
    img = Image.new("RGB", (img_w, img_h), (25, 20, 35))
    draw = ImageDraw.Draw(img)

    try:
        font_name = ImageFont.truetype("arial.ttf", 22)
        font_text = ImageFont.truetype("arial.ttf", 18)
    except:
        font_name = font_text = ImageFont.load_default()

    # 1. Vẽ Background (Nếu có file)
    if os.path.exists(state.location):
        try:
            bg_img = Image.open(state.location).convert("RGBA")
            bg_img = bg_img.resize((img_w, img_h))
            img.paste(bg_img, (0, 0))
        except: pass

    if state.mode == "POEM":
        # Màn hình làm thơ
        draw.rectangle([50, 30, 550, 370], fill=(40, 30, 50, 200))
        draw.text((200, 40), f"📝 POEM MINIGAME ({state.poem_count} từ)", fill=(255, 150, 200), font=font_name)
        
        for idx, item in enumerate(state.poem_words):
            cy = 100 + idx * 50
            color = (255, 100, 180) if idx == state.poem_idx else (70, 50, 80)
            draw.rectangle([100, cy, 500, cy + 40], fill=color)
            draw.text((120, cy + 10), f"{idx+1}. {item['word']}", fill=(255,255,255), font=font_text)
            
    else:
        # 2. Vẽ Nhân vật
        char_file = f"{state.speaker.lower()}.png"
        if os.path.exists(char_file):
            try:
                char_img = Image.open(char_file).convert("RGBA")
                char_img = char_img.resize((250, 350))
                img.paste(char_img, (175, 50), char_img)
            except: pass
            
        # 3. Khung thoại
        box_y1 = 280
        draw.rectangle([20, box_y1, 580, 380], fill=(20, 15, 30, 220), outline=(255, 100, 180), width=3)
        draw.rectangle([30, box_y1 - 15, 160, box_y1 + 15], fill=(255, 100, 180))
        draw.text((40, box_y1 - 10), state.speaker, fill=(255, 255, 255), font=font_name)
        
        wrapped = textwrap.fill(state.text, width=55)
        draw.text((35, box_y1 + 25), wrapped, fill=(240, 240, 240), font=font_text)

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
        embed = discord.Embed(title="DDLC: Mở Rộng", color=0xff77aa)
        embed.set_image(url="attachment://game.png")
        await interaction.message.edit(embed=embed, attachments=[file])

    @discord.ui.button(label="⬆️ Lên", style=discord.ButtonStyle.blurple, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = (self.state.poem_idx - 1) % 4
            await self.handle_update(interaction)

    @discord.ui.button(label="⬇️ Xuống", style=discord.ButtonStyle.blurple, row=0)
    async def btn_down(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = (self.state.poem_idx + 1) % 4
            await self.handle_update(interaction)

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
                st.text = f"Bài thơ Nam viết... tớ rất thích nó. Chúng ta ra ngoài dạo một lát không?"
            else:
                words = []
                for c, w_list in POEM_WORDS.items():
                    words.append({"word": random.choice(w_list), "char": c})
                random.shuffle(words)
                st.poem_words = words
                st.poem_idx = 0
            await self.handle_update(interaction)
        else:
            await process_ai_story(self.ctx, st, "Người chơi ấn tiếp tục.")
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

# --- XỬ LÝ CỐT TRUYỆN MỞ BẰNG AI ---
async def process_ai_story(ctx, state, user_input):
    if not ai_model: return
    
    prompt = f"""
    Bạn là Game Engine quản lý thế giới mở DDLC. Cốt truyện có thể vượt ra khỏi trường học (VD: quán cafe, đường phố, nhà riêng, lễ hội...).
    - Người chơi tên: Nam.
    - Địa điểm hiện tại: {state.location}
    - Điểm tình cảm: {state.scores}
    - Hành động/Lời nói của Nam: {user_input}
    
    Tạo tình tiết tiếp theo. Hãy quyết định xem có đổi cảnh hay không.
    Trả về định dạng JSON nghiêm ngặt:
    {{
        "speaker": "Tên nhân vật (hoặc 'Hệ Thống')",
        "text": "Lời thoại hoặc mô tả tiếng Việt (tối đa 25 từ).",
        "location": "clubroom.jpg hoặc street.jpg hoặc cafe.jpg hoặc park.jpg",
        "bgm": "club.mp3 hoặc street.mp3 hoặc romance.mp3"
    }}
    """
    try:
        res = ai_model.generate_content(prompt)
        data = json.loads(res.text.replace("```json", "").replace("```", "").strip())
        state.speaker = data.get("speaker", state.speaker)
        state.text = data.get("text", "...")
        new_loc = data.get("location", state.location)
        
        # Xử lý đổi nhạc nếu chuyển cảnh
        if "bgm" in data and state.voice_client and state.voice_client.is_connected():
            bgm_file = data["bgm"]
            if os.path.exists(bgm_file):
                if state.voice_client.is_playing(): state.voice_client.stop()
                state.voice_client.play(discord.FFmpegPCMAudio(bgm_file))
                
        state.location = new_loc
    except Exception as e:
        print(e)
        state.text = "Có vẻ mọi người đang suy nghĩ..."

# --- LỆNH CHÍNH ---
@bot.command(name="start")
async def start_game(ctx):
    state = get_session(ctx.guild.id)
    state.game_active = True
    
    # Kết nối vào Voice Channel để phát nhạc
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        try:
            state.voice_client = await channel.connect()
            if os.path.exists("club.mp3"):
                state.voice_client.play(discord.FFmpegPCMAudio("club.mp3"))
        except: pass

    buf = render_screen(state)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(title="DDLC: THẾ GIỚI MỞ", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    view = GameControls(ctx, state)
    state.last_msg = await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="chat")
async def player_chat(ctx, *, message: str):
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    if not state.game_active: return
    
    await process_ai_story(ctx, state, f"Nam nói/làm: {message}")
    
    buf = render_screen(state)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(title="DDLC: THẾ GIỚI MỞ", description=f"🗣️ **Nam:** {message}", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    if state.last_msg:
        await state.last_msg.edit(embed=embed, attachments=[file], view=GameControls(ctx, state))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
