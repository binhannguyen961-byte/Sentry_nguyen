import discord
from discord.ext import commands
from discord.ui import View, Button
from PIL import Image, ImageDraw, ImageFont
import io
import os

# --- CẤU HÌNH BOT ---
TOKEN = 'YOUR_BOT_TOKEN_HERE' # Nhập token của bot vào đây
PREFIX = '!'
ASSET_DIR = './assets' # Thư mục chứa ảnh và font

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Quản lý session: lưu trạng thái người chơi {user_id: current_node}
user_sessions = {}

# --- CÂY CỐT TRUYỆN MỞ RỘNG (4 ROUTES) ---
STORY_TREE = {
    "ch1_start": {
        "chapter": 1, "speaker": "Bác sĩ", "bg": "hospital.jpg",
        "text": "Kiểm tra cuối cùng đã xong. Cơ thể cậu phục hồi rất tốt, hôm nay có thể chính thức xuất viện rồi. Có mấy cô bạn gái đang ríu rít đợi cậu ở cổng nãy giờ kìa.",
        "choices": [{"label": "Thu dọn đồ đạc và ra cổng", "next": "ch2_meet"}]
    },
    "ch2_meet": {
        "chapter": 2, "speaker": "System", "bg": "hospital.jpg",
        "text": "Vừa bước ra khỏi cổng, bạn thấy cả 4 thành viên của Câu Lạc Bộ Thơ Văn đang đứng đợi. Ánh nắng nhẹ chiếu xuống, mọi người đều mỉm cười rạng rỡ.",
        "choices": [
            {"label": "Cùng Sayori đi bộ về nhà", "next": "route_sayori_street"},
            {"label": "Đi cùng Monika", "next": "route_monika_street"},
            {"label": "Để Natsuki xách phụ đồ", "next": "route_natsuki_street"},
            {"label": "Sánh bước cùng Yuri", "next": "route_yuri_street"}
        ]
    },

    # --- ROUTE: SAYORI ---
    "route_sayori_street": {
        "chapter": 2, "speaker": "Sayori", "bg": "street_sayori.JPEG",
        "text": "Hehe! Tớ vui quá đi mất! Từ nay tớ sẽ làm vệ sĩ kiêm người đánh thức cậu mỗi sáng để cậu không gặp tai nạn ngốc nghếch nữa!",
        "choices": [{"label": "Rủ Sayori ghé công viên", "next": "route_sayori_park"}]
    },
    "route_sayori_park": {
        "chapter": 3, "speaker": "Sayori", "bg": "park_sayori.JPEG",
        "text": "Thời tiết hôm nay đẹp thật đấy. Ngồi ngắm mây trôi ở đây làm tớ thấy bình yên... Ơ kìa, đằng kia có xe bán kem!",
        "choices": [{"label": "Đi mua đồ ngọt", "next": "route_sayori_cafe"}]
    },
    "route_sayori_cafe": {
        "chapter": 4, "speaker": "Sayori", "bg": "cafe_sayori.JPEG",
        "text": "Oa! Bánh dâu tây ở đây ngon tuyệt vời! Cậu có muốn thử một miếng không? Há miệng ra nàoooo... Aaaaa!",
        "choices": [{"label": "Ăn thử bánh và về CLB", "next": "route_sayori_club"}]
    },
    "route_sayori_club": {
        "chapter": 5, "speaker": "Sayori", "bg": "club_sayori.jpg",
        "text": "Cuối cùng cũng được trở lại đây! CLB Thơ Văn không thể thiếu cậu được đâu. Chào mừng cậu đã trở về nhé, đồ ngốc!",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    },

    # --- ROUTE: MONIKA ---
    "route_monika_street": {
        "chapter": 2, "speaker": "Monika", "bg": "street_monika.JPEG",
        "text": "Tớ rất vui vì cậu đã bình an. Những ngày cậu vắng mặt, mã nguồn... à không, ý tớ là không khí CLB trầm xuống hẳn.",
        "choices": [{"label": "Đi dạo ra công viên", "next": "route_monika_park"}]
    },
    "route_monika_park": {
        "chapter": 3, "speaker": "Monika", "bg": "park_monika.JPEG",
        "text": "Cậu biết không, đôi khi tớ ước thời gian cứ dừng lại mãi ở khoảnh khắc này. Chỉ có ánh nắng, tiếng chim hót, và cậu...",
        "choices": [{"label": "Mời Monika tới quán cafe", "next": "route_monika_cafe"}]
    },
    "route_monika_cafe": {
        "chapter": 4, "speaker": "Monika", "bg": "cafe_monika.JPEG",
        "text": "Cà phê đen không đường. Tớ luôn thích sự tĩnh lặng và hương vị nguyên bản của nó. Còn cậu thì sao? Cậu thích thế giới này chứ?",
        "choices": [{"label": "Lắng nghe và về CLB", "next": "route_monika_club"}]
    },
    "route_monika_club": {
        "chapter": 5, "speaker": "Monika", "bg": "club_monika.JPEG", # Đã sửa đuôi theo list file của bạn
        "text": "Dù ở thực tại nào, cậu vẫn luôn chọn quay về nơi đây. Cảm ơn cậu... vì tất cả. Hãy bắt đầu buổi sinh hoạt thôi nào!",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    },

    # --- ROUTE: NATSUKI ---
    "route_natsuki_street": {
        "chapter": 2, "speaker": "Natsuki", "bg": "street_natsuki.JPEG",
        "text": "Đ-Đừng có hiểu lầm! Tớ xách phụ đồ cho cậu chỉ vì cậu mới xuất viện thôi, không phải vì tớ lo lắng hay gì đâu nhé! Cấm cười!",
        "choices": [{"label": "Nhịn cười và đi qua công viên", "next": "route_natsuki_park"}]
    },
    "route_natsuki_park": {
        "chapter": 3, "speaker": "Natsuki", "bg": "park_natsuki.JPEG",
        "text": "Nhìn kìa! Có một chú mèo hoang dưới ghế đá! Dễ thương quá đi mất... Cậu có mang theo chút đồ ăn vặt nào không?",
        "choices": [{"label": "Chỉ đường tới quán cafe", "next": "route_natsuki_cafe"}]
    },
    "route_natsuki_cafe": {
        "chapter": 4, "speaker": "Natsuki", "bg": "cafe_natsuki.JPEG",
        "text": "Mẻ bánh cupcake mới của tớ dạo này có công thức siêu đặc biệt đấy. Quán này làm đồ ngọt cũng được, nhưng chắc thua bánh của tớ!",
        "choices": [{"label": "Hứa sẽ ăn bánh khi về CLB", "next": "route_natsuki_club"}]
    },
    "route_natsuki_club": {
        "chapter": 5, "speaker": "Natsuki", "bg": "club_natsuki.JPEG",
        "text": "Về tới nơi rồi. Lát nữa nhớ đọc tiếp cuốn manga Parfait Girls với tớ đấy nhé. Bỏ lỡ mấy tập rồi, tớ sẽ phải kể lại cho cậu nghe!",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    },

    # --- ROUTE: YURI ---
    "route_yuri_street": {
        "chapter": 2, "speaker": "Yuri", "bg": "street_yuri.JPEG",
        "text": "Tớ... tớ đã rất lo lắng. Những lúc cậu trong bệnh viện, tớ chỉ biết đọc sách để giữ cho tâm trí mình được bình tĩnh lại...",
        "choices": [{"label": "Cảm ơn Yuri và đi dạo công viên", "next": "route_yuri_park"}]
    },
    "route_yuri_park": {
        "chapter": 3, "speaker": "Yuri", "bg": "park_yuri.JPEG",
        "text": "Ngồi dưới bóng cây thế này thật dễ chịu. Cuốn tiểu thuyết chân dung vĩ đại mà tớ đang đọc dở... cậu có muốn nghe thử một đoạn không?",
        "choices": [{"label": "Ngồi sát lại lắng nghe", "next": "route_yuri_cafe"}]
    },
    "route_yuri_cafe": {
        "chapter": 4, "speaker": "Yuri", "bg": "cafe_yuri.JPEG",
        "text": "Hương trà Oolong ở quán này rất thanh tao. Nó giúp xoa dịu những nhịp đập vội vã trong lồng ngực... giống như lúc tớ ngồi cạnh cậu lúc này vậy.",
        "choices": [{"label": "Tận hưởng trà chiều và về CLB", "next": "route_yuri_club"}]
    },
    "route_yuri_club": {
        "chapter": 5, "speaker": "Yuri", "bg": "club_yuri.jpg",
        "text": "Câu lạc bộ lại đầy đủ thành viên rồi. Tớ sẽ đun một ấm trà mới nhé. Thật mừng vì cậu đã trở lại với chúng tớ an toàn.",
        "choices": [{"label": "Chơi lại từ đầu", "next": "ch1_start"}]
    }
}

