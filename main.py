import discord
from discord.ext import commands
from discord.ui import View, Button
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import os
import textwrap
import asyncio

# --- CẤU HÌNH BOT ---
# Prefer reading token from environment for safety
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # Set DISCORD_BOT_TOKEN env var or edit here
PREFIX = '!'
ASSET_DIR = './assets'  # Thư mục chứa ảnh, font và file mp3

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Quản lý session: lưu trạng thái người chơi {user_id: current_node}
user_sessions = {}

# --- CÂY CỐT TRUYỆN MỞ RỘNG (THÊM NHIỀU NODE ĐỂ TĂNG THỜI LƯỢNG) ---
# Mỗi node có thể có trường "music" để chỉ file mp3 trong ASSET_DIR để phát khi render
STORY_TREE = {
    "ch1_start": {
        "chapter": 1, "speaker": "Bác sĩ", "bg": "hospital.jpg", "music": "calm_intro.mp3",
        "text": "Kiểm tra cuối cùng đã xong. Cơ thể cậu phục hồi rất tốt, hôm nay có thể chính thức xuất viện rồi. Có mấy cô bạn gái đang ríu rít đợi cậu ở cổng. Hãy chọn người muốn đi cùng.",
        "choices": [
            {"label": "Thu dọn đồ đạc và ra cổng", "next": "ch2_meet"}
        ]
    },
    "ch2_meet": {
        "chapter": 2, "speaker": "System", "bg": "hospital.jpg",
        "text": "Vừa bước ra khỏi cổng, bạn thấy cả 4 thành viên của Câu Lạc Bộ Thơ Văn đang đứng đợi. Ánh nắng nhẹ chiếu xuống, mọi người đều mỉm cười chào bạn.",
        "choices": [
            {"label": "Cùng Sayori đi bộ về nhà", "next": "route_sayori_street"},
            {"label": "Đi cùng Monika", "next": "route_monika_street"},
            {"label": "Để Natsuki xách phụ đồ", "next": "route_natsuki_street"},
            {"label": "Sánh bước cùng Yuri", "next": "route_yuri_street"}
        ]
    },

    # --- ROUTE: SAYORI (đã mở rộng) ---
    "route_sayori_street": {
        "chapter": 2, "speaker": "Sayori", "bg": "street_sayori.JPEG", "music": "happy_walk.mp3",
        "text": "Hehe! Tớ vui quá đi mất! Từ nay tớ sẽ làm vệ sĩ kiêm người đánh thức cậu mỗi sáng để cậu không gặp tai nạn ngốc nghếch nữa!",
        "choices": [{"label": "Rủ Sayori ghé công viên", "next": "route_sayori_park"}]
    },
    "route_sayori_park": {
        "chapter": 3, "speaker": "Sayori", "bg": "park_sayori.JPEG", "music": "park_birds.mp3",
        "text": "Thời tiết hôm nay đẹp thật đấy. Ngồi ngắm mây trôi ở đây làm tớ thấy bình yên... Ơ kìa, đằng kia có xe bán kem!",
        "choices": [{"label": "Đi mua đồ ngọt", "next": "route_sayori_cafe"}]
    },
    "route_sayori_cafe": {
        "chapter": 4, "speaker": "Sayori", "bg": "cafe_sayori.JPEG", "music": "cafe_chatter.mp3",
        "text": "Oa! Bánh dâu tây ở đây ngon tuyệt vời! Cậu có muốn thử một miếng không? Há miệng ra nàoooo... Aaaaa!",
        "choices": [{"label": "Ăn thử bánh và tiếp tục đi dạo", "next": "route_sayori_walk"}]
    },
    "route_sayori_walk": {
        "chapter": 4, "speaker": "Sayori", "bg": "street_evening.jpg",
        "text": "Sau khi ăn bánh, cả hai cùng dạo chơi, trò chuyện nhiều hơn về ước mơ và những ngày tớ lười dậy. Khoảnh khắc này thật ấm áp.",
        "choices": [{"label": "Quay lại CLB cùng Sayori", "next": "route_sayori_club"}]
    },
    "route_sayori_club": {
        "chapter": 5, "speaker": "Sayori", "bg": "club_sayori.jpg", "music": "club_warm.mp3",
        "text": "Cuối cùng cũng được trở lại đây! CLB Thơ Văn không thể thiếu cậu được đâu. Chào mừng cậu đã trở về nhé, đồ ngốc!",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    },

    # --- ROUTE: MONIKA (đã mở rộng) ---
    "route_monika_street": {
        "chapter": 2, "speaker": "Monika", "bg": "street_monika.JPEG", "music": "soft_piano.mp3",
        "text": "Tớ rất vui vì cậu đã bình an. Những ngày cậu vắng mặt, không khí CLB buồn lắm.",
        "choices": [{"label": "Đi dạo ra công viên", "next": "route_monika_park"}]
    },
    "route_monika_park": {
        "chapter": 3, "speaker": "Monika", "bg": "park_monika.JPEG",
        "text": "Cậu biết không, đôi khi tớ ước thời gian cứ dừng lại mãi ở khoảnh khắc này. Chỉ có ánh nắng, tiếng chim hót, và cậu...",
        "choices": [{"label": "Mời Monika tới quán cafe", "next": "route_monika_cafe"}]
    },
    "route_monika_cafe": {
        "chapter": 4, "speaker": "Monika", "bg": "cafe_monika.JPEG", "music": "cafe_piano.mp3",
        "text": "Cà phê đen không đường. Tớ luôn thích sự tĩnh lặng và hương vị nguyên bản của nó. Còn cậu thì sao? Cậu thích thế giới này chứ?",
        "choices": [{"label": "Lắng nghe và đến thư viện", "next": "route_monika_library"}]
    },
    "route_monika_library": {
        "chapter": 4, "speaker": "Monika", "bg": "library_monika.jpg",
        "text": "Trong thư viện, Monika đọc cho cậu nghe một đoạn thơ hiếm. Lắng nghe từng chữ, cậu cảm thấy thế giới trở nên sâu sắc hơn.",
        "choices": [{"label": "Quay lại CLB cùng Monika", "next": "route_monika_club"}]
    },
    "route_monika_club": {
        "chapter": 5, "speaker": "Monika", "bg": "club_monika.JPEG", "music": "club_warm.mp3",
        "text": "Dù ở thực tại nào, cậu vẫn luôn chọn quay về nơi đây. Cảm ơn cậu... vì tất cả. Hãy bắt đầu buổi sinh hoạt thôi nào!",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    },

    # --- ROUTE: NATSUKI (đã mở rộng) ---
    "route_natsuki_street": {
        "chapter": 2, "speaker": "Natsuki", "bg": "street_natsuki.JPEG", "music": "cute_bounce.mp3",
        "text": "Đ-Đừng có hiểu lầm! Tớ xách phụ đồ cho cậu chỉ vì cậu mới xuất viện thôi, không phải vì tớ lo lắng hay gì đâu nhé!",
        "choices": [{"label": "Nhịn cười và đi qua công viên", "next": "route_natsuki_park"}]
    },
    "route_natsuki_park": {
        "chapter": 3, "speaker": "Natsuki", "bg": "park_natsuki.JPEG",
        "text": "Nhìn kìa! Có một chú mèo hoang dưới ghế đá! Dễ thương quá đi mất...",
        "choices": [{"label": "Chỉ đường tới quán cafe", "next": "route_natsuki_cafe"}]
    },
    "route_natsuki_cafe": {
        "chapter": 4, "speaker": "Natsuki", "bg": "cafe_natsuki.JPEG", "music": "baking_loop.mp3",
        "text": "Mẻ bánh cupcake mới của tớ dạo này có công thức siêu đặc biệt đấy. Quán này làm đồ ngọt cũng được, nhưng chắc thua bánh của tớ!",
        "choices": [{"label": "Hứa sẽ ăn bánh khi về CLB", "next": "route_natsuki_bakery"}]
    },
    "route_natsuki_bakery": {
        "chapter": 4, "speaker": "Natsuki", "bg": "bakery_natsuki.jpg",
        "text": "Natsuki dẫn cậu đến tiệm bánh nhỏ của gia đình — cô chủ mỉm cười và tặng vài chiếc bánh mới nướng. Không khí ấm áp khiến cô bớt cáu hơn một chút.",
        "choices": [{"label": "Quay lại CLB cùng Natsuki", "next": "route_natsuki_club"}]
    },
    "route_natsuki_club": {
        "chapter": 5, "speaker": "Natsuki", "bg": "club_natsuki.JPEG",
        "text": "Về tới nơi rồi. Lát nữa nhớ đọc tiếp cuốn manga Parfait Girls với tớ đấy nhé. Bỏ lỡ mấy tập rồi, tớ sẽ phải kể lại cho cậu nghe!",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    },

    # --- ROUTE: YURI (đã mở rộng) ---
    "route_yuri_street": {
        "chapter": 2, "speaker": "Yuri", "bg": "street_yuri.JPEG", "music": "soft_string.mp3",
        "text": "Tớ... tớ đã rất lo lắng. Những lúc cậu trong bệnh viện, tớ chỉ biết đọc sách để giữ cho tâm trí mình được bình tĩnh lại...",
        "choices": [{"label": "Cảm ơn Yuri và đi dạo công viên", "next": "route_yuri_park"}]
    },
    "route_yuri_park": {
        "chapter": 3, "speaker": "Yuri", "bg": "park_yuri.JPEG",
        "text": "Ngồi dưới bóng cây thế này thật dễ chịu. Cuốn tiểu thuyết chân dung vĩ đại mà tớ đang đọc dở... cậu có muốn nghe thử một đoạn không?",
        "choices": [{"label": "Ngồi sát lại lắng nghe", "next": "route_yuri_cafe"}]
    },
    "route_yuri_cafe": {
        "chapter": 4, "speaker": "Yuri", "bg": "cafe_yuri.JPEG", "music": "tea_room.mp3",
        "text": "Hương trà Oolong ở quán này rất thanh tao. Nó giúp xoa dịu những nhịp đập vội vã trong lồng ngực...",
        "choices": [{"label": "Tận hưởng trà chiều và ghé hiệu sách", "next": "route_yuri_bookshop"}]
    },
    "route_yuri_bookshop": {
        "chapter": 4, "speaker": "Yuri", "bg": "bookshop_yuri.jpg",
        "text": "Trong hiệu sách cũ, Yuri chỉ cho cậu một cuốn sách cũ có dòng chữ được gạch tay. Cảm giác lạ lùng len vào tim.",
        "choices": [{"label": "Quay lại CLB cùng Yuri", "next": "route_yuri_club"}]
    },
    "route_yuri_club": {
        "chapter": 5, "speaker": "Yuri", "bg": "club_yuri.jpg",
        "text": "Câu lạc bộ lại đầy đủ thành viên rồi. Tớ sẽ đun một ấm trà mới nhé. Thật mừng vì cậu đã trở lại với chúng tớ an toàn.",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    }
}

