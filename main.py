import os
import requests
import discord
from discord.ext import commands
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from pillow_heif import register_heif_opener
from google import genai

# Đăng ký mở file HEIC của iOS cho Pillow
register_heif_opener()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

REPO_LINK = "https://github.com/binhannguyen961-byte/Sentry_nguyen/tree/main"
RAW_GITHUB_BASE = "https://raw.githubusercontent.com/binhannguyen961-byte/Sentry_nguyen/main/assets"

LINK_GOOD_LUCK_DIGGER = "https://x.com/felenopy_/status/2094876317472739524?s=46"
LINK_DEVNOTE = "https://x.com/thetruthisalies/status/2095092376071290952?s=46"

ASSETS_DIR = "game_01"
os.makedirs(ASSETS_DIR, exist_ok=True)

# Các tài nguyên đồng bộ từ Repo GitHub của Nam
REQUIRED_ASSETS = [
    "meltdown_ending.jpg",
    "mirror_0.jpg",
    "walking_01.mov",
    "starting_sence.mov",
    "room_background.heic",
    "bg_music.mp3",
    "jumpscare.mp4"
]

game_state = {
    "mirror_clicks": 0,
    "is_night_mode": False
}

# ==========================================
# 1. TỰ ĐỘNG ĐỒNG BỘ ASSETS TỪ GITHUB
# ==========================================
def sync_assets_from_repo():
    print("🔄 Đang kiểm tra và đồng bộ tài nguyên từ GitHub Repo...")
    for filename in REQUIRED_ASSETS:
        local_path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(local_path):
            file_url = f"{RAW_GITHUB_BASE}/{filename}"
            print(f"📥 Đang tải: {filename}...")
            try:
                res = requests.get(file_url, timeout=15)
                if res.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(res.content)
                    print(f"✅ Đã tải xong: {filename}")
                else:
                    print(f"⚠️ Không tìm thấy {filename} (HTTP {res.status_code})")
            except Exception as e:
                print(f"❌ Lỗi tải {filename}: {e}")

# ==========================================
# 2. TẠO KHUNG CHAT BẰNG PILLOW
# ==========================================
def create_chat_frame(username: str, message_text: str, bg_image_name: str) -> str:
    output_path = os.path.join(ASSETS_DIR, "generated_chat.jpg")
    bg_image_path = os.path.join(ASSETS_DIR, bg_image_name)

    if os.path.exists(bg_image_path):
        base_img = Image.open(bg_image_path).convert("RGBA")
    else:
        base_img = Image.new("RGBA", (800, 600), (30, 30, 30, 255))

    base_img = base_img.resize((800, 600))
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Khung thoại Discord
    draw.rounded_rectangle([40, 420, 760, 560], radius=15, fill=(32, 34, 37, 220), outline=(88, 101, 242, 255), width=2)
    draw.ellipse([55, 435, 105, 485], fill=(88, 101, 242, 255))
    
    try:
        font_title = ImageFont.truetype("arial.ttf", 20)
        font_text = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((120, 440), f"{username} [SYSTEM]", fill=(255, 255, 255, 255), font=font_title)
    wrapped_text = message_text if len(message_text) < 60 else message_text[:57] + "..."
    draw.text((120, 475), wrapped_text, fill=(220, 221, 222, 255), font=font_text)

    final_img = Image.alpha_composite(base_img, overlay)
    final_img.convert("RGB").save(output_path, "JPEG", quality=90)
    return output_path

# ==========================================
# 3. XỬ LÝ TTS & VOICE
# ==========================================
def generate_tts_audio(text: str, filename: str = "dialogue.mp3") -> str:
    filepath = os.path.join(ASSETS_DIR, filename)
    tts = gTTS(text=text, lang='en', tld='co.uk', slow=False)
    tts.save(filepath)
    return filepath

async def play_tts_in_voice(ctx, audio_path: str):
    if ctx.voice_client and ctx.voice_client.is_connected():
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        source = discord.FFmpegPCMAudio(audio_path)
        ctx.voice_client.play(source)

# ==========================================
# 4. CÁC LỆNH BOT
# ==========================================
@bot.event
async def on_ready():
    sync_assets_from_repo()
    print(f"🚀 Bot Sentry [{bot.user.name}] đã sẵn sàng hoạt động!")

@bot.command(name="join")
async def join_voice(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"🔊 Đã vào kênh voice: `{channel.name}`")
    else:
        await ctx.send("❌ Bạn cần vào phòng Voice trước!")

