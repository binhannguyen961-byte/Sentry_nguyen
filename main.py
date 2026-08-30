import asyncio
import os
import random
import threading
import discord
from discord.ext import commands
from flask import Flask
from google import genai
from google.genai import types

# ================= 1. CẤU HÌNH WEB SERVER (FLASK) =================
app = Flask(__name__)


@app.route("/")
def home():
  return "War Thunder Advanced Co-op Bot is operational..."


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  server_thread = threading.Thread(target=run_flask)
  server_thread.daemon = True
  server_thread.start()


# ================= 2. CẤU HÌNH BOT & GEMINI =================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

coop_sessions = {}

DAMAGE_CALCULATOR_PROMPT = (
    "Bạn là hệ thống tính toán sát thương (Damage Engine) chiến trường hiện đại. "
    "Dựa vào vũ khí, góc ngắm và trạng thái cơ động, hãy đưa ra sát thương % chính xác "
    "và một dòng thông báo kỹ thuật quân sự sắc lạnh. "
    "Cấu trúc trả lời bắt buộc: [SỐ_%_SÁT_THƯƠNG]|[THÔNG_BÁO_KỸ_THUẬT]. "
    "Ví dụ: 40|Trúng nóc xe thiết giáp qua dẫn đường ATGM, phá hủy cấu trúc -40% HP."
)

# ================= 3. QUẢN LÝ PHIÊN CO-OP (TANK & HELI) =================


class CoOpSession:

  def __init__(self, members, mode_type, sub_mode=3, faction="Nga", heli_model="Ka-50"):
    self.members = members
    self.mode_type = mode_type  # "tank" hoặc "heli"
    self.sub_mode = sub_mode  # 3 hoặc 4 (cho tank), 1 hoặc 2 (cho heli)
    self.faction = faction
    self.heli_model = heli_model

    if mode_type == "tank":
      self.team = "Nga (T-90M)" if sub_mode == 3 else "NATO / Uka (M1A3 Abrams)"
      self.commander = members[0]
      self.driver = members[1]
      self.gunner = members[2]
      self.loader = members[3] if sub_mode == 4 else None
    else:
      if sub_mode == 1:
        self.solo_player = members[0]
        self.pilot = members[0]
        self.gunner_cmd = members[0]
        self.current_view = "pilot"
      else:
        self.pilot = members[0]
        self.gunner_cmd = members[1]

      self.team = f"Phe {faction} ({heli_model})"

    self.hp = 100
    self.enemy_hp = 100
    self.turret_angle = 12
    self.current_ammo = "APFSDS" if mode_type == "tank" else "ATGM / Hellfire"
    self.loader_cooldown = 0
    self.driver_pos = "Tuyến đầu (Đứng yên)"
    self.radar_locked = False
    self.lock_target_info = "Chưa khóa mục tiêu"
    self.under_sam_attack = False
    self.sam_warning_msg = "Bầu trời an toàn."
    self.last_log = "Kíp chiến đấu đã vào vị trí sẵn sàng!"

    self.has_radar = True
    if heli_model in ["Ka-50", "Mi-24 SuperHind"]:
      self.has_radar = False
      self.lock_target_info = "Khí tài không trang bị Radar (Ngắm thủ công)"


# ================= 4. GIAO DIỆN TANK =================


class CommanderCaroView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop
    for r in range(3):
      for c in range(3):
        btn = discord.ui.Button(
            label=f"[{r+1},{c+1}]", style=discord.ButtonStyle.secondary, row=r
        )
        btn.callback = self.make_cb(r, c)
        self.add_item(btn)

  def make_cb(self, r, c):
    async def cb(interaction: discord.Interaction):
      if interaction.user != self.coop.commander:
        return await interaction.response.send_message(
            "⚠️ Chỉ Sĩ quan Chỉ huy mới dùng bảng này!", ephemeral=True
        )
      hour = random.choice([1, 2, 3, 9, 10, 11, 12])
      self.coop.last_log = (
          f"🎯 Chỉ huy phát hiện địch ở ô [{r+1},{c+1}]! Hướng tháp pháo:"
          f" **{hour}H**."
      )
      await interaction.response.send_message(
          f"✅ Phát hiện mục tiêu tại ô [{r+1},{c+1}]! Hướng tháp pháo: **{hour}"
          " giờ**.",
          ephemeral=True,
      )

    return cb


