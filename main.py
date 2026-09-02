import os
import io
import cv2
import asyncio
import threading
from PIL import Image
from flask import Flask
import discord
from discord.ext import commands
from discord.ui import Button, View

# Thư viện gTTS cho TTS
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

# Thư viện SpeechRecognition & PyDub cho Tạo phụ đề
try:
    import speech_recognition as sr
    from pydub import AudioSegment
    HAS_STT = True
except ImportError:
    HAS_STT = False

# ==========================================
# 1. LOAD OPUS CHO VOICE CHANNEL (DOCKER)
# ==========================================
if not discord.opus.is_loaded():
    for opus_lib in ['libopus.so.0', 'libopus.so', '/usr/lib/x86_64-linux-gnu/libopus.so.0']:
        try:
            discord.opus.load_opus(opus_lib)
            print(f"-> Đã load Opus thành công: {opus_lib}")
            break
        except Exception:
            pass

# ==========================================
# 2. WEB SERVER GIỮ BOT ONLINE 24/7
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "All-in-One Discord Bot is Online!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 3. KHỞI TẠO DISCORD BOT & HÀNG CHỜ NHẠC
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

music_queues = {}
is_looping = {}
current_track = {}

def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    return music_queues[guild_id]

@bot.event
async def on_ready():
    print(f"-> Bot đã sẵn sàng hoạt động: {bot.user}")

