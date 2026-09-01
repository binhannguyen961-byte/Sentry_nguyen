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
# HÀM TÌM FILE ASSETS (TỰ ĐỘNG QUÉT ĐUÔI FILE)
# ---------------------------------------------------------
def get_asset_path(base_filename, is_audio=False):
    extensions = ['.mp3', '.wav', '.ogg'] if is_audio else ['.png', '.jpg', '.jpeg']
    
    for ext in extensions:
        full_path = os.path.join("assets", base_filename + ext)
        if os.path.exists(full_path):
            return full_path
            
    if is_audio:
        for ext in extensions:
            full_path = os.path.join("assets", "sfx", base_filename + ext)
            if os.path.exists(full_path):
                return full_path

    return None

# ---------------------------------------------------------
# KỊCH BẢN GAME (CÓ CẤU HÌNH BGM & OUT VOICE)
# ---------------------------------------------------------
STORY_NODES = {
    # --- CHƯƠNG 1: ĐÊM LẠNH (PHÁT NHẠC NỀN LET GO) ---
    "start": {
        "text": (
            "🌲 **[THÁP CANH TOWER 4 - 02:15 AM]**\n"
            "Mưa tầm tã bên ngoài. Bạn đang ca trực đêm một mình tại khu vực Gracewind Park.\n"
            "Tiếng rè rít chói tai vang lên từ bàn làm việc..."
        ),
        "image_key": "background_view",
        "audio_key": "bgm_letgo",  # PHÁT BGM LET GO BẮT ĐẦU GAME!
        "choices": [
            {"label": "🎙️ Tiến lại bàn làm việc kiểm tra Radio", "next": "radio_static"},
            {"label": "🔍 Rọi đèn pin đọc Sổ nhật ký ca trực", "next": "read_logbook"},
            {"label": "🗺️ Kiểm tra Bản đồ địa hình", "next": "examine_map"}
        ]
    },

    "read_logbook": {
        "text": (
            "📓 **[SỔ NHẬT KÝ CA TRỰC - NGUYÊN TẮC AN TOÀN]**\n"
            "1. Cảnh báo sinh vật nhại giọng con người nguy hiểm khu vực quanh Hồ.\n"
            "2. Không bao giờ ra ngoài sau 12 giờ đêm mà không bật Đèn pha tháp canh.\n"
            "3. Nếu nghe tiếng gọi tên mình từ ngoài rừng: **TUYỆT ĐỐI KHÔNG TRẢ LỜI.**"
        ),
        "image_key": "background_view",
        "choices": [
            {"label": "🎙️ Quay lại bàn Radio", "next": "radio_static"},
            {"label": "🗺️ Xem bản đồ khu vực", "next": "examine_map"}
        ]
    },

    "examine_map": {
        "text": (
            "🗺️ **[BẢN ĐỒ GRACE WIND PARK]**\n"
            "Tháp 4 nằm ở vị trí cao nhất. Phía Tây là Khu cắm trại C-4 (An toàn).\n"
            "Phía Đông là Hồ Gracewind (Khu vực nguy hiểm)."
        ),
        "image_key": "background_map",
        "choices": [
            {"label": "🎙️ Tiến lại bàn Radio", "next": "radio_static"}
        ]
    },

    # --- CHƯƠNG 2: TÍN HIỆU CẤP CỨU ---
    "radio_static": {
        "text": (
            "📻 **[RADIO BANG BANG TÍCH TẮC]**\n"
            "\"Alo?! Trạm 4 nghe rõ không?! Tôi là tay leo núi bị lạc... Có cái gì đó... "
            "nó đang bắt chước tiếng hét của tôi từ phía sau! Tôi phải làm gì đây?!\""
        ),
        "image_key": "background_mainview",
        "choices": [
            {"label": "🎙️ Hỏi: 'Bạn đang thấy gì xung quanh?'", "next": "ask_location"},
            {"label": "🎙️ Hướng dẫn ngay: 'Hãy chạy về phía Tây (Khu Cắm Trại)'", "next": "guide_camp"},
            {"label": "🔭 Cầm ống nhòm bước ra ban công quan sát", "next": "look_balcony"}
        ]
    },

    "ask_location": {
        "text": (
            "📻 **[NGƯỜI LEO NÚI]:**\n"
            "\"Tôi đang đứng cạnh một vách đá dốc... Hình như mặt hồ chói ánh trăng ở ngay phía dưới! "
            "Trời ơi! Nó đang tiến lại gần!!\""
        ),
        "image_key": "background_mainview",
        "choices": [
            {"label": "💡 Bật Đèn pha tháp canh hướng về phía Hồ", "next": "turn_on_floodlight"},
            {"label": "🎙️ Yêu cầu trốn vào khu Mỏ đá phía Bắc", "next": "guide_mines"}
        ]
    },

    # --- CHƯƠNG 3: RA HỒ (TỰ ĐỘNG TẮT LET GO -> PHÁT GOATMAN HOWL) ---
    "look_balcony": {
        "text": (
            "🌊 **[BAN CÔNG THÁP CANH - HƯỚNG RA HỒ]**\n"
            "Gió lạnh tạt thẳng vào mặt. Bạn cầm ống nhòm lia về phía mặt hồ u tối...\n\n"
            "⚡ *XUẤT HIỆN TIẾNG GẦM XANH MẶT TỪ TRONG RỪNG!*"
        ),
        "image_key": "background_lake",
        "audio_key": "goatman_howl",  # CHUYỂN SANG TIẾNG HÚ GỐC
        "choices": [
            {"label": "🎙️ Chạy vội vào gào lên Mic: 'NHẢY XUỐNG HỒ NGAY!'", "next": "ending_bad"},
            {"label": "💡 Chạy vào Bật Đèn pha tháp canh chiếu vào quái vật", "next": "turn_on_floodlight"}
        ]
    },

    "turn_on_floodlight": {
        "text": (
            "🔦 **[ĐÈN PHA THÁP CANH BẬT SÁNG RỰC]**\n"
            "Cột sáng xé tan màn đêm, chiếu thẳng xuống vùng rừng ven hồ. Sinh vật dị dạng bỏ chạy sâu vào rừng!"
        ),
        "image_key": "background_lake",
        "audio_key": "goatman_howl",
        "choices": [
            {"label": "🎙️ Báo nạn nhân: 'Đường đã mở, chạy ngay về Khu Cắm Trại!'", "next": "ending_good"},
            {"label": "🎙️ Báo nạn nhân: 'Lại gần Tháp Canh của tôi!'", "next": "ending_bad"}
        ]
    },

    "guide_camp": {
        "text": "📻 **[ĐIỀU HƯỚNG TỚI KHU CẮM TRẠI]**\nNạn nhân chạy thục mạng theo sự chỉ dẫn của bạn...",
        "image_key": "background_mainview",
        "choices": [
            {"label": "⏳ Chờ đợi tin báo tiếp theo qua Radio...", "next": "ending_good"}
        ]
    },

    "guide_mines": {
        "text": "📻 **[ĐIỀU HƯỚNG VÀO MỎ ĐÁ BỎ HOANG]**\nTiếng đập cửa hang rần rật vang lên qua bộ đàm... Tín hiệu bị ngắt đột ngột!",
        "image_key": "background_mainview",
        "choices": [
            {"label": "⏳ Chờ đợi trong vô vọng...", "next": "ending_bad"}
        ]
    },

    # --- CÁC KẾT THÚC (ENDINGS - TỰ ĐỘNG OUT VOICE CHANNEL) ---
    "ending_good": {
        "text": "🏆 **[GOOD ENDING: CỨU SỐNG NẠN NHÂN]**\nSáng hôm sau, lực lượng cứu hộ đã tìm thấy người leo núi an toàn tại Khu cắm trại.",
        "image_key": "good_ending",
        "stop_voice": True, # ĐÁNH DẤU OUT VOICE
        "choices": []
    },
    "ending_misanthrope": {
        "text": "👁️ **[MISANTHROPE ENDING: BỎ MẶC]**\nBạn tắt Radio và chùm chăn ngủ. Báo chí sáng hôm sau đưa tin về một vụ mất tích bí ẩn...",
        "image_key": "misanthrope_ending",
        "stop_voice": True,
        "choices": []
    },
    "ending_bad": {
        "text": "☠️ **[BAD ENDING: KẺ SẮC TỘC]**\nQuyết định sai lầm đã khiến quái vật lần theo tiếng Radio và trèo lên tận Tháp Canh của bạn...",
        "image_key": "bad_ending",
        "stop_voice": True,
        "choices": []
    }
}

