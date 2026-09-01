import os
import random
import asyncio
import threading
import io
import textwrap
import cv2
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from flask import Flask

# ==========================================
# 1. WEB SERVER NGẦM (Giữ Bot Online 24/7)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Monika Video Renderer & Controller Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. HÀM HỖ TRỢ TẢI TÀI NGUYÊN (ASSETS)
# ==========================================
def load_image_flexible(base_name):
    extensions = [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]
    
    if base_name == "background":
        choices = [f"background_{i}" for i in range(1, 6)] + ["background"]
        random.shuffle(choices)
        for choice in choices:
            for ext in extensions:
                path = os.path.join("assets", choice + ext)
                if os.path.exists(path):
                    try:
                        return Image.open(path).convert("RGBA")
                    except Exception:
                        pass
                        
    for ext in extensions:
        path = os.path.join("assets", base_name + ext)
        if os.path.exists(path):
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                pass
    return None

def get_font(size):
    for font_name in ["font_regular.ttf", "arial.ttf", "DejaVuSans.ttf", "Roboto-Regular.ttf"]:
        font_path = os.path.join("assets", font_name)
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
    return ImageFont.load_default()

# ==========================================
# 3. RENDER KHUNG HÌNH VIDEO KÈM GIAO DIỆN
# ==========================================
def render_video_frame(video_frame_pil, subtitle_text=""):
    try:
        bg = load_image_flexible("background")
        if bg:
            bg = bg.resize((1000, 600))
        else:
            bg = Image.new("RGBA", (1000, 600), (40, 25, 45, 255))

        vid_resized = video_frame_pil.resize((420, 240)).convert("RGBA")
        bg.paste(vid_resized, (35, 80))

        chibi = load_image_flexible("monika_happy")
        if not chibi:
            chibi = load_image_flexible("monika_happy")
        if chibi:
            chibi = chibi.resize((380, 480))
            bg.paste(chibi, (310, 120), chibi)

        draw = ImageDraw.Draw(bg)
        
        textbox = load_image_flexible("textbox")
        if textbox:
            textbox = textbox.resize((960, 160))
            bg.paste(textbox, (20, 420), textbox)
        else:
            draw.rectangle([(30, 410), (970, 570)], fill=(15, 15, 25, 220), outline=(255, 180, 200), width=2)

        font_name = get_font(21)
        font_text = get_font(18)
        draw.text((60, 423), "Monika", fill=(255, 200, 220), font=font_name)

        wrapped_lines = textwrap.wrap(subtitle_text, width=46)
        y_offset = 452
        for line in wrapped_lines[:4]:
            draw.text((60, y_offset), line, fill=(255, 255, 255), font=font_text)
            y_offset += 25

        buffer = io.BytesIO()
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Lỗi Render Frame: {e}")
        return None

# ==========================================
# 4. QUẢN LÝ PHÁT VIDEO VÀ TRẠNG THÁI SESSION
# ==========================================
active_sessions = {} # Lưu trạng thái session theo guild_id

class VideoControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="⏸️ Tạm Dừng", style=discord.ButtonStyle.secondary, custom_id="btn_pause")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session and session["is_playing"]:
            session["is_paused"] = True
            if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Đã tạm dừng phát video/âm thanh.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có video nào đang chạy.", ephemeral=True)

    @discord.ui.button(label="▶️ Tiếp Tục", style=discord.ButtonStyle.success, custom_id="btn_resume")
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session and session["is_playing"]:
            session["is_paused"] = False
            if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
                interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Tiếp tục phát video/âm thanh.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Video không ở trạng thái tạm dừng.", ephemeral=True)

    @discord.ui.button(label="⏹️ Dừng Hoàn Toàn", style=discord.ButtonStyle.danger, custom_id="btn_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session:
            session["stop_flag"] = True
            if interaction.guild.voice_client:
                if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
                    interaction.guild.voice_client.stop()
                await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("⏹️ Đã dừng hoàn toàn và thoát kênh thoại.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có tiến trình nào đang chạy.", ephemeral=True)

# ==========================================
# 5. DISCORD BOT COMMANDS
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=["!V", "!v"], intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"-> Video Control Bot đã online: {bot.user}")

@bot.command(name="help", aliases=["h"])
async def custom_help(ctx):
    embed = discord.Embed(
        title="🎬 Kho Quản Lý Video & Trình Điều Khiển",
        description="Bot render hình ảnh video ra chat, phát âm thanh vào voice, tự động nghỉ ngơi sau 5 phút và hỗ trợ nút bấm điều khiển thủ công.",
        color=discord.Color.from_rgb(120, 198, 122)
    )
    embed.add_field(name="📁 `!Vlist`", value="Xem danh sách video trong thư mục `assets`.", inline=False)
    embed.add_field(name="▶️ `!Vplay [tên_file]`", value="Phát video (tự động chia khúc 5 phút + bảng nút điều khiển).", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="list", aliases=["files", "danhsach"])
