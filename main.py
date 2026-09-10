import os, io, asyncio, threading, json, random, textwrap, time
from datetime import datetime, timedelta
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
    
    active_key = api_keys[current_key_idx]
    genai.configure(api_key=active_key)
    
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

# --- CƠ SỞ DỮ LIỆU MINIGAME MỞ RỘNG ---
POEM_WORDS = {
    "Sayori": ["Nắng", "Hạnh phúc", "Cầu vồng", "Ấm áp", "Bạn bè", "Nụ cười", "Mây", "Tươi sáng", "Yêu thương", "Hy vọng"],
    "Yuri": ["Bí ẩn", "U tối", "Sâu thẳm", "Triết học", "Đam mê", "Trà", "Đêm", "Tâm linh", "Kinh điển", "Tư duy"],
    "Natsuki": ["Kẹo", "Dễ thương", "Hồng", "Bánh kem", "Manga", "Ngọt ngào", "Sáng tạo", "Cô độc", "Sức mạnh", "Giấc mơ"],
    "Monika": ["Tương lai", "Thực tại", "Tình yêu", "Lập trình", "Tự do", "Vĩnh cửu", "Thiên định", "Kiểm soát", "Tâm thức", "Vũ trụ"]
}

CHAR_MINIGAMES = {
    "Sayori": {
        "title": "🌈 Đuổi Bắt Cảm Xúc (Sayori)",
        "choices": ["Ôm ấp động viên", "Kể chuyện cười", "Tặng kẹo ngọt", "Lắng nghe tâm sự"],
        "correct": 0,
        "difficulty": "dễ"
    },
    "Yuri": {
        "title": "📖 Giải Mã Triết Học (Yuri)",
        "choices": ["Vũ trụ và ý thức", "Bản ngã con người", "Thời gian vô tận", "Bóng tối tâm hồn"],
        "correct": 2,
        "difficulty": "khó"
    },
    "Natsuki": {
        "title": "🧁 Nướng Cupcake (Natsuki)",
        "choices": ["Thêm đường bột", "Đánh bông kem", "Trang trí dâu tây", "Nướng lò 180°C"],
        "correct": 2,
        "difficulty": "vừa"
    },
    "Monika": {
        "title": "💻 Gỡ Lỗi Python (Monika)",
        "choices": ["import love", "print(Y/N)", "while True: run()", "os.remove(barriers)"],
        "correct": 3,
        "difficulty": "khó"
    }
}

class GameState:
    def __init__(self):
        self.game_active = False
        self.mode = "STORY"  # STORY, POEM, CHAR_GAME, INVENTORY, ACHIEVEMENTS
        self.speaker = "Monika"
        self.user_name = "Y/N"
        self.text = "Chào mừng Y/N trở lại! Hãy nói chuyện hoặc chọn hành động nhé!"
        self.bg_image = "club_monika.JPEG"
        self.scores = {"Sayori": 0, "Yuri": 0, "Natsuki": 0, "Monika": 0}
        
        # --- HỆ THỐNG ĐIỂM VÀ CẤP ĐỘ MỚI ---
        self.total_points = 0
        self.level = 1
        self.experience = 0
        self.exp_next_level = 100
        self.affection = {"Sayori": 0, "Yuri": 0, "Natsuki": 0, "Monika": 0}
        
        # --- HỆ THỐNG POEM NÂNG CAO ---
        self.poem_words = []
        self.poem_idx = 0
        self.poem_count = 10  # Tăng từ 5 lên 10
        self.total_poems = 0
        
        # --- HỆ THỐNG MINIGAME ---
        self.char_game_idx = 0
        self.last_msg = None
        self.voice_client = None
        
        # --- THỐNG KÊ CHƠI ---
        self.game_start_time = None
        self.play_duration = 0
        self.total_chats = 0
        self.achievements = {
            "first_chat": False,
            "poem_master": False,
            "high_affection": False,
            "level_5": False,
            "all_games": False
        }
        
        # --- INVENTORY VÀ SỰ KIỆN ---
        self.inventory = {"chocolate": 0, "flowers": 0, "book": 0, "cupcakes": 0}
        self.current_location = "club"
        self.events_seen = set()