@bot.command(name="leave")
async def leave_voice(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🔇 Đã ngắt kết nối Voice.")

@bot.command(name="playbg")
async def play_background_music(ctx):
    if not ctx.voice_client:
        await ctx.invoke(join_voice)
    
    bg_path = os.path.join(ASSETS_DIR, "bg_music.mp3")
    if os.path.exists(bg_path):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            
        ffmpeg_options = {'options': '-stream_loop -1'}
        source = discord.FFmpegPCMAudio(bg_path, **ffmpeg_options)
        ctx.voice_client.play(source)
        await ctx.send("🎶 Đang phát nhạc nền bầu không khí từ Repo...")
    else:
        await ctx.send("❌ Không tìm thấy `bg_music.mp3`!")

@bot.command(name="start")
async def start_game(ctx, repo: str = None):
    if not repo or repo.strip() != REPO_LINK:
        await ctx.send("❌ Link Repository không hợp lệ!")
        return

    game_state["mirror_clicks"] = 0
    dialogue = "The truth is a lie. Welcome to the abandoned house."
    
    chat_img_path = create_chat_frame("SYSTEM", dialogue, "room_background.heic")
    audio_path = generate_tts_audio(dialogue, "start.mp3")

    await play_tts_in_voice(ctx, audio_path)

    files = [
        discord.File(chat_img_path, filename="scene.jpg"),
        discord.File(audio_path, filename="voice.mp3")
    ]
    await ctx.send(files=files)

@bot.command(name="look")
async def look_around(ctx):
    game_state["mirror_clicks"] += 1
    clicks = game_state["mirror_clicks"]

    if clicks < 8:
        dialogue = f"You stare into the mirror on the floor. Count {clicks}."
        bg_name = "mirror_0.jpg"
    else:
        dialogue = "Identity meltdown detected. Enter code 4099."
        bg_name = "meltdown_ending.jpg"

    chat_img_path = create_chat_frame("MIRROR", dialogue, bg_name)
    audio_path = generate_tts_audio(dialogue, f"look_{clicks}.mp3")

    await play_tts_in_voice(ctx, audio_path)

    files = [
        discord.File(chat_img_path, filename="scene.jpg"),
        discord.File(audio_path, filename="voice.mp3")
    ]
    await ctx.send(files=files)

@bot.command(name="write")
async def write_command(ctx, *, code: str = None):
    if not code:
        await ctx.send("❌ Nhập mã kèm theo!")
        return

    code_clean = code.strip().lower()

    if code_clean == "an09328":
        dialogue = "Good luck digger. Link unlocked."
        audio_path = generate_tts_audio(dialogue, "an.mp3")
        await play_tts_in_voice(ctx, audio_path)
        await ctx.send(content=f"🔗 {LINK_GOOD_LUCK_DIGGER}", file=discord.File(audio_path))
        return

    if code_clean == "devnote":
        dialogue = "Devnote accessed. Remember 2007."
        audio_path = generate_tts_audio(dialogue, "dev.mp3")
        await play_tts_in_voice(ctx, audio_path)
        await ctx.send(content=f"📝 {LINK_DEVNOTE}", file=discord.File(audio_path))
        return

    # Mã chạy video chuyển động trực tiếp (.mov / .mp4)
    if code_clean == "walking":
        video_path = os.path.join(ASSETS_DIR, "walking_01.mov")
        if os.path.exists(video_path):
            dialogue = "Footsteps approaching..."
            audio_path = generate_tts_audio(dialogue, "walking.mp3")
            await play_tts_in_voice(ctx, audio_path)
            
            files = [
                discord.File(video_path, filename="walking.mov"),
                discord.File(audio_path, filename="voice.mp3")
            ]
            await ctx.send(content="⚠️ **[MOVEMENT DETECTED]**", files=files)
            return

    # MÃ LẠ: Gọi Gemini phản hồi luyên thuyên + nhắc mốc năm 2007
    try:
        prompt = (
            f"Bạn là một nhân vật kỳ dị trong game tâm lý kinh dị ARG. "
            f"Người chơi vừa gõ mã '{code}'. Hãy trả lời luyên thuyên, vô định,bí ẩn một cách điềm tĩnh, "
            f"thi thoảng lái sang chủ đề khác nhưng phải thường xuyên nhắc tới con số 2007. "
            f"Trả lời ngắn gọn bằng tiếng Anh."
        )
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        ai_reply = response.text.strip()
        
        chat_img = create_chat_frame("STRANGER", ai_reply, "mirror_0.jpg")
        audio_path = generate_tts_audio(ai_reply, "ai_reply.mp3")

        await play_tts_in_voice(ctx, audio_path)

        files = [
            discord.File(chat_img, filename="scene.jpg"),
            discord.File(audio_path, filename="voice.mp3")
        ]
        await ctx.send(files=files)
    except Exception as e:
        await ctx.send("❌ Dữ liệu mã nhiễu sóng...")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
    bot.run(TOKEN)
