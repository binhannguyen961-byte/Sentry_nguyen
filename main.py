import os
import random
import time
import discord
from discord.ext import commands

# --------------------------------------------------
# 1. KHỞI TẠO BOT & CƠ SỞ DỮ LIỆU
# --------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Database lưu dữ liệu người chơi
player_data = {}


def get_player(user_id):
  if user_id not in player_data:
    player_data[user_id] = {
        "step": 1,
        "balance": 5000,
        "lands": [],  # Công nghiệp dân sự: nhamay, trangtrai
        "military_factories": 0,  # Nhà máy quốc phòng
        "tech_level": 1,  # Cấp độ công nghệ quân sự
        "military": {"tank": 0, "plane": 0, "missile": 0, "ammo": 50},
        "territories": 1,  # Số vùng đất/lãnh thổ đang cai trị
        "inventory": {"grapnel": 1, "batarang": 3, "sat": 10, "nongsan": 10},
        "last_raid": 0,
        "last_conquer": 0,
    }
  return player_data[user_id]


# --------------------------------------------------
# 2. HÀM DÒ FILE ẢNH ALFRED
# --------------------------------------------------
def get_alfred_image():
  possible_filenames = [
      "alfred.png",
      "Alfred.png",
      "alfred.jpg",
      "Alfred.jpg",
      "ALFRED.PNG",
      "ALFRED.JPG",
  ]
  for name in possible_filenames:
    if os.path.exists(name):
      return name
  return None


