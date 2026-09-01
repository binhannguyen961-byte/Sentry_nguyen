import os
import re
import asyncio
import threading
import io
import textwrap
import tempfile
import cv2
import yt_dlp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from flask import Flask
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai

# ==========================================
# 1. WEB SERVER NGẦM (Giữ Bot Online 24/7)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "SubVibe AI Subtitle Video Bot is Live!"

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
# 3. RENDER KHUNG HÌNH SẠCH KÈM PHỤ ĐỀ AI
# ==========================================
def render_clean_video_frame(video_frame_pil, subtitle_text=""):
    try:
        canvas = Image.new("RGBA", (800, 520), (20, 20, 25, 255))
        vid_resized = video_frame_pil.resize((800, 450)).convert("RGBA")
        canvas.paste(vid_resized, (0, 0))

        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(0, 450), (800, 520)], fill=(10, 10, 15, 230))

        font_sub = get_font(18)
        wrapped_lines = textwrap.wrap(subtitle_text, width=65)
        y_offset = 462
        for line in wrapped_lines[:2]:
            draw.text((25, y_offset), line, fill=(255, 255, 255), font=font_sub)
            y_offset += 24

        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Lỗi Render Frame: {e}")
        return None

# ==========================================
# 4. HÀM LẤY VÀ DỊCH PHỤ ĐỀ BẰNG GEMINI
# ==========================================
def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

def get_ai_translated_subtitles(video_url):
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return []

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        texts_to_translate = [item['text'] for item in transcript_list]

        translated_texts = texts_to_translate
        if gemini_client and texts_to_translate:
            combined_text = "\n---\n".join(texts_to_translate[:150])
            prompt = (
                "Translate the following English subtitle lines into natural Vietnamese. "
                "Keep the exact same number of lines separated by '---'. Do not add extra notes:\n\n" + combined_text
            )
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            if response and response.text:
                translated_texts = response.text.split('---')
                translated_texts = [t.strip() for t in translated_texts]

        subtitles = []
        for i, item in enumerate(transcript_list[:len(translated_texts)]):
            subtitles.append({
                "start": item['start'],
                "end": item['start'] + item['duration'],
                "text": translated_texts[i]
            })
        return subtitles
    except Exception as e:
        print(f"Không thể lấy phụ đề AI: {e}")
        return []

def get_current_subtitle(subtitles, current_sec):
    for sub in subtitles:
        if sub['start'] <= current_sec <= sub['end']:
            return sub['text']
    return ""

