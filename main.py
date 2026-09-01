import os
import re
import asyncio
import threading
import queue
import io
import textwrap
import tempfile
import random
import time
import urllib.request
import cv2
import yt_dlp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
from google import genai
import requests

# ==========================================
# 1. WEB SERVER NGẦM (Giữ Bot Online 24/7)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "SubVibe TikTok & TTS Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. KHỞI TẠO GEMINI & ELEVENLABS API KEY
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

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Mặc định nếu chưa cài

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
# 3. RENDER KHUNG HÌNH TỐI ƯU (NÉN 55%)
# ==========================================
def render_clean_video_frame(video_frame_pil, subtitle_text=""):
    try:
        canvas = Image.new("RGB", (560, 380), (15, 15, 20))
        vid_resized = video_frame_pil.resize((214, 380), Image.Resampling.NEAREST).convert("RGB")
        canvas.paste(vid_resized, (173, 0))

        draw = ImageDraw.Draw(canvas)
        font_sub = get_font(13)
        wrapped_lines = textwrap.wrap(subtitle_text, width=40)
        
        if wrapped_lines:
            draw.rectangle([(120, 320), (440, 378)], fill=(10, 10, 15))
            y_offset = 325
            for line in wrapped_lines[:3]:
                draw.text((130, y_offset), line, fill=(240, 240, 240), font=font_sub)
                y_offset += 16

        buffer = io.BytesIO()
        canvas.save(buffer, format="JPEG", quality=55, optimize=True)
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Lỗi Render Frame: {e}")
        return None

# ==========================================
# 4. TẠO FILE GIỌNG NÓI ELEVENLABS
# ==========================================
def generate_elevenlabs_tts(text, output_path):
    if not ELEVENLABS_API_KEY:
        print("Lỗi: Chưa cài đặt ELEVENLABS_API_KEY!")
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    else:
        print(f"Lỗi ElevenLabs: {response.text}")
        return False

# ==========================================
# 5. QUẢN LÝ HÀNG ĐỢI & SEARCH VIDEO
# ==========================================
guild_queues = {}     
played_counters = {}  
active_sessions = {}

def get_tiktok_video_info(query):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
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
        except Exception:
            continue

    return None

class TikTokControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary, custom_id="btn_skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session and interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Đã chuyển sang bài tiếp theo!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có nội dung nào đang phát.", ephemeral=True)

    @discord.ui.button(label="⏹️ Dừng Hẳn", style=discord.ButtonStyle.danger, custom_id="btn_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if self.guild_id in guild_queues:
            guild_queues[self.guild_id] = []
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
        title="📱 SubVibe Video & TTS Bot",
        description="Hỗ trợ phát Video TikTok/Shorts mượt mà và Thuyết minh TTS ElevenLabs kèm nhạc nền.",
        color=discord.Color.from_rgb(255, 0, 80)
    )
    embed.add_field(name="▶️ `!Vplay [Link/Từ khóa]`", value="Thêm video TikTok/Shorts vào hàng đợi.", inline=False)
    embed.add_field(name="🎙️ `!Vttp [Nội dung] (Link SoundCloud)`", value="Tạo giọng thuyết minh ElevenLabs + Nhạc nền SoundCloud.", inline=False)
    await ctx.send(embed=embed)

