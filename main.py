import os, io, asyncio, threading, textwrap
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
import discord
from discord.ext import commands
from discord.ui import Button, View

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

app = Flask(__name__)
@app.route('/')
def home(): return "DDLC Static Engine Online!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# --- KỊCH BẢN CỐT TRUYỆN THỦ CÔNG (KHÔNG PHỤ THUỘC AI) ---
STORY_NODES = {
    "start": {
        "speaker": "Monika",
        "text": "Chào mừng Y/N đến với phòng câu lạc bộ! Hôm nay trời khá đẹp, chúng ta nên bắt đầu từ đâu đây?",
        "bg_image": "club_monika.JPEG",
        "choices": [
            {"text": "Trò chuyện riêng với Monika về lập trình.", "next": "monika_chat"},
            {"text": "Tìm Sayori ở khu vực hành lang.", "next": "sayori_meet"},
            {"text": "Đến góc đọc sách cùng Yuri.", "next": "yuri_book"}
        ]
    },
    "monika_chat": {
        "speaker": "Monika",
        "text": "Cậu thích lập trình thật à? Thế giới này thực ra cũng chỉ là những dòng code và câu lệnh Python thôi đấy...",
        "bg_image": "club_monika.JPEG",
        "choices": [
            {"text": "Hỏi Monika về bí mật của thế giới.", "next": "monika_secret"},
            {"text": "Rủ Monika ra quán cà phê trường.", "next": "cafe_date"},
            {"text": "Quay lại phòng chính câu lạc bộ.", "next": "start"}
        ]
    },
    "sayori_meet": {
        "speaker": "Sayori",
        "text": "A, Y/N đây rồi! Tớ đang định rủ cậu đi mua bánh cupcake dâu tây với Natsuki nè. Đi cùng tụi mình nha?",
        "bg_image": "club_sayori.jpg",
        "choices": [
            {"text": "Đồng ý đi mua bánh cùng Sayori.", "next": "natsuki_bakery"},
            {"text": "Từ chối và ở lại câu lạc bộ.", "next": "start"}
        ]
    },
    "yuri_book": {
        "speaker": "Yuri",
        "text": "Ừm... Cậu muốn đọc chung cuốn tiểu thuyết này với tớ không? Câu chuyện hơi u tối một chút, nhưng rất có chiều sâu...",
        "bg_image": "club_yuri.jpg",
        "choices": [
            {"text": "Ngồi xuống đọc sách yên tĩnh với Yuri.", "next": "yuri_deep"},
            {"text": "Cáo lỗi và đi tìm người khác.", "next": "start"}
        ]
    },
    "monika_secret": {
        "speaker": "Monika",
        "text": "Hì hì... Cậu tò mò thật đấy. Đôi khi biết quá nhiều chưa chắc đã là điều tốt đâu, Y/N ạ...",
        "bg_image": "club_monika.JPEG",
        "choices": [
            {"text": "Quay lại từ đầu.", "next": "start"}
        ]
    },
    "cafe_date": {
        "speaker": "Monika",
        "text": "Không gian quán cà phê này yên tĩnh thật. Ngồi nói chuyện riêng thế này tuyệt thật đấy nhỉ?",
        "bg_image": "cafe_monika.JPEG",
        "choices": [
            {"text": "Quay lại phòng câu lạc bộ.", "next": "start"}
        ]
    },
    "natsuki_bakery": {
        "speaker": "Natsuki",
        "text": "Này! Đừng có mà nghĩ tớ làm mấy cái bánh này vì cậu đấy nhé... nhưng mà cậu ăn thử xem có ngon không đi!",
        "bg_image": "club_natsuki.JPEG",
        "choices": [
            {"text": "Khen bánh ngon và quay lại câu lạc bộ.", "next": "start"}
        ]
    },
    "yuri_deep": {
        "speaker": "Yuri",
        "text": "Cảm ơn cậu... Khoảng thời gian yên bình thế này thực sự rất hiếm hoi.",
        "bg_image": "club_yuri.jpg",
        "choices": [
            {"text": "Quay lại phòng câu lạc bộ.", "next": "start"}
        ]
    }
}

class GameState:
    def __init__(self):
        self.game_active = False
        self.user_name = "Y/N"
        self.current_node = "start"
        self.last_msg = None
        self.voice_client = None

