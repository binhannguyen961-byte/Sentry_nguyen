import os
import asyncio
import discord
from discord.ext import commands

# ---------------------------------------------------------
# BOT SETUP
# ---------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN") # Lấy token từ Environment Variable

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# DỮ LIỆU KỊCH BẢN & ASSETS
# ---------------------------------------------------------
STORY_NODES = {
    "start": {
        "text": "📻 **[THÁP CANH TOWER 4 - 02:15 AM]**\nBạn đang một mình trong tháp canh giữa khu rừng Gracewind Park. Tiếng rè phát ra từ chiếc Micro trên bàn...",
        "image": "assets/background_view.jpg",
        "choices": [
            {"label": "🎙️ Lại gần bàn làm việc (Radio)", "next": "radio_desk"},
            {"label": "🗺️ Xem bản đồ khu vực", "next": "examine_map"}
        ]
    },
    "examine_map": {
        "text": "🗺️ **[BẢN ĐỒ GRACE WIND PARK]**\nHồ Grace Wind Lake nằm ở trung tâm. Phía Bắc là Mining Tunnels, phía Nam là Tháp 4 của bạn.",
        "image": "assets/map_gracewind.jpg",
        "choices": [
            {"label": "🎙️ Quay lại bàn Radio", "next": "radio_desk"}
        ]
    },
    "radio_desk": {
        "text": "📻 **[NGƯỜI LEO NÚI GỬI TÍN HIỆU]:**\n'Trạm 4 nghe rõ không?! Có cái gì đó đang đuổi theo tôi! Tôi nên chạy về hướng nào?!'",
        "image": "assets/background_mic.jpg",
        "choices": [
            {"label": "👈 Chỉ hướng ra Khu Cắm Trại", "next": "ending_good"},
            {"label": "👁️ Bước ra ban công nhìn về phía Hồ", "next": "look_at_lake"},
            {"label": "🔇 Bỏ mặc, không trả lời", "next": "ending_misanthrope"}
        ]
    },
    "look_at_lake": {
        "text": "🌊 **[GÓC NHÌN RA HỒ GRACE WIND]**\n'Trạm 4... Anh... Anh có đang nhìn ra phía hồ không?'\n\n*Một bóng đen khổng lồ sừng sững nổi lên giữa mặt hồ u tối...*",
        "image": "assets/background_lake.jpg",
        "sfx": "goatman_howl.mp3", # TIẾNG HÚ GỐC
        "choices": [
            {"label": "🚪 Chạy ra cửa phòng thủ!", "next": "balcony_check"},
            {"label": "🎙️ Hét vào Mic bảo trốn xuống nước", "next": "ending_worst"}
        ]
    },
    "balcony_check": {
        "text": "🚪 Bạn chạy ra hướng cửa. Ánh đèn chớp tắt ngoài rừng... Con quái vật đang tiến thẳng tới chân tháp canh!",
        "image": "assets/background_balcony.jpg",
        "choices": [
            {"label": "🚨 Cố gắng né tránh", "next": "ending_bad"}
        ]
    },
    "ending_good": {
        "text": "🏆 **[GOOD ENDING]** Nạn nhân thoát chết nhờ sự chỉ dẫn chính xác của bạn!",
        "image": "assets/good_ending.jpg",
        "choices": []
    },
    "ending_misanthrope": {
        "text": "👁️ **[MISANTHROPE ENDING]** Bạn chọn sự an toàn cho bản thân và bỏ mặc người leo núi...",
        "image": "assets/misanthrope_ending.jpg",
        "choices": []
    },
    "ending_worst": {
        "text": "☠️ **[WORST ENDING]** Cả bạn và người leo núi đều không thể sống sót qua đêm nay...",
        "image": "assets/worst_ending.jpg",
        "choices": []
    },
    "ending_bad": {
        "text": "💀 **[BAD ENDING]** Con quái vật đã lên tới tháp canh...",
        "image": "assets/worst_ending.jpg",
        "choices": []
    }
}

# ---------------------------------------------------------
# KHUNG NÚT BẤM CỦA DISCORD (UI VIEW)
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
# XỬ LÝ PHÁT ÂM THANH KHI ĐẾN NODE KINHI ĐIỂN
# ---------------------------------------------------------
async def handle_sfx(interaction: discord.Interaction, sfx_file: str):
    user = interaction.user
    if user.voice and user.voice.channel:
        voice_channel = user.voice.channel
        
        # Kết nối Voice Channel nếu chưa tham gia
        voice_client = interaction.guild.voice_client
        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        # Phát file tiếng hú
        sfx_path = os.path.join("assets", "sfx", sfx_file)
        if os.path.exists(sfx_path):
            if voice_client.is_playing():
                voice_client.stop()
            voice_client.play(discord.FFmpegPCMAudio(sfx_path))

# ---------------------------------------------------------
# XỬ LÝ RENDER HÌNH ẢNH & CHỮ
# ---------------------------------------------------------
async def render_node(interaction: discord.Interaction, node_key: str):
    node = STORY_NODES[node_key]
    
    # Kiểm tra xem node có phát SFX không
    if "sfx" in node and interaction:
        asyncio.create_task(handle_sfx(interaction, node["sfx"]))

    view = GameView(node_key)
    file_path = node.get("image")
    
    if file_path and os.path.exists(file_path):
        file = discord.File(file_path, filename="scene.jpg")
        embed = discord.Embed(description=node["text"], color=0x2b2d31)
        embed.set_image(url="attachment://scene.jpg")
        
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
    
    file_path = node.get("image")
    if file_path and os.path.exists(file_path):
        file = discord.File(file_path, filename="scene.jpg")
        embed = discord.Embed(description=node["text"], color=0x2b2d31)
        embed.set_image(url="attachment://scene.jpg")
        await ctx.send(embed=embed, file=file, view=view)
    else:
        await ctx.send(content=node["text"], view=view)

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} đã sẵn sàng hoạt động!")

if __name__ == "__main__":
    bot.run(TOKEN)