game_session = {}
def get_session(guild_id):
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- HÀM VẼ GIAO DIỆN NÂNG CAO ---
def render_screen(state):
    """Vẽ giao diện game với thiết kế đẹp hơn"""
    img_w, img_h = 800, 600  # Tăng độ phân giải từ 600x400 lên 800x600
    
    font_file = get_asset("font_regular.ttf")
    try:
        if os.path.exists(font_file):
            font_title = ImageFont.truetype(font_file, 32)
            font_name = ImageFont.truetype(font_file, 24)
            font_text = ImageFont.truetype(font_file, 18)
            font_small = ImageFont.truetype(font_file, 14)
        else:
            font_title = font_name = font_text = font_small = ImageFont.load_default()
    except:
        font_title = font_name = font_text = font_small = ImageFont.load_default()

    if state.mode == "POEM":
        img = Image.new("RGB", (img_w, img_h), (15, 10, 20))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Background gradient effect
        draw.rectangle([30, 15, 770, 585], fill=(20, 15, 30), outline=(255, 100, 180), width=3)
        
        # Title với trang trí
        draw.text((280, 30), "📝 POEM MINIGAME 📝", fill=(255, 150, 200), font=font_title)
        draw.text((350, 65), f"{state.poem_count} từ còn lại", fill=(200, 120, 160), font=font_small)
        
        # Hiển thị từ với animation
        for idx, item in enumerate(state.poem_words):
            cy = 110 + idx * 65
            if cy + 50 > 550:
                break
            
            is_selected = idx == state.poem_idx
            if is_selected:
                color = (255, 150, 200)
                bg_color = (80, 40, 70)
                outline_color = (255, 200, 220)
                width = 3
            else:
                color = (150, 100, 140)
                bg_color = (40, 25, 50)
                outline_color = (120, 70, 110)
                width = 1
            
            draw.rectangle([60, cy, 740, cy + 50], fill=bg_color, outline=outline_color, width=width)
            draw.text((90, cy + 12), f"✦ {idx+1}. {item['word']} ({item['char']})", fill=color, font=font_text)
        
        # Progress bar
        progress = (state.total_poems - state.poem_count) / state.total_poems if state.total_poems > 0 else 0
        bar_width = int(700 * progress)
        draw.rectangle([50, 560, 750, 575], fill=(40, 30, 50), outline=(200, 100, 150))
        if bar_width > 0:
            draw.rectangle([50, 560, 50 + bar_width, 575], fill=(255, 100, 180))
            
    elif state.mode == "CHAR_GAME":
        img = Image.new("RGB", (img_w, img_h), (20, 15, 35))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        draw.rectangle([30, 15, 770, 585], fill=(20, 15, 30), outline=(100, 200, 255), width=3)
        game_info = CHAR_MINIGAMES.get(state.speaker, CHAR_MINIGAMES["Monika"])
        
        draw.text((200, 30), game_info["title"], fill=(150, 220, 255), font=font_title)
        difficulty_color = {
            "dễ": (100, 255, 100),
            "vừa": (255, 200, 100),
            "khó": (255, 100, 100)
        }
        draw.text((650, 40), f"[{game_info['difficulty'].upper()}]", fill=difficulty_color.get(game_info['difficulty'], (255, 255, 255)), font=font_small)
        
        for idx, choice_text in enumerate(game_info["choices"]):
            cy = 120 + idx * 90
            is_selected = idx == state.char_game_idx
            
            if is_selected:
                bg_color = (60, 120, 180)
                outline_color = (150, 220, 255)
                width = 3
                text_color = (255, 255, 255)
            else:
                bg_color = (30, 50, 80)
                outline_color = (80, 140, 180)
                width = 1
                text_color = (180, 200, 220)
            
            draw.rectangle([60, cy, 740, cy + 70], fill=bg_color, outline=outline_color, width=width)
            draw.text((90, cy + 18), f"❖ Lựa chọn {idx+1}:", fill=(150, 220, 255), font=font_small)
            draw.text((90, cy + 38), choice_text, fill=text_color, font=font_text)

    elif state.mode == "ACHIEVEMENTS":
        img = Image.new("RGB", (img_w, img_h), (25, 15, 35))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        draw.rectangle([30, 15, 770, 585], fill=(20, 15, 30), outline=(255, 215, 0), width=3)
        draw.text((320, 30), "🏆 ACHIEVEMENTS 🏆", fill=(255, 215, 0), font=font_title)
        
        achievements_data = [
            ("first_chat", "💬 Cuộc Trò Chuyện Đầu Tiên", "Nói chuyện lần đầu tiên"),
            ("poem_master", "📖 Bậc Thầy Thơ Ca", "Viết 5 bài thơ"),
            ("high_affection", "💕 Tình Cảm Mãnh Liệt", "Đạt 50 điểm tình cảm với ai đó"),
            ("level_5", "⭐ Cấp 5", "Lên cấp độ 5"),
            ("all_games", "🎮 Thử Hết Trò Chơi", "Chơi tất cả mini-game")
        ]
        
        for i, (key, title, desc) in enumerate(achievements_data):
            cy = 100 + i * 85
            achieved = state.achievements.get(key, False)
            
            color = (255, 215, 0) if achieved else (100, 100, 100)
            bg_color = (60, 50, 20) if achieved else (30, 30, 30)
            icon = "✓" if achieved else "✗"
            
            draw.rectangle([50, cy, 750, cy + 75], fill=bg_color, outline=color, width=2)
            draw.text((70, cy + 10), f"{icon} {title}", fill=color, font=font_name)
            draw.text((70, cy + 40), desc, fill=(200, 200, 200), font=font_small)

    elif state.mode == "STATS":
        img = Image.new("RGB", (img_w, img_h), (20, 15, 30))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        draw.rectangle([30, 15, 770, 585], fill=(20, 15, 30), outline=(100, 255, 200), width=3)
        draw.text((300, 30), "📊 THỐNG KÊ TRÒ CHƠI 📊", fill=(100, 255, 200), font=font_title)
        
        # Level và Experience
        draw.text((50, 85), f"Cấp độ: {state.level}", fill=(255, 255, 100), font=font_name)
        draw.text((50, 115), f"Kinh nghiệm: {state.experience} / {state.exp_next_level}", fill=(200, 200, 200), font=font_text)
        
        exp_progress = state.experience / state.exp_next_level
        bar_width = int(400 * exp_progress)
        draw.rectangle([50, 145, 450, 160], fill=(50, 40, 60), outline=(100, 255, 200))
        if bar_width > 0:
            draw.rectangle([50, 145, 50 + bar_width, 160], fill=(100, 255, 200))
        
        # Điểm tình cảm
        draw.text((50, 190), "❤️ Tình Cảm:", fill=(255, 100, 150), font=font_name)
        y_pos = 220
        for char, aff in state.affection.items():
            draw.text((70, y_pos), f"{char}: {aff} ⭐", fill=(200, 150, 180), font=font_text)
            y_pos += 30
        
        # Thống kê chung
        draw.text((450, 190), "📈 Thống Kê:", fill=(100, 200, 255), font=font_name)
        draw.text((470, 220), f"Tổng điểm: {state.total_points}", fill=(200, 200, 200), font=font_text)
        draw.text((470, 250), f"Bài thơ: {state.total_poems}", fill=(200, 200, 200), font=font_text)
        draw.text((470, 280), f"Chat: {state.total_chats}", fill=(200, 200, 200), font=font_text)
        
        if state.game_start_time:
            duration = datetime.now() - state.game_start_time
            hours = duration.total_seconds() // 3600
            minutes = (duration.total_seconds() % 3600) // 60
            draw.text((470, 310), f"Thời gian chơi: {int(hours)}h {int(minutes)}m", fill=(200, 200, 200), font=font_text)

    else:  # STORY MODE
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

        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Header với thông tin nhân vật
        draw.rectangle([0, 0, img_w, 50], fill=(20, 15, 30, 200))
        draw.text((15, 12), f"💕 {state.speaker} • Điểm: {state.scores[state.speaker]}", fill=(255, 150, 200), font=font_name)
        draw.text((img_w - 200, 12), f"Cấp: {state.level} | XP: {state.experience}", fill=(100, 255, 200), font=font_text)
        
        # Hộp thoại chính
        box_y1 = 340
        draw.rectangle([15, box_y1, 785, 585], fill=(20, 15, 30, 240), outline=(255, 100, 180), width=4)
        
        # Tên nhân vật
        draw.rectangle([25, box_y1 - 20, 200, box_y1 + 15], fill=(255, 100, 180))
        draw.text((35, box_y1 - 16), state.speaker, fill=(255, 255, 255), font=font_name)
        
        # Nội dung thoại
        wrapped = textwrap.fill(state.text, width=50)
        draw.text((30, box_y1 + 25), wrapped, fill=(245, 245, 245), font=font_text)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

