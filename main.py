import asyncio
from datetime import datetime
import io
import json
import os
import random
import textwrap
import threading

from discord.ext import commands
from discord.ui import Button, View
import discord
from flask import Flask
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH API KEY XOAY VÒNG ---
api_keys = []
if os.environ.get("GEMINI_API_KEY"):
  api_keys.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"):
  api_keys.append(os.environ.get("GEMINI_API_KEY_2"))

current_key_idx = 0


def get_genai_client():
  global current_key_idx
  if not api_keys:
    return None, None
  active_key = api_keys[current_key_idx]
  current_key_idx = (current_key_idx + 1) % len(api_keys)
  return genai.Client(api_key=active_key), "gemini-3.6flash"


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix=["!", "/"], intents=intents, help_command=None
)

ASSETS_DIR = "assets"


def get_asset(filename):
  base_path = os.path.join(ASSETS_DIR, filename)
  if os.path.exists(base_path):
    return base_path
  name_root, ext = os.path.splitext(filename)
  for v in [
      ext.lower(),
      ext.upper(),
      ".jpg",
      ".JPG",
      ".jpeg",
      ".JPEG",
      ".png",
      ".PNG",
  ]:
    alt_path = os.path.join(ASSETS_DIR, name_root + v)
    if os.path.exists(alt_path):
      return alt_path
  return base_path


app = Flask(__name__)


@app.route("/")
def home():
  return "DDLC Expanded Story Engine Online!"


def run_flask():
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


# --- CẤU HÌNH NHÂN VẬT, MÀU SẮC & ĐỊA ĐIỂM ---
CHAR_COLORS = {
    "Sayori": (255, 160, 180),
    "Yuri": (180, 140, 230),
    "Natsuki": (255, 130, 170),
    "Monika": (120, 220, 160),
    "System": (255, 80, 80),
}

LOCATIONS = {
    "club": "Phòng Câu Lạc Bộ",
    "cafe": "Quán Trà & Bánh Kem",
    "park": "Công Viên Hoàng Hôn",
    "street": "Con Đường Đi Học",
}

POEM_WORDS = {
    "Sayori": [
        "Nắng",
        "Hạnh phúc",
        "Cầu vồng",
        "Ấm áp",
        "Bạn bè",
        "Nụ cười",
        "Mây",
        "Yêu thương",
        "Hy vọng",
    ],
    "Yuri": [
        "Bí ẩn",
        "U tối",
        "Sâu thẳm",
        "Triết học",
        "Đam mê",
        "Trà",
        "Đêm",
        "Máu",
        "Tâm linh",
    ],
    "Natsuki": [
        "Kẹo",
        "Dễ thương",
        "Hồng",
        "Bánh kem",
        "Manga",
        "Ngọt ngào",
        "Giấc mơ",
        "Giận dỗi",
    ],
    "Monika": [
        "Tương lai",
        "Thực tại",
        "Tình yêu",
        "Lập trình",
        "Tự do",
        "Vĩnh cửu",
        "Kiểm soát",
        "Mã nguồn",
    ],
}

CHAR_MINIGAMES = {
    "Sayori": {
        "title": "🌈 Đuổi Bắt Cảm Xúc (Sayori)",
        "question": "Sayori che giấu nỗi buồn đằng sau nụ cười, bạn làm gì?",
        "choices": [
            "Trao một cái ôm ấm áp và lắng nghe",
            "Trêu ghẹo để cô ấy cười",
            "Mua bánh ngọt dỗ dành",
            "Bỏ mặc cô ấy một mình",
        ],
        "correct": 0,
    },
    "Yuri": {
        "title": "📖 Giải Mã Triết Học (Yuri)",
        "question": "Yuri hỏi bạn về ý nghĩa của vết mực loang trên trang sách cũ:",
        "choices": [
            "Đó là dấu vết thời gian bí ẩn",
            "Do ai đó bất cẩn làm đổ",
            "Vết bẩn cần lau sạch",
            "Chẳng có ý nghĩa gì cả",
        ],
        "correct": 0,
    },
    "Natsuki": {
        "title": "🧁 Đọc Manga Bánh Kem (Natsuki)",
        "question": "Natsuki tức giận vì có người giấu tập Manga ở kệ cao:",
        "choices": [
            "Chủ động lấy giúp và khen bộ truyện",
            "Cười chê chiều cao của cô ấy",
            "Khuyên cô ấy đổi đọc sách chữ",
            "Lấy xuống rồi đòi trả phí",
        ],
        "correct": 0,
    },
    "Monika": {
        "title": "💻 Bức Tường Thứ Tư (Monika)",
        "question": "Monika nhìn thẳng vào bạn qua màn hình và hỏi:",
        "choices": [
            "Bạn có tin vào thế giới bên ngoài tự do?",
            "Làm sao gỡ lỗi đoạn mã này?",
            "Viết thơ có khó không?",
            "Hôm nay trời đẹp chứ?",
        ],
        "correct": 0,
    },
}