class DriverControlView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

  async def move(self, interaction: discord.Interaction, pos):
    if interaction.user != self.coop.driver:
      return await interaction.response.send_message(
          "⚠️ Chỉ Lái xe mới điều khiển hướng!", ephemeral=True
      )
    self.coop.driver_pos = pos
    self.coop.last_log = f"⚙️ Lái xe cơ động: {pos}"
    await interaction.response.send_message(
        f"🏎️ Đã đổi vị trí thành: **{pos}**", ephemeral=True
    )

  @discord.ui.button(
      label="⬆️ Tiến thẳng", style=discord.ButtonStyle.success, row=0
  )
  async def ts(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move(interaction, "Tiến thẳng tuyến đầu")

  @discord.ui.button(
      label="↗️ Tiến phải", style=discord.ButtonStyle.success, row=0
  )
  async def tr(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move(interaction, "Tiến chếch phải")

  @discord.ui.button(label="⬇️ Lùi ẩn nấp", style=discord.ButtonStyle.danger, row=1)
  async def bs(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move(interaction, "Lùi về sau gờ đất")


# ================= 5. GIAO DIỆN TRỰC THĂNG =================


class HeliPilotView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

  async def move_heli(self, interaction: discord.Interaction, pos):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.pilot
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Chỉ Phi công mới điều khiển chuyến bay!", ephemeral=True
      )

    if self.coop.under_sam_attack and pos in [
        "Lách né trái gấp",
        "Lách né phải gấp",
    ]:
      self.coop.under_sam_attack = False
      self.coop.sam_warning_msg = "Đã né thành công tên lửa phòng không!"
      self.coop.last_log = (
          f"🛡️ Phi công thực hiện thao tác **{pos}** né thành công SAM!"
      )
      return await interaction.response.send_message(
          f"🎯 **XUẤT SẮC!** Bạn đã thực hiện **{pos}** kịp thời và cắt đuôi"
          " thành công tên lửa phòng không địch!",
          ephemeral=False,
      )

    self.coop.driver_pos = pos
    self.coop.last_log = f"🚁 Phi công cơ động: {pos}"
    await interaction.response.send_message(
        f"🛫 Trạng thái bay: **{pos}**", ephemeral=True
    )

  @discord.ui.button(
      label="🔥 THẢ FLARE (Chống SAM)",
      style=discord.ButtonStyle.success,
      row=0,
  )
  async def flare(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.pilot
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Chỉ Phi công mới được thả mồi bẫy Flare!", ephemeral=True
      )

    if self.coop.under_sam_attack:
      self.coop.under_sam_attack = False
      self.coop.sam_warning_msg = "Đã đánh lừa tên lửa bằng Flare!"
      self.coop.last_log = "🔥 Thả Flare thành công, đánh lạc hướng tên lửa!"
      await interaction.response.send_message(
          "🔥 **FLARE DEPLOYED!** Mồi bẫy nhiệt đã đánh lừa hoàn toàn tên lửa"
          " phòng không địch. Trực thăng an toàn tuyệt đối!",
          ephemeral=False,
      )
    else:
      await interaction.response.send_message(
          "✨ Đã thả Flare (Khu vực hiện tại không có tên lửa đe dọa).",
          ephemeral=True,
      )

  @discord.ui.button(
      label="⬅️ Lách trái né SAM", style=discord.ButtonStyle.primary, row=1
  )
  async def dodge_left(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move_heli(interaction, "Lách né trái gấp")

  @discord.ui.button(
      label="➡️ Lách phải né SAM", style=discord.ButtonStyle.primary, row=1
  )
  async def dodge_right(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move_heli(interaction, "Lách né phải gấp")

  @discord.ui.button(
      label="⬇️ Lùi thẳng (Rút lui)", style=discord.ButtonStyle.danger, row=2
  )
  async def bwd_straight(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move_heli(interaction, "Lùi thẳng né phòng không")

  @discord.ui.button(
      label="🛑 Treo lơ lửng (Hover)", style=discord.ButtonStyle.secondary, row=2
  )
  async def hover(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move_heli(interaction, "Treo lơ lửng (Hover ngắm bắn)")


class HeliGunnerCommanderView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

  @discord.ui.button(
      label="📡 Quét Radar (Lock-on)", style=discord.ButtonStyle.primary, row=0
  )
  async def scan_radar(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.gunner_cmd
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Bạn không có quyền sử dụng giao diện này!", ephemeral=True
      )

    if not self.coop.has_radar:
      return await interaction.response.send_message(
          f"⚠️ Khí tài **{self.coop.heli_model}** không được trang bị hệ thống Radar! Bạn bắt buộc phải ngắm bắn thủ công.",
          ephemeral=True,
      )

    found = random.choice([True, True, False])
    if found:
      target_hour = random.choice([12, 1, 2, 10, 11])
      dist = random.randint(2, 6)
      self.coop.radar_locked = True
      self.coop.lock_target_info = (
          f"Đã khóa mục tiêu hướng **{target_hour}H** (Cự ly {dist}km)"
      )

      if random.random() < 0.4:
        self.coop.under_sam_attack = True
        self.coop.sam_warning_msg = (
            "⚠️ BÁO ĐỘNG: Địch phóng tên lửa phòng không (SAM) tới trực thăng!"
        )
        msg = f"🎯 **RADAR LOCKED!** Thấy mục tiêu ở {target_hour}H.\n🚨 **CẢNH BÁO ĐỎ:** Địch đã phát hiện sóng radar và **phóng tên lửa phòng không** lên trực thăng! **Báo ngay cho Phi công thả Flare hoặc Lách né ngay lập tức!**"
      else:
        msg = f"🎯 **RADAR LOCKED!** Phát hiện mục tiêu ở **{target_hour} giờ**, cự ly **{dist}km**. Đã đồng bộ đường đạn!"
    else:
      self.coop.radar_locked = False
      self.coop.lock_target_info = "Không có mục tiêu trong tầm quét"
      msg = "🔍 Radar quét không tìm thấy tín hiệu điện từ nào."

    await interaction.response.send_message(msg, ephemeral=True)

  @discord.ui.button(
      label="🔄 Xoay góc ngắm (+1h)", style=discord.ButtonStyle.secondary, row=0
  )
  async def rotate_sight(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.gunner_cmd
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Bạn không có quyền chỉnh góc ngắm!", ephemeral=True
      )
    self.coop.turret_angle = (self.coop.turret_angle % 12) + 1
    await interaction.response.send_message(
        f"🔄 Đã xoay ống ngắm quang học sang hướng **{self.coop.turret_angle}"
        " giờ**.",
        ephemeral=True,
    )

  @discord.ui.button(
      label="🚀 KHAI HỎA ATGM / RỐC-KÉT",
      style=discord.ButtonStyle.danger,
      row=1,
  )
  async def fire_heli(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.gunner_cmd
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Bạn không có quyền khai hỏa vũ khí!", ephemeral=True
      )

    await interaction.response.defer(thinking=True)

    if random.random() < 0.5:
      self.coop.under_sam_attack = True
      self.coop.sam_warning_msg = (
          "⚠️ BÁO ĐỘNG: Vừa phóng đạn, hệ thống phòng không địch đã khóa và phản"
          " công tên lửa!"
      )

    radar_bonus = (
        " (Có khóa mục tiêu Radar - Độ chính xác tối đa)"
        if self.coop.radar_locked
        else " (Bắn mù không có Radar lock / Không có Radar)"
    )
    prompt = (
        f"Vũ khí: {self.coop.current_ammo}. Trạng thái bay: {self.coop.driver_pos}."
        f" Tình trạng radar: {self.coop.lock_target_info}{radar_bonus}. "
        "Tính toán sát thương % gây lên mục tiêu mặt đất."
    )

    damage_dealt = 35 if self.coop.radar_locked else 20
    tech_msg = "Tên lửa dẫn đường lao thẳng vào mục tiêu."

    try:
      response = ai_client.models.generate_content(
          model="gemini-2.5-flash",
          contents=prompt,
          config=types.GenerateContentConfig(
              system_instruction=DAMAGE_CALCULATOR_PROMPT
          ),
      )
      if response and response.text:
        parts = response.text.strip().split("|")
        if len(parts) == 2:
          damage_dealt = int("".join(filter(str.isdigit, parts[0])))
          tech_msg = parts[1].strip()
    except Exception:
      pass

    self.coop.enemy_hp = max(0, self.coop.enemy_hp - damage_dealt)
    self.coop.radar_locked = False

    sam_hit_dmg = 0
    if self.coop.under_sam_attack:
      sam_hit_dmg = random.randint(25, 45)
      self.coop.hp = max(0, self.coop.hp - sam_hit_dmg)
      self.coop.under_sam_attack = False
      self.coop.sam_warning_msg = (
          f"💥 Trực thăng trúng tên lửa phòng không gây -{sam_hit_dmg}% HP!"
      )

    embed = discord.Embed(
        title=f"🚁 KẾT QUẢ KHAI HỎA TRỰC THĂNG ({self.coop.heli_model})",
        description=(
            f"🎯 **Tình trạng Khí tài:** `{self.coop.lock_target_info}`\n"
            f"📝 **Phân tích chiến trường:** *{tech_msg}*\n\n"
            f"💥 **Sát thương ATGM:** `-{damage_dealt}% HP`\n"
            f"🎯 **HP Mục tiêu mặt đất:** **{self.coop.enemy_hp}%**\n"
            + (
                f"\n🚨 **{self.coop.sam_warning_msg}**\n❤️ **HP Trực thăng:**"
                f" **{self.coop.hp}%**"
                if sam_hit_dmg > 0
                else "\n🛡️ *Không có tên lửa phòng không trúng đích.*"
            )
        ),
        color=discord.Color.red()
        if self.coop.enemy_hp <= 0
        else discord.Color.blurple(),
    )
    await interaction.followup.send(embed=embed)


# ================= 6. GIAO DIỆN PHÁO THỦ TANK =================


class GunnerControlView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

  @discord.ui.button(
      label="🔄 Xoay tháp (+1h)", style=discord.ButtonStyle.primary, row=0
  )
  async def rotate(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.user != self.coop.gunner:
      return await interaction.response.send_message(
          "⚠️ Chỉ Pháo thủ mới xoay tháp pháo!", ephemeral=True
      )
    self.coop.turret_angle = (self.coop.turret_angle % 12) + 1
    await interaction.response.send_message(
        f"🔄 Tháp pháo chuyển sang hướng **{self.coop.turret_angle} giờ**.",
        ephemeral=True,
    )

  @discord.ui.button(
      label="💥 KHAI HỎA TANK!", style=discord.ButtonStyle.danger, row=1
  )
  async def fire(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.user != self.coop.gunner:
      return await interaction.response.send_message(
          "⚠️ Chỉ Pháo thủ mới được bấm khai hỏa!", ephemeral=True
      )
    if self.coop.loader_cooldown > 0 and self.coop.sub_mode == 4:
      return await interaction.response.send_message(
          f"⏳ Đang nạp đạn! Chờ còn **{self.coop.loader_cooldown} giây**.",
          ephemeral=True,
      )

    await interaction.response.defer(thinking=True)
    prompt = (
        f"Loại đạn: {self.coop.current_ammo}. Góc tháp pháo: {self.coop.turret_angle}H."
        f" Vị trí lái: {self.coop.driver_pos}. Tính toán sát thương % lên xe địch."
    )
    damage_dealt = 25
    tech_msg = "Xuyên giáp mục tiêu."
    try:
      response = ai_client.models.generate_content(
          model="gemini-2.5-flash",
          contents=prompt,
          config=types.GenerateContentConfig(
              system_instruction=DAMAGE_CALCULATOR_PROMPT
          ),
      )
      if response and response.text:
        parts = response.text.strip().split("|")
        if len(parts) == 2:
          damage_dealt = int("".join(filter(str.isdigit, parts[0])))
          tech_msg = parts[1].strip()
    except Exception:
      pass

    self.coop.enemy_hp = max(0, self.coop.enemy_hp - damage_dealt)
    enemy_dmg = (
        random.randint(10, 30) if self.coop.enemy_hp > 0 else 0
    )
    self.coop.hp = max(0, self.coop.hp - enemy_dmg)

    embed = discord.Embed(
        title="🎯 KẾT QUẢ KHAI HỎA TANK (DAMAGE ENGINE)",
        description=(
            f"📦 **Đạn:** `{self.coop.current_ammo}` | 🔄 **Góc:**"
            f" `{self.coop.turret_angle}H`\n"
            f"📝 **Phân tích:** *{tech_msg}*\n\n"
            f"💥 **Sát thương:** `-{damage_dealt}% HP` | 🎯 **Địch còn:**"
            f" **{self.coop.enemy_hp}%**"
        ),
        color=discord.Color.red()
        if self.coop.enemy_hp <= 0
        else discord.Color.orange(),
    )
    await interaction.followup.send(embed=embed)


class LoaderControlView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

  async def ammo(self, interaction: discord.Interaction, t):
    if interaction.user != self.coop.loader:
      return await interaction.response.send_message(
          "⚠️ Chỉ Nạp đạn viên mới chọn loại đạn!", ephemeral=True
      )
    if self.coop.loader_cooldown > 0:
      return await interaction.response.send_message(
          f"⏳ Đang nạp ({self.coop.loader_cooldown}s)!", ephemeral=True
      )
    self.coop.current_ammo = t
    self.coop.loader_cooldown = 8
    await interaction.response.send_message(
        f"✅ Đã nạp đạn **{t}**. Sẵn sàng!", ephemeral=True
    )

    async def cd():
      await asyncio.sleep(8)
      self.coop.loader_cooldown = 0

    asyncio.create_task(cd())

  @discord.ui.button(label="📦 APFSDS", style=discord.ButtonStyle.primary)
  async def a1(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.ammo(interaction, "APFSDS")

  @discord.ui.button(label="🔥 HEAT", style=discord.ButtonStyle.danger)
  async def a2(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.ammo(interaction, "HEAT")

  @discord.ui.button(label="💣 HE", style=discord.ButtonStyle.secondary)
  async def a3(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.ammo(interaction, "HE")


# ================= 7. LỆNH HƯỚNG DẪN (!Chelps) =================


@bot.command(name="Chelps")
async def chelps_cmd(ctx):
  embed = discord.Embed(
      title="📖 BẢNG HƯỚNG DẪN CHIẾN TRƯỜNG TOÀN DIỆN",
      description="Hướng dẫn chi tiết kíp lái Xe tăng và Trực thăng các phe:",
      color=discord.Color.blue(),
  )

  embed.add_field(
      name="🛡️ 1. CHẾ ĐỘ XE TĂNG",
      value="• **Lệnh:** `!tank-coop @LáiXe @PháoThủ [@NạpĐạn]`",
      inline=False,
  )

  embed.add_field(
      name="🚁 2. CHẾ ĐỘ TRỰC THĂNG (2 PHÊ & SOLO MODE)",
      value=(
          "• **Lệnh 2 người:** `!heli-coop [Mỹ/Nga] [TênHeli] @Pilot @Gunner`\n"
          "• **Lệnh Solo 1 người:** `!heli-coop Nga Ka-50`\n"
          "  - Chuyển góc nhìn Pilot: **`!Pv`** hoặc **`!Pview`**\n"
          "  - Chuyển góc nhìn Gunner: **`!Gv`** hoặc **`!Gview`**"
      ),
      inline=False,
  )

  await ctx.send(embed=embed)


# ================= 8. LỆNH KHỞI TẠO PHÒNG =================


@bot.command(name="tank-coop")
async def tank_coop_cmd(
    ctx,
    m1: discord.Member,
    m2: discord.Member,
    m3: discord.Member = None,
    m4: discord.Member = None,
):
  if m3 is not None and m4 is not None:
    members = [ctx.author, m1, m2, m3]
    mode = 4
  elif m3 is not None:
    members = [ctx.author, m1, m2, m3]
    mode = 4
  else:
    members = [ctx.author, m1, m2]
    mode = 3

  coop = CoOpSession(members, "tank", mode)
  coop_sessions[ctx.channel.id] = coop

  embed = discord.Embed(
      title=f"🛡️ KÍP TANK CO-OP ({mode} THÀNH VIÊN - {coop.team})",
      description=(
          f"👑 **Chỉ huy:** {coop.commander.mention}\n"
          f"🏎️ **Lái xe:** {coop.driver.mention}\n"
          f"🎯 **Pháo thủ:** {coop.gunner.mention}\n"
          + (f"📦 **Nạp đạn:** {coop.loader.mention}\n" if mode == 4 and coop.loader else "")
          + "\n👉 Gõ **`!start`** để xuất kích!"
      ),
      color=discord.Color.blue(),
  )
  await ctx.send(embed=embed)


@bot.command(name="heli-coop")
async def heli_coop_cmd(
    ctx, faction: str, heli_model: str, m1: discord.Member = None, m2: discord.Member = None
):
  if m1 is None:
    sub_mode = 1
    members = [ctx.author]
    team_desc = f"Solo Trực thăng {faction} ({heli_model})"
  else:
    sub_mode = 2
    members = [m1, m2 if m2 else ctx.author]
    team_desc = f"Co-op 2 người {faction} ({heli_model})"

  coop = CoOpSession(members, "heli", sub_mode, faction, heli_model)
  coop_sessions[ctx.channel.id] = coop

  if sub_mode == 1:
    desc = (
        f"👤 **Người điều khiển:** {ctx.author.mention}\n"
        f"🚁 **Khí tài:** `{faction} - {heli_model}`\n"
        f"📡 **Trang bị Radar:** `{'Có' if coop.has_radar else 'Không'}`\n\n"
        "🕹️ **Đổi góc nhìn linh hoạt:**\n"
        "• Gõ **`!Pv`** hoặc **`!Pview`** sang Phi công.\n"
        "• Gõ **`!Gv`** hoặc **`!Gview`** sang Xạ thủ.\n\n"
        "👉 Gõ **`!start`** để cất cánh!"
    )
  else:
    desc = (
        f"🛫 **Phi công:** {m1.mention}\n"
        f"🎯 **Xạ thủ:** {m2.mention if m2 else ctx.author.mention}\n"
        f"🚁 **Khí tài:** `{faction} - {heli_model}`\n\n"
        "👉 Gõ **`!start`** để chiến đấu!"
    )

  embed = discord.Embed(
      title=f"🚁 TRỰC THĂNG CHIẾN ĐẤU: {team_desc.upper()}",
      description=desc,
      color=discord.Color.dark_purple(),
  )
  await ctx.send(embed=embed)


# ================= 9. LỆNH ĐỔI GÓC NHÌN SOLO (!Pv / !Gv) =================


@bot.command(name="Pv")
async def pview_alias(ctx):
  await switch_view_handler(ctx, "pilot")


@bot.command(name="Pview")
async def pview_full(ctx):
  await switch_view_handler(ctx, "pilot")


@bot.command(name="Gv")
async def gview_alias(ctx):
  await switch_view_handler(ctx, "gunner")


@bot.command(name="Gview")
async def gview_full(ctx):
  await switch_view_handler(ctx, "gunner")


async def switch_view_handler(ctx, view_type):
  if ctx.channel.id not in coop_sessions:
    return await ctx.send("⚠️ Không có phiên chiến đấu nào đang hoạt động ở kênh này.")
  coop = coop_sessions[ctx.channel.id]
  if coop.mode_type != "heli" or coop.sub_mode != 1:
    return await ctx.send("⚠️ Lệnh này chỉ dành riêng cho chế độ Trực thăng Solo 1 người!")

  coop.current_view = view_type
  if view_type == "pilot":
    embed = discord.Embed(
        title="🛫 ĐÃ CHUYỂN SANG GÓC NHÌN PHI CÔNG (PILOT VIEW)",
        description="Bạn đang nắm quyền điều khiển hướng bay, thả Flare và né tránh SAM.",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed, view=HeliPilotView(coop))
  else:
    embed = discord.Embed(
        title="🎯 ĐÃ CHUYỂN SANG GÓC NHÌN XẠ THỦ (GUNNER VIEW)",
        description=f"Bạn đang ngồi ghế xạ thủ. Khí tài: `{coop.heli_model}` | Radar: `{'Có' if coop.has_radar else 'Không'}`.",
        color=discord.Color.orange(),
    )
    await ctx.send(embed=embed, view=HeliGunnerCommanderView(coop))


@bot.command(name="start")
async def start_cmd(ctx):
  if ctx.channel.id not in coop_sessions:
    return await ctx.send("⚠️ Chưa có phiên chiến dịch! Gõ lệnh khởi tạo trước.")
  coop = coop_sessions[ctx.channel.id]

  if coop.mode_type == "tank":
    embed = discord.Embed(
        title=f"🚀 TANK KHÍ TÀI: {coop.team.upper()}",
        description=(
            f"❤️ HP Xe: **{coop.hp}%** | 🎯 HP Địch: **{coop.enemy_hp}%**\n"
            f"⚙️ Vị trí: `{coop.driver_pos}` | 📦 Đạn: `{coop.current_ammo}`\n"
            f"🔄 Tháp pháo: `{coop.turret_angle}H`\n\n"
            f"📌 **Trạng thái:** *{coop.last_log}*"
        ),
        color=discord.Color.green(),
    )
    await ctx.send(
        "👑 **[COMMANDER] Bảng trinh sát caro:**",
        embed=embed,
        view=CommanderCaroView(coop),
    )
    await ctx.send(
        "🏎️ **[DRIVER] Bảng điều khiển hướng lái:**",
        view=DriverControlView(coop),
    )
    await ctx.send(
        "🎯 **[GUNNER] Giao diện ngắm bắn FCS:**", view=GunnerControlView(coop),
    )
    if coop.sub_mode == 4 and coop.loader:
      await ctx.send(
          "📦 **[LOADER] Kho đạn (Cooldown 8s):**",
          view=LoaderControlView(coop),
      )
  else:
    embed = discord.Embed(
        title=f"🚁 TRỰC THĂNG KHÍ TÀI: {coop.team.upper()}",
        description=(
            f"❤️ HP Trực thăng: **{coop.hp}%** | 🎯 HP Mục tiêu: **{coop.enemy_hp}%**\n"
            f"🛫 Trạng thái bay: `{coop.driver_pos}` | 📡 Radar:"
            f" `{coop.lock_target_info}`\n"
            f"🚨 **Tình trạng SAM:** `{coop.sam_warning_msg}`\n\n"
            f"📌 **Trạng thái:** *{coop.last_log}*"
        ),
        color=discord.Color.gold(),
    )
    if coop.sub_mode == 1:
      await ctx.send(
          f"🕹️ **Đang ở góc nhìn:** `{'PHI CÔNG (Pilot)' if coop.current_view=='pilot' else 'XẠ THỦ (Gunner)'}`\n*(Dùng lệnh `!Pv` hoặc `!Gv` để chuyển đổi)*",
          embed=embed,
          view=HeliPilotView(coop)
          if coop.current_view == "pilot"
          else HeliGunnerCommanderView(coop),
      )
    else:
      await ctx.send(
          "🛫 **[PILOT] Bảng điều khiển chuyến bay:**",
          embed=embed,
          view=HeliPilotView(coop),
      )
      await ctx.send(
          "🎯 **[GUNNER] Màn hình Radar & Ngắm bắn:**",
          view=HeliGunnerCommanderView(coop),
      )


@bot.event
async def on_message(message):
  if message.author == bot.user:
    return
  await bot.process_commands(message)


@bot.event
async def on_ready():
  print(f"✅ Bot All-in-One sẵn sàng: {bot.user.name}")


if __name__ == "__main__":
  keep_alive()
  bot.run(DISCORD_TOKEN)