# --- DISCORD UI BUTTONS NÂNG CAO ---
class GameControls(View):
    def __init__(self, ctx, state):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.state = state

    async def handle_update(self, interaction):
        await interaction.response.defer()
        buf = render_screen(self.state)
        file = discord.File(fp=buf, filename="game.png")
        
        description = f"👤 **{self.state.user_name}** | Cấp {self.state.level}"
        embed = discord.Embed(title=f"🎮 DDLC: THẾ GIỚI MỞ", description=description, color=0xff77aa)
        embed.set_image(url="attachment://game.png")
        
        await interaction.message.edit(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="⬆️ Lên", style=discord.ButtonStyle.blurple, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = max(0, self.state.poem_idx - 1)
            await self.handle_update(interaction)
        elif self.state.mode == "CHAR_GAME":
            self.state.char_game_idx = max(0, self.state.char_game_idx - 1)
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⬇️ Xuống", style=discord.ButtonStyle.blurple, row=0)
    async def btn_down(self, interaction: discord.Interaction, button: Button):
        if self.state.mode == "POEM":
            self.state.poem_idx = min(len(self.state.poem_words) - 1, self.state.poem_idx + 1)
            await self.handle_update(interaction)
        elif self.state.mode == "CHAR_GAME":
            self.state.char_game_idx = min(3, self.state.char_game_idx + 1)
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.gray, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: Button):
        old_mode = self.state.mode
        self.state.mode = "STATS"
        await self.handle_update(interaction)
        self.state.mode = old_mode

    @discord.ui.button(label="🏆 Achievements", style=discord.ButtonStyle.gray, row=0)
    async def btn_achievements(self, interaction: discord.Interaction, button: Button):
        old_mode = self.state.mode
        self.state.mode = "ACHIEVEMENTS"
        await self.handle_update(interaction)
        self.state.mode = old_mode

    @discord.ui.button(label="🅰️ Chọn / Tiếp Tục", style=discord.ButtonStyle.green, row=1)
    async def btn_a(self, interaction: discord.Interaction, button: Button):
        st = self.state
        if st.mode == "POEM":
            chosen = st.poem_words[st.poem_idx]
            points_earned = 10 if st.poem_idx == 0 else 5
            st.scores[chosen["char"]] += points_earned
            st.affection[chosen["char"]] += points_earned
            st.total_points += points_earned
            st.experience += points_earned
            st.poem_count -= 1
            st.total_poems += 1
            
            # Level up check
            while st.experience >= st.exp_next_level:
                st.experience -= st.exp_next_level
                st.level += 1
                st.exp_next_level = int(st.exp_next_level * 1.2)
                st.text = f"🎉 {st.user_name} lên cấp {st.level}!"
            
            # Achievement check
            if st.total_poems >= 5:
                st.achievements["poem_master"] = True
            
            if st.poem_count <= 0:
                st.mode = "STORY"
                best_char = max(st.scores, key=st.scores.get)
                st.speaker = best_char
                st.text = f"Bài thơ tuyệt vời quá, {st.user_name}! ✨"
            else:
                words = [{"word": random.choice(w_list), "char": c} for c, w_list in POEM_WORDS.items()]
                random.shuffle(words)
                st.poem_words = words
                st.poem_idx = 0
            await self.handle_update(interaction)
            
        elif st.mode == "CHAR_GAME":
            game_info = CHAR_MINIGAMES[st.speaker]
            if st.char_game_idx == game_info["correct"]:
                points_earned = 20
                st.scores[st.speaker] += points_earned
                st.affection[st.speaker] += points_earned
                st.total_points += points_earned
                st.experience += points_earned
                st.text = f"Tuyệt đỉnh! {st.user_name} hiểu tớ quá đi mất! 💕"
                st.achievements["all_games"] = True
            else:
                points_earned = 5
                st.total_points += points_earned
                st.experience += points_earned
                st.text = f"Hơi tiếc một chút, nhưng không sao đâu {st.user_name}!"
            
            # Level up check
            while st.experience >= st.exp_next_level:
                st.experience -= st.exp_next_level
                st.level += 1
                st.exp_next_level = int(st.exp_next_level * 1.2)
            
            if st.level >= 5:
                st.achievements["level_5"] = True
            
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

    @discord.ui.button(label="✨ Poem Mode", style=discord.ButtonStyle.danger, row=1)
    async def btn_poem_mode(self, interaction: discord.Interaction, button: Button):
        st = self.state
        if st.mode == "STORY":
            st.mode = "POEM"
            st.poem_count = 10
            st.total_poems = 0
            words = [{"word": random.choice(w_list), "char": c} for c, w_list in POEM_WORDS.items()]
            random.shuffle(words)
            st.poem_words = words
            st.poem_idx = 0
            st.text = "Hãy chọn những từ phù hợp để viết thành bài thơ đẹp!"
            await self.handle_update(interaction)
        else:
            await interaction.response.defer()