# --- HÀM TẠO ẢNH VISUAL NOVEL BẰNG PILLOW ---
def generate_scene_image(bg_filename, speaker_name, text_content):
    bg_path = os.path.join(ASSET_DIR, bg_filename)
    
    # Mở ảnh nền hoặc tạo ảnh đen nếu thiếu file
    try:
        base_img = Image.open(bg_path).convert("RGBA")
        base_img = base_img.resize((800, 600))
    except FileNotFoundError:
        base_img = Image.new('RGBA', (800, 600), (30, 30, 30, 255))
    
    # Tạo box thoại (Textbox) mờ ảo
    overlay = Image.new('RGBA', base_img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Vẽ hcn đen trong suốt làm nền chữ (bottom textbox)
    textbox_rect = [20, 430, 780, 580]
    draw.rectangle(textbox_rect, fill=(0, 0, 0, 180), outline=(255, 192, 203, 255), width=2)
    
    # Load Font (fallback nếu thiếu file)
    font_path = os.path.join(ASSET_DIR, "font_regular.ttf")
    try:
        font_name = ImageFont.truetype(font_path, 28)
        font_text = ImageFont.truetype(font_path, 20)
    except OSError:
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # In tên nhân vật
    draw.text((40, 440), speaker_name, font=font_name, fill=(255, 182, 193, 255))
    
    # Cắt dòng text để không tràn box
    import textwrap
    wrapped_text = textwrap.fill(text_content, width=65)
    draw.text((40, 480), wrapped_text, font=font_text, fill=(255, 255, 255, 255))
    
    # Gộp overlay vào ảnh gốc
    final_img = Image.alpha_composite(base_img, overlay)
    
    # Lưu vào buffer để gửi qua Discord
    buffer = io.BytesIO()
    final_img.convert("RGB").save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer

# --- GIAO DIỆN NÚT BẤM (UI VIEW) ---
class StoryView(View):
    def __init__(self, user_id, current_node):
        super().__init__(timeout=300) # Timeout 5 phút
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

# --- HÀM RENDER CẢNH VÀ GỬI TIN NHẮN ---
async def render_scene(interaction_or_ctx, node_id):
    node_data = STORY_TREE[node_id]
    user_id = interaction_or_ctx.author.id if isinstance(interaction_or_ctx, commands.Context) else interaction_or_ctx.user.id
    
    # Tạo ảnh từ Pillow
    img_buffer = generate_scene_image(
        bg_filename=node_data["bg"],
        speaker_name=node_data["speaker"],
        text_content=node_data["text"]
    )
    file = discord.File(fp=img_buffer, filename="scene.jpg")
    view = StoryView(user_id, node_id)
    
    # Nếu là lệnh từ bot
    if isinstance(interaction_or_ctx, commands.Context):
        await interaction_or_ctx.send(file=file, view=view)
    # Nếu là phản hồi từ nút bấm
    else:
        # Edit message cũ hoặc gửi message mới
        await interaction_or_ctx.response.edit_message(attachments=[file], view=view)

# --- LỆNH KHỞI ĐỘNG GAME ---
@bot.command(name="start")
async def start_game(ctx):
    user_id = ctx.author.id
    start_node = "ch1_start"
    user_sessions[user_id] = start_node
    
    await ctx.send(f"Đang khởi động giả lập không gian cho {ctx.author.name}...")
    await render_scene(ctx, start_node)

@bot.event
async def on_ready():
    print(f'Bot {bot.user} đã sẵn sàng hoạt động!')
    print('Hệ thống đang chạy 4 tuyến nhân vật Visual Novel.')

bot.run(TOKEN)
