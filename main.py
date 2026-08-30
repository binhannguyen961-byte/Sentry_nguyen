import asyncio
import os
import random
import threading
import discord
from discord.ext import commands
from flask import Flask
from google import genai
from google.genai import types

# ================= 1. WEB SERVER (FLASK) =================
app = Flask(__name__)


@app.route("/")
def home():
  return "War Thunder Advanced Co-op Bot Operational..."


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  server_thread = threading.Thread(target=run_flask)
  server_thread.daemon = True
  server_thread.start()


# ================= 2. BOT & GEMINI CONFIG =================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
coop_sessions = {}

DAMAGE_CALCULATOR_PROMPT = (
    "Bạn là hệ thống tính toán sát thương (Damage Engine) chiến trường hiện"
    " đại. Dựa vào vũ khí, góc ngắm và trạng thái cơ động, hãy đưa ra sát"
    " thương % chính xác và một dòng thông báo kỹ thuật quân sự sắc lạnh. Cấu"
    " trúc trả lời bắt buộc: [SỐ_%_SÁT_THƯƠNG]|[THÔNG_BÁO_KỸ_THUẬT]. Ví dụ:"
    " 40|Trúng nóc xe thiết giáp qua dẫn đường ATGM, phá hủy cấu trúc -40% HP."
)

# ================= 3. CO-OP SESSION CLASS =================


class CoOpSession:

  def __init__(
      self,
      members,
      mode_type,
      sub_mode=3,
      faction="Nga",
      heli_model="Ka-50",
  ):
    self.members = members
    self.mode_type = mode_type
    self.sub_mode = sub_mode
    self.faction = faction
    self.heli_model = heli_model

    if mode_type == "tank":
      self.team = "Nga (T-90M)" if sub_mode == 3 else "NATO (M1A3 Abrams)"
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

      self.team = f"{faction} ({heli_model})"

    self.hp = 100
    self.enemy_hp = 100
    self.turret_angle = 12
    self.current_ammo = "APFSDS" if mode_type == "tank" else "ATGM / Hellfire"
    self.loader_cooldown = 0
    self.driver_pos = "Tuyến đầu"
    self.radar_locked = False
    self.lock_target_info = "Chưa lock"
    self.under_sam_attack = False
    self.sam_warning_msg = "An toàn"
    self.last_log = "Sẵn sàng chiến đấu!"

    self.has_radar = True
    if heli_model in ["Ka-50", "Mi-24 SuperHind"]:
      self.has_radar = False
      self.lock_target_info = "Ngắm thủ công"


# ================= 4. ASCII MAP COMPACT (MOBILE FRIENDLY - 32 COLS) =================


def generate_role_ascii_map(coop: CoOpSession, role: str) -> str:
  unit = (
      coop.team.split("(")[-1].replace(")", "")
      if "(" in coop.team
      else coop.team
  )
  unit_tag = f"[{unit[:8]:^8}]"

  # --- TANK VIEWS ---
  if coop.mode_type == "tank":
    if role == "commander":
      header = f"COMMANDER | HƯỚNG:{coop.turret_angle}H"
      enemy_sec = (
          " [1,1]    [1,2]    [1,3] \n  v        v        v   \n [T72]    [BMP]"
          "   [ATGM]"
          if coop.enemy_hp > 0
          else "   💥 TIÊU DIỆT MỤC TIÊU 💥   "
      )
      bottom = f"LÁI XE: {coop.driver_pos[:12]}"

    elif role == "driver":
      header = f"DRIVER HUD | THÂN XE"
      enemy_sec = (
          f"     ▲ PHÍA TRƯỚC ▲      \n VỊ TRÍ: {coop.driver_pos[:14]}\n"
          " ═════════════════════════"
      )
      bottom = f"ĐỘNG CƠ: 100% OK"

    else:  # gunner / loader
      header = f"GUNNER FCS | {coop.turret_angle}H"
      enemy_sec = (
          "           |             \n       ───[ + ]───       \n     MỤC"
          f" TIÊU: {coop.enemy_hp}% HP"
          if coop.enemy_hp > 0
          else "   💥 MỤC TIÊU ĐÃ SẬP 💥  "
      )
      bottom = f"ĐẠN: {coop.current_ammo:<6} | CD: {coop.loader_cooldown}s"

  # --- HELI VIEWS ---
  else:
    if role == "pilot":
      header = f"PILOT HUD | {coop.heli_model[:10]}"
      sam_txt = (
          "🚨 SAM ĐANG BAY TỚI! 🚨"
          if coop.under_sam_attack
          else "   [ BẦU TRỜI AN TOÀN ]  "
      )
      enemy_sec = (
          f"BAY: {coop.driver_pos[:18]}\n{sam_txt}\n ═════════════════════════"
      )
      bottom = (
          f"SAM: {'🔴 BÁO ĐỘNG' if coop.under_sam_attack else '🟢 AN TOÀN'} |"
          f" HP:{coop.hp}%"
      )

    else:  # gunner
      header = f"GUNNER RADAR | {coop.heli_model[:8]}"
      radar_txt = (
          "🎯 RADAR LOCK ON"
          if coop.radar_locked
          else ("🔍 SCANNING..." if coop.has_radar else "👁️ NGẮM THỦ CÔNG")
      )
      enemy_sec = (
          f"           |             \n    {radar_txt:^17}\n     MỤC"
          f" TIÊU: {coop.enemy_hp}% HP"
      )
      bottom = f"LOCK: {coop.lock_target_info[:10]} | HP:{coop.hp}%"

  return f"""```text
┌──────────────────────────────┐
│ {header:<28} │
├──────────────────────────────┤
{enemy_sec}
│ ───────────┬────┬─────────── │
│          {unit_tag}          │
├──────────────────────────────┤
│ {bottom:<28} │
└──────────────────────────────┘
```"""