# --- XỬ LÝ CỐT TRUYỆN MỞ BẰNG AI (XOAY VÒNG 2 API KEY) ---
async def process_ai_story(ctx, state, user_input):
    model = get_next_ai_model()
    if not model:
        state.text = "Chưa cấu hình API Key trên hệ thống!"
        return
    
    state.total_chats += 1
    if state.total_chats == 1:
        state.achievements["first_chat"] = True
    
    prompt = f"""
    Bạn là Game Engine quản lý thế giới mở DDLC. 
    - Tên người chơi: {state.user_name}
    - Nhân vật hiện tại: {state.speaker}
    - Điểm hiện tại của {state.speaker}: {state.scores[state.speaker]}
    - Cấp độ: {state.level}
    - Ảnh nền hiện tại: {state.bg_image}
    - Hành động của {state.user_name}: {user_input}
    
    Hãy viết một câu thoại mới phù hợp bằng tiếng Việt cho nhân vật nói với {state.user_name}, đồng thời chọn một file ảnh khớp chính xác 100% từ danh sách:
    - 'club_monika.JPEG' | 'club_sayori.jpg' | 'club_yuri.jpg' | 'club_natsuki.JPEG'
    - 'cafe_monika.JPEG' | 'cafe_sayori.JPEG' | 'cafe_yuri.JPEG' | 'cafe_natsuki.JPEG'
    - 'park_monika.JPEG' | 'park_sayori.JPEG' | 'park_yuri.JPEG' | 'park_natsuki.JPEG'
    - 'street_monika.JPEG' | 'street_sayori.JPEG' | 'street_yuri.JPEG' | 'street_natsuki.JPEG'
    
    Trả về ĐÚNG cấu trúc JSON gồm 3 trường: speaker, text, bg_image.
    """
    
    for attempt in range(len(api_keys) if api_keys else 1):
        try:
            res = model.generate_content(prompt)
            data = json.loads(res.text.strip())
            
            state.speaker = data.get("speaker", state.speaker)
            state.text = data.get("text", state.text)
            state.bg_image = data.get("bg_image", state.bg_image)
            
            # Thêm điểm cho việc chat
            state.total_points += 5
            state.experience += 5
            state.affection[state.speaker] += 2
            
            # Level up check
            while state.experience >= state.exp_next_level:
                state.experience -= state.exp_next_level
                state.level += 1
                state.exp_next_level = int(state.exp_next_level * 1.2)
            
            if state.affection[state.speaker] >= 50:
                state.achievements["high_affection"] = True
            
            return
        except Exception as e:
            print(f"Lỗi AI với Key hiện tại (Lần thử {attempt+1}): {e}")
            model = get_next_ai_model()