# --- HÀM HỖ TRỢ VẼ ROUNDED RECT ---

def rounded_rectangle(draw, xy, radius, fill, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


# --- HÀM TẠO ẢNH VISUAL NOVEL BẰNG PILLOW (CẢI TIẾN CHO ĐẸP HƠN) ---
def generate_scene_image(bg_filename, speaker_name, text_content):
    bg_path = os.path.join(ASSET_DIR, bg_filename)

    # Mở ảnh nền hoặc tạo ảnh tối nếu thiếu file
    try:
        base_img = Image.open(bg_path).convert("RGBA")
        base_img = base_img.resize((1024, 640))
    except FileNotFoundError:
        base_img = Image.new('RGBA', (1024, 640), (20, 20, 30, 255))

    # Áp dụng blur nhẹ phần nền để làm nổi textbox
    blurred = base_img.filter(ImageFilter.GaussianBlur(radius=2))
    darken = Image.new('RGBA', blurred.size, (0, 0, 0, 90))
    base_img = Image.alpha_composite(blurred, darken)

    overlay = Image.new('RGBA', base_img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Vẽ textbox với bo góc
    textbox_rect = [40, 420, 984, 612]
    rounded_rectangle(draw, textbox_rect, radius=18, fill=(10, 10, 10, 200), outline=(255, 182, 193, 255), width=2)

    # Tạo decorative name badge
    name_badge = [40, 380, 280, 420]
    rounded_rectangle(draw, name_badge, radius=12, fill=(255, 182, 193, 230))

    # Load Font (fallback nếu thiếu file)
    font_path = os.path.join(ASSET_DIR, "font_regular.ttf")
    try:
        font_name = ImageFont.truetype(font_path, 28)
        font_text = ImageFont.truetype(font_path, 20)
    except OSError:
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # In tên nhân vật
    draw.text((56, 388), speaker_name, font=font_name, fill=(30, 30, 30, 255))

    # Cắt dòng text để không tràn box
    wrapped_text = textwrap.fill(text_content, width=70)
    draw.multiline_text((56, 448), wrapped_text, font=font_text, fill=(255, 255, 255, 255), spacing=4)

    # Nếu có ảnh chân dung theo tên nhân vật, vẽ lên góc
    portrait_path = os.path.join(ASSET_DIR, f"{speaker_name.lower()}.png")
    try:
        portrait = Image.open(portrait_path).convert("RGBA")
        portrait.thumbnail((280, 420))
        # Vẽ portrait bên trái căn giữa với textbox
        base_img.paste(portrait, (680, 120), portrait)
    except FileNotFoundError:
        # không có portrait -> bỏ qua
        pass

    final_img = Image.alpha_composite(base_img, overlay)

    # Lưu vào buffer để gửi qua Discord
    buffer = io.BytesIO()
    final_img.convert("RGB").save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    return buffer


# --- PHÁT ÂM THANH (nếu người dùng ở cùng Voice Channel) ---
async def play_node_audio(ctx_or_interaction, node_id):
    node = STORY_TREE.get(node_id, {})
    music_file = node.get("music")
    if not music_file:
        return None

    path = os.path.join(ASSET_DIR, music_file)
    if not os.path.isfile(path):
        return None

    # Tìm voice channel của người dùng
    voice_channel = None
    if isinstance(ctx_or_interaction, commands.Context):
        author = ctx_or_interaction.author
    else:
        author = ctx_or_interaction.user

    if getattr(author, 'voice', None) and author.voice and author.voice.channel:
        voice_channel = author.voice.channel

    # Nếu không có voice channel -> gửi file MP3 như attachment (fallback)
    if voice_channel is None:
        try:
            # gửi file trực tiếp vào text channel
            file = discord.File(path, filename=music_file)
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(file=file)
            else:
                await ctx_or_interaction.followup.send(file=file)
        except Exception:
            pass
        return None

    guild = voice_channel.guild
    voice_client = guild.voice_client

    try:
        if voice_client is None:
            voice_client = await voice_channel.connect()
        else:
            # nếu đang ở kênh khác, di chuyển
            if voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)

        # Phát audio bằng FFmpeg
        if not os.path.isfile(path):
            return None

        source = discord.FFmpegPCMAudio(path)
        # Nếu đang phát, dừng trước
        if voice_client.is_playing():
            voice_client.stop()

        play_finished = asyncio.Event()

        def after_play(err):
            try:
                if err:
                    print("Error when playing audio:", err)
            finally:
                # hủy kết nối sau 1.5s delay để tránh disconnect quá nhanh
                coro = cleanup_after_play(voice_client)
                asyncio.run_coroutine_threadsafe(coro, bot.loop)
                play_finished.set()

        voice_client.play(source, after=after_play)
        # không block main loop — trả về event để caller tuỳ chọn chờ
        return play_finished
    except Exception as e:
        print("Audio playback error:", e)
        return None


async def cleanup_after_play(voice_client):
    await asyncio.sleep(1.5)
    try:
        if voice_client.is_connected():
            await voice_client.disconnect()
    except Exception:
        pass


# --- GIAO DIỆN NÚT BẤM (UI VIEW) ---
class StoryView(View):
    def __init__(self, user_id, current_node):
        super().__init__(timeout=300)  # Timeout 5 phút
        self.user_id = user_id
        # Tạo nút bấm dựa trên lựa chọn của node hiện tại
        choices = STORY_TREE[current_node]["choices"]
        for idx, choice in enumerate(choices):
            btn = Button(label=choice["label"], style=discord.ButtonStyle.primary, custom_id=f"choice_{idx}")
            btn.callback = self.create_callback(choice["next"]) 
            self.add_item(btn)

    def create_callback(self, next_node):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Đây không phải là phiên chơi của bạn!", ephemeral=True)
                return

            # Cập nhật session và render cảnh mới
            user_sessions[self.user_id] = next_node
            await render_scene(interaction, next_node)
        return callback

    async def on_timeout(self):
        # Khi timeout, disable các nút
        for item in self.children:
            item.disabled = True


# --- HÀM RENDER CẢNH VÀ GỬI TIN NHẮN ---
async def render_scene(interaction_or_ctx, node_id):
    node_data = STORY_TREE[node_id]
    # Determine user id
    if isinstance(interaction_or_ctx, commands.Context):
        user_id = interaction_or_ctx.author.id
        channel = interaction_or_ctx.channel
    else:
        user_id = interaction_or_ctx.user.id
        channel = interaction_or_ctx.channel

    # Tạo ảnh từ Pillow
    img_buffer = generate_scene_image(
        bg_filename=node_data.get("bg", ""),
        speaker_name=node_data.get("speaker", ""),
        text_content=node_data.get("text", "")
    )
    file = discord.File(fp=img_buffer, filename="scene.jpg")
    view = StoryView(user_id, node_id)

    # Phát nhạc nền (nếu có) — không chặn giao diện
    _ = await play_node_audio(interaction_or_ctx, node_id)

    # Nếu là lệnh từ bot
    if isinstance(interaction_or_ctx, commands.Context):
        await interaction_or_ctx.send(file=file, view=view)
    # Nếu là phản hồi từ nút bấm
    else:
        try:
            # Sửa message cũ bằng edit
            await interaction_or_ctx.response.edit_message(attachments=[file], view=view)
        except Exception:
            # Nếu sửa không được (ví dụ đã trả lời trước đó), gửi 1 message mới
            await channel.send(file=file, view=view)


# --- LỆNH KHỞI ĐỘNG GAME ---
@bot.command(name="start")
async def start_game(ctx):
    user_id = ctx.author.id
    start_node = "ch1_start"
    user_sessions[user_id] = start_node

    await ctx.send(f"Đang khởi động Visual Novel cho {ctx.author.name}... (Bạn có thể vào kênh thoại và bot sẽ phát nhạc nền nếu file mp3 tồn tại trong /assets)")
    await render_scene(ctx, start_node)


@bot.command(name="stopaudio")
async def stop_audio(ctx):
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("Đã dừng phát âm thanh.")
    else:
        await ctx.send("Không có âm thanh nào đang được phát.")


@bot.command(name="reset")
async def reset_session(ctx):
    user_id = ctx.author.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    await ctx.send("Phiên chơi của bạn đã được đặt lại. Dùng !start để bắt đầu lại.")


@bot.event
async def on_ready():
    print(f'Bot {bot.user} đã sẵn sàng hoạt động!')
    print('Hệ thống đang chạy nhiều tuyến nhân vật Visual Novel (mở rộng).')
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Chú ý: Bạn chưa cấu hình biến môi trường DISCORD_BOT_TOKEN. Hãy đặt token hoặc chỉnh file main.py.")


bot.run(TOKEN)
