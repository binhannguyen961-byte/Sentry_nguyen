import asyncio
import io
import json
import os
import textwrap
import threading

from discord.ext import commands
from discord.ui import Button, View
import discord
from flask import Flask
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- CẤU HÌNH API KEY ---
api_keys = []
if os.environ.get("GEMINI_API_KEY"):
    api_keys.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"):
    api_keys.append(os.environ.get("GEMINI_API_KEY_2"))

current_key_idx = 0

def get_genai_client():
    global current_key_idx
    if not api_keys:
        return None, None
    active_key = api_keys[current_key_idx]
    current_key_idx = (current_key_idx + 1) % len(api_keys)
    return genai.Client(api_key=active_key), "gemini-2.0-flash"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

ASSETS_DIR = "assets"

def get_asset(filename):
    base_path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(base_path):
        return base_path
    name_root, ext = os.path.splitext(filename)
    for v in [ext.lower(), ext.upper(), ".jpg", ".jpeg", ".png"]:
        alt_path = os.path.join(ASSETS_DIR, name_root + v)
        if os.path.exists(alt_path):
            return alt_path
    return base_path

app = Flask(__name__)

@app.route("/")
def home():
    return "DDLC Pure VN Engine - Deep Story Mode Online!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- CẤU HÌNH NHÂN VẬT & MÀU SẮC ---
CHAR_COLORS = {
    "Sayori": (255, 160, 180),
    "Yuri": (180, 140, 230),
    "Natsuki": (255, 130, 170),
    "Monika": (120, 220, 160),
    "Bác sĩ": (100, 200, 255),
    "Y tá": (150, 220, 200),
    "Nội tâm": (180, 180, 180),
    "System": (200, 200, 200),
}

class GameState:
    def __init__(self):
        self.user_name = "Y/N"
        self.chapter = 1
        self.location_name = "Phòng Bệnh 404 (Sự Đơn Độc)"
        self.speaker = "Nội tâm"
        
        # Mở đầu đầy chiều sâu và cô độc
        self.text = (
            "Tiếng 'tít... tít...' của máy đo nhịp tim vang lên đều đặn, xé toạc sự tĩnh lặng. "
            "Mùi thuốc sát trùng xộc thẳng vào mũi khiến bạn khẽ nhăn mặt. "
            "Ký ức cuối cùng đọng lại là ánh đèn xe chói lòa ngay sau buổi họp thứ hai tại Câu Lạc Bộ Thơ Văn. "
            "Cơ thể bạn nặng trĩu. Căn phòng trống rỗng, lạnh lẽo và hoàn toàn không có lấy một bóng người quen..."
        )
        self.bg_image = "hospital_room_empty.jpg"
        
        self.current_choices = [
            "Cố gắng nhúc nhích ngón tay và mở hẳn mắt ra",
            "Nằm im, mặc kệ cơn đau và chìm vào dòng hồi tưởng",
            "Thóp giọng gọi nhỏ xem có ai ở ngoài hành lang không"
        ]
        
        # Chỉ số ẩn: Trạng thái tinh thần (Sanity) và Hy vọng (Hope)
        self.mental_state = 50 
        self.history = []

game_session = {}

