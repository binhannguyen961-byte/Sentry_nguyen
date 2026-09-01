import os
import asyncio
import discord
from discord.ext import commands

# ---------------------------------------------------------
# BOT SETUP
# ---------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# HÀM TÌM FILE TRONG THƯ MỤC ASSETS (TỰ ĐỘNG NHẬN ĐUÔI FILE)
# ---------------------------------------------------------
def get_asset_path(base_filename, is_audio=False):
    """
    Tự động tìm file trong thư mục assets:
    - Nếu là ảnh: thử đuôi .png, .jpg, .jpeg
    - Nếu là âm thanh: thử đuôi .mp3, .wav, .ogg
    """
    extensions = ['.mp3', '.wav', '.ogg'] if is_audio else ['.png', '.jpg', '.jpeg']
    
    # Kiểm tra trực tiếp trong thư mục assets/
    for ext in extensions:
        full_path = os.path.join("assets", base_filename + ext)
        if os.path.exists(full_path):
            return full_path
            
    # Kiểm tra thêm trong assets/sfx/ (nếu có)
    if is_audio:
        for ext in extensions:
            full_path = os.path.join("assets", "sfx", base_filename + ext)
            if os.path.exists(full_path):
                return full_path

    return None

# ---------------------------------------------------------
# DỮ LIỆU KỊCH BẢN - KHỚP TÊN ASSETS CỦA NAM
# ---------------------------------------------------------
STORY_NODES = {
    # 1. BẮT ĐẦU: Toàn cảnh trạm canh (background_view)
    "start": {
        "text": "📻 **[THÁP CANH TOWER 4 - 02:15 AM]**\nBạn đang một mình trong tháp canh giữa khu rừng Gracewind Park. Tiếng rè phát ra từ chiếc Micro trên bàn...",
        "image_key": "background_view",
        "choices": [
            {"label": "🎙️ Lại gần bàn làm việc (Radio)", "next": "radio_desk"},
            {"label": "🗺️ Xem bản đồ khu vực", "next": "examine_map"}
        ]
    },

    # 2. XEM BẢN ĐỒ: (background_map)
    "examine_map": {
        "text": "🗺️ **[BẢN ĐỒ GRACE WIND PARK]**\nHồ Grace Wind Lake nằm ở trung tâm. Phía Bắc là Mining Tunnels, phía Nam là Tháp 4 của bạn.",
        "image_key": "background_map",
        "choices": [
            {"label": "🎙️ Quay lại bàn Radio", "next": "radio_desk"}
        ]
    },

    # 3. BÀN RADIO / BÀN CHÍNH: (background_mainview)
    "radio_desk": {
        "text": "📻 **[NGƯỜI LEO NÚI GỬI TÍN HIỆU]:**\n'Trạm 4 nghe rõ không?! Có cái gì đó đang đuổi theo tôi! Tôi nên chạy về hướng nào?!'",
        "image_key": "background_mainview",
        "choices": [
            {"label": "👈 Chỉ hướng ra Khu Cắm Trại", "next": "ending_good"},
            {"label": "👁️ Bước ra ban công nhìn về phía Hồ", "next": "look_at_lake"},
            {"label": "🔇 Bỏ mặc, không trả lời", "next": "ending_misanthrope"}
        ]
    },

    # 4. GÓC NHÌN RA HỒ - PHÁT ÂM THANH GOATMAN_HOWL: (background_lake)
    "look_at_lake": {
        "text": "🌊 **[GÓC NHÌN RA HỒ GRACE WIND]**\n'Trạm 4... Anh... Anh có đang nhìn ra phía hồ không?'\n\n*Một bóng đen khổng lồ sừng sững nổi lên giữa mặt hồ u tối...*",
        "image_key": "background_lake",
        "sfx_key": "goatman_howl",  # Tự động nhận diện file goatman_howl trên máy Nam!
        "choices": [
            {"label": "🚪 Cố gắng cố thủ trong trạm!", "next": "ending_bad"},
            {"label": "🎙️ Hét vào Mic bảo trốn xuống nước", "next": "ending_bad"}
        ]
    },

    # --- CÁC KẾT THÚC (ENDINGS) ---
    "ending_good": {
        "text": "🏆 **[GOOD ENDING]** Nạn nhân thoát chết nhờ sự chỉ dẫn chính xác của bạn!",
        "image_key": "good_ending",
        "choices": []
    },
    "ending_misanthrope": {
        "text": "👁️ **[MISANTHROPE ENDING]** Bạn chọn sự an toàn cho bản thân và bỏ mặc người leo núi...",
        "image_key": "misanthrope_ending",
        "choices": []
    },
    "ending_bad": {
        "text": "☠️ **[BAD ENDING]** Con quái vật đã tìm thấy trạm canh...",
        "image_key": "bad_ending",
        "choices": []
    }
}