# ==========================================
# 5. QUẢN LÝ ĐIỀU KHIỂN (VIEW & BUTTONS)
# ==========================================
active_sessions = {}

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
            await interaction.response.send_message("⏸️ Đã tạm dừng video.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có video nào đang chạy.", ephemeral=True)

    @discord.ui.button(label="▶️ Tiếp Tục", style=discord.ButtonStyle.success, custom_id="btn_resume")
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session and session["is_playing"]:
            session["is_paused"] = False
            if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
                interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Tiếp tục phát video.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Video không ở trạng thái tạm dừng.", ephemeral=True)

    @discord.ui.button(label="⏹️ Dừng Hẳn", style=discord.ButtonStyle.danger, custom_id="btn_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = active_sessions.get(self.guild_id)
        if session:
            session["stop_flag"] = True
            if interaction.guild.voice_client:
                if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
                    interaction.guild.voice_client.stop()
                await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("⏹️ Đã dừng và thoát kênh thoại.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có tiến trình nào đang chạy.", ephemeral=True)

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
        title="🎬 SubVibe - Trình Phát Video & Phụ Đề AI",
        description="Bot phát trực tiếp video YouTube vào voice, render khung hình sạch và dịch phụ đề tiếng Việt tự động bằng Gemini.",
        color=discord.Color.from_rgb(120, 198, 122)
    )
    embed.add_field(name="▶️ `!Vplay [Link hoặc Tên Video]`", value="Phát video kèm phụ đề AI tiếng Việt, tự động nghỉ sau mỗi 5 phút.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="play", aliases=["render", "phat"])
async def play_asset_video(ctx, *, query: str = None):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("⚠️ Nam cần vào Kênh Thoại trước khi dùng lệnh này!")
        return

    if not query:
        await ctx.send("⚠️ Vui lòng nhập link hoặc tên video. Ví dụ: `!Vplay Shermans vs Panthers`")
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
    session = {"is_playing": True, "is_paused": False, "stop_flag": False}
    active_sessions[guild_id] = session

    status_msg = await ctx.send(f"🤖 *Đang tìm kiếm video và dịch phụ đề tiếng Việt bằng AI...*")

    # Xử lý thông minh: Nếu không phải link trực tiếp, tự động chuyển thành từ khóa tìm kiếm ytsearch để lách lỗi bot
    search_target = query if query.startswith("http") else f"ytsearch1:{query}"

    target_video_path = None
    is_temp_file = False

    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'noplaylist': True,
            'outtmpl': os.path.join(tempfile.gettempdir(), 'downloaded_video.%(ext)s'),
            'quiet': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=True)
            # Nếu dùng ytsearch, kết quả trả về là list, ta lấy phần tử đầu tiên
            if 'entries' in info:
                info = info['entries'][0]
            
            target_video_path = ydl.prepare_filename(info)
            real_video_url = info.get('webpage_url', query if query.startswith("http") else f"https://www.youtube.com/watch?v={info.get('id')}")
            is_temp_file = True

        # Lấy sub dựa trên link chuẩn của video tìm được
        subtitles = get_ai_translated_subtitles(real_video_url)

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        audio_source = discord.FFmpegPCMAudio(target_video_path)
        ctx.voice_client.play(audio_source)

        cap = cv2.VideoCapture(target_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        target_fps = 5.0
        frame_interval = int(fps / target_fps) if fps > target_fps else 1
        
        frame_count = 0
        rendered_message = None
        five_min_counter = 0.0

        while cap.isOpened() and not session["stop_flag"]:
            while session["is_paused"] and not session["stop_flag"]:
                await asyncio.sleep(0.5)

            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                current_sec = int(frame_count / fps) if fps > 0 else 0
                current_sub_text = get_current_subtitle(subtitles, current_sec)
                if not current_sub_text:
                    current_sub_text = f"Đang phát... [{current_sec}s]"

                img_buf = render_clean_video_frame(pil_img, subtitle_text=current_sub_text)

                if img_buf:
                    file = discord.File(fp=img_buf, filename="video_render.png")
                    if rendered_message is None:
                        rendered_message = await ctx.send(file=file)
                    else:
                        await status_msg.edit(content=f"🎬 *Đang chiếu video kèm phụ đề AI [⏱️ {current_sec}s]*", view=VideoControlView(guild_id))
                        await rendered_message.edit(attachments=[file])

                five_min_counter += (1.0 / target_fps)
                if five_min_counter >= 300.0:
                    five_min_counter = 0.0
                    session["is_paused"] = True
                    if ctx.voice_client and ctx.voice_client.is_playing():
                        ctx.voice_client.pause()
                    
                    await ctx.send(
                        "☕ *Đã phát liên tục 5 phút rồi! Chúng ta nghỉ giải lao 1 phút nhé.*\n"
                        "*(Nam có thể bấm nút **▶️ Tiếp Tục** bất cứ lúc nào)*"
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
        if is_temp_file and target_video_path and os.path.exists(target_video_path):
            os.remove(target_video_path)

        await ctx.send("✨ *Video đã phát xong hoàn tất!* 💚")

    except Exception as e:
        active_sessions.pop(guild_id, None)
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.disconnect()
        if is_temp_file and target_video_path and os.path.exists(target_video_path):
            os.remove(target_video_path)
        await ctx.send(f"❌ Lỗi xảy ra khi phát video: {e}")

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