async def list_assets_videos(ctx):
    if not os.path.exists("assets"):
        await ctx.send("⚠️ Thư mục `assets` không tồn tại!")
        return
    files = [f for f in os.listdir("assets") if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
    if not files:
        await ctx.send("📂 Không tìm thấy file video nào trong `assets`.")
        return
    file_list_str = "\n".join([f"• `{f}`" for f in files])
    embed = discord.Embed(title="📁 Danh Sách Video Assets", description=file_list_str, color=discord.Color.from_rgb(120, 198, 122))
    await ctx.send(embed=embed)

@bot.command(name="play", aliases=["render", "phat"])
async def play_asset_video(ctx, *, filename: str = None):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("⚠️ Nam cần vào Kênh Thoại trước khi dùng lệnh này!")
        return

    if not filename:
        await ctx.send("⚠️ Vui lòng nhập tên file video. Ví dụ: `!Vplay spider_man.mp4`")
        return

    file_path = os.path.join("assets", filename.strip())
    if not os.path.exists(file_path):
        all_files = os.listdir("assets") if os.path.exists("assets") else []
        matches = [f for f in all_files if filename.lower() in f.lower() and f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
        if matches:
            file_path = os.path.join("assets", matches[0])
            filename = matches[0]
        else:
            await ctx.send(f"❌ Không tìm thấy file video `{filename}` trong `assets`!")
            return

    voice_channel = ctx.author.voice.channel
    try:
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
    except Exception as e:
        await ctx.send(f"❌ Không thể kết nối voice: {e}")
        return

    # Khởi tạo session cho server này
    guild_id = ctx.guild.id
    session = {
        "is_playing": True,
        "is_paused": False,
        "stop_flag": False
    }
    active_sessions[guild_id] = session

    status_msg = await ctx.send(
        f"🎬 *Đang chuẩn bị phát video `{filename}`*\n"
        f"*(Cơ chế bảo vệ: Tự động nghỉ giải lao sau mỗi 5 phút hoạt động)*",
        view=VideoControlView(guild_id)
    )

    try:
        cap = cv2.VideoCapture(file_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        target_fps = 5.0
        frame_interval = int(fps / target_fps) if fps > target_fps else 1
        
        # Bắt đầu phát âm thanh bằng FFmpeg
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        audio_source = discord.FFmpegPCMAudio(file_path)
        ctx.voice_client.play(audio_source)

        frame_count = 0
        rendered_message = None
        five_min_counter = 0.0 # Đếm thời gian thực tế để ngắt nghỉ 5 phút

        while cap.isOpened() and not session["stop_flag"]:
            # Xử lý nếu bấm Tạm Dừng (Pause)
            while session["is_paused"] and not session["stop_flag"]:
                await asyncio.sleep(0.5)

            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                current_sec = int(frame_count / fps) if fps > 0 else 0
                total_sec = int(duration)
                sub = f"*Đang phát: {filename} [{current_sec}s / {total_sec}s]*"
                
                img_buf = render_video_frame(pil_img, subtitle_text=sub)

                if img_buf:
                    file = discord.File(fp=img_buf, filename="video_render.png")
                    if rendered_message is None:
                        rendered_message = await ctx.send(file=file)
                    else:
                        await status_msg.edit(content=f"🎬 *Đang chiếu video: `{filename}` [{current_sec}s / {total_sec}s]*", view=VideoControlView(guild_id))
                        await rendered_message.edit(attachments=[file])

                # Kiểm tra mốc 5 phút (300 giây) để nghỉ giải lao tự động
                five_min_counter += (1.0 / target_fps)
                if five_min_counter >= 300.0:
                    five_min_counter = 0.0
                    session["is_paused"] = True
                    if ctx.voice_client and ctx.voice_client.is_playing():
                        ctx.voice_client.pause()
                    
                    await ctx.send(
                        "☕ *Đã phát liên tục 5 phút rồi! Monika đề xuất chúng ta nghỉ giải lao 1 phút nhé.*\n"
                        "*(Bot đang tạm dừng. Nam có thể bấm nút **▶️ Tiếp Tục** bất cứ lúc nào để xem tiếp)*"
                    )
                    while session["is_paused"] and not session["stop_flag"]:
                        await asyncio.sleep(1)
                    if ctx.voice_client and ctx.voice_client.is_paused():
                        ctx.voice_client.resume()

            await asyncio.sleep(1.0 / target_fps)
            frame_count += 1

        cap.release()
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.disconnect()

        active_sessions.pop(guild_id, None)
        await ctx.send("✨ *Video đã phát xong hoàn tất!* 💚")

    except Exception as e:
        active_sessions.pop(guild_id, None)
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.disconnect()
        await ctx.send(f"❌ Lỗi xảy ra khi phát video: {e}")

# ==========================================
# 6. KHỞI CHẠY BOT
# ==========================================
if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Lỗi: Không tìm thấy DISCORD_TOKEN trong Environment Variables!")