def get_session(guild_id):
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- RENDER GIAO DIỆN PIL (TĂNG TÍNH BẮT MẮT) ---
def render_screen(state):
    img_w, img_h = 800, 600
    font_file = get_asset("font_regular.ttf")

    try:
        font_title = ImageFont.truetype(font_file, 24) if os.path.exists(font_file) else ImageFont.load_default()
        font_name = ImageFont.truetype(font_file, 22) if os.path.exists(font_file) else ImageFont.load_default()
        font_text = ImageFont.truetype(font_file, 19) if os.path.exists(font_file) else ImageFont.load_default()
    except Exception:
        font_title = font_name = font_text = ImageFont.load_default()

    bg_path = get_asset(state.bg_image)
    if os.path.exists(bg_path):
        try:
            img = Image.open(bg_path).convert("RGBA").resize((img_w, img_h))
        except Exception:
            img = Image.new("RGBA", (img_w, img_h), (25, 25, 30, 255))
    else:
        # Gradient nền nếu không có ảnh
        img = Image.new("RGBA", (img_w, img_h), (15, 20, 25, 255))
        draw_temp = ImageDraw.Draw(img)
        for i in range(img_h):
            draw_temp.line([(0, i), (img_w, i)], fill=(15 + int(i/40), 20, 25 + int(i/30), 255))

    # Tạo layer overlay để vẽ các hình khối bán trong suốt
    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top Bar (Header)
    draw.rectangle([0, 0, img_w, 45], fill=(10, 15, 20, 220))
    draw.text((20, 10), f"📍 {state.location_name}", fill=(255, 220, 100, 255), font=font_title)
    
    # Hiển thị thanh Tinh Thần (Mental State)
    mental_color = (100, 255, 100, 255) if state.mental_state > 50 else (255, 150, 150, 255)
    draw.text((600, 12), f"Tâm lý: {state.mental_state}%", fill=mental_color, font=font_text)

    # Hộp thoại Visual Novel (Sleek Design)
    box_y = 370
    theme_color = CHAR_COLORS.get(state.speaker, (200, 200, 200))
    
    # Nền hộp thoại (Trong suốt mờ + Viền)
    draw.rectangle([20, box_y, 780, 580], fill=(10, 12, 18, 215), outline=theme_color, width=2)

    # Thẻ Tên Nhân Vật (Badge)
    if state.speaker:
        badge_width = font_name.getlength(state.speaker) + 40
        draw.rectangle([35, box_y - 25, 35 + badge_width, box_y + 10], fill=theme_color + (255,))
        # Đổ bóng nhẹ cho tên nhân vật
        draw.text((56, box_y - 19), state.speaker, fill=(0, 0, 0, 150), font=font_name)
        draw.text((55, box_y - 20), state.speaker, fill=(20, 20, 20, 255), font=font_name)

    # Gộp overlay vào ảnh chính
    img = Image.alpha_composite(img, overlay)
    draw_final = ImageDraw.Draw(img)

    # Nội dung lời thoại (Text Wrapper)
    wrapped = textwrap.fill(state.text, width=65)
    text_x, text_y = 45, box_y + 25
    
    # Đổ bóng (Drop shadow) cho lời thoại để tăng độ nét
    draw_final.multiline_text((text_x+2, text_y+2), wrapped, fill=(0, 0, 0, 200), font=font_text, spacing=8)
    draw_final.multiline_text((text_x, text_y), wrapped, fill=(245, 245, 250, 255), font=font_text, spacing=8)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf

# --- XỬ LÝ GEMINI AI (ĐÀO SÂU TÂM LÝ) ---
async def process_ai_choice_story(state, user_choice_text):
    client, model_name = get_genai_client()
    if not client:
        state.text = "Lỗi hệ thống: Chưa cấu hình API Key!"
        return

    history_text = "\n".join(state.history[-4:]) if state.history else "Chưa có"

    prompt = f"""
    Bạn là Game Engine AI điều hành Visual Novel "DDLC: Nơi Thời Gian Ngưng Đọng" (Bản Alternate Reality).
    
    - NGỮ CẢNH CỐT TRUYỆN:
      + Kịch bản gốc bị phá vỡ. Tai nạn của MC (nhân vật chính) ở ngày thứ 2 đã ngăn chặn mọi bi kịch kinh dị. Thể loại hiện tại là Chữa lành (Healing), Slice-of-life, và Tâm lý học (Psychological Drama).
      + GIAI ĐOẠN HIỆN TẠI (CHƯƠNG 1): MC ({state.user_name}) đang ở Bệnh Viện. CHƯA CÓ DOKI NÀO XUẤT HIỆN. Các Doki (Sayori, Yuri, Natsuki, Monika) chưa hay tin về vụ tai nạn.
      + Trọng tâm lúc này: Sự cô đơn, cơn đau thể xác, tiếng bíp của máy móc, các tương tác với y tá/bác sĩ, và những đoạn độc thoại nội tâm miên man, giằng xé của MC.

    - Người chơi: {state.user_name}
    - Nhân vật đang tương tác: {state.speaker}
    - Lựa chọn vừa đưa ra: "{user_choice_text}"
    - Lịch sử đối thoại: {history_text}

    YÊU CẦU:
    1. Trả lời bằng tiếng Việt. Viết 1 đoạn văn (khoảng 50-80 từ) miêu tả diễn biến tiếp theo. Hãy dùng ngôn từ giàu sức gợi, tập trung vào ngũ quan (cảm giác lạnh lẽo, mùi thuốc, âm thanh).
    2. Đề xuất 3 lựa chọn tiếp theo hợp logic. Các lựa chọn phải mang tính nội tâm hoặc tương tác với môi trường phòng bệnh.
    3. Cập nhật chỉ số "mental_state_change" (từ -10 đến +10 tùy thuộc lựa chọn của người chơi có tích cực hay buông xuôi).

    TRẢ VỀ ĐỊNH DẠNG JSON TUYỆT ĐỐI CHÍNH XÁC:
    {{
      "speaker": "Nội tâm / Bác sĩ / Y tá",
      "text": "Đoạn miêu tả chi tiết và sâu sắc...",
      "location_name": "Phòng Bệnh 404 / Hành lang / Phòng khám",
      "bg_image": "hospital_room_empty.jpg",
      "mental_state_change": 2,
      "choices": ["Hành động 1", "Hành động 2", "Hành động 3"]
    }}
    """

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        if response and response.text:
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("\n", 1)[0].strip()
                if raw.startswith("json"):
                    raw = raw[4:].strip()

            data = json.loads(raw)
            state.speaker = data.get("speaker", "Nội tâm")
            state.text = data.get("text", state.text)
            state.location_name = data.get("location_name", state.location_name)
            state.bg_image = data.get("bg_image", state.bg_image)
            
            state.mental_state += data.get("mental_state_change", 0)
            state.mental_state = max(0, min(100, state.mental_state)) # Giới hạn 0 - 100

            state.current_choices = data.get("choices", ["...", "...", "..."])

            state.history.append(f"{state.user_name}: {user_choice_text}")
            state.history.append(f"{state.speaker}: {state.text}")

    except Exception as e:
        print(f"🔥 Lỗi Gemini: {e}")
        state.text = "Khung cảnh chao đảo. Một cơn đau đầu ập đến khiến tâm trí bạn mờ mịt..."
        state.current_choices = ["Cố giữ tỉnh táo", "Thả lỏng và chìm vào bóng tối", "Gọi sự trợ giúp"]

