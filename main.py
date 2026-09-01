import os
import re
import asyncio
import threading
import io
import textwrap
import tempfile
import random
import cv2
import yt_dlp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
from google import genai

# ==========================================
# 1. WEB SERVER NGẦM (Giữ Bot Online 24/7)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "SubVibe TikTok Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. KHỞI TẠO GEMINI CLIENT & HỖ TRỢ FONT
# ==========================================
gemini_client = None
for env_name, env_val in os.environ.items():
    if any(k in env_name.upper() for k in ["GEMINI", "API_KEY", "GOOGLE_KEY"]) and "DISCORD" not in env_name:
        if env_val and env_val.strip():
            try:
                gemini_client = genai.Client(api_key=env_val.strip())
                break
            except Exception:
                pass

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
# 3. RENDER KHUNG HÌNH (Tối ưu tỷ lệ dọc)
# ==========================================
def render_clean_video_frame(video_frame_pil, subtitle_text=""):
    try:
        canvas = Image.new("RGBA", (800, 520), (20, 20, 25, 255))
        vid_resized = video_frame_pil.resize((292, 520)).convert("RGBA")
        canvas.paste(vid_resized, (254, 0))

        draw = ImageDraw.Draw(canvas)
        font_sub = get_font(16)
        wrapped_lines = textwrap.wrap(subtitle_text, width=50)
        
        if wrapped_lines:
            draw.rectangle([(200, 460), (600, 518)], fill=(10, 10, 15, 210))
            y_offset = 466
            for line in wrapped_lines[:2]:
                draw.text((215, y_offset), line, fill=(255, 255, 255), font=font_sub)
                y_offset += 22

        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Lỗi Render Frame: {e}")
        return None

# ==========================================
# 4. QUẢN LÝ HÀNG ĐỢI & TÌM KIẾM CHỐNG LỖI
# ==========================================
guild_queues = {}     
played_counters = {}  

def get_tiktok_video_info(query):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # Xây dựng danh sách các kiểu truy vấn để thử lần lượt chống bị block
    search_queries = []
    if "tiktok.com" in query or "youtube.com" in query or "youtu.be" in query:
        search_queries.append(query)
    else:
        search_queries.extend([
            f"ytsearch1:{query} tiktok",
            f"ytsearch1:{query} shorts",
            f"ytsearch1:viral {query}"
        ])

    for target in search_queries:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    info = info['entries'][0]
                
                if info and info.get('url'):
                    return {
                        'url': info.get('url'),
                        'title': info.get('title', 'Video Giải Trí'),
                        'uploader': info.get('uploader', 'Creator')
                    }
        except Exception as e:
            print(f"Thử query '{target}' gặp lỗi: {e}")
            continue

    # Phương án dự phòng cuối cùng nếu mọi cách tìm kiếm đều nghẽn mạng
    try:
        fallback_url = "https://www.youtube.com/shorts/3q712uaK4aU"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(fallback_url, download=False)
            return {
                'url': info.get('url'),
                'title': f"Video giải trí cho từ khóa: {query}",
                'uploader': 'SubVibe System'
            }
    except Exception as e:
        print(f"Lỗi fallback hoàn toàn: {e}")
        return None

# ==========================================
# 5. QUẢN LÝ ĐIỀU KHIỂN (VIEW & BUTTONS)
# ==========================================
active_sessions = {}

class TikTokControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary, custom_id="btn_skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session and interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Đã chuyển sang video tiếp theo!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có video nào đang chạy.", ephemeral=True)

    @discord.ui.button(label="⏹️ Dừng Hẳn", style=discord.ButtonStyle.danger, custom_id="btn_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if guild_id := self.guild_id:
            guild_queues[guild_id] = []
        if session:
            session["stop_flag"] = True
            if interaction.guild.voice_client:
                if interaction.guild.voice_client.is_playing():
                    interaction.guild.voice_client.stop()
                await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("⏹️ Đã dọn hàng đợi và thoát kênh thoại.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Bot không ở trong kênh thoại.", ephemeral=True)

# ==========================================
# 6. DISCORD BOT COMMANDS
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=["!V", "!v"], intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"-> SubVibe Bot đã online: {bot.user}")

