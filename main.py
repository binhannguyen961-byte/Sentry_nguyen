import asyncio
import json
import os
import textwrap
import threading

from discord.ext import commands
from discord.ui import Button, View
import discord
from flask import Flask
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH BOT CƠ BẢN ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

ASSETS_DIR = "assets"
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

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
    return "DDLC Offline Story Engine Online!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- CẤU HÌNH MÀU SẮC NHÂN VẬT ---
CHAR_COLORS = {
    "Sayori": (255, 160, 180),
    "Yuri": (180, 140, 230),
    "Natsuki": (255, 130, 170),
    "Monika": (120, 220, 160),
    "Bác sĩ": (100, 200, 255),
    "Nội tâm": (180, 180, 180),
    "System": (200, 200, 200),
}

# --- CÂY CỐT TRUYỆN (HARDCODED STORY TREE) ---
# Rút ngắn Chương 1, tập trung vào Chương 2, 3, 4
STORY_TREE = {
    "ch1_start": {
        "chapter": 1,
        "speaker": "Nội tâm",
        "location": "Phòng Bệnh 404 (Sự Đơn Độc)",
        "bg": "hospital_room_empty.jpg",
        "text": "Tiếng 'tít... tít...' vang lên đều đặn. Mùi thuốc sát trùng xộc vào mũi. Bạn tỉnh dậy với cơ thể nặng trĩu sau vụ tai nạn hôm qua. Căn phòng trống rỗng và lạnh lẽo...",
        "choices": [
            {"label": "Cố gắng mở hẳn mắt ra và ngồi dậy", "next": "ch1_end"},
            {"label": "Nhấn nút gọi y tá ở đầu giường", "next": "ch1_end"}
        ]
    },
    "ch1_end": {
        "chapter": 1,
        "speaker": "Bác sĩ",
        "location": "Phòng Bệnh 404",
        "bg": "hospital_room_empty.jpg",
        "text": "Cậu tỉnh rồi à? May mắn là không có chấn thương nghiêm trọng. Có mấy cô bé mặc đồng phục trường liên tục gọi điện và túc trực ngoài sảnh từ sớm đấy.",
        "choices": [
            {"label": "Là các thành viên Câu Lạc Bộ...", "next": "ch2_start"},
            {"label": "Xin bác sĩ cho họ vào thăm", "next": "ch2_start"}
        ]
    },
    "ch2_start": {
        "chapter": 2,
        "speaker": "Sayori",
        "location": "Phòng Bệnh 404 (Sự Ấm Áp)",
        "bg": "hospital_room_day.jpg",
        "text": "Y/N!!! Cậu ngốc nghếch này! Tớ đã lo muốn chết đi được! *Sayori òa khóc nức nở ôm chầm lấy bạn, trong khi Natsuki đứng khoanh tay cạnh cửa, bĩu môi nhưng mắt cũng đỏ hoe.*",
        "choices": [
            {"label": "An ủi và xoa đầu Sayori", "next": "ch2_sayori"},
            {"label": "Nhìn sang Natsuki cười nhẹ", "next": "ch2_natsuki"}
        ]
    },
    "ch2_sayori": {
        "chapter": 2,
        "speaker": "Sayori",
        "location": "Phòng Bệnh 404",
        "bg": "hospital_room_day.jpg",
        "text": "Tớ hứa sẽ không bao giờ để cậu đi bộ về một mình nữa! Natsuki cũng đã thức trắng đêm để làm bánh cupcake cho cậu tĩnh dưỡng đấy...",
        "choices": [
            {"label": "Cảm ơn hai người rất nhiều", "next": "ch3_start"}
        ]
    },
    "ch2_natsuki": {
        "chapter": 2,
        "speaker": "Natsuki",
        "location": "Phòng Bệnh 404",
        "bg": "hospital_room_day.jpg",
        "text": "K-Không phải tớ lo cho cậu hay gì đâu nhé! Chỉ là lỡ tay làm thừa một mẻ bánh kem nên mang tới thôi. Đừng có tưởng bở!",
        "choices": [
            {"label": "Bánh của Natsuki luôn là nhất", "next": "ch3_start"}
        ]
    },
    "ch3_start": {
        "chapter": 3,
        "speaker": "Monika",
        "location": "Phòng Bệnh (Chiều tà)",
        "bg": "hospital_room_sunset.jpg",
        "text": "Chào Y/N. Thật mừng vì cậu bình an. CLB thiếu cậu quả thật rất trống trải. Yuri cũng đã mang theo một cuốn tiểu thuyết để đọc cho cậu nghe đây.",
        "choices": [
            {"label": "Lắng nghe Yuri đọc sách", "next": "ch3_yuri"},
            {"label": "Hỏi Monika về việc học trên lớp", "next": "ch3_monika"}
        ]
    },
    "ch3_yuri": {
        "chapter": 3,
        "speaker": "Yuri",
        "location": "Phòng Bệnh (Chiều tà)",
        "bg": "hospital_room_sunset.jpg",
        "text": "T-Tớ nghĩ cuốn sách tĩnh tâm này sẽ giúp nhịp tim của cậu ổn định hơn... Nếu cậu không phiền, tớ sẽ ngồi ở góc này và đọc nhé...",
        "choices": [
            {"label": "Nhắm mắt và tận hưởng giọng Yuri", "next": "ch4_start"}
        ]
    },
    "ch3_monika": {
        "chapter": 3,
        "speaker": "Monika",
        "location": "Phòng Bệnh (Chiều tà)",
        "bg": "hospital_room_sunset.jpg",
        "text": "Tớ đã chép lại toàn bộ bài vở cho cậu rồi. Cứ từ từ thôi, thế giới ngoài kia để nó tự xoay, lúc này cậu chỉ cần bình phục là được.",
        "choices": [
            {"label": "Cảm ơn sự chu đáo của Monika", "next": "ch4_start"}
        ]
    },
    "ch4_start": {
        "chapter": 4,
        "speaker": "System",
        "location": "Phòng Bệnh (Đông đủ)",
        "bg": "hospital_room_day.jpg",
        "text": "Căn phòng ngập tràn tiếng cười nói. Dù không ở phòng sinh hoạt chung, Câu Lạc Bộ Thơ Văn vẫn đang hiện diện trọn vẹn ngay tại đây. Một tương lai mới, bình yên hơn, đang chờ phía trước.",
        "choices": [
            {"label": "Khép lại câu chuyện (Hoàn thành)", "next": "end"}
        ]
    },
    "end": {
        "chapter": 4,
        "speaker": "System",
        "location": "Màn hình kết thúc",
        "bg": "hospital_room_empty.jpg",
        "text": "Cảm ơn bạn đã trải nghiệm Bản Alternate Reality - Nơi thời gian ngưng đọng. Không có glitch, không có bi kịch, chỉ có sự chữa lành.",
        "choices": [
            {"label": "Chơi lại từ đầu", "next": "ch1_start"}
        ]
    }
}

