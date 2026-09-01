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
    
    # Kiểm tra trực tiếp trong assets/
    for ext in extensions:
        full_path = os.path.join("assets", base_filename + ext)
        if os.path.exists(full_path):
            return full_path
            
    # Kiểm tra thêm trong assets/sfx/
    if is_audio:
        for ext in extensions:
            full_path = os.path.join("assets", "sfx", base_filename + ext)
            if os.path.exists(full_path):
                return full_path

    return None

# ---------------------------------------------------------
# KỊCH BẢN MỞ RỘNG (DỪNG LẠI TẠO ĐỘ SÂU & HỒI HỘP)
# ---------------------------------------------------------
STORY_NODES = {
    # --- CHƯƠNG 1: ĐÊM LẠNH TẠI THÁP CANH ---
    "start": {
        "text": (
            "🌲 **[THÁP CANH TOWER 4 - 02:15 AM]**\n"
            "Mưa tầm tã bên ngoài. Bạn đang ca trực đêm một mình tại khu vực Gracewind Park.\n"
            "Tiếng gió rít qua khe cửa kính. Đột nhiên, tiếng rè rít chói tai vang lên từ bàn làm việc..."
        ),
        "image_key": "background_view",
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
            "Phía Đông là Hồ Gracewind (Khu vực nguy hiểm). Phía Bắc có Các mỏ đá cũ bị bỏ hoang."
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
            "*(Tiếng thở dốc hỗn hển hòa lẫn tiếng bước chân giẫm trên lá khô)*\n"
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
            "\"Tôi... tôi đang đứng cạnh một vách đá dốc... Hình như mặt hồ chói ánh trăng ở ngay phía dưới! "
            "Trời ơi! Nó đang tiến lại gần! Nó đi bằng 4 chân nhưng thân hình giống hệt con người!!\""
        ),
        "image_key": "background_mainview",
        "choices": [
            {"label": "💡 Bật Đèn pha tháp canh hướng về phía Hồ", "next": "turn_on_floodlight"},
            {"label": "🎙️ Yêu cầu trốn vào khu Mỏ đá phía Bắc", "next": "guide_mines"}
        ]
    },

    # --- CHƯƠNG 3: SỰ XUẤT HIỆN CỦA GOATMAN (CÓ TIẾNG HÚ SFX) ---
    "look_balcony": {
        "text": (
            "🌊 **[BAN CÔNG THÁP CANH - HƯỚNG RA HỒ]**\n"
            "Gió lạnh tạt thẳng vào mặt. Bạn cầm ống nhòm lia về phía mặt hồ u tối...\n\n"
            "⚡ *XUẤT HIỆN TIẾNG GẦM XANH MẶT TỪ TRONG RỪNG!*"
        ),
        "image_key": "background_lake",
        "sfx_key": "goatman_howl",  # PHÁT TIẾNG HÚ TỰ ĐỘNG QUA VOICE CHANNEL!
        "choices": [
            {"label": "🎙️ Chạy vội vào gào lên Mic: 'NHẢY XUỐNG HỒ NGAY!'", "next": "ending_bad"},
            {"label": "💡 Chạy vào Bật Đèn pha tháp canh chiếu vào quái vật", "next": "turn_on_floodlight"}
        ]
    },

    "turn_on_floodlight": {
        "text": (
            "🔦 **[ĐÈN PHA THÁP CANH BẬT SÁNG RỰC]**\n"
            "Cột sáng công suất lớn xé tan màn đêm, chiếu thẳng xuống vùng rừng ven hồ.\n"
            "Ánh sáng quét qua một sinh vật cao nghều, dị dạng đang gầm lên đớn đau vì chói mắt! "
            "Nó bỏ chạy xói trần vào sâu trong rừng sâu!"
        ),
        "image_key": "background_lake",
        "sfx_key": "goatman_howl",
        "choices": [
            {"label": "🎙️ Báo nạn nhân: 'Đường đã mở, chạy ngay về Khu Cắm Trại!'", "next": "ending_good"},
            {"label": "🎙️ Báo nạn nhân: 'Lại gần Tháp Canh của tôi!'", "next": "ending_bad"}
        ]
    },

    "guide_camp": {
        "text": (
            "📻 **[ĐIỀU HƯỚNG TỚI KHU CẮM TRẠI]**\n"
            "Nạn nhân chạy thục mạng theo sự chỉ dẫn của bạn. Tiếng bước chân quái vật phía sau xa dần..."
        ),
        "image_key": "background_mainview",
        "choices": [
            {"label": "⏳ Chờ đợi tin báo tiếp theo qua Radio...", "next": "ending_good"}
        ]
    },

    "guide_mines": {
        "text": (
            "📻 **[ĐIỀU HƯỚNG VÀO MỎ ĐÁ BỎ HOANG]**\n"
            "Nạn nhân chui vào hang đá tối om. Tiếng đập cửa hang rần rật vang lên qua bộ đàm...\n"
            "Tín hiệu bị ngắt đột ngột!"
        ),
        "image_key": "background_mainview",
        "choices": [
            {"label": "⏳ Chờ đợi trong vô vọng...", "next": "ending_bad"}
        ]
    },

    # --- CÁC KẾT THÚC (ENDINGS) ---
    "ending_good": {
        "text": "🏆 **[GOOD ENDING: CỨU SỐNG NẠN NHÂN]**\nSáng hôm sau, lực lượng cứu hộ đã tìm thấy người leo núi an toàn tại Khu cắm trại.",
        "image_key": "good_ending",
        "choices": []
    },
    "ending_misanthrope": {
        "text": "👁️ **[MISANTHROPE ENDING: BỎ MẶC]**\nBạn tắt Radio và chùm chăn ngủ. Báo chí sáng hôm sau đưa tin về một vụ mất tích bí ẩn...",
        "image_key": "misanthrope_ending",
        "choices": []
    },
    "ending_bad": {
        "text": "☠️ **[BAD ENDING: KẺ SẮC TỘC]**\nQuyết định sai lầm đã khiến quái vật lần theo tiếng Radio và trèo lên tận Tháp Canh của bạn...",
        "image_key": "bad_ending",
        "choices": []
    }
}

# ---------------------------------------------------------
# CÁC HÀM UI & XỬ LÝ GAME (GIỮ NGUYÊN LOGIC CHUẨN)
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

async def render_node(interaction: discord.Interaction, node_key: str):
    node = STORY_NODES[node_key]
    
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
    print(f"🤖 Bot {bot.user.name} đã sẵn sàng với kịch bản mở rộng!")

if __name__ == "__main__":
    bot.run(TOKEN)