async def play_next_in_queue(ctx):
    guild_id = ctx.guild.id
    queue_data = guild_queues.get(guild_id, [])

    if not queue_data:
        active_sessions.pop(guild_id, None)
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.disconnect()
        return

    current_video = queue_data.pop(0)
    session = active_sessions.get(guild_id)
    if not session or session["stop_flag"]:
        return

    status_msg = await ctx.send(f"🤖 *Đang tải xuống video: `{current_video['title']}`...*")
    target_video_path = None
    is_temp_file = False

    try:
        source_url = current_video['url']
        if "discordapp.com" in source_url or "cdn.discordapp.com" in source_url:
            ext = os.path.splitext(source_url.split("?")[0])[1] or ".mp4"
            target_video_path = os.path.join(tempfile.gettempdir(), f"uploaded_{random.randint(1000,9999)}{ext}")
            req = urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(target_video_path, 'wb') as out_file:
                out_file.write(response.read())
            is_temp_file = True
        else:
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(tempfile.gettempdir(), 'video_temp.%(ext)s'),
                'quiet': True,
                'user_agent': 'Mozilla/5.0'
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=True)
                target_video_path = ydl.prepare_filename(info)
                is_temp_file = True

        # HÀNG ĐỢI & THỜI GIAN BUFFER 10 GIÂY
        frame_queue = queue.Queue(maxsize=40)
        stop_thread_flag = threading.Event()

        def frame_worker(video_path, title_text):
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_interval = max(1, int(fps / 4.0))
            
            f_count = 0
            while cap.isOpened() and not stop_thread_flag.is_set():
                ret, frame = cap.read()
                if not ret:
                    break
                if f_count % frame_interval == 0:
                    try:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(frame_rgb)
                        img_buf = render_clean_video_frame(pil_img, subtitle_text=f"🎵 {title_text[:40]}")
                        if img_buf and not frame_queue.full():
                            frame_queue.put(img_buf)
                    except Exception:
                        pass
                f_count += 1
            cap.release()
            frame_queue.put(None)

        worker_thread = threading.Thread(target=frame_worker, args=(target_video_path, current_video['title']))
        worker_thread.daemon = True
        worker_thread.start()

        await status_msg.edit(content=f"⚙️ *Đang tạo các lớp khung hình (Buffer 10s) cho: `{current_video['title']}`...*")
        await asyncio.sleep(10)

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        audio_source = discord.FFmpegPCMAudio(target_video_path)
        ctx.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_in_queue(ctx), bot.loop))

        rendered_message = None
        first_frame = True
        last_update_time = time.time()

        while not session["stop_flag"] and ctx.voice_client and ctx.voice_client.is_playing():
            try:
                img_buf = frame_queue.get(timeout=0.2)
                if img_buf is None:
                    break
                
                file = discord.File(fp=img_buf, filename="render.jpg")
                current_time = time.time()

                if first_frame:
                    rendered_message = await ctx.send(file=file, view=TikTokControlView(guild_id))
                    first_frame = False
                    last_update_time = current_time
                else:
                    if current_time - last_update_time >= 0.22:
                        try:
                            await status_msg.edit(content=f"📱 *Đang phát từ @{current_video['uploader']}*")
                            await rendered_message.edit(attachments=[file])
                            last_update_time = current_time
                        except Exception:
                            pass
            except queue.Empty:
                if not worker_thread.is_alive() and frame_queue.empty():
                    break
                await asyncio.sleep(0.05)
                continue

        stop_thread_flag.set()
        worker_thread.join(timeout=1.0)

        if is_temp_file and target_video_path and os.path.exists(target_video_path):
            os.remove(target_video_path)

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

    attachment_url = None
    if ctx.message.attachments:
        for att in ctx.message.attachments:
            if att.filename.lower().endswith(('.mp4', '.mov', '.webm', '.mkv', '.avi')):
                attachment_url = att.url
                break

    if not query and not attachment_url:
        await ctx.send("⚠️ Cú pháp: `!Vplay [Link/Từ khóa]` hoặc gửi kèm video!")
        return

    voice_channel = ctx.author.voice.channel
    try:
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
    except Exception as e:
        await ctx.send(f"❌ Lỗi voice: {e}")
        return

    guild_id = ctx.guild.id
    if guild_id not in guild_queues:
        guild_queues[guild_id] = []

    if attachment_url:
        video_info = {'url': attachment_url, 'title': 'Video Đính Kèm', 'uploader': ctx.author.display_name}
    else:
        await ctx.send(f"🔍 *Đang tìm kiếm: `{query}`...*")
        video_info = get_tiktok_video_info(query)

    if not video_info:
        await ctx.send("❌ Không tìm thấy video!")
        return

    guild_queues[guild_id].append(video_info)

    if guild_id not in active_sessions or not active_sessions[guild_id]["is_playing"]:
        active_sessions[guild_id] = {"is_playing": True, "stop_flag": False}
        await play_next_in_queue(ctx)
    else:
        await ctx.send(f"✅ Đã thêm vào hàng đợi: **{video_info['title']}**")

@bot.command(name="ttp", aliases=["tts"])
async def tts_with_bgm(ctx, *, args: str = None):
    # YÊU CẦU BẮT BUỘC: Phải ở trong Voice Channel
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("⚠️ **Yêu cầu bắt buộc:** Nam phải vào Kênh Thoại trước khi dùng lệnh này!")
        return

    if not args:
        await ctx.send("⚠️ Cú pháp: `!Vttp [Nội dung văn bản] (Link SoundCloud nhạc nền)`")
        return

    # Tách văn bản và SoundCloud URL
    soundcloud_url = None
    url_match = re.search(r'(https?://(?:www\.)?soundcloud\.com/[^\s]+)', args)
    if url_match:
        soundcloud_url = url_match.group(1)
        text_content = args.replace(soundcloud_url, "").strip(" ()")
    else:
        text_content = args.strip()

    if not text_content:
        await ctx.send("⚠️ Vui lòng nhập nội dung văn bản cần đọc!")
        return

    voice_channel = ctx.author.voice.channel
    try:
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
    except Exception as e:
        await ctx.send(f"❌ Lỗi kết nối voice: {e}")
        return

    status_msg = await ctx.send("🎙️ *Đang tạo giọng đọc ElevenLabs & trộn nhạc nền SoundCloud...*")

    temp_dir = tempfile.gettempdir()
    tts_audio_path = os.path.join(temp_dir, f"tts_{random.randint(1000,9999)}.mp3")
    bgm_audio_path = os.path.join(temp_dir, f"bgm_{random.randint(1000,9999)}.mp3")
    output_audio_path = os.path.join(temp_dir, f"merged_{random.randint(1000,9999)}.mp3")

    try:
        # 1. Tạo TTS ElevenLabs
        tts_success = generate_elevenlabs_tts(text_content, tts_audio_path)
        if not tts_success:
            await ctx.send("❌ Tạo giọng đọc ElevenLabs thất bại. Kiểm tra Variable API Key / Quota!")
            return

        # 2. Xử lý nhạc nền & Mix Âm Lượng
        if soundcloud_url:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': bgm_audio_path,
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([soundcloud_url])

            # MIX ÂM LƯỢNG: Giọng đọc x1.2 (120%), Nhạc x0.25 (25%)
            ffmpeg_cmd = (
                f'ffmpeg -i "{tts_audio_path}" -i "{bgm_audio_path}" '
                f'-filter_complex "[0:a]volume=1.2[voice];[1:a]volume=0.25[bgm];[voice][bgm]amix=inputs=2:duration=first[a]" '
                f'-map "[a]" "{output_audio_path}" -y'
            )
            os.system(ffmpeg_cmd)
            final_audio = output_audio_path
        else:
            final_audio = tts_audio_path

        # 3. Phát vào kênh thoại
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

        audio_source = discord.FFmpegPCMAudio(final_audio)
        ctx.voice_client.play(audio_source)

        await status_msg.edit(content=f"🗣️ **Đang phát Thuyết Minh:** *\"{text_content}\"*")

    except Exception as e:
        print(f"Lỗi TTS: {e}")
        await ctx.send("❌ Có lỗi xảy ra trong quá trình trộn âm thanh!")

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
