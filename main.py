import asyncio
import json
import os
import textwrap
import threading
import io
import random
import time
from typing import Optional, List

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

# helper to find assets with different extensions/casing
def get_asset(filename: str) -> str:
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
# Rút ngắn Chương 1, tập trung vào Chương 2, 3, 4 và mở rộng theo phong cách "Blue Skies" (ấm áp, chữa lành)
STORY_TREE = {
    "ch1_start": {
        "chapter": 1,
        "speaker": "Nội tâm",
        "location": "Phòng Bệnh 404 (Sự Đơn Độc)",
        "bg": "hospital_room_empty.jpg",
        "text": "Tiếng 'tít... tít...' vang lên đều đặn. Mùi thuốc sát trùng xộc vào mũi. Bạn tỉnh dậy với cơ thể nặng trĩu sau vụ tai nạn hôm qua. Căn phòng nhỏ bỗng trở nên rất lớn. (một khúc cắt ngắn)",
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
        "text": "Cậu tỉnh rồi à? May mắn là không có chấn thương nghiêm trọng. Có mấy cô bé mặc đồng phục trường liên tục gọi điện và túc trực ngoài sân. (một khúc cắt ngắn)",
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
        "text": "Y/N!!! Cậu ngốc nghếch này! Tớ đã lo muốn chết đi được! Sayori òa khóc nức nở ôm chầm lấy bạn, trong khi Natsuki đứng khoanh tay cạnh cửa, bĩu môi nhưng mắt thì đỏ", 
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
        "text": "Chào Y/N. Thật mừng vì cậu bình an. CLB thiếu cậu quả thật rất trống trải. Yuri cũng đã mang theo một cuốn tiểu thuyết để đọc cho cậu nghe...",
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
            {"label": "Nhắm mắt và tận hưởng giọng Yuri", "next": "ch4_start"},
            {"label": "Đề nghị một trò chơi nhỏ để giải trí", "next": "minigame_reaction"}
        ]
    },
    "ch3_monika": {
        "chapter": 3,
        "speaker": "Monika",
        "location": "Phòng Bệnh (Chiều tà)",
        "bg": "hospital_room_sunset.jpg",
        "text": "Tớ đã chép lại toàn bộ bài vở cho cậu rồi. Cứ từ từ thôi, thế giới ngoài kia để nó tự xoay, lúc này cậu chỉ cần bình phục là được.",
        "choices": [
            {"label": "Cảm ơn sự chu đáo của Monika", "next": "ch4_start"},
            {"label": "Đề nghị Monika kể một kỷ niệm vui", "next": "ch4_extra"}
        ]
    },
    "ch4_start": {
        "chapter": 4,
        "speaker": "System",
        "location": "Phòng Bệnh (Đông đủ)",
        "bg": "hospital_room_day.jpg",
        "text": "Căn phòng ngập tràn tiếng cười nói. Dù không ở phòng sinh hoạt chung, Câu Lạc Bộ Thơ Văn vẫn đang hiện diện trọn vẹn ngay tại đây.",
        "choices": [
            {"label": "Khép lại câu chuyện (Hoàn thành)", "next": "end"},
            {"label": "Ra sân vườn cùng Sayori", "next": "ch4_extra"}
        ]
    },
    "ch4_extra": {
        "chapter": 4,
        "speaker": "Sayori",
        "location": "Sân bệnh viện (Ánh nắng)",
        "bg": "hospital_garden.jpg",
        "text": "Ra ngoài hít thở không khí, ánh nắng nhẹ ấm trên mặt. Sayori kéo tay bạn đi dạo quanh vườn. Có cảm giác thế giới rộng ra nhưng lại gần hơn.",
        "choices": [
            {"label": "Đi dạo với Sayori", "next": "ch5_start"},
            {"label": "Ngồi lại và suy nghĩ một mình", "next": "ch4_reflect"}
        ]
    },
    "ch4_reflect": {
        "chapter": 4,
        "speaker": "Nội tâm",
        "location": "Băng ghế vườn",
        "bg": "hospital_garden.jpg",
        "text": "Ngồi trên băng ghế, bạn nghĩ về những gì đã mất và những gì có thể bắt đầu lại. Một khoảnh khắc lặng im nhưng không cô ��ộc.",
        "choices": [
            {"label": "Đứng lên, tham gia mọi người", "next": "ch5_start"},
            {"label": "Ở lại thêm một lúc", "next": "end"}
        ]
    },
    "ch5_start": {
        "chapter": 5,
        "speaker": "Monika",
        "location": "Ban công bệnh viện (Hoàng hôn)",
        "bg": "hospital_balcony.jpg",
        "text": "Monika mỉm cười: \"'Một chương mới bắt đầu khi ta cho phép nó'\". Cô ấy đặt một tay lên vai bạn như muốn truyền sức mạnh.",
        "choices": [
            {"label": "Nói lời cảm ơn chân thành", "next": "ch5_thanks"},
            {"label": "Đề nghị mọi người làm một hoạt động nhỏ (memory)", "next": "minigame_memory"}
        ]
    },
    "ch5_thanks": {
        "chapter": 5,
        "speaker": "System",
        "location": "Ban công",
        "bg": "hospital_balcony.jpg",
        "text": "Cả nhóm cùng cười. Một khoảnh khắc bình yên, đủ để thấy rằng chữa lành là một quá trình, nhưng không đơn độc.",
        "choices": [
            {"label": "Kết thúc câu chuyện (Good Ending)", "next": "ending_good"},
            {"label": "Tìm hiểu thêm về Yuri", "next": "ch5_yuri_extra"}
        ]
    },
    "ch5_yuri_extra": {
        "chapter": 5,
        "speaker": "Yuri",
        "location": "Góc phòng",
        "bg": "hospital_room_sunset.jpg",
        "text": "Yuri kể về một đoạn trong cuốn sách và chia sẻ vì sao cô ấy thích những câu chữ ấy. Đó là một kết nối nhỏ nhưng ấm áp.",
        "choices": [
            {"label": "Lắng nghe thêm", "next": "ending_true"},
            {"label": "Cảm ơn và ngẩng lên", "next": "ending_good"}
        ]
    },
    "ending_good": {
        "chapter": 6,
        "speaker": "System",
        "location": "Màn hình kết thúc",
        "bg": "hospital_room_empty.jpg",
        "text": "Cảm ơn bạn đã trải nghiệm - Một kết thúc ấm áp nơi mọi người cùng nhau chữa lành.",
        "choices": [
            {"label": "Chơi lại từ đầu", "next": "ch1_start"}
        ]
    },
    "ending_true": {
        "chapter": 6,
        "speaker": "System",
        "location": "Màn hình kết thúc (True)",
        "bg": "hospital_room_empty.jpg",
        "text": "Bạn và các thành viên tìm được sự đồng cảm sâu hơn. Đây là một kết thúc đặc biệt, mở ra khả năng tiếp tục câu chuyện.",
        "choices": [
            {"label": "Chơi lại từ đầu", "next": "ch1_start"}
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

    def load_node(self, node_id: str):
        node = STORY_TREE.get(node_id, STORY_TREE["ch1_start"]) if node_id in STORY_TREE else STORY_TREE["ch1_start"]
        self.current_node = node_id
        self.chapter = node.get("chapter", 1)
        self.speaker = node.get("speaker", "System")
        self.location_name = node.get("location", "")
        self.bg_image = node.get("bg", "hospital_room_day.jpg")
        self.text = node.get("text", "")
        self.current_choices = node.get("choices", [])


game_session = {}


def get_session(guild_id: int) -> GameState:
    if guild_id not in game_session:
        game_session[guild_id] = GameState()
    return game_session[guild_id]

# --- RENDER GIAO DIỆN PIL ---

def rounded_rectangle(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    try:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    except Exception:
        # fallback: draw simple rectangle
        draw.rectangle(box, fill=fill, outline=outline)


def render_portrait(img: Image.Image, state: GameState, img_w: int, img_h: int):
    portrait_path = get_asset(f"portraits/{state.speaker}.png")
    if os.path.exists(portrait_path):
        try:
            p = Image.open(portrait_path).convert("RGBA")
            target_h = int(img_h * 0.55)
            target_w = int(target_h * (p.width / p.height))
            p = p.resize((target_w, target_h))
            paste_x = 20
            paste_y = img_h - target_h - 40
            img.paste(p, (paste_x, paste_y), p)
        except Exception:
            pass


def render_screen(state: GameState):
    img_w, img_h = 900, 600
    font_file = get_asset("font_regular.ttf")

    try:
        font_title = ImageFont.truetype(font_file, 24) if os.path.exists(font_file) else ImageFont.load_default()
        font_name = ImageFont.truetype(font_file, 22) if os.path.exists(font_file) else ImageFont.load_default()
        font_text = ImageFont.truetype(font_file, 18) if os.path.exists(font_file) else ImageFont.load_default()
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

    # draw portrait (if exists)
    render_portrait(img, state, img_w, img_h)

    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # vignette
    for i in range(120):
        alpha = int(80 * (i / 120))
        draw.rectangle([i, i, img_w - i, img_h - i], outline=(0, 0, 0, alpha))

    # Top Bar
    draw.rectangle([0, 0, img_w, 50], fill=(10, 15, 20, 220))
    draw.text((24, 12), f"📍 {state.location_name} | Chương {state.chapter}", fill=(255, 220, 100, 255), font=font_title)
    draw.text((img_w - 240, 14), f"Người chơi: {state.user_name}", fill=(200, 200, 200, 255), font=font_text)

    # Hộp thoại Visual Novel
    box_y = img_h - 230
    theme_color = CHAR_COLORS.get(state.speaker, (200, 200, 200))

    # rounded box
    rect_box = [30, box_y, img_w - 30, img_h - 30]
    rounded_rectangle(draw, rect_box, radius=12, fill=(10, 12, 18, 220), outline=theme_color + (220,), width=2)

    # Speaker badge
    if state.speaker:
        try:
            text_w = font_name.getlength(state.speaker) if hasattr(font_name, 'getlength') else draw.textbbox((0,0), state.speaker, font=font_name)[2]
            badge_w = int(text_w) + 36
        except Exception:
            badge_w = 140
        badge_box = [50, box_y - 28, 50 + badge_w, box_y - 4]
        rounded_rectangle(draw, badge_box, radius=8, fill=theme_color + (255,))
        draw.text((60, box_y - 26), state.speaker, fill=(20, 20, 20, 255), font=font_name)

    img = Image.alpha_composite(img, overlay)
    draw_final = ImageDraw.Draw(img)

    wrapped = textwrap.fill(state.text, width=60)
    text_x, text_y = 70, box_y + 12
    # drop shadow
    draw_final.multiline_text((text_x + 2, text_y + 2), wrapped, fill=(0, 0, 0, 200), font=font_text, spacing=6)
    draw_final.multiline_text((text_x, text_y), wrapped, fill=(245, 245, 250, 255), font=font_text, spacing=6)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


# --- MINIGAMES ---
class ReactionView(View):
    def __init__(self, ctx: commands.Context, timeout: Optional[float] = 10.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.started_at: Optional[float] = None
        self.result_ms: Optional[float] = None
        self.btn = Button(label="CLICK!", style=discord.ButtonStyle.danger, disabled=True)
        async def on_click(interaction: discord.Interaction):
            if self.started_at is None:
                await interaction.response.send_message("Chưa bật tín hiệu!", ephemeral=True)
                return
            self.result_ms = (time.time() - self.started_at) * 1000
            await interaction.response.send_message(f"⏱️ Phản ứng của bạn: {int(self.result_ms)} ms")
            self.stop()
        self.btn.callback = on_click
        self.add_item(self.btn)

    async def start(self, channel: discord.abc.Messageable):
        msg = await channel.send("Chuẩn bị... Giữ chặt ngón tay...", view=self)
        await asyncio.sleep(random.uniform(1.2, 3.0))
        self.started_at = time.time()
        self.btn.disabled = False
        await msg.edit(content="NOW! Bấm nút!", view=self)
        # wait until user clicks or timeout
        await self.wait()
        # disable button after finish
        self.btn.disabled = True
        try:
            await msg.edit(view=self)
        except Exception:
            pass
        return self.result_ms

class MemoryView(View):
    def __init__(self, ctx: commands.Context, length: int = 4, timeout: Optional[float] = 20.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.sequence: List[int] = [random.randint(1,4) for _ in range(length)]
        self.entered: List[int] = []
        self.success: Optional[bool] = None
        # create 4 buttons
        for i in range(1,5):
            btn = Button(label=str(i), style=discord.ButtonStyle.secondary, row=(i-1)//2)
            async def make_cb(interaction: discord.Interaction, val=i):
                # only accept interactions from the original author in this simplified version
                if interaction.user != self.ctx.author:
                    await interaction.response.send_message("Không phải lượt của bạn.", ephemeral=True)
                    return
                self.entered.append(val)
                await interaction.response.defer()
                # check prefix
                if self.sequence[:len(self.entered)] != self.entered:
                    self.success = False
                    self.stop()
                    return
                if len(self.entered) == len(self.sequence):
                    self.success = True
                    self.stop()
            btn.callback = make_cb
            self.add_item(btn)

    async def start(self, channel: discord.abc.Messageable):
        # show sequence briefly
        display = " → ".join(str(x) for x in self.sequence)
        msg = await channel.send(f"Hãy nhớ chuỗi: {display}")
        await asyncio.sleep(2 + 0.8 * len(self.sequence))
        try:
            await msg.delete()
        except Exception:
            pass
        prompt = await channel.send("Bấm các nút theo thứ tự nhớ được", view=self)
        await self.wait()
        try:
            await prompt.edit(view=self)
        except Exception:
            pass
        return self.success


# --- DISCORD UI VIEWS ---
class PureVNView(View):
    def __init__(self, ctx: commands.Context, state: GameState, guild_id: int):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.state = state
        self.guild_id = guild_id
        self.build_buttons()

    def build_buttons(self):
        self.clear_items()
        for idx, choice_data in enumerate(self.state.current_choices):
            label = choice_data.get('label', '')[:80]
            next_node = choice_data.get('next')
            btn = Button(
                label=f"{idx+1}. {label}",
                style=discord.ButtonStyle.primary,
                row=idx,
            )

            async def make_callback(interaction: discord.Interaction, next_node_inner=next_node):
                await interaction.response.defer()
                # handle special minigame triggers
                if next_node_inner == 'minigame_reaction':
                    rv = ReactionView(self.ctx)
                    result = await rv.start(interaction.channel)
                    # decide branch based on result speed
                    if result is not None and result < 500:
                        self.state.load_node('ch4_start')
                    else:
                        self.state.load_node('ch4_reflect')
                    await self.update_message(interaction)
                    return
                if next_node_inner == 'minigame_memory':
                    mv = MemoryView(self.ctx)
                    success = await mv.start(interaction.channel)
                    if success:
                        # successful memory unlocks a better ending
                        self.state.load_node('ch5_thanks')
                    else:
                        self.state.load_node('ch4_reflect')
                    await self.update_message(interaction)
                    return

                # normal node transition
                self.state.load_node(next_node_inner)
                await self.update_message(interaction)

            btn.callback = make_callback
            self.add_item(btn)

    async def update_message(self, interaction: discord.Interaction):
        loop = asyncio.get_running_loop()
        buf = await loop.run_in_executor(None, render_screen, self.state)

        # rebuild view with updated state
        view = PureVNView(self.ctx, self.state, self.guild_id)
        file = discord.File(fp=buf, filename="game.png")

        embed = discord.Embed(
            title=f"📖 Chương {self.state.chapter}: {self.state.location_name}",
            color=0x3498DB if self.state.chapter > 1 else 0x2C3E50,
        )
        embed.set_image(url="attachment://game.png")

        try:
            # interaction.message may be None if triggered from context menu; fallback
            if interaction.message:
                await interaction.message.edit(embed=embed, attachments=[file], view=view)
            else:
                await self.ctx.send(embed=embed, file=file, view=view)
        except Exception:
            await self.ctx.send(embed=embed, file=file, view=view)


# --- LỆNH BOT ---
@bot.command(name="start")
async def start_game(ctx: commands.Context):
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
        title="📖 DDLC: BẢN GIAO HƯỞNG CHỮA LÀNH (BLUE SKIES)",
        description="Một vụ tai nạn đã khiến định mệnh chệch hướng. Hãy trải qua giai đoạn chữa lành cùng Câu Lạc Bộ Thơ Văn.",
        color=0x2C3E50,
    )
    embed.set_image(url="attachment://game.png")

    view = PureVNView(ctx, state, ctx.guild.id)
    await ctx.send(embed=embed, file=file, view=view)

@bot.command(name="name")
async def set_name(ctx: commands.Context, *, name: str):
    state = get_session(ctx.guild.id)
    state.user_name = name.strip()
    await ctx.send(f"✅ Đã cập nhật tên nhân vật chính: **{state.user_name}**", delete_after=5)

# direct commands to try minigames
@bot.command(name="reaction")
async def reaction_cmd(ctx: commands.Context):
    rv = ReactionView(ctx)
    result = await rv.start(ctx)
    if result is None:
        await ctx.send("Không có phản hồi.")
    else:
        await ctx.send(f"⏱️ Phản ứng: {int(result)} ms")

@bot.command(name="memory")
async def memory_cmd(ctx: commands.Context):
    mv = MemoryView(ctx)
    success = await mv.start(ctx)
    if success:
        await ctx.send("🎉 Bạn nhớ đúng chuỗi!")
    else:
        await ctx.send("✖ Sai chuỗi. Cố gắng lần sau.")

# simple save/load per guild
@bot.command(name="save")
async def save_cmd(ctx: commands.Context):
    state = get_session(ctx.guild.id)
    data = {
        'user_name': state.user_name,
        'current_node': state.current_node
    }
    path = os.path.join(SESSION_DIR, f"session_{ctx.guild.id}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    await ctx.send("💾 Đã lưu tiến trình cho server này.")

@bot.command(name="load")
async def load_cmd(ctx: commands.Context):
    path = os.path.join(SESSION_DIR, f"session_{ctx.guild.id}.json")
    if not os.path.exists(path):
        await ctx.send("Không tìm thấy file save.")
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    state = get_session(ctx.guild.id)
    state.user_name = data.get('user_name', state.user_name)
    state.load_node(data.get('current_node', state.current_node))
    await ctx.send("♻️ Đã load tiến trình.")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