@bot.command(name="help", aliases=["h"])
async def custom_help(ctx):
    embed = discord.Embed(
        title="📱 SubVibe Video Bot - Phát Video & Autoplay",
        description="Bot phát video trực tiếp vào voice, tự động tìm video liên quan và nghỉ ngơi sau mỗi 5 video.",
        color=discord.Color.from_rgb(255, 0, 80)
    )
    embed.add_field(name="▶️ `!Vplay [Link hoặc Từ khóa]`", value="Thêm video vào hàng đợi phát.", inline=False)
    await ctx.send(embed=embed)

async def play_next_in_queue(ctx):
    guild_id = ctx.guild.id
    queue = guild_queues.get(guild_id, [])

    if not queue:
        fallback_queries = ["tiktok trending", "viral shorts", "satisfying clips", "anime edit"]
        auto_query = random.choice(fallback_queries)
        next_data = get_tiktok_video_info(auto_query)
        if next_data:
            queue.append(next_data)

    if not queue:
        await ctx.send("✨ Hàng đợi đã trống. Dùng lệnh `!Vplay` để thêm video tiếp theo nhé! 💚")
        active_sessions.pop(guild_id, None)
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.disconnect()
        return

    current_video = queue.pop(0)
    session = active_sessions.get(guild_id)
    if not session or session["stop_flag"]:
        return

    status_msg = await ctx.send(f"🤖 *Đang tải video: `{current_video['title']}` từ `{current_video['uploader']}`...*")

    target_video_path = None
    is_temp_file = False

    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(tempfile.gettempdir(), 'video_temp.%(ext)s'),
            'quiet': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(current_video['url'], download=True)
            target_video_path = ydl.prepare_filename(info)
            is_temp_file = True

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        audio_source = discord.FFmpegPCMAudio(target_video_path)
        ctx.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_in_queue(ctx), bot.loop))

        cap = cv2.VideoCapture(target_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        target_fps = 5.0
        frame_interval = int(fps / target_fps) if fps > target_fps else 1
        
        frame_count = 0
        rendered_message = None

        while cap.isOpened() and not session["stop_flag"] and ctx.voice_client and ctx.voice_client.is_playing():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                img_buf = render_clean_video_frame(pil_img, subtitle_text=f"🎵 {current_video['title'][:40]}")

                if img_buf:
                    file = discord.File(fp=img_buf, filename="render.png")
                    if rendered_message is None:
                        rendered_message = await ctx.send(file=file, view=TikTokControlView(guild_id))
                    else:
                        await status_msg.edit(content=f"📱 *Đang phát từ @{current_video['uploader']}*")
                        await rendered_message.edit(attachments=[file])

            await asyncio.sleep(1.0 / target_fps)
            frame_count += 1

        cap.release()
        if is_temp_file and target_video_path and os.path.exists(target_video_path):
            os.remove(target_video_path)

        played_counters[guild_id] = played_counters.get(guild_id, 0) + 1
        if played_counters[guild_id] >= 5:
            played_counters[guild_id] = 0
            await ctx.send("☕ *Đã phát liên tục 5 video rồi! Chúng ta nghỉ giải lao thư giãn 1 phút nhé.*")
            await asyncio.sleep(60)

    except Exception as e:
        print(f"Lỗi phát video: {e}")
        if is_temp_file and target_video_path and os.path.exists(target_video_path):
            os.remove(target_video_path)
        asyncio.run_coroutine_threadsafe(play_next_in_queue(ctx), bot.loop)

@bot.command(name="play", aliases=["t", "phat"])
async def play_tiktok(ctx, *, query: str = None):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("⚠️ Nam cần vào Kênh Thoại trước khi dùng lệnh này!")
        return

    if not query:
        await ctx.send("⚠️ Vui lòng nhập link hoặc từ khóa. Ví dụ: `!Vplay ka-52`")
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

    guild_id = ctx.guild.id
    if guild_id not in guild_queues:
        guild_queues[guild_id] = []

    await ctx.send(f"🔍 *Đang tìm kiếm video cho từ khóa: `{query}`...*")
    video_info = get_tiktok_video_info(query)

    if not video_info:
        await ctx.send("❌ Không thể tìm thấy video phù hợp, vui lòng thử từ khóa khác!")
        return

    guild_queues[guild_id].append(video_info)

    if guild_id not in active_sessions or not active_sessions[guild_id]["is_playing"]:
        active_sessions[guild_id] = {"is_playing": True, "stop_flag": False}
        await play_next_in_queue(ctx)
    else:
        await ctx.send(f"✅ Đã thêm vào hàng đợi: **{video_info['title']}** (@{video_info['uploader']})")

# ==========================================
# 7. KHỞI CHẠY BOT
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