class GameState:
    def __init__(self):
        self.user_name = "Y/N"
        self.current_node = "ch1_start"
        self.load_node(self.current_node)

    def load_node(self, node_id):
        node = STORY_TREE.get(node_id, STORY_TREE["ch1_start"])
        self.current_node = node_id
        self.chapter = node["chapter"]
        self.speaker = node["speaker"]
        self.location_name = node["location"]
        self.bg_image = node["bg"]
        self.text = node["text"]
        self.current_choices = node["choices"]

game_session = {}

def get_session(guild_id):
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- RENDER GIAO DIỆN PIL ---
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
            img = Image.new("RGBA", (img_w, img_h), (15, 20, 25, 255))
    else:
        img = Image.new("RGBA", (img_w, img_h), (25, 30, 40, 255))

    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top Bar
    draw.rectangle([0, 0, img_w, 45], fill=(10, 15, 20, 220))
    draw.text((20, 10), f"📍 {state.location_name} | Chương {state.chapter}", fill=(255, 220, 100, 255), font=font_title)
    draw.text((650, 12), f"Người chơi: {state.user_name}", fill=(200, 200, 200, 255), font=font_text)

    # Hộp thoại Visual Novel
    box_y = 370
    theme_color = CHAR_COLORS.get(state.speaker, (200, 200, 200))

    draw.rectangle([20, box_y, 780, 580], fill=(10, 12, 18, 215), outline=theme_color, width=2)

    if state.speaker:
        badge_width = font_name.getlength(state.speaker) + 40
        draw.rectangle([35, box_y - 25, 35 + badge_width, box_y + 10], fill=theme_color + (255,))
        draw.text((56, box_y - 19), state.speaker, fill=(0, 0, 0, 150), font=font_name)
        draw.text((55, box_y - 20), state.speaker, fill=(20, 20, 20, 255), font=font_name)

    img = Image.alpha_composite(img, overlay)
    draw_final = ImageDraw.Draw(img)

    wrapped = textwrap.fill(state.text, width=65)
    text_x, text_y = 45, box_y + 25
    draw_final.multiline_text((text_x + 2, text_y + 2), wrapped, fill=(0, 0, 0, 200), font=font_text, spacing=8)
    draw_final.multiline_text((text_x, text_y), wrapped, fill=(245, 245, 250, 255), font=font_text, spacing=8)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