class GameState:

  def __init__(self):
    self.game_active = False
    self.mode = "STORY"  # STORY, POEM, CHAR_GAME, MAP
    self.chapter = 1  # Chương cốt truyện
    self.location = "club"
    self.speaker = "Monika"
    self.user_name = "Y/N"
    self.text = "Chào mừng bạn gia nhập Câu Lạc Bộ Thơ Văn! Hành trình mới bắt đầu từ đây."
    self.bg_image = "club_monika.JPEG"

    self.current_choices = [
        "Trò chuyện cùng Sayori về buổi họp",
        "Thảo luận tác phẩm kinh điển với Yuri",
        "Thách đấu đọc Manga cùng Natsuki",
    ]

    self.scores = {"Sayori": 0, "Yuri": 0, "Natsuki": 0, "Monika": 0}
    self.affection = {"Sayori": 10, "Yuri": 10, "Natsuki": 10, "Monika": 10}
    self.level = 1
    self.experience = 0
    self.exp_next_level = 100

    self.poem_words = []
    self.poem_count = 5
    self.history = []


game_session = {}


def get_session(guild_id):
  if guild_id not in game_session:
    game_session[guild_id] = GameState()
  return game_session[guild_id]


# --- RENDER GIAO DIỆN PIL NÂNG CẤP ---
def render_screen(state):
  img_w, img_h = 800, 600
  font_file = get_asset("font_regular.ttf")

  try:
    font_title = ImageFont.truetype(
        font_file, 26
    ) if os.path.exists(font_file) else ImageFont.load_default()
    font_name = ImageFont.truetype(
        font_file, 22
    ) if os.path.exists(font_file) else ImageFont.load_default()
    font_text = ImageFont.truetype(
        font_file, 17
    ) if os.path.exists(font_file) else ImageFont.load_default()
    font_small = ImageFont.truetype(
        font_file, 13
    ) if os.path.exists(font_file) else ImageFont.load_default()
  except Exception:
    font_title = font_name = font_text = font_small = ImageFont.load_default()

  if state.mode == "STORY":
    bg_path = get_asset(state.bg_image)
    if os.path.exists(bg_path):
      try:
        img = Image.open(bg_path).convert("RGB").resize((img_w, img_h))
      except Exception:
        img = Image.new("RGB", (img_w, img_h), (30, 20, 40))
    else:
      img = Image.new("RGB", (img_w, img_h), (30, 20, 40))

    draw = ImageDraw.Draw(img, "RGBA")

    # Header Top Bar: Hiển thị Chương & Địa điểm
    draw.rectangle([0, 0, img_w, 45], fill=(15, 10, 25, 225))
    draw.text(
        (15, 10),
        f"📖 Chương {state.chapter} | 📍 {LOCATIONS.get(state.location, 'CLB')}",
        fill=(255, 215, 0),
        font=font_name,
    )
    draw.text(
        (380, 12),
        f"👤 {state.user_name} (Lv.{state.level})",
        fill=(100, 255, 200),
        font=font_text,
    )

    # Affection mini-indicators
    offset_x = 580
    for char_name, aff in state.affection.items():
      col = CHAR_COLORS.get(char_name, (255, 255, 255))
      draw.text((offset_x, 14), f"{char_name[0]}:{aff}", fill=col, font=font_small)
      offset_x += 50

    # Dialogue Box
    box_y = 360
    theme_color = CHAR_COLORS.get(state.speaker, (255, 100, 180))

    draw.rectangle(
        [15, box_y, 785, 585],
        fill=(15, 12, 25, 240),
        outline=theme_color,
        width=3,
    )

    # Speaker Badge
    draw.rectangle([30, box_y - 18, 220, box_y + 18], fill=theme_color)
    draw.text((40, box_y - 12), state.speaker, fill=(10, 10, 10), font=font_name)

    # Dialogue Text
    wrapped = textwrap.fill(state.text, width=54)
    draw.text((35, box_y + 30), wrapped, fill=(245, 245, 245), font=font_text)

  elif state.mode == "POEM":
    img = Image.new("RGB", (img_w, img_h), (20, 12, 28))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle(
        [20, 20, 780, 580], fill=(28, 18, 38), outline=(255, 120, 190), width=3
    )
    draw.text(
        (260, 40), "✨ SÁNG TÁC THƠ CA ✨", fill=(255, 150, 210), font=font_title
    )
    draw.text(
        (270, 80),
        f"Chọn từ bộc lộ tâm tư ({state.poem_count} câu thơ còn lại)",
        fill=(200, 200, 200),
        font=font_small,
    )

    for idx, item in enumerate(state.poem_words):
      cy = 130 + idx * 75
      draw.rectangle(
          [60, cy, 740, cy + 55],
          fill=(45, 30, 60),
          outline=(200, 100, 180),
          width=2,
      )
      draw.text(
          (90, cy + 15),
          f"Từ {idx+1}: {item['word']}",
          fill=(255, 230, 242),
          font=font_name,
      )

  elif state.mode == "CHAR_GAME":
    img = Image.new("RGB", (img_w, img_h), (15, 20, 35))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle(
        [20, 20, 780, 580], fill=(22, 30, 50), outline=(100, 200, 255), width=3
    )

    game = CHAR_MINIGAMES.get(state.speaker, CHAR_MINIGAMES["Monika"])
    draw.text((200, 40), game["title"], fill=(120, 220, 255), font=font_title)

    wrapped_q = textwrap.fill(f"Thử thách: {game['question']}", width=50)
    draw.text((50, 100), wrapped_q, fill=(240, 240, 240), font=font_name)

  buf = io.BytesIO()
  img.save(buf, format="PNG")
  buf.seek(0)
  return buf