# --- LỆNH CHÍNH ---
@bot.command(name="start")
async def start_game(ctx):
    """Bắt đầu game"""
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    state.game_active = True
    state.game_start_time = datetime.now()
    
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
    embed = discord.Embed(
        title=f"🎮 DDLC: THẾ GIỚI MỞ", 
        description=f"👤 **{state.user_name}** | Cấp {state.level}\n\n📖 Dùng nút hoặc gõ `!chat <nội dung>` để trò chuyện!", 
        color=0xff77aa
    )
    embed.set_image(url="attachment://game.png")
    
    view = GameControls(ctx, state)
    state.last_msg = await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="name")
async def set_username(ctx, *, name: str):
    """Đổi tên người chơi"""
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    state.user_name = name.strip()
    await ctx.send(f"✅ Đã đổi tên người chơi thành: **{state.user_name}**", delete_after=5)

@bot.command(name="chat")
async def player_chat(ctx, *, message: str):
    """Chat với nhân vật"""
    await ctx.message.delete()
    state = get_session(ctx.guild.id)
    if not state.game_active:
        await ctx.send("⚠️ Bạn chưa bắt đầu game! Dùng `!start` để bắt đầu.", delete_after=5)
        return
    
    await process_ai_story(ctx, state, f"{state.user_name} nói/làm: {message}")
    
    buf = render_screen(state)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(
        title=f"🎮 DDLC: THẾ GIỚI MỞ", 
        description=f"🗣️ **{state.user_name}:** {message[:100]}", 
        color=0xff77aa
    )
    embed.set_image(url="attachment://game.png")
    
    if state.last_msg:
        try:
            await state.last_msg.edit(embed=embed, attachments=[file], view=GameControls(ctx, state))
        except:
            state.last_msg = await ctx.send(embed=embed, file=file, view=GameControls(ctx, state))
    else:
        state.last_msg = await ctx.send(embed=embed, file=file, view=GameControls(ctx, state))