# ---------------------------------------------------------
# XỬ LÝ ÂM THANH & VOICE CHANNEL
# ---------------------------------------------------------
async def handle_audio_logic(interaction: discord.Interaction, node: dict):
    guild = interaction.guild
    voice_client = guild.voice_client

    # 1. Nếu là CẢNH KẾT THÚC (Ending) -> TẮT ÂM THANH VÀ NGẮT KẾT NỐI VOICE
    if node.get("stop_voice", False):
        if voice_client and voice_client.is_connected():
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
        return

    # 2. Nếu CẢNH CÓ ÂM THANH (BGM hoặc SFX)
    audio_key = node.get("audio_key")
    if audio_key:
        user = interaction.user
        if user.voice and user.voice.channel:
            voice_channel = user.voice.channel
            
            if not voice_client:
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)

            audio_path = get_asset_path(audio_key, is_audio=True)
            if audio_path and os.path.exists(audio_path):
                # Ngắt âm thanh cũ để phát âm thanh mới
                if voice_client.is_playing():
                    voice_client.stop()
                voice_client.play(discord.FFmpegPCMAudio(audio_path))

# ---------------------------------------------------------
# CÁC HÀM UI & XỬ LÝ CHUYỂN CẢNH
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

async def render_node(interaction: discord.Interaction, node_key: str):
    node = STORY_NODES[node_key]
    
    # Xử lý âm thanh và kết nối Voice
    if interaction:
        asyncio.create_task(handle_audio_logic(interaction, node))

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

@bot.command(name="play")
async def start_game(ctx):
    node = STORY_NODES["start"]
    view = GameView("start")
    
    # Nếu người gõ lệnh đang ở Voice Channel thì mời bot vào luôn
    if ctx.author.voice and ctx.author.voice.channel:
        voice_channel = ctx.author.voice.channel
        voice_client = await voice_channel.connect()
        bgm_path = get_asset_path("bgm_letgo", is_audio=True)
        if bgm_path:
            voice_client.play(discord.FFmpegPCMAudio(bgm_path))

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
    print(f"🤖 Bot {bot.user.name} đã sẵn sàng với BGM 'Let Go' và tính năng Auto-Disconnect Voice!")

if __name__ == "__main__":
    bot.run(TOKEN)