# --- DISCORD UI VIEWS ---
class PureVNView(View):
    def __init__(self, ctx, state, guild_id):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.state = state
        self.guild_id = guild_id
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        
        for idx, choice_data in enumerate(self.state.current_choices):
            btn = Button(
                label=f"{idx+1}. {choice_data['label'][:75]}",
                style=discord.ButtonStyle.primary,
                row=idx,
            )

            # Callback xử lý việc chuyển Next Node
            async def make_callback(interaction: discord.Interaction, next_node=choice_data["next"]):
                await interaction.response.defer()
                self.state.load_node(next_node)
                await self.update_message(interaction)

            btn.callback = make_callback
            self.add_item(btn)

    async def update_message(self, interaction):
        loop = asyncio.get_running_loop()
        buf = await loop.run_in_executor(None, render_screen, self.state)

        view = PureVNView(self.ctx, self.state, self.guild_id)
        file = discord.File(fp=buf, filename="game.png")

        embed = discord.Embed(
            title=f"📖 Chương {self.state.chapter}: {self.state.location_name}",
            color=0x3498DB if self.state.chapter > 1 else 0x2C3E50,
        )
        embed.set_image(url="attachment://game.png")

        try:
            await interaction.message.edit(embed=embed, attachments=[file], view=view)
        except Exception:
            await self.ctx.send(embed=embed, file=file, view=view)


# --- LỆNH BOT ---
@bot.command(name="start")
async def start_game(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    state = get_session(ctx.guild.id)
    state.__init__() # Load lại từ ch1_start

    loop = asyncio.get_running_loop()
    buf = await loop.run_in_executor(None, render_screen, state)

    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(
        title="📖 DDLC: BẢN GIAO HƯỞNG CHỮA LÀNH (OFFLINE)",
        description="Một vụ tai nạn đã khiến định mệnh chệch hướng. Hãy trải qua giai đoạn chữa lành cùng Câu Lạc Bộ Thơ Văn.",
        color=0x2C3E50,
    )
    embed.set_image(url="attachment://game.png")

    view = PureVNView(ctx, state, ctx.guild.id)
    await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="name")
async def set_name(ctx, *, name: str):
    state = get_session(ctx.guild.id)
    state.user_name = name.strip()
    await ctx.send(f"✅ Đã cập nhật tên nhân vật chính: **{state.user_name}**", delete_after=5)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
