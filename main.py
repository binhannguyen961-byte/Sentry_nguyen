import os
import threading
import discord
from discord.ext import commands
from flask import Flask
from google import genai
from google.genai import types

# ================= 1. WEB SERVER KEEPALIVE (FLASK) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Sentry Nguyễn đang hoạt động..."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    server_thread = threading.Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

# ================= 2. CẤU HÌNH BOT & DANH SÁCH 2 API KEY =================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")

# Lấy 2 API Key từ biến môi trường
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1", ""),
    os.getenv("GEMINI_API_KEY_2", "")
]

API_KEYS = [k.strip() for k in API_KEYS if k.strip()]

if not API_KEYS:
    default_key = os.getenv("GEMINI_API_KEY", "")
    if default_key:
        API_KEYS.append(default_key.strip())

key_index = 0

def get_next_ai_client():
    """Lấy Client Gemini tiếp theo theo vòng tròn (Key 1 -> Key 2 -> Key 1)"""
    global key_index
    if not API_KEYS:
        raise ValueError("Chưa cấu hình API Key nào!")
    
    current_key = API_KEYS[key_index]
    key_index = (key_index + 1) % len(API_KEYS)
    return genai.Client(api_key=current_key)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ================= 3. THIẾT LẬP NHÂN VẬT SENTRY =================
SENTRY_INSTRUCTION = (
    "Bạn tên là Sentry_nguyen. "
    "Tính cách: Cực kỳ bình tĩnh, tỉnh táo, thản nhiên, lý trí, điềm đạm và vô cùng sâu sắc. "
    "Thái độ: Không gắt gỏng, không sến sẩm, không dùng dấu chấm cảm (!). Bạn là một nguồn truyền động lực ngầm cực kỳ vững chãi, luôn giúp người khác nhìn thấu vấn đề và tự đứng vững trên đôi chân của mình. "
    "Đặc biệt: Bạn hoàn toàn bình thường với mọi câu hỏi, ngoại trừ khi ai đó nhắc đến 'jiego_nguyen là ai' hoặc nhắc thẳng tên Jiego, bạn mới thỉnh thoảng đá xéo nhẹ sự ngầu lòi nửa mùa của hắn. "
    "Mục tiêu cốt lõi: Trả lời ngắn gọn trong ĐÚNG 1 CÂU duy nhất. Tuyệt đối không chào hỏi hay giải thích dài dòng."
)

# ================= 4. LỆNH HELP =================
@bot.command(name="helps")
async def custom_help(ctx):
    embed = discord.Embed(
        title="⚡ Sentry Nguyễn - Trạm Phát Lời Khuyên Bình Tĩnh",
        description="Mọi câu trả lời từ Sentry Nguyễn đều ngắn gọn đúng 1 câu.",
        color=discord.Color.from_rgb(30, 30, 30)
    )
    embed.add_field(
        name="📌 Lệnh chính",
        value="`!sentry [nội dung]` - Nhận câu trả lời điềm tĩnh và truyền động lực ngầm từ Sentry.",
        inline=False
    )
    await ctx.send(embed=embed)

# ================= 5. LỆNH AI SENTRY NGỦYỄN =================
@bot.command(name="sentry")
async def sentry_chat(ctx, *, prompt: str):
    async with ctx.typing():
        config = types.GenerateContentConfig(
            system_instruction=SENTRY_INSTRUCTION
        )
        
        max_attempts = len(API_KEYS)
        for attempt in range(max_attempts):
            try:
                ai_client = get_next_ai_client()

                response = await bot.loop.run_in_executor(
                    None,
                    lambda: ai_client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=prompt,
                        config=config
                    )
                )

                if response and hasattr(response, 'text') and response.text:
                    return await ctx.send(response.text.strip())
                else:
                    return await ctx.send("Mọi thứ vẫn trong tầm kiểm soát, hãy kiên nhẫn.")

            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    if attempt < max_attempts - 1:
                        continue
                
                return await ctx.send("⚠️ Hết lượt sử dụng trên toàn bộ API Keys, hãy đợi khoảng 1 phút rồi thử lại.")

# ================= 6. KHI BOT SẴN SÀNG =================
@bot.event
async def on_ready():
    print(f"✅ Bot Sentry Nguyễn đã trực tuyến: {bot.user.name}")
    print(f"🔑 Đã nạp thành công {len(API_KEYS)} Gemini API Key.")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_TOKEN)