game_session = {}
def get_session(guild_id):
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- VẼ GIAO DIỆN TĨNH ---
def render_screen(node_data):
    img_w, img_h = 600, 430
    font_file = get_asset("font_regular.ttf")
    try:
        if os.path.exists(font_file):
            font_name = ImageFont.truetype(font_file, 22)
            font_text = ImageFont.truetype(font_file, 18)
            font_small = ImageFont.truetype(font_file, 15)
        else:
            font_name = font_text = font_small = ImageFont.load_default()
    except:
        font_name = font_text = font_small = ImageFont.load_default()

    bg_path = get_asset(node_data["bg_image"])
    if os.path.exists(bg_path):
        try:
            img = Image.open(bg_path).convert("RGB")
            img = img.resize((img_w, 250))
        except:
            img = Image.new("RGB", (img_w, 250), (35, 25, 45))
    else:
        img = Image.new("RGB", (img_w, 250), (35, 25, 45))

    full_img = Image.new("RGB", (img_w, img_h), (20, 15, 30))
    full_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(full_img)
    
    # Khung thoại
    draw.rectangle([10, 260, 590, 345], fill=(20, 15, 30), outline=(255, 100, 180), width=2)
    draw.rectangle([20, 245, 160, 275], fill=(255, 100, 180))
    draw.text((28, 250), node_data["speaker"], fill=(255, 255, 255), font=font_name)
    wrapped = textwrap.fill(node_data["text"], width=50)
    draw.text((20, 280), wrapped, fill=(245, 245, 245), font=font_text)

    # Khung lựa chọn trên ảnh
    choices = node_data["choices"]
    box_h = 20 + len(choices) * 22
    draw.rectangle([10, 355, 590, 355 + box_h], fill=(30, 20, 40), outline=(100, 200, 255), width=2)
    draw.text((20, 362), "📌 Lựa chọn hành động:", fill=(150, 220, 255), font=font_small)
    
    for idx, c in enumerate(choices):
        y_pos = 385 + idx * 22
        draw.text((20, y_pos), f"{idx+1}. {c['text']}", fill=(255, 255, 255), font=font_small)

    buf = io.BytesIO()
    full_img.save(buf, format='PNG')
    buf.seek(0)
    return buf

# --- NÚT BẤM ĐIỀU HƯỚNG ---
class StaticControls(View):
    def __init__(self, state):
        super().__init__(timeout=None)
        self.state = state
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        node = STORY_NODES.get(self.state.current_node, STORY_NODES["start"])
        for idx, choice in enumerate(node["choices"]):
            btn = Button(label=f"Lựa chọn {idx+1}", style=discord.ButtonStyle.blurple, custom_id=f"choice_{idx}")
            btn.callback = self.make_callback(choice["next"], choice["text"])
            self.add_item(btn)

    def make_callback(self, next_node, choice_text):
        async def button_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.state.current_node = next_node
            self.update_buttons()
            
            node_data = STORY_NODES[self.state.current_node]
            buf = render_screen(node_data)
            file = discord.File(fp=buf, filename="game.png")
            embed = discord.Embed(title=f"🎮 DDLC: THẾ GIỚI MỞ ({self.state.user_name})", description=f"👉 **{self.state.user_name}** đã chọn: *{choice_text}*", color=0xff77aa)
            embed.set_image(url="attachment://game.png")
            
            await interaction.message.edit(embed=embed, attachments=[file], view=self)
        return button_callback

@bot.command(name="start")
async def start_game(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
        
    state = get_session(ctx.guild.id)
    state.game_active = True
    state.current_node = "start"

    if state.last_msg:
        try:
            await state.last_msg.delete()
        except:
            pass

    node_data = STORY_NODES[state.current_node]
    buf = render_screen(node_data)
    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(title=f"🎮 DDLC: THẾ GIỚI MỞ ({state.user_name})", description="Bấm các nút bên dưới để chọn hướng đi cho câu chuyện!", color=0xff77aa)
    embed.set_image(url="attachment://game.png")
    
    view = StaticControls(state)
    state.last_msg = await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="name")
async def set_username(ctx, *, name: str):
    try:
        await ctx.message.delete()
    except:
        pass
    state = get_session(ctx.guild.id)
    state.user_name = name.strip()
    await ctx.send(f"✅ Đã đổi tên người chơi thành: **{state.user_name}**", delete_after=5)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