# ---------------------------------------------------------
# KHUNG NÚT BẤM (DISCORD UI VIEW)
# ---------------------------------------------------------
class GameView(discord.ui.View):
    def __init__(self, current_node_key):
        super().__init__(timeout=None)
        node_data = STORY_NODES.get(current_node_key, {})
        
        for choice in node_data.get("choices", []):
            button = discord.ui.Button(
                label=choice["label"], 
                style=discord.ButtonStyle.secondary, 
                custom_id=choice["next"]
            )
            button.callback = self.make_callback(choice["next"])
            self.add_item(button)

    def make_callback(self, next_node_key):
        async def callback(interaction: discord.Interaction):
            await render_node(interaction, next_node_key)
        return callback

# ---------------------------------------------------------
# XỬ LÝ PHÁT ÂM THANH TIẾNG HÚ GOATMAN
# ---------------------------------------------------------
async def handle_sfx(interaction: discord.Interaction, sfx_key: str):
    user = interaction.user
    if user.voice and user.voice.channel:
        voice_channel = user.voice.channel
        
        voice_client = interaction.guild.voice_client
        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        sfx_path = get_asset_path(sfx_key, is_audio=True)
        if sfx_path and os.path.exists(sfx_path):
            if voice_client.is_playing():
                voice_client.stop()
            voice_client.play(discord.FFmpegPCMAudio(sfx_path))
        else:
            print(f"⚠️ Không tìm thấy file âm thanh cho key: {sfx_key}")

# ---------------------------------------------------------
# XỬ LÝ CHUYỂN CẢNH VÀ HIỂN THỊ HÌNH ẢNH
# ---------------------------------------------------------
async def render_node(interaction: discord.Interaction, node_key: str):
    node = STORY_NODES[node_key]
    
    # Kiểm tra và phát SFX nếu cảnh đó có âm thanh
    if "sfx_key" in node and interaction:
        asyncio.create_task(handle_sfx(interaction, node["sfx_key"]))

    view = GameView(node_key)
    image_key = node.get("image_key")
    file_path = get_asset_path(image_key, is_audio=False) if image_key else None
    
    if file_path:
        file_ext = os.path.splitext(file_path)[1]
        filename = f"scene{file_ext}"
        file = discord.File(file_path, filename=filename)
        
        embed = discord.Embed(description=node["text"], color=0x2b2d31)
        embed.set_image(url=f"attachment://{filename}")
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=view)
    else:
        embed = discord.Embed(description=node["text"], color=0x2b2d31)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=view)

# ---------------------------------------------------------
# LỆNH BẮT ĐẦU GAME (!play)
# ---------------------------------------------------------
@bot.command(name="play")
async def start_game(ctx):
    node = STORY_NODES["start"]
    view = GameView("start")
    
    image_key = node.get("image_key")
    file_path = get_asset_path(image_key, is_audio=False) if image_key else None
    
    if file_path:
        file_ext = os.path.splitext(file_path)[1]
        filename = f"scene{file_ext}"
        file = discord.File(file_path, filename=filename)
        
        embed = discord.Embed(description=node["text"], color=0x2b2d31)
        embed.set_image(url=f"attachment://{filename}")
        await ctx.send(embed=embed, file=file, view=view)
    else:
        await ctx.send(content=node["text"], view=view)

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} đã kết nối thành công và sẵn sàng!")

if __name__ == "__main__":
    bot.run(TOKEN)