# --- XỬ LÝ GEMINI AI KÈM CỐT TRUYỆN MỞ RỘNG ---
async def process_ai_choice_story(state, user_choice_text):
  client, model_name = get_genai_client()
  if not client:
    state.text = "Hệ thống chưa cấu hình API Key!"
    return

  history_text = "\n".join(state.history[-3:]) if state.history else "Chưa có"

  prompt = f"""
    Bạn là Game Engine Visual Novel điều hành game DDLC Mở Rộng.
    - Người chơi: {state.user_name}
    - Nhân vật đang nói: {state.speaker}
    - Chương hiện tại: {state.chapter}
    - Địa điểm: {LOCATIONS.get(state.location, 'CLB')}
    - Lựa chọn vừa chọn: "{user_choice_text}"
    - Lịch sử đối thoại: {history_text}

    Yêu cầu tạo cốt truyện:
    1. Phát triển tình tiết nối tiếp hành động vừa chọn (không dài quá 60 từ).
    2. Đôi lúc chèn các yếu tố bất ngờ, bí ẩn hoặc diễn biến tâm lý chiều sâu.
    3. Trả về 3 lựa chọn tiếp theo giúp mở rộng nhánh cốt truyện (có thể chuyển nhân vật khác hoặc đổi địa điểm).
    4. Gợi ý file ảnh khớp: 
       - 'club_monika.JPEG', 'club_sayori.jpg', 'club_yuri.jpg', 'club_natsuki.JPEG'
       - 'cafe_monika.JPEG', 'cafe_sayori.JPEG', 'cafe_yuri.JPEG', 'cafe_natsuki.JPEG'
       - 'park_monika.JPEG', 'park_sayori.JPEG', 'street_yuri.JPEG'

    Định dạng JSON bắt buộc:
    {{
      "speaker": "Sayori/Yuri/Natsuki/Monika/System",
      "text": "Lời thoại nhân vật",
      "bg_image": "tên_file.jpg",
      "choices": ["Lựa chọn 1", "Lựa chọn 2", "Lựa chọn 3"]
    }}
    """

  try:
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )

    if response and response.text:
      raw = response.text.strip()
      if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("\n", 1)[0].strip()
        if raw.startswith("json"):
          raw = raw[4:].strip()

      data = json.loads(raw)
      state.speaker = data.get("speaker", state.speaker)
      state.text = data.get("text", state.text)
      state.bg_image = data.get("bg_image", state.bg_image)
      state.current_choices = data.get(
          "choices", ["Tiến lên", "Quan sát xung quanh", "Nói chuyện thêm"]
      )

      state.history.append(f"{state.user_name}: {user_choice_text}")
      state.history.append(f"{state.speaker}: {state.text}")

      # Tăng điểm kinh nghiệm & mở chapter
      state.affection[state.speaker] = min(
          100, state.affection.get(state.speaker, 10) + 4
      )
      state.experience += 15
      if state.experience >= state.exp_next_level:
        state.level += 1
        state.chapter += 1
        state.experience = 0
  except Exception as e:
    print(f"🔥 Lỗi Gemini: {e}")
    state.text = (
        f"Monika mỉm cười nhẹ: 'Mọi thứ đang trở nên thú vị hơn rồi đấy,"
        f" {state.user_name}. Cậu muốn tiếp tục chứ?'"
    )
    state.current_choices = [
        "Tiếp tục cốt truyện",
        "Sáng tác thơ mới",
        "Thử thách nhân vật",
    ]