# --- DISCORD UI VIEWS ---
class PureVNView(View):
    def __init__(self, ctx, state):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.state = state
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        
        for idx, choice in enumerate(self.state.current_choices[:3]):
            btn = Button(
                label=f"{idx+1}. {choice[:75]}",
                style=discord.ButtonStyle.secondary if self.state.mental_state < 40 else discord.ButtonStyle.primary,
                row=idx,
            )

            async def make_callback(interaction: discord.Interaction, c_text=choice):
                await interaction.response.defer()
                await process_ai_choice_story(self.state, c_text)
                await self.update_message(interaction)

            btn.callback = make_callback
            self.add_item(btn)

    async def update_message(self, interaction):
        loop = asyncio.get_running_loop()
        buf = await loop.run_in_executor(None, render_screen, self.state)

        view = PureVNView(self.ctx, self.state)
        file = discord.File(fp=buf, filename="game.png")
        
        # Nhúng Embed tông màu u buồn nhẹ
        embed_color = 0x2C3E50 if self.state.mental_state < 50 else 0x3498DB
        embed = discord.Embed(
            title=f"📖 Chương {self.state.chapter}: Nơi Thời Gian Ngưng Đọng",
            description=f"*Tâm lý hiện tại: {self.state.mental_state}%*",
            color=embed_color,
        )
        embed.set_image(url="attachment://game.png")
        await interaction.message.edit(embed=embed, attachments=[file], view=view)

# --- LỆNH BOT ---
@bot.command(name="start")
async def start_game(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    state = get_session(ctx.guild.id)
    state.__init__() # Reset Game

    loop = asyncio.get_running_loop()
    buf = await loop.run_in_executor(None, render_screen, state)

    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(
        title="📖 DDLC: BẢN GIAO HƯỞNG CHỮA LÀNH",
        description="Một vụ tai nạn đã làm chệch bánh răng định mệnh. Bạn mắc kẹt trong sự cô độc trước khi bất kỳ ai hay tin. Hãy đưa ra lựa chọn của mình.",
        color=0x2C3E50,
    )
    embed.set_image(url="attachment://game.png")

    view = PureVNView(ctx, state)
    await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="name")
async def set_name(ctx, *, name: str):
    state = get_session(ctx.guild.id)
    state.user_name = name.strip()
    await ctx.send(f"✅ Đã cập nhật tên nhân vật chính: **{state.user_name}**", delete_after=5)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