@bot.command(name="reset")
async def reset_game(ctx):
    """Reset game"""
    await ctx.message.delete()
    if ctx.guild.id in game_session:
        del game_session[ctx.guild.id]
    await ctx.send("✅ Game đã được reset!", delete_after=5)

@bot.command(name="help")
async def show_help(ctx):
    """Hiển thị hướng dẫn"""
    await ctx.message.delete()
    embed = discord.Embed(title="📖 Hướng Dẫn Chơi DDLC Open World", color=0xff77aa)
    embed.add_field(name="🎮 Các Lệnh Chính", value=
        "`!start` - Bắt đầu game\n"
        "`!name <tên>` - Đặt tên nhân vật\n"
        "`!chat <lời nói>` - Chat với nhân vật\n"
        "`!reset` - Reset game\n"
        "`!help` - Xem hướng dẫn", inline=False)
    embed.add_field(name="🎯 Hệ Thống Điểm", value=
        "💬 Chat: +5 XP\n"
        "📝 Chọn từ thơ: +5-10 XP\n"
        "🎮 Mini-game đúng: +20 XP\n"
        "⭐ Level up tự động khi có đủ XP", inline=False)
    embed.add_field(name="📚 Chế Độ Chơi", value=
        "🎭 Story Mode: Tương tác với nhân vật\n"
        "✨ Poem Mode: Viết 10 bài thơ\n"
        "🎮 Mini-game: Chơi trò riêng của từng nhân vật", inline=False)
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/fake/image.png")
    await ctx.send(embed=embed)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