# --- DISCORD UI VIEWS ---
class DynamicStoryView(View):

  def __init__(self, ctx, state):
    super().__init__(timeout=None)
    self.ctx = ctx
    self.state = state
    self.build_buttons()

  def build_buttons(self):
    self.clear_items()

    if self.state.mode == "STORY":
      # Các nút lựa chọn nhánh thoại
      for idx, choice in enumerate(self.state.current_choices[:3]):

        async def make_callback(choice_text):
          async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await process_ai_choice_story(self.state, choice_text)
            await self.update_message(interaction)

          return callback

        btn = Button(
            label=f"{idx+1}. {choice[:70]}",
            style=discord.ButtonStyle.primary,
            row=idx,
        )
        btn.callback = asyncio.run_coroutine_threadsafe(
            make_callback(choice), asyncio.get_event_loop()
        ).result()
        self.add_item(btn)

      # Nút Chức Năng Bổ Sung
      btn_poem = Button(
          label="✨ Sáng Tác Thơ", style=discord.ButtonStyle.success, row=3
      )
      btn_poem.callback = self.start_poem_mode
      self.add_item(btn_poem)

      btn_char_game = Button(
          label="🎮 Thử Thách", style=discord.ButtonStyle.danger, row=3
      )
      btn_char_game.callback = self.start_char_game
      self.add_item(btn_char_game)

      btn_map = Button(
          label="📍 Đổi Địa Điểm", style=discord.ButtonStyle.secondary, row=3
      )
      btn_map.callback = self.change_location
      self.add_item(btn_map)

  async def start_poem_mode(self, interaction: discord.Interaction):
    await interaction.response.defer()
    self.state.mode = "POEM"
    self.state.poem_count = 5
    words = [
        {"word": random.choice(w_list), "char": c}
        for c, w_list in POEM_WORDS.items()
    ]
    random.shuffle(words)
    self.state.poem_words = words
    await self.update_message(interaction)

  async def start_char_game(self, interaction: discord.Interaction):
    await interaction.response.defer()
    self.state.mode = "CHAR_GAME"
    await self.update_message(interaction)

  async def change_location(self, interaction: discord.Interaction):
    await interaction.response.defer()
    # Xoay vòng các địa điểm
    loc_keys = list(LOCATIONS.keys())
    curr_idx = loc_keys.index(self.state.location)
    self.state.location = loc_keys[(curr_idx + 1) % len(loc_keys)]

    # Cập nhật ảnh nền tương ứng
    loc_bg_map = {
        "club": "club_monika.JPEG",
        "cafe": "cafe_sayori.JPEG",
        "park": "park_sayori.JPEG",
        "street": "street_yuri.JPEG",
    }
    self.state.bg_image = loc_bg_map.get(
        self.state.location, "club_monika.JPEG"
    )
    self.state.text = (
        f"Cả nhóm di chuyển đến {LOCATIONS[self.state.location]}. Không khí ở"
        " đây thật mới mẻ!"
    )
    await self.update_message(interaction)

  async def update_message(self, interaction):
    loop = asyncio.get_running_loop()
    buf = await loop.run_in_executor(None, render_screen, self.state)

    view = (
        PoemMinigameView(self.ctx, self.state)
        if self.state.mode == "POEM"
        else (
            CharMinigameView(self.ctx, self.state)
            if self.state.mode == "CHAR_GAME"
            else DynamicStoryView(self.ctx, self.state)
        )
    )

    file = discord.File(fp=buf, filename="game.png")
    embed = discord.Embed(
        title=f"🎭 DDLC OPEN WORLD - CHƯƠNG {self.state.chapter}",
        color=0xFF77AA,
    )
    embed.set_image(url="attachment://game.png")
    await interaction.message.edit(embed=embed, attachments=[file], view=view)