# ==========================================
# 4. VIEW NÚT BẤM ĐIỀU KHIỂN MP3 (DISCORD UI)
# ==========================================
class MusicPlayerView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏯️ Play/Pause", style=discord.ButtonStyle.primary)
    async def btn_play_pause(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("❌ Bot không ở trong Voice Channel!", ephemeral=True)
            return

        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Đã tiếp tục phát!", ephemeral=True)
        elif vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Đã tạm dừng!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có bài hát nào đang phát!", ephemeral=True)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary)
    async def btn_skip(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Không có bài hát nào để bỏ qua!", ephemeral=True)
            return

        vc.stop()
        await interaction.response.send_message("⏭️ Đã bỏ qua bài hiện tại!", ephemeral=True)

    @discord.ui.button(label="🔁 Loop", style=discord.ButtonStyle.success)
    async def btn_loop(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id
        is_looping[guild_id] = not is_looping.get(guild_id, False)
        status = "BẬT 🔁" if is_looping[guild_id] else "TẮT 🔄"
        await interaction.response.send_message(f"🔁 Chế độ lặp lại: **{status}**", ephemeral=True)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def btn_stop(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id
        queue = get_queue(guild_id)
        queue.clear()
        is_looping[guild_id] = False

        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()

        await interaction.response.send_message("⏹️ Đã dừng phát, xóa hàng chờ và thoát Voice!", ephemeral=True)

# ==========================================
# 5. ENGINE PHÁT MP3
# ==========================================
def play_next_track(ctx):
    guild_id = ctx.guild.id
    queue = get_queue(guild_id)
    vc = ctx.voice_client

    if not vc:
        return

    if is_looping.get(guild_id, False) and guild_id in current_track:
        song_info = current_track[guild_id]
    elif len(queue) > 0:
        song_info = queue.pop(0)
        current_track[guild_id] = song_info
    else:
        current_track.pop(guild_id, None)
        return

    file_path = song_info['path']
    song_title = song_info['title']

    audio_source = discord.FFmpegPCMAudio(file_path, executable="ffmpeg")
    vc.play(audio_source, after=lambda e: play_next_track(ctx))

    embed = discord.Embed(
        title="🎶 ĐANG PHÁT NHẠC MP3",
        description=f"🎵 **Bài hát:** `{song_title}`\n👤 **Yêu cầu bởi:** {song_info['requester'].mention}",
        color=discord.Color.blue()
    )
    
    view = MusicPlayerView(ctx)
    asyncio.run_coroutine_threadsafe(ctx.send(embed=embed, view=view), bot.loop)

# ==========================================
# 6. LỆNH PHÁT NHẠC MP3 (!add, !queue)
# ==========================================
@bot.command(name="add")
async def add_mp3(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Cậu phải vào một Voice Channel trước khi dùng lệnh `!add`!")
        return

    if not ctx.message.attachments:
        await ctx.send("❌ Cậu hãy gửi kèm một file nhạc (.mp3) cùng với lệnh `!add`!")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith('.mp3'):
        await ctx.send("❌ Chỉ hỗ trợ định dạng file nhạc `.mp3`!")
        return

    user_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        vc = await user_channel.connect()
    elif vc.channel != user_channel:
        await vc.move_to(user_channel)

    if not os.path.exists("temp_audio"):
        os.makedirs("temp_audio")

    file_path = f"temp_audio/{ctx.guild.id}_{attachment.id}_{attachment.filename}"
    await attachment.save(file_path)

    song_info = {
        'title': attachment.filename,
        'path': file_path,
        'requester': ctx.author
    }

    queue = get_queue(ctx.guild.id)

    if not vc.is_playing() and not vc.is_paused():
        queue.append(song_info)
        play_next_track(ctx)
    else:
        queue.append(song_info)
        await ctx.send(f"➕ Đã thêm **`{attachment.filename}`** vào hàng chờ (Vị trí #{len(queue)})!")

@bot.command(name="queue", aliases=["q"])
async def show_queue(ctx):
    queue = get_queue(ctx.guild.id)
    guild_id = ctx.guild.id

    embed = discord.Embed(title="📜 HÀNG CHỜ NHẠC MP3", color=discord.Color.purple())

    if guild_id in current_track:
        loop_status = " (🔁 Loop)" if is_looping.get(guild_id, False) else ""
        embed.add_field(
            name="🔊 Đang phát:",
            value=f"`{current_track[guild_id]['title']}`{loop_status}",
            inline=False
        )

    if len(queue) == 0:
        embed.add_field(name="📋 Hàng chờ tiếp theo:", value="*Hàng chờ đang trống*", inline=False)
    else:
        queue_text = ""
        for idx, song in enumerate(queue, start=1):
            queue_text += f"**{idx}.** `{song['title']}` - Yêu cầu bởi {song['requester'].mention}\n"
        embed.add_field(name="📋 Hàng chờ tiếp theo:", value=queue_text, inline=False)

    await ctx.send(embed=embed)

# ==========================================
# 7. LỆNH TỰ ĐỘNG TẠO PHỤ ĐỀ TIẾNG VIỆT (!sub / !subtitle)
# ==========================================
def generate_subtitles_from_audio(mp3_path):
    """
    Chuyển đổi MP3 sang WAV và nhận diện giọng nói Tiếng Việt bằng SpeechRecognition.
    Trả về nội dung văn bản phụ đề và file .srt tạm thời.
    """
    if not HAS_STT:
        return None, "Thư viện `SpeechRecognition` hoặc `pydub` chưa được cài đặt trong requirements.txt!"

    try:
        # Convert MP3 sang WAV tạm thời để đọc dữ liệu âm thanh
        wav_path = mp3_path.rsplit(".", 1)[0] + ".wav"
        sound = AudioSegment.from_file(mp3_path)
        sound.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            # Dùng Google Speech API nhận diện Tiếng Việt
            text = recognizer.recognize_google(audio_data, language="vi-VN")

        # Xóa file WAV tạm
        if os.path.exists(wav_path):
            os.remove(wav_path)

        # Tạo file phụ đề chuẩn SRT
        srt_path = mp3_path.rsplit(".", 1)[0] + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:01:00,000\n" + text + "\n")

        return text, srt_path

    except sr.UnknownValueError:
        return None, "Không nhận diện được giọng nói trong file âm thanh này."
    except sr.RequestError as e:
        return None, f"Lỗi kết nối tới dịch vụ nhận diện: {e}"
    except Exception as e:
        return None, f"Lỗi xử lý file âm thanh: {e}"

@bot.command(name="sub", aliases=["subtitle", "phude"])
async def create_subtitle(ctx):
    """Lệnh nhận diện lời nói trong MP3 và xuất ra văn bản + file .srt"""
    if not ctx.message.attachments:
        await ctx.send("❌ Cậu hãy gửi kèm một file âm thanh (`.mp3` hoặc `.wav`) cùng với lệnh `!sub`!")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith(('.mp3', '.wav', '.m4a')):
        await ctx.send("❌ Chỉ hỗ trợ các file âm thanh (`.mp3`, `.wav`, `.m4a`)!")
        return

    status_msg = await ctx.send("⏳ *Đang lắng nghe và trích xuất phụ đề Tiếng Việt... Vui lòng chờ!*")

    if not os.path.exists("temp_audio"):
        os.makedirs("temp_audio")

    temp_path = f"temp_audio/sub_{attachment.id}_{attachment.filename}"
    await attachment.save(temp_path)

    loop = asyncio.get_event_loop()
    text, srt_file = await loop.run_in_executor(None, generate_subtitles_from_audio, temp_path)

    if text:
        embed = discord.Embed(
            title="📝 KẾT QUẢ TRÍCH XUẤT PHỤ ĐỀ TIẾNG VIỆT",
            description=f"```text\n{text}\n```",
            color=discord.Color.teal()
        )
        if srt_file and os.path.exists(srt_file):
            file = discord.File(srt_file, filename="phu_de_tieng_viet.srt")
            await status_msg.edit(content="✅ **Đã tạo xong phụ đề!**", embed=embed)
            await ctx.send(file=file)
            os.remove(srt_file)
        else:
            await status_msg.edit(content="✅ **Đã nhận diện văn bản:**", embed=embed)
    else:
        await status_msg.edit(content=f"❌ **Không thể tạo phụ đề:** {srt_file}")

    if os.path.exists(temp_path):
        os.remove(temp_path)

# ==========================================
# 8. LỆNH TTS ĐỌC GIỌNG NÓI + NHẠC NỀN (!tts)
# ==========================================
@bot.command(name="tts")
async def text_to_speech(ctx, lang_or_text: str = None, *, text_rest: str = None):
    if not HAS_GTTS:
        await ctx.send("❌ Thư viện `gTTS` chưa được cài đặt trong `requirements.txt`!")
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Cậu phải tham gia vào Voice Channel trước!")
        return

    if not lang_or_text:
        await ctx.send("❌ Cậu phải nhập nội dung cần đọc! Ví dụ: `!tts Xin chào` hoặc `!tts en Hello` (Gửi kèm MP3 nếu muốn có nhạc nền).")
        return

    if text_rest:
        lang_code = lang_or_text
        text_content = text_rest
    else:
        lang_code = "vi"
        text_content = lang_or_text

    user_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        vc = await user_channel.connect()
    elif vc.channel != user_channel:
        await vc.move_to(user_channel)

    if vc.is_playing():
        vc.stop()

    if not os.path.exists("temp_audio"):
        os.makedirs("temp_audio")

    tts_path = f"temp_audio/tts_{ctx.author.id}.mp3"

    try:
        tts = gTTS(text=text_content, lang=lang_code, slow=False)
        tts.save(tts_path)
    except Exception as e:
        await ctx.send(f"❌ Lỗi tạo TTS (Kiểm tra lại mã ngôn ngữ `{lang_code}`): {e}")
        return

    bg_music_path = None
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.filename.lower().endswith('.mp3'):
            bg_music_path = f"temp_audio/bg_{attachment.id}_{attachment.filename}"
            await attachment.save(bg_music_path)

    if bg_music_path:
        ffmpeg_options = {
            'options': f'-i "{bg_music_path}" -filter_complex "[0:a]volume=1.6[voice];[1:a]volume=0.25[bg];[voice][bg]amix=inputs=2:duration=first[out]" -map "[out]"'
        }
        audio_source = discord.FFmpegPCMAudio(tts_path, executable="ffmpeg", **ffmpeg_options)
        await ctx.send(f"🗣️ **Đang đọc TTS (`{lang_code}`) kèm Nhạc nền:** `{text_content}`")
    else:
        audio_source = discord.FFmpegPCMAudio(tts_path, executable="ffmpeg")
        await ctx.send(f"🗣️ **Đang đọc TTS (`{lang_code}`):** `{text_content}`")

    def after_playing(error):
        if os.path.exists(tts_path):
            os.remove(tts_path)
        if bg_music_path and os.path.exists(bg_music_path):
            os.remove(bg_music_path)

    vc.play(audio_source, after=after_playing)

# ==========================================
# 9. HÀM TÁCH VIDEO THÀNH GIF (!process - FIX 413)
# ==========================================
def process_video_to_gifs(video_path, chunk_duration=10, target_fps=8):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, "Không thể đọc file video!"

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    if duration > 61:
        cap.release()
        return None, "Video vượt quá giới hạn 1 phút!"

    frames_per_chunk = int(fps * chunk_duration)
    frame_interval = max(1, int(fps / target_fps))
    
    gif_buffers = []
    current_frame = 0
    chunk_index = 1

    while cap.isOpened():
        chunk_frames = []
        chunk_end_frame = current_frame + frames_per_chunk

        while current_frame < chunk_end_frame and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if current_frame % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                pil_img = pil_img.resize((360, 202), Image.Resampling.BILINEAR)
                pil_img = pil_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
                chunk_frames.append(pil_img)

            current_frame += 1

        if chunk_frames:
            buf = io.BytesIO()
            chunk_frames[0].save(
                buf,
                format="GIF",
                save_all=True,
                append_images=chunk_frames[1:],
                duration=int(1000 / target_fps),
                loop=0,
                optimize=True
            )
            buf.seek(0)
            gif_buffers.append((f"part_{chunk_index}.gif", buf))
            chunk_index += 1
        else:
            break

    cap.release()
    return gif_buffers, None

@bot.command(name="process", aliases=["convert", "gif"])
async def process_media(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Cậu phải tham gia vào Voice Channel trước!")
        return

    if not ctx.message.attachments:
        await ctx.send("❌ Cậu hãy gửi kèm một file video (.mp4, .mov, .mkv)!")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith(('.mp4', '.mov', '.mkv')):
        await ctx.send("❌ Chỉ hỗ trợ định dạng video (.mp4, .mov, .mkv)!")
        return

    status_msg = await ctx.send("⏳ *Đang tải và xử lý video... Vui lòng chờ!*")
    temp_video_path = f"temp_{ctx.author.id}_{int(asyncio.get_event_loop().time())}_{attachment.filename}"
    await attachment.save(temp_video_path)

    try:
        loop = asyncio.get_event_loop()
        gif_list, err = await loop.run_in_executor(None, process_video_to_gifs, temp_video_path)

        if err:
            await status_msg.edit(content=f"❌ Lỗi: {err}")
            return

        user_channel = ctx.author.voice.channel
        vc = ctx.voice_client

        if vc is None:
            vc = await user_channel.connect()
        elif vc.channel != user_channel:
            await vc.move_to(user_channel)

        if vc.is_playing():
            vc.stop()

        ffmpeg_options = {'options': '-af "adelay=3000|3000"'}
        audio_source = discord.FFmpegPCMAudio(temp_video_path, executable="ffmpeg", **ffmpeg_options)
        vc.play(audio_source)

        total_parts = len(gif_list)
        current_msg = status_msg

        for index, (gif_name, gif_buf) in enumerate(gif_list, start=1):
            file = discord.File(fp=gif_buf, filename=gif_name)
            embed = discord.Embed(
                title="🎬 TRÌNH CHIẾU MEDIA",
                description=f"**Đang phát phân đoạn:** `[{index}/{total_parts}]` *(Âm thanh delay 3s)*",
                color=discord.Color.gold()
            )
            embed.set_image(url=f"attachment://{gif_name}")

            if current_msg and current_msg != status_msg:
                try:
                    await current_msg.delete()
                except Exception:
                    pass

            current_msg = await ctx.send(embed=embed, file=file)
            gif_buf.close()

            if index < total_parts:
                await asyncio.sleep(10)

        final_embed = discord.Embed(
            title="✅ TRÌNH CHIẾU HOÀN TẤT",
            description=f"Đã phát xong toàn bộ **{total_parts}** phân đoạn GIF!",
            color=discord.Color.green()
        )
        await current_msg.edit(embed=final_embed)

    except Exception as e:
        await ctx.send(f"❌ Lỗi xử lý: {e}")
    finally:
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)

# ==========================================
# 10. TỰ ĐỘNG NGẮT VOICE KHI PHÒNG TRỐNG
# ==========================================
@bot.event
async def on_voice_state_update(member, before, after):
    for vc in bot.voice_clients:
        if len(vc.channel.members) == 1:
            await vc.disconnect()

# ==========================================
# 11. KHỞI CHẠY BOT
# ==========================================
if __name__ == "__main__":
    t_flask = threading.Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Lỗi: Chưa thiết lập DISCORD_TOKEN trong Environment Variables!")
