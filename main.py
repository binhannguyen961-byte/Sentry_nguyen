import os
import io
import cv2
import asyncio
import threading
from PIL import Image
from flask import Flask
import discord
from discord.ext import commands

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
    return "Media Convert Bot is Online!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 3. KHỞI TẠO DISCORD BOT
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"-> Bot đã sẵn sàng: {bot.user}")

# ==========================================
# 4. HÀM TÁCH VIDEO THÀNH CÁC FILE GIF (10s/GIF)
# ==========================================
def process_video_to_gifs(video_path, chunk_duration=10, target_fps=8):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    if duration > 61:  # Giới hạn 1 phút
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
                # Thu nhỏ kích thước ảnh để đảm bảo file GIF nhẹ < 8MB
                pil_img = pil_img.resize((480, 270))
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

# ==========================================
# 5. LỆNH XỬ LÝ CHÍNH (!process / !gif / !convert)
# ==========================================
@bot.command(name="process", aliases=["convert", "gif"])
async def process_media(ctx):
    # 1. Kiểm tra xem người dùng có ở trong Voice Channel không
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ **Yêu cầu bắt buộc:** Cậu phải tham gia vào một Voice Channel trước khi dùng lệnh này!")
        return

    # 2. Kiểm tra file MP4 đính kèm
    if not ctx.message.attachments:
        await ctx.send("❌ Cậu hãy gửi kèm một file video (MP4) cùng với lệnh nhé!")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith(('.mp4', '.mov', '.mkv')):
        await ctx.send("❌ Chỉ hỗ trợ định dạng video (.mp4, .mov, .mkv)!")
        return

    display_msg = await ctx.send("⏳ *Đang tải và xử lý video... Vui lòng chờ trong giây lát!*")
    temp_video_path = f"temp_{ctx.author.id}_{attachment.filename}"
    await attachment.save(temp_video_path)

    try:
        # 3. Cắt Video thành danh sách các file GIF (10s/đoạn)
        loop = asyncio.get_event_loop()
        gif_list, err = await loop.run_in_executor(None, process_video_to_gifs, temp_video_path)

        if err:
            await display_msg.edit(content=f"❌ Lỗi: {err}")
            return

        if not gif_list:
            await display_msg.edit(content="❌ Không thể cắt GIF từ video này.")
            return

        # 4. Kết nối Voice Channel
        user_channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        if voice_client is None:
            voice_client = await user_channel.connect()
        elif voice_client.channel != user_channel:
            await voice_client.move_to(user_channel)

        if voice_client.is_playing():
            voice_client.stop()

        # 5. Phát Âm thanh từ Video trong Voice Channel
        audio_source = discord.FFmpegPCMAudio(temp_video_path, executable="ffmpeg")
        voice_client.play(audio_source)

        # 6. HIỂN THỊ VÀ CHỈNH SỬA TIN NHẮN THEO TIẾN ĐỘ (EDIT MESSAGE)
        total_parts = len(gif_list)
        for index, (gif_name, gif_buf) in enumerate(gif_list, start=1):
            file = discord.File(fp=gif_buf, filename=gif_name)
            
            # Sửa trực tiếp tin nhắn ban đầu với file GIF mới
            await display_msg.edit(
                content=f"🎬 **Đang trình chiếu đoạn [{index}/{total_parts}]**",
                attachments=[file]
            )

            # Nếu chưa tới GIF cuối cùng, chờ 10 giây (thời lượng GIF) rồi mới edit đoạn tiếp theo
            if index < total_parts:
                await asyncio.sleep(10)

        # Cập nhật thông báo sau khi trình chiếu xong toàn bộ
        await display_msg.edit(content=f"✅ **Đã hoàn thành trình chiếu {total_parts} đoạn GIF!**")

    except Exception as e:
        await ctx.send(f"❌ Lỗi trong quá trình xử lý: {e}")
    finally:
        # Dọn dẹp file tạm
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)

# ==========================================
# 6. TỰ ĐỘNG NGẮT VOICE KHI KHÔNG CÒN AI
# ==========================================
@bot.event
async def on_voice_state_update(member, before, after):
    for vc in bot.voice_clients:
        if len(vc.channel.members) == 1:  # Chỉ còn lại Bot
            await vc.disconnect()

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
        print("Lỗi: Chưa thiết lập DISCORD_TOKEN trong Environment Variables!")