# ================= 5. BUTTON VIEWS & LOGIC SAM (TỰ ĐỘNG XÓA 5S) =================


async def trigger_enemy_sam_attack(channel, coop: CoOpSession):
  """Hàm kích hoạt tên lửa SAM tấn công ngẫu nhiên đếm ngược từ 3-8s và tự xóa tin nhắn sau 5s."""
  if coop.under_sam_attack or coop.hp <= 0:
    return

  coop.under_sam_attack = True
  delay_time = random.randint(3, 8)
  coop.sam_warning_msg = (
      f"⚠️ CẢNH BÁO SAM: Tên lửa địch sẽ va chạm trong {delay_time} giây!"
  )

  warn_embed = discord.Embed(
      title="🚨 BÁO ĐỘNG TÊN LỬA PHÒNG KHÔNG (SAM) 🚨",
      description=(
          f"⚡ **Phát hiện tên lửa SAM đang khóa vào {coop.heli_model}!**\n"
          f"⏱️ **Thời gian va chạm:** `{delay_time} giây`!\n"
          "👉 **Phi công hãy thả Flare hoặc Lách né khẩn cấp ngay!**"
      ),
      color=discord.Color.red(),
  )
  # Xóa thông báo SAM sau 5s
  warn_msg = await channel.send(embed=warn_embed, delete_after=5)

  await asyncio.sleep(delay_time)

  # Kiểm tra nếu sau khoảng thời gian đếm ngược mà chưa né/thả flare
  if coop.under_sam_attack and coop.hp > 0:
    dmg = random.randint(30, 50)
    coop.hp = max(0, coop.hp - dmg)
    coop.under_sam_attack = False
    coop.sam_warning_msg = "An toàn"

    hit_embed = discord.Embed(
        title="💥 TÊN LỬA SAM ĐÃ TRÚNG ĐÍCH!",
        description=(
            f"❌ Quá thời gian né tránh! Trực thăng bị bắn trúng tổn thất"
            f" **-{dmg}% HP**.\n❤️ **HP Trực thăng còn lại:** **{coop.hp}%**"
        ),
        color=discord.Color.dark_red(),
    )
    # Xóa thông báo trúng đạn sau 5s
    await channel.send(embed=hit_embed, delete_after=5)


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
            "⚠️ Chỉ Chỉ huy mới dùng bảng này!", ephemeral=True
        )
      hour = random.choice([1, 2, 3, 9, 10, 11, 12])
      self.coop.last_log = f"🎯 Phát hiện địch ô [{r+1},{c+1}] - Hướng {hour}H"
      await interaction.response.send_message(
          f"✅ Mục tiêu tại ô [{r+1},{c+1}]! Hướng: **{hour} giờ**.",
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
          "⚠️ Chỉ Lái xe mới điều khiển!", ephemeral=True
      )
    self.coop.driver_pos = pos
    await interaction.response.send_message(
        f"🏎️ Vị trí mới: **{pos}**", ephemeral=True
    )

  @discord.ui.button(
      label="⬆️ Tiến thẳng", style=discord.ButtonStyle.success, row=0
  )
  async def ts(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move(interaction, "Tiến thẳng")

  @discord.ui.button(
      label="↗️ Tiến phải", style=discord.ButtonStyle.success, row=0
  )
  async def tr(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move(interaction, "Tiến phải")

  @discord.ui.button(label="⬇️ Lùi ẩn nấp", style=discord.ButtonStyle.danger, row=1)
  async def bs(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move(interaction, "Lùi nấp")


class HeliPilotView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

    if coop.sub_mode == 1:
      switch_btn = discord.ui.Button(
          label="🔄 Đổi Góc Nhìn (Xạ Thủ)",
          style=discord.ButtonStyle.primary,
          row=0,
      )
      switch_btn.callback = self.switch_view_cb
      self.add_item(switch_btn)

  async def switch_view_cb(self, interaction: discord.Interaction):
    if interaction.user != self.coop.solo_player:
      return await interaction.response.send_message(
          "⚠️ Không có quyền!", ephemeral=True
      )
    self.coop.current_view = "gunner"
    embed = discord.Embed(
        title="🎯 CHUYỂN SANG GÓC NHÌN XẠ THỦ / RADAR",
        description=generate_role_ascii_map(self.coop, "gunner"),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(
        embed=embed, view=HeliGunnerCommanderView(self.coop)
    )

  async def move_heli(self, interaction: discord.Interaction, pos):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.pilot
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Chỉ Phi công mới điều khiển bay!", ephemeral=True
      )

    if self.coop.under_sam_attack and pos in ["Lách trái", "Lách phải"]:
      self.coop.under_sam_attack = False
      self.coop.sam_warning_msg = "An toàn"
      return await interaction.response.send_message(
          f"🛡️ **NÉ THÀNH CÔNG!** Thao tác **{pos}** đã né trọn tên lửa SAM!",
          ephemeral=False,
          delete_after=5,
      )

    self.coop.driver_pos = pos
    await interaction.response.send_message(
        f"🛫 Trạng thái bay: **{pos}**", ephemeral=True
    )

  @discord.ui.button(
      label="🔥 THẢ FLARE", style=discord.ButtonStyle.success, row=1
  )
  async def flare(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.pilot
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Chỉ Phi công mới thả Flare!", ephemeral=True
      )

    if self.coop.under_sam_attack:
      self.coop.under_sam_attack = False
      self.coop.sam_warning_msg = "An toàn"
      await interaction.response.send_message(
          "🔥 **FLARE DEPLOYED!** Mồi bẫy nhiệt đã cản phá thành công tên lửa"
          " SAM!",
          ephemeral=False,
          delete_after=5,
      )
    else:
      await interaction.response.send_message(
          "✨ Đã thả Flare bẫy nhiệt.", ephemeral=True
      )

  @discord.ui.button(
      label="⬅️ Lách trái", style=discord.ButtonStyle.secondary, row=2
  )
  async def dodge_left(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move_heli(interaction, "Lách trái")

  @discord.ui.button(
      label="➡️ Lách phải", style=discord.ButtonStyle.secondary, row=2
  )
  async def dodge_right(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.move_heli(interaction, "Lách phải")


class HeliGunnerCommanderView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

    if coop.sub_mode == 1:
      switch_btn = discord.ui.Button(
          label="🔄 Đổi Góc Nhìn (Phi Công)",
          style=discord.ButtonStyle.primary,
          row=0,
      )
      switch_btn.callback = self.switch_view_cb
      self.add_item(switch_btn)

  async def switch_view_cb(self, interaction: discord.Interaction):
    if interaction.user != self.coop.solo_player:
      return await interaction.response.send_message(
          "⚠️ Không có quyền!", ephemeral=True
      )
    self.coop.current_view = "pilot"
    embed = discord.Embed(
        title="🛫 CHUYỂN SANG GÓC NHÌN PHI CÔNG",
        description=generate_role_ascii_map(self.coop, "pilot"),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(
        embed=embed, view=HeliPilotView(self.coop)
    )

  @discord.ui.button(
      label="📡 Quét Radar / Ngắm", style=discord.ButtonStyle.secondary, row=1
  )
  async def scan_radar(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.gunner_cmd
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Không có quyền!", ephemeral=True
      )

    if not self.coop.has_radar:
      return await interaction.response.send_message(
          f"⚠️ **{self.coop.heli_model}** không có Radar. Bắt buộc ngắm thủ"
          " công!",
          ephemeral=True,
      )

    self.coop.radar_locked = True
    self.coop.lock_target_info = "LOCKED"
    await interaction.response.send_message(
        "🎯 **RADAR LOCK-ON!** Đã khóa mục tiêu.", ephemeral=True
    )

    if random.random() < 0.5:
      asyncio.create_task(
          trigger_enemy_sam_attack(interaction.channel, self.coop)
      )

  @discord.ui.button(
      label="🚀 KHAI HỎA ATGM", style=discord.ButtonStyle.danger, row=1
  )
  async def fire_heli(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_check = self.coop.solo_player if self.coop.sub_mode == 1 else self.coop.gunner_cmd
    if interaction.user != user_check:
      return await interaction.response.send_message(
          "⚠️ Không có quyền!", ephemeral=True
      )

    await interaction.response.defer(thinking=True)

    prompt = (
        f"Vũ khí: {self.coop.current_ammo}. Bắn từ {self.coop.heli_model}."
        f" Trạng thái lock: {self.coop.lock_target_info}."
    )
    damage_dealt = 30
    tech_msg = "Phóng tên lửa ATGM trúng mục tiêu."

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

    embed = discord.Embed(
        title=f"💥 KHAI HỎA ATGM ({self.coop.heli_model})",
        description=(
            f"📝 *{tech_msg}*\n💥 **Sát thương:** `-{damage_dealt}% HP`\n🎯 **Địch"
            f" còn:** **{self.coop.enemy_hp}% HP**"
        ),
        color=discord.Color.red()
        if self.coop.enemy_hp <= 0
        else discord.Color.orange(),
    )

    # Đặt tự động xóa kết quả bắn sau 5s
    await interaction.followup.send(embed=embed, delete_after=5)

    if random.random() < 0.6 and self.coop.enemy_hp > 0:
      asyncio.create_task(
          trigger_enemy_sam_attack(interaction.channel, self.coop)
      )


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
          "⚠️ Chỉ Pháo thủ!", ephemeral=True
      )
    self.coop.turret_angle = (self.coop.turret_angle % 12) + 1
    await interaction.response.send_message(
        f"🔄 Tháp pháo: **{self.coop.turret_angle} giờ**", ephemeral=True
    )

  @discord.ui.button(
      label="💥 KHAI HỎA TANK", style=discord.ButtonStyle.danger, row=1
  )
  async def fire(self, interaction: discord.Interaction, button: discord.ui.Button):
    if interaction.user != self.coop.gunner:
      return await interaction.response.send_message(
          "⚠️ Chỉ Pháo thủ!", ephemeral=True
      )
    if self.coop.loader_cooldown > 0 and self.coop.sub_mode == 4:
      return await interaction.response.send_message(
          f"⏳ Đang nạp ({self.coop.loader_cooldown}s)!", ephemeral=True
      )

    await interaction.response.defer(thinking=True)
    damage_dealt = random.randint(25, 40)

    self.coop.enemy_hp = max(0, self.coop.enemy_hp - damage_dealt)
    embed = discord.Embed(
        title="💥 TANK KHAI HỎA",
        description=(
            f"📦 Đạn: `{self.coop.current_ammo}`\n💥 Sát thương:"
            f" `-{damage_dealt}%`\n🎯 Địch còn: **{self.coop.enemy_hp}% HP**"
        ),
        color=discord.Color.red(),
    )
    # Tự động xóa sau 5s
    await interaction.followup.send(embed=embed, delete_after=5)


class LoaderControlView(discord.ui.View):

  def __init__(self, coop: CoOpSession):
    super().__init__(timeout=300)
    self.coop = coop

  async def ammo(self, interaction: discord.Interaction, t):
    if interaction.user != self.coop.loader:
      return await interaction.response.send_message(
          "⚠️ Chỉ Nạp đạn viên!", ephemeral=True
      )
    if self.coop.loader_cooldown > 0:
      return await interaction.response.send_message(
          f"⏳ Đang nạp đạn ({self.coop.loader_cooldown}s)...", ephemeral=True
      )
    self.coop.current_ammo = t
    self.coop.loader_cooldown = 6
    await interaction.response.send_message(
        f"✅ Đã nạp đạn **{t}**", ephemeral=True
    )

    async def cd():
      await asyncio.sleep(6)
      self.coop.loader_cooldown = 0

    asyncio.create_task(cd())

  @discord.ui.button(label="📦 APFSDS", style=discord.ButtonStyle.primary)
  async def a1(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.ammo(interaction, "APFSDS")

  @discord.ui.button(label="🔥 HEAT", style=discord.ButtonStyle.danger)
  async def a2(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.ammo(interaction, "HEAT")


# ================= 6. LỆNH BOT =================


@bot.command(name="Chelps")
async def chelps_cmd(ctx):
  embed = discord.Embed(
      title="📖 HƯỚNG DẪN BOT WAR THUNDER CO-OP",
      description=(
          "• `!tank-coop @LáiXe @PháoThủ [@NạpĐạn]`\n"
          "• `!heli-coop Nga Ka-50` (Chơi Solo)\n"
          "• `!heli-coop [Phe] [Heli] @Pilot @Gunner` (Chơi 2 người)\n"
          "• `!start` xuất kích."
      ),
      color=discord.Color.blue(),
  )
  await ctx.send(embed=embed)


@bot.command(name="tank-coop")
async def tank_coop_cmd(
    ctx,
    m1: discord.Member,
    m2: discord.Member,
    m3: discord.Member = None,
    m4: discord.Member = None,
):
  members = [ctx.author, m1, m2] if m3 is None else [ctx.author, m1, m2, m3]
  mode = 4 if len(members) == 4 else 3
  coop_sessions[ctx.channel.id] = CoOpSession(members, "tank", mode)
  await ctx.send(f"🛡️ **KÍP TANK CO-OP SẴN SÀNG!** Gõ `!start` để xuất kích.")


@bot.command(name="heli-coop")
async def heli_coop_cmd(
    ctx,
    faction: str,
    heli_model: str,
    m1: discord.Member = None,
    m2: discord.Member = None,
):
  if m1 is None:
    sub_mode = 1
    members = [ctx.author]
  else:
    sub_mode = 2
    members = [m1, m2 if m2 else ctx.author]

  coop = CoOpSession(members, "heli", sub_mode, faction, heli_model)
  coop_sessions[ctx.channel.id] = coop
  await ctx.send(
      f"🚁 **TRỰC THĂNG {heli_model.upper()} SẴN SÀNG!** Gõ `!start` để cất"
      " cánh."
  )


@bot.command(name="start")
async def start_cmd(ctx):
  if ctx.channel.id not in coop_sessions:
    return await ctx.send("⚠️ Chưa có phiên đấu! Khởi tạo bằng lệnh trước.")

  coop = coop_sessions[ctx.channel.id]

  if coop.mode_type == "tank":
    await ctx.send(
        content=f"👑 **Chỉ huy {coop.commander.mention}:**",
        embed=discord.Embed(
            title="👑 [COMMANDER HUD]",
            description=generate_role_ascii_map(coop, "commander"),
            color=discord.Color.gold(),
        ),
        view=CommanderCaroView(coop),
    )
    await ctx.send(
        content=f"🏎️ **Lái xe {coop.driver.mention}:**",
        embed=discord.Embed(
            title="🏎️ [DRIVER HUD]",
            description=generate_role_ascii_map(coop, "driver"),
            color=discord.Color.blue(),
        ),
        view=DriverControlView(coop),
    )
    await ctx.send(
        content=f"🎯 **Pháo thủ {coop.gunner.mention}:**",
        embed=discord.Embed(
            title="🎯 [GUNNER HUD]",
            description=generate_role_ascii_map(coop, "gunner"),
            color=discord.Color.red(),
        ),
        view=GunnerControlView(coop),
    )
    if coop.sub_mode == 4 and coop.loader:
      await ctx.send(
          content=f"📦 **Nạp đạn {coop.loader.mention}:**",
          embed=discord.Embed(
              title="📦 [LOADER HUD]",
              description=generate_role_ascii_map(coop, "loader"),
              color=discord.Color.green(),
          ),
          view=LoaderControlView(coop),
      )
  else:
    if coop.sub_mode == 1:
      role = coop.current_view
      view = (
          HeliPilotView(coop) if role == "pilot" else HeliGunnerCommanderView(coop)
      )
      await ctx.send(
          content=f"🚁 **Trực thăng {coop.heli_model} Solo HUD:**",
          embed=discord.Embed(
              title=f"🚁 [{role.upper()} VIEW]",
              description=generate_role_ascii_map(coop, role),
              color=discord.Color.purple(),
          ),
          view=view,
      )
    else:
      await ctx.send(
          content=f"🛫 **Phi công {coop.pilot.mention}:**",
          embed=discord.Embed(
              title="🛫 [PILOT HUD]",
              description=generate_role_ascii_map(coop, "pilot"),
              color=discord.Color.green(),
          ),
          view=HeliPilotView(coop),
      )
      await ctx.send(
          content=f"🎯 **Xạ thủ {coop.gunner_cmd.mention}:**",
          embed=discord.Embed(
              title="🎯 [GUNNER HUD]",
              description=generate_role_ascii_map(coop, "gunner"),
              color=discord.Color.orange(),
          ),
          view=HeliGunnerCommanderView(coop),
      )


@bot.event
async def on_ready():
  print(f"✅ Bot sẵn sàng: {bot.user.name}")


if __name__ == "__main__":
  keep_alive()
  bot.run(DISCORD_TOKEN)