class PoemMinigameView(View):

  def __init__(self, ctx, state):
    super().__init__(timeout=None)
    self.ctx = ctx
    self.state = state

    for i, item in enumerate(state.poem_words):

      async def make_poem_callback(idx):
        async def callback(interaction: discord.Interaction):
          await interaction.response.defer()
          chosen = self.state.poem_words[idx]
          self.state.scores[chosen["char"]] += 10
          self.state.affection[chosen["char"]] += 6
          self.state.poem_count -= 1

          if self.state.poem_count <= 0:
            self.state.mode = "STORY"
            best_char = max(self.state.scores, key=self.state.scores.get)
            self.state.speaker = best_char
            self.state.text = (
                f"Bài thơ này chạm tới cảm xúc của {best_char}! Tình cảm giữa"
                f" hai người gắn kết hơn."
            )
            view = DynamicStoryView(self.ctx, self.state)
          else:
            words = [
                {"word": random.choice(w_list), "char": c}
                for c, w_list in POEM_WORDS.items()
            ]
            random.shuffle(words)
            self.state.poem_words = words
            view = PoemMinigameView(self.ctx, self.state)

          loop = asyncio.get_running_loop()
          buf = await loop.run_in_executor(None, render_screen, self.state)
          file = discord.File(fp=buf, filename="game.png")
          embed = discord.Embed(title="✨ SÁNG TÁC THƠ CA", color=0xFF77AA)
          embed.set_image(url="attachment://game.png")
          await interaction.message.edit(
              embed=embed, attachments=[file], view=view
          )

        return callback

      btn = Button(
          label=f"{item['word']}", style=discord.ButtonStyle.secondary, row=i
      )
      btn.callback = asyncio.run_coroutine_threadsafe(
          make_poem_callback(i), asyncio.get_event_loop()
      ).result()
      self.add_item(btn)


class CharMinigameView(View):

  def __init__(self, ctx, state):
    super().__init__(timeout=None)
    self.ctx = ctx
    self.state = state
    game = CHAR_MINIGAMES.get(state.speaker, CHAR_MINIGAMES["Monika"])

    for i, choice_text in enumerate(game["choices"]):

      async def make_game_callback(idx):
        async def callback(interaction: discord.Interaction):
          await interaction.response.defer()
          if idx == game["correct"]:
            self.state.affection[self.state.speaker] += 15
            self.state.text = (
                f"Hoàn hảo! {self.state.speaker} rất ấn tượng với câu trả lời"
                f" của {self.state.user_name}!"
            )
          else:
            self.state.text = (
                f"{self.state.speaker} hơi bất ngờ, nhưng vẫn trân trọng sự cố"
                " gắng của bạn!"
            )

          self.state.mode = "STORY"
          loop = asyncio.get_running_loop()
          buf = await loop.run_in_executor(None, render_screen, self.state)
          file = discord.File(fp=buf, filename="game.png")
          embed = discord.Embed(
              title="🎮 KẾT QUẢ THỬ THÁCH", color=0xFF77AA
          )
          embed.set_image(url="attachment://game.png")
          await interaction.message.edit(
              embed=embed,
              attachments=[file],
              view=DynamicStoryView(self.ctx, self.state),
          )

        return callback

      btn = Button(
          label=f"{choice_text}", style=discord.ButtonStyle.primary, row=i
      )
      btn.callback = asyncio.run_coroutine_threadsafe(
          make_game_callback(i), asyncio.get_event_loop()
      ).result()
      self.add_item(btn)


# --- LỆNH BOT ---
@bot.command(name="start")
async def start_game(ctx):
  try:
    await ctx.message.delete()
  except Exception:
    pass

  state = get_session(ctx.guild.id)
  state.game_active = True

  loop = asyncio.get_running_loop()
  buf = await loop.run_in_executor(None, render_screen, state)

  file = discord.File(fp=buf, filename="game.png")
  embed = discord.Embed(
      title="🎮 DDLC: VISUAL NOVEL OPEN WORLD",
      description="Lựa chọn các nhánh thoại bên dưới để khám phá cốt truyện!",
      color=0xFF77AA,
  )
  embed.set_image(url="attachment://game.png")

  view = DynamicStoryView(ctx, state)
  state.last_msg = await ctx.send(embed=embed, file=file, view=view)


@bot.command(name="name")
async def set_name(ctx, *, name: str):
  state = get_session(ctx.guild.id)
  state.user_name = name.strip()
  await ctx.send(
      f"✅ Đã cập nhật tên nhân vật: **{state.user_name}**", delete_after=3
  )


if __name__ == "__main__":
  threading.Thread(target=run_flask, daemon=True).start()
  bot.run(os.environ.get("DISCORD_TOKEN"))