# --------------------------------------------------
# 3. GIAO DIỆN NÚT BẤM (BUTTON VIEWS)
# --------------------------------------------------
class GameStoryView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="Tiếp", style=discord.ButtonStyle.primary, emoji="➡️"
  )
  async def next_button_callback(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    p = get_player(interaction.user.id)
    p["step"] += 1

    if p["step"] == 2:
      new_dialogue = (
          "Chiến tranh toàn cầu đã nổ ra! Ngài cần xây dựng Nhà máy Quốc phòng"
          " (`!buildmil`) và nghiên cứu công nghệ (`!research`)."
      )
    elif p["step"] == 3:
      new_dialogue = (
          "Hãy sản xuất Xe tăng, Máy bay (`!produce`) và tiến hành chinh phục"
          " các lãnh thổ mới (`!conquer`) ngay hôm nay!"
      )
    else:
      new_dialogue = (
          f"Ngài đang ở giai đoạn kịch bản thứ {p['step']}.\nHãy gõ `!help` để"
          " xem lại toàn bộ hệ thống lệnh quân sự."
      )

    embed = interaction.message.embeds[0]
    embed.description = new_dialogue
    await interaction.response.edit_message(embed=embed, view=self)


class TradeView(discord.ui.View):

  def __init__(self, sender, target, item, amount, price):
    super().__init__(timeout=60)
    self.sender = sender
    self.target = target
    self.item = item
    self.amount = amount
    self.price = price

  @discord.ui.button(
      label="Xác nhận giao dịch", style=discord.ButtonStyle.success, emoji="✅"
  )
  async def accept(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if interaction.user.id != self.target.id:
      return await interaction.response.send_message(
          "Đây không phải lời mời cho bạn!", ephemeral=True
      )

    p_sender = get_player(self.sender.id)
    p_target = get_player(self.target.id)

    if p_sender["inventory"].get(self.item, 0) < self.amount:
      return await interaction.response.send_message(
          "Người bán không còn đủ hàng!", ephemeral=True
      )
    if p_target["balance"] < self.price:
      return await interaction.response.send_message(
          "Bạn không đủ tiền!", ephemeral=True
      )

    p_sender["inventory"][self.item] -= self.amount
    p_target["inventory"][self.item] = (
        p_target["inventory"].get(self.item, 0) + self.amount
    )
    p_target["balance"] -= self.price
    p_sender["balance"] += self.price

    await interaction.response.edit_message(
        content=(
            f"✅ **Giao dịch thành công!** {self.target.mention} đã mua"
            f" {self.amount}x `{self.item}` từ {self.sender.mention} với giá"
            f" **${self.price:,}**."
        ),
        view=None,
    )


# --------------------------------------------------
# 4. CÂY CÔNG NGHIỆP QUÂN SỰ (MILITARY-INDUSTRIAL COMPLEX)
# --------------------------------------------------
@bot.command(name="buildmil")
async def buildmil(ctx):
  p = get_player(ctx.author.id)
  cost = (p["military_factories"] + 1) * 3000

  if p["balance"] < cost:
    return await ctx.send(
        f"❌ Ngài cần **${cost:,}** để xây Nhà máy Quốc phòng tiếp theo!"
    )

  p["balance"] -= cost
  p["military_factories"] += 1
  await ctx.send(
      f"🏭 **Thành công!** Ngài vừa xây dựng 1 **Nhà máy Quốc phòng** (Tổng"
      f" cộng: {p['military_factories']})."
  )


@bot.command(name="research")
async def research(ctx):
  p = get_player(ctx.author.id)
  cost = p["tech_level"] * 5000

  if p["balance"] < cost:
    return await ctx.send(
        f"❌ Ngài cần **${cost:,}** để nâng cấp Công nghệ Quân sự lên Cấp"
        f" {p['tech_level'] + 1}!"
    )

  p["balance"] -= cost
  p["tech_level"] += 1
  await ctx.send(
      f"🔬 **Nghiên cứu hoàn tất!** Công nghệ Quân sự của ngài đã đạt **Cấp"
      f" {p['tech_level']}**!"
  )


@bot.command(name="produce")
async def produce(ctx, unit: str = None, amount: int = 1):
  p = get_player(ctx.author.id)
  recipes = {
      "tank": {"sat": 5, "cost": 1000, "tech": 1},
      "plane": {"sat": 10, "cost": 2500, "tech": 2},
      "missile": {"sat": 15, "cost": 5000, "tech": 3},
      "ammo": {"sat": 1, "cost": 100, "tech": 1},
  }

  if not unit or unit.lower() not in recipes or amount <= 0:
    return await ctx.send(
        "❌ **Cú pháp:** `!produce <tank|plane|missile|ammo> <số_lượng>`\n•"
        " `tank`: 5 Sắt, $1,000 (Tech 1)\n• `plane`: 10 Sắt, $2,500 (Tech 2)\n•"
        " `missile`: 15 Sắt, $5,000 (Tech 3)\n• `ammo`: 1 Sắt, $100 (Đạn)"
    )

  unit = unit.lower()
  req = recipes[unit]

  if p["tech_level"] < req["tech"]:
    return await ctx.send(
        f"❌ Ngài cần Công nghệ Quân sự **Cấp {req['tech']}** để sản xuất"
        f" {unit.upper()}!"
    )
  if p["military_factories"] < 1:
    return await ctx.send(
        "❌ Ngài cần có ít nhất 1 **Nhà máy Quốc phòng** (`!buildmil`)!"
    )

  total_sat = req["sat"] * amount
  total_cost = req["cost"] * amount

  if p["inventory"].get("sat", 0) < total_sat:
    return await ctx.send(
        f"❌ Không đủ Sắt! Ngài cần {total_sat} Sắt để chế tạo."
    )
  if p["balance"] < total_cost:
    return await ctx.send(
        f"❌ Không đủ ngân sách! Ngài cần **${total_cost:,}**."
    )

  p["inventory"]["sat"] -= total_sat
  p["balance"] -= total_cost
  p["military"][unit] += amount

  await ctx.send(
      f"🪖 **Sản xuất hoàn tất!** +{amount}x `{unit.upper()}` đã được thêm vào"
      " kho vũ khí."
  )


# --------------------------------------------------
# 5. CƠ CHẾ CHIẾN ĐẤU XÂM CHIẾM (CONQUER THE WORLD)
# --------------------------------------------------
def calculate_power(p):
  # Công thức tính sức mạnh: Tank=100, Plane=250, Missile=500, Nhân với Tech Level
  m = p["military"]
  raw_power = (
      (m["tank"] * 100) + (m["plane"] * 250) + (m["missile"] * 500)
  ) * p["tech_level"]
  return raw_power


@bot.command(name="conquer")
async def conquer(ctx, target: discord.Member = None):
  p_attacker = get_player(ctx.author.id)

  now = time.time()
  if now - p_attacker["last_conquer"] < 600:  # 10 phút hồi chiêu
    wait = int(600 - (now - p_attacker["last_conquer"]))
    return await ctx.send(
        f"⏳ Quân đội đang sắp xếp lại đội hình! Hãy chờ {wait}s nữa để phát"
        " động chiến dịch mới."
    )

  attacker_power = calculate_power(p_attacker)
  if attacker_power <= 0:
    return await ctx.send(
        "❌ Ngài không có lực lượng quân sự! Hãy dùng `!produce` để sản xuất"
        " Xe tăng/Máy bay."
    )

  if p_attacker["military"]["ammo"] < 10:
    return await ctx.send(
        "❌ Quân đội thiếu đạn dược! Ngài cần ít nhất 10 Đạn (`!produce ammo`)"
        " để tiến công."
    )

  p_attacker["military"]["ammo"] -= 10
  p_attacker["last_conquer"] = now

  # Truong hop 1: Danh NPC mở rộng lãnh thổ
  if not target or target.id == ctx.author.id:
    npc_power = p_attacker["territories"] * 300
    win_chance = attacker_power / (attacker_power + npc_power)

    if random.random() < win_chance:
      p_attacker["territories"] += 1
      stolen_cash = p_attacker["territories"] * 1000
      p_attacker["balance"] += stolen_cash
      await ctx.send(
          "🌍 **CHIẾN THẮNG RỰC RỠ!** Ngài đã xâm chiếm thành công 1 Lãnh thổ"
          f" mới! (Tổng: {p_attacker['territories']} vùng đất, Chiếm đoạt:"
          f" **${stolen_cash:,}**)"
      )
    else:
      # Tổn thất 20% Tank
      lost_tanks = int(p_attacker["military"]["tank"] * 0.2)
      p_attacker["military"]["tank"] -= lost_tanks
      await ctx.send(
          "💥 **CHIẾN DỊCH THẤT BẠI!** Lực lượng phòng thủ vùng đất quá mạnh."
          f" Ngài mất {lost_tanks} Xe tăng trong trận chiến."
      )

  # Truong hop 2: Đánh người chơi khác
  else:
    p_defender = get_player(target.id)
    defender_power = calculate_power(p_defender) + (
        p_defender["territories"] * 200
    )

    if attacker_power > defender_power:
      stolen_land = 1 if p_defender["territories"] > 1 else 0
      p_defender["territories"] -= stolen_land
      p_attacker["territories"] += stolen_land

      stolen_cash = int(p_defender["balance"] * 0.25)
      p_defender["balance"] -= stolen_cash
      p_attacker["balance"] += stolen_cash

      await ctx.send(
          f"⚔️ **ĐẠI THẮNG!** Quân đội của {ctx.author.mention} (Sức mạnh:"
          f" {attacker_power:,}) đã đè bẹp {target.mention} (Sức mạnh:"
          f" {defender_power:,})!\n• Cướp được **${stolen_cash:,}**\n• Cướp"
          f" được {stolen_land} Lãnh thổ!"
      )
    else:
      # Phạt giảm sức mạnh
      p_attacker["military"]["tank"] = int(p_attacker["military"]["tank"] * 0.7)
      await ctx.send(
          f"🛡️ **THẤT BẠI TẢN MÁC!** {target.mention} đã phòng thủ kiên"
          f" cường. {ctx.author.mention} bị thiệt hại 30% lực lượng Xe tăng!"
      )


# --------------------------------------------------
# 6. KINH TẾ DÂN SỰ & THƯƠNG MẠI
# --------------------------------------------------
@bot.command(name="buyland")
async def buyland(ctx, land_type: str = None):
  p = get_player(ctx.author.id)
  prices = {"nhamay": 2000, "trangtrai": 1000}

  if not land_type or land_type.lower() not in prices:
    return await ctx.send(
        "❌ **Cú pháp:** `!buyland <nhamay|trangtrai>`\n• `trangtrai`: $1,000\n•"
        " `nhamay`: $2,000"
    )

  land_type = land_type.lower()
  cost = prices[land_type]
  if p["balance"] < cost:
    return await ctx.send(f"❌ Bạn cần **${cost:,}**!")

  p["balance"] -= cost
  p["lands"].append(
      {"type": land_type, "level": 1, "last_harvest": time.time()}
  )
  await ctx.send(f"🏗️ Ngài đã mua 1 `{land_type}`.")


@bot.command(name="harvest")
async def harvest(ctx):
  p = get_player(ctx.author.id)
  now = time.time()
  total_sat, total_nongsan = 0, 0

  for land in p["lands"]:
    elapsed = now - land["last_harvest"]
    if elapsed >= 60:
      cycles = int(elapsed // 60)
      land["last_harvest"] = now
      if land["type"] == "nhamay":
        total_sat += cycles * 5
      elif land["type"] == "trangtrai":
        total_nongsan += cycles * 10

  p["inventory"]["sat"] = p["inventory"].get("sat", 0) + total_sat
  p["inventory"]["nongsan"] = p["inventory"].get("nongsan", 0) + total_nongsan
  await ctx.send(
      f"📦 **Thu hoạch:** +{total_sat} Sắt, +{total_nongsan} Nông sản."
  )


@bot.command(name="sell")
async def sell(ctx, item: str = None, amount: int = 1):
  p = get_player(ctx.author.id)
  price_table = {"sat": 50, "nongsan": 20}

  if not item or item.lower() not in price_table or amount <= 0:
    return await ctx.send("❌ **Cú pháp:** `!sell <sat|nongsan> <số_lượng>`")

  item = item.lower()
  if p["inventory"].get(item, 0) < amount:
    return await ctx.send(f"❌ Không đủ {item}!")

  earned = price_table[item] * amount
  p["inventory"][item] -= amount
  p["balance"] += earned
  await ctx.send(f"💰 Đã bán {amount}x `{item}` lấy **${earned:,}**.")


@bot.command(name="pay")
async def pay(ctx, target: discord.Member = None, amount: int = 0):
  if not target or target.bot or amount <= 0:
    return await ctx.send("❌ **Cú pháp:** `!pay @NgườiDùng <số_tiền>`")
  p_sender, p_target = get_player(ctx.author.id), get_player(target.id)

  if p_sender["balance"] < amount:
    return await ctx.send("❌ Không đủ tiền!")

  p_sender["balance"] -= amount
  p_target["balance"] += amount
  await ctx.send(f"💸 Đã chuyển **${amount:,}** cho {target.mention}.")


@bot.command(name="trade")
async def trade(
    ctx, target: discord.Member = None, item: str = None, amount: int = 1, price: int = 0
):
  if not target or target.bot or not item or price <= 0:
    return await ctx.send(
        "❌ **Cú pháp:** `!trade @NgườiDùng <vật_phẩm> <số_lượng> <giá>`"
    )
  item = item.lower()
  if get_player(ctx.author.id)["inventory"].get(item, 0) < amount:
    return await ctx.send(f"❌ Không đủ `{item}`!")

  view = TradeView(ctx.author, target, item, amount, price)
  await ctx.send(
      f"🤝 {target.mention}, {ctx.author.mention} muốn bán **{amount}x"
      f" `{item}`** với giá **${price:,}**.",
      view=view,
  )


# --------------------------------------------------
# 7. TRẠNG THÁI & HỆ THỐNG
# --------------------------------------------------
@bot.event
async def on_ready():
  print(f"✅ Bot đã đăng nhập: {bot.user.name}")


@bot.command(name="startgame")
async def startgame(ctx):
  img_filename = get_alfred_image()
  p = get_player(ctx.author.id)
  p["step"] = 1

  dialogue_text = (
      f"Chào mừng ngài đã trở lại hệ thống, {ctx.author.display_name}.\nTình"
      " hình hiện tại đang rất khẩn cấp, xin hãy chú ý lắng nghe."
  )
  embed = discord.Embed(
      title="🎮 KHỞI ĐẦU TRÒ CHƠI", description=dialogue_text, color=0x2B2D31
  )
  embed.add_field(
      name="📜 Hướng dẫn lệnh quân sự & kinh tế",
      value=(
          "• `!buildmil` / `!research` / `!produce` - Công nghiệp quân sự\n•"
          " `!conquer [@user]` - Xâm chiếm lãnh thổ\n• `!buyland` / `!harvest` /"
          " `!sell` - Kinh tế dân sự\n• `!status` / `!army` - Kiểm tra thông"
          " tin"
      ),
      inline=False,
  )

  if img_filename:
    file = discord.File(img_filename, filename=img_filename)
    embed.set_image(url=f"attachment://{img_filename}")
    await ctx.send(file=file, embed=embed, view=GameStoryView())
  else:
    await ctx.send(embed=embed, view=GameStoryView())


@bot.command(name="army")
async def army(ctx):
  p = get_player(ctx.author.id)
  m = p["military"]
  power = calculate_power(p)

  embed = discord.Embed(
      title=f"🪖 ĐỘI HÌNH QUÂN SỰ - {ctx.author.display_name}",
      color=discord.Color.red(),
  )
  embed.add_field(
      name="⚡ Tổng Sức Mạnh", value=f"**{power:,}** Power", inline=False
  )
  embed.add_field(
      name="🔬 Cấp Công Nghệ", value=f"Cấp {p['tech_level']}", inline=True
  )
  embed.add_field(
      name="🏭 Nhà Máy QP", value=f"{p['military_factories']}", inline=True
  )
  embed.add_field(
      name="🌍 Lãnh Thổ", value=f"{p['territories']} Vùng", inline=True
  )
  embed.add_field(
      name="📦 Lực Lượng",
      value=(
          f"• **Xe tăng**: {m['tank']}\n• **Máy bay**: {m['plane']}\n• **Tên"
          f" lửa**: {m['missile']}\n• **Đạn dược**: {m['ammo']}"
      ),
      inline=False,
  )
  await ctx.send(embed=embed)


@bot.command(name="status")
async def status(ctx):
  p = get_player(ctx.author.id)
  embed = discord.Embed(
      title=f"📊 Trạng Thái - {ctx.author.display_name}",
      color=discord.Color.blue(),
  )
  embed.add_field(name="💰 Ngân sách", value=f"${p['balance']:,}", inline=True)
  embed.add_field(
      name="⚡ Sức mạnh", value=f"{calculate_power(p):,}", inline=True
  )
  embed.add_field(
      name="🌍 Lãnh thổ", value=f"{p['territories']}", inline=True
  )
  await ctx.send(embed=embed)


# --------------------------------------------------
# 8. CHẠY BOT
# --------------------------------------------------
if __name__ == "__main__":
  bot.run("YOUR_BOT_TOKEN_HERE")
