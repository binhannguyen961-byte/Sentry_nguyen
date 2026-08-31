import io
import os
import random
import sqlite3
import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

GRID_ROWS = 4
GRID_COLS = ["A", "B", "C", "D"]

def init_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            money REAL DEFAULT 1000.0,
            debt REAL DEFAULT 500000.0,
            ore INTEGER DEFAULT 0,
            steel INTEGER DEFAULT 0,
            weapon_power INTEGER DEFAULT 0,
            defense_power INTEGER DEFAULT 0,
            territory_level INTEGER DEFAULT 1,
            tech_level INTEGER DEFAULT 1,
            last_transfer_date TEXT DEFAULT '',
            daily_transferred REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grid_cells (
            user_id INTEGER,
            cell_id TEXT,
            building_type TEXT DEFAULT 'trong',
            connected_to TEXT DEFAULT '',
            PRIMARY KEY (user_id, cell_id)
        )
    """)
    # Bảng lưu trữ danh mục bất động sản đầu tư của người chơi
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS real_estate (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            property_name TEXT,
            purchase_price REAL,
            current_value REAL,
            risk_tier TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_player(user_id):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT money, debt, ore, steel, weapon_power, defense_power, territory_level, tech_level, daily_transferred 
        FROM players WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT INTO players (user_id, money, debt, ore, steel, weapon_power, defense_power, territory_level, tech_level) 
            VALUES (?, 1000.0, 500000.0, 0, 0, 0, 0, 1, 1)
        """, (user_id,))
        for r in range(1, GRID_ROWS + 1):
            for c in GRID_COLS:
                cursor.execute("INSERT OR IGNORE INTO grid_cells (user_id, cell_id, building_type, connected_to) VALUES (?, ?, 'trong', '')", (user_id, f"{c}{r}"))
        conn.commit()
        row = (1000.0, 500000.0, 0, 0, 0, 0, 1, 1, 0.0)
    conn.close()
    return {
        "money": row[0], "debt": row[1], "ore": row[2], "steel": row[3], 
        "weapon": row[4], "defense": row[5], "territory": row[6], "tech": row[7], "daily_transferred": row[8]
    }

def update_player(user_id, data):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE players 
        SET money = ?, debt = ?, ore = ?, steel = ?, weapon_power = ?, defense_power = ?, territory_level = ?, tech_level = ?, daily_transferred = ? 
        WHERE user_id = ?
    """, (data['money'], data['debt'], data['ore'], data['steel'], data['weapon'], data['defense'], data['territory'], data['tech'], data['daily_transferred'], user_id))
    conn.commit()
    conn.close()

def get_grid(user_id):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT cell_id, building_type, connected_to FROM grid_cells WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: {"type": row[1], "target": row[2]} for row in rows}

def create_vn_image(background_color, speaker_name, dialogue_text):
    width, height = 800, 450
    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 300, 760, 420], fill=(15, 15, 25), outline=(200, 200, 200), width=2)
    draw.rectangle([50, 270, 250, 305], fill=(40, 40, 70), outline=(200, 200, 200), width=1)
    
    try:
        font_name = ImageFont.truetype("arial.ttf", 16)
        font_text = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((65, 278), speaker_name, fill=(255, 220, 100), font=font_name)
    lines, current_line = [], ""
    for word in dialogue_text.split(" "):
        if len(current_line + " " + word) <= 65:
            current_line += (" " if current_line else "") + word
        else:
            lines.append(current_line)
            current_line = word
    if current_line: lines.append(current_line)
        
    text_y = 320
    for line in lines[:4]:
        draw.text((60, text_y), line, fill=(255, 255, 255), font=font_text)
        text_y += 22

    bio = io.BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return discord.File(bio, filename="visual_novel.png")

async def get_butler_dialogue(prompt_context):
    if not gemini_model: return "Thưa cậu chủ, tôi luôn sẵn sàng."
    try:
        res = gemini_model.generate_content(f"Bạn là quản gia thực dụng, sắc sảo, hay cà khịa cậu chủ phá sản đang trả nợ 500k$. Trả lời dưới 2 câu bằng tiếng Việt.\nTình huống: {prompt_context}")
        return res.text.strip()
    except: return "Thưa cậu chủ, hệ thống liên lạc đang chập chờn."

@tasks.loop(seconds=30)
async def factory_production_loop():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM players")
    for u in cursor.fetchall():
        user_id = u[0]
        grid = get_grid(user_id)
        player = get_player(user_id)
        
        miners = sum(1 for c in grid.values() if c["type"] == "miner")
        smelters = sum(1 for c in grid.values() if c["type"] == "smelter" and c["target"] in grid and grid[c["target"]]["type"] == "miner")
        
        multiplier = player['tech']
        added_ore = miners * 4 * multiplier
        consumed_ore = smelters * 3
        actual_smelted = min(added_ore, consumed_ore) if smelters > 0 else 0
        added_steel = int(actual_smelted * 0.8 * multiplier)

        cursor.execute("SELECT ore, steel FROM players WHERE user_id = ?", (user_id,))
        p = cursor.fetchone()
        cursor.execute("UPDATE players SET ore = ?, steel = ? WHERE user_id = ?", (max(0, p[0] + added_ore - consumed_ore), p[1] + added_steel, user_id))
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    factory_production_loop.start()
    print(f"Bot Tycoon RealEstate Edition Online: {bot.user}")

@bot.command(name="start_empire")
async def start_game(ctx):
    player = get_player(ctx.author.id)
    diag = await get_butler_dialogue("Cậu chủ nhìn mảnh đất hoang.")
    embed = discord.Embed(title="🏛️ ĐẾ CHẾ CÔNG NGHIỆP: KHỞI ĐẦU", description=f"*{diag}*\n\n💵 Tiền: `${player['money']:,.2f}` | 💳 Nợ: `${player['debt']:,.2f}`", color=discord.Color.dark_red())
    await ctx.send(embed=embed)

@bot.command(name="factory")
async def show_factory(ctx):
    player = get_player(ctx.author.id)
    grid = get_grid(user_id=ctx.author.id)
    board = "```\n" + "      " + "   ".join(GRID_COLS) + "  \n    +----+----+----+----+\n"
    for r in range(1, GRID_ROWS + 1):
        line = f"  {r} |"
        for c in GRID_COLS:
            t = grid.get(f"{c}{r}", {}).get("type", "trong")
            sym = " ⛏️ " if t=="miner" else " 🏭 " if t=="smelter" else " 🚚 " if t=="truck" else "    "
            line += sym + "|"
        board += line + "\n    +----+----+----+----+\n"
    board += "```"
    embed = discord.Embed(title="🗺️ BẢN ĐỒ NHÀ MÁY & LOGISTICS", color=discord.Color.dark_green())
    embed.add_field(name="Trạng Thái", value=f"💵 Tiền: `${player['money']:,.2f}` | 📦 Quặng: {player['ore']} | 🔩 Thép: {player['steel']}\n🔬 Công nghệ: Cấp {player['tech']} | ⚔️ Sức mạnh: {player['weapon'] + player['defense']}", inline=False)
    embed.add_field(name="Sơ Đồ (⛏️ Mỏ | 🏭 Lò | 🚚 Xe chở)", value=board, inline=False)
    embed.set_footer(text="Lệnh: !f_place [miner/smelter/truck] [ô] | !f_connect [đích] [nguồn]")
    await ctx.send(embed=embed)

@bot.command(name="f_place")
async def f_place(ctx, b_type: str, cell: str):
    b_type = b_type.lower()
    cell = cell.upper()
    if b_type not in ["miner", "smelter", "truck"]:
        return await ctx.send("❌ Thiết bị không hợp lệ! Dùng: `miner`, `smelter`, hoặc `truck`.")
    
    costs = {"miner": 300, "smelter": 600, "truck": 500}
    player = get_player(ctx.author.id)
    cost = costs[b_type]
    
    if player['money'] < cost:
        return await ctx.send(f"❌ Không đủ tiền! Cần `${cost}`.")
        
    player['money'] -= cost
    update_player(ctx.author.id, player)

    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE grid_cells SET building_type = ? WHERE user_id = ? AND cell_id = ?", (b_type, ctx.author.id, cell))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Đã đặt `{b_type}` tại ô **{cell}** với giá `${cost}`!")

@bot.command(name="f_remove")
async def f_remove(ctx, cell: str):
    cell = cell.upper()
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE grid_cells SET building_type = 'trong', connected_to = '' WHERE user_id = ? AND cell_id = ?", (ctx.author.id, cell))
    conn.commit()
    conn.close()
    await ctx.send(f"🗑️ Đã thu hồi thiết bị tại ô **{cell}**!")

@bot.command(name="f_connect")
async def f_connect(ctx, target: str, source: str):
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE grid_cells SET connected_to = ? WHERE user_id = ? AND cell_id = ?", (source.upper(), ctx.author.id, target.upper()))
    conn.commit()
    conn.close()
    await ctx.send(f"🔌 Đã nối dây dữ liệu từ **{source.upper()}** sang **{target.upper()}**!")

@bot.command(name="f_sell")
async def f_sell(ctx, res: str):
    user_id = ctx.author.id
    player = get_player(user_id)
    grid = get_grid(user_id)
    res = res.lower()

    has_connected_truck = False
    for cell_id, data in grid.items():
        if data["type"] == "truck" and data["target"] in grid:
            has_connected_truck = True
            break

    if not has_connected_truck:
        return await ctx.send("❌ Không thể bán hàng! Bạn phải đặt một **Xe chở (truck)** trên lưới và dùng `!f_connect` nối nguồn tài nguyên vào xe chở đó.")

    earned = 0
    if res in ["quang", "ore"] and player['ore'] > 0:
        earned, player['ore'] = player['ore'] * 10 * player['tech'], 0
    elif res in ["thep", "steel"] and player['steel'] > 0:
        earned, player['steel'] = player['steel'] * 35 * player['tech'], 0
    else: 
        return await ctx.send("❌ Kho trống hoặc tài nguyên không hợp lệ (`ore`/`steel`)!")

    player['money'] += earned
    update_player(user_id, player)
    await ctx.send(f"🚚 Xe chở đã vận chuyển thành công! Thu về **${earned:,.2f}** tiền mặt!")

# --- HỆ THỐNG ĐẦU TƯ BẤT ĐỘNG SẢN MỚI ---
@bot.command(name="real_estate", aliases=["bds"])
async def real_estate_market(ctx):
    embed = discord.Embed(title="🏢 SÀN GIAO DỊCH BẤT ĐỘNG SẢN & ĐẦU TƯ", color=discord.Color.orange())
    embed.description = (
        "Gặp gỡ danh nhân bất động sản để mua các dự án đất đai chiến lược. "
        "Giá trị bất động sản sẽ biến động ngẫu nhiên hoặc dựa trên tổng tài sản & số ô đất bạn đang sở hữu!\n\n"
        "🏠 **1. Khu đất vùng ven thành phố**\n"
        "   - Giá khởi điểm: `$2,000` | Rủi ro: Thấp | Lợi nhuận ổn định\n"
        "   - Lệnh mua: `!buy_property ven`\n\n"
        "🏗️ **2. Tổ hợp thương mại trung tâm**\n"
        "   - Giá khởi điểm: `$8,000` | Rủi ro: Trung bình | Lợi nhuận cao\n"
        "   - Lệnh mua: `!buy_property trungtam`\n\n"
        "🌆 **3. Siêu dự án khu đô thị mới**\n"
        "   - Giá khởi điểm: `$25,000` | Rủi ro: Cao | Siêu lợi nhuận\n"
        "   - Lệnh mua: `!buy_property do-thi`\n\n"
        "📋 Xem danh mục đang sở hữu: `!my_properties` | Bán lại: `!sell_property [ID]`"
    )
    await ctx.send(embed=embed)

@bot.command(name="buy_property")
async def buy_property(ctx, prop_type: str):
    user_id = ctx.author.id
    player = get_player(user_id)
    prop_type = prop_type.lower()
    
    props_info = {
        "ven": ("Đất vùng ven thành phố", 2000, "Thấp"),
        "trungtam": ("Tổ hợp thương mại trung tâm", 8000, "Trung bình"),
        "do-thi": ("Siêu dự án khu đô thị mới", 25000, "Cao")
    }
    
    if prop_type not in props_info:
        return await ctx.send("❌ Loại bất động sản không hợp lệ! Chọn: `ven`, `trungtam`, hoặc `do-thi`.")
        
    name, price, risk = props_info[prop_type]
    if player['money'] < price:
        return await ctx.send(f"❌ Không đủ tiền mua bất động sản này! Cần `${price:,.2f}`.")
        
    player['money'] -= price
    update_player(user_id, player)
    
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO real_estate (user_id, property_name, purchase_price, current_value, risk_tier)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, price, price, risk))
    conn.commit()
    conn.close()
    
    file = create_vn_image((45, 35, 25), "Đại gia BĐS Arthur", f"Chúc mừng cậu chủ đã sở hữu thành công {name}! Hy vọng thị trường sẽ mỉm cười với khoản đầu tư này.")
    await ctx.send(file=file)

@bot.command(name="my_properties", aliases=["ds_bds"])
async def my_properties(ctx):
    user_id = ctx.author.id
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, property_name, purchase_price, current_value, risk_tier FROM real_estate WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return await ctx.send("📁 Bạn chưa sở hữu dự án bất động sản nào! Dùng lệnh `!real_estate` để tham khảo.")
        
    embed = discord.Embed(title="📋 DANH MỤC ĐẦU TƯ BẤT ĐỘNG SẢN", color=discord.Color.gold())
    total_val = 0
    for row in rows:
        prop_id, name, p_price, c_val, risk = row
        # Cập nhật biến động giá ngẫu nhiên mỗi lần xem danh mục kết hợp với tổng tài sản & số ô đất sở hữu
        player = get_player(user_id)
        # Hệ số tăng trưởng dựa trên ngẫu nhiên (-10% đến +25%) + thưởng từ cấp lãnh thổ và tài sản
        factor = random.uniform(0.90, 1.25) + (player['territory'] * 0.02)
        new_val = round(c_val * factor, 2)
        
        # Cập nhật giá trị mới vào db
        conn = sqlite3.connect("game.db")
        cur = conn.cursor()
        cur.execute("UPDATE real_estate SET current_value = ? WHERE id = ?", (new_val, prop_id))
        conn.commit()
        conn.close()
        
        profit_loss = new_val - p_price
        color_icon = "📈" if profit_loss >= 0 else "📉"
        embed.add_field(
            name=f"ID [{prop_id}] - {name}",
            value=f"🏷️ Vốn mua: `${p_price:,.2f}`\n💎 Giá hiện tại: `${new_val:,.2f}` ({color_icon} `${profit_loss:+,.2f}`)\n⚡ Rủi ro: {risk}",
            inline=False
        )
        total_val += new_val
        
    embed.set_footer(text=f"Tổng giá trị danh mục BĐS: ${total_val:,.2f} | Dùng !sell_property [ID] để chốt lời/cắt lỗ.")
    await ctx.send(embed=embed)

@bot.command(name="sell_property")
async def sell_property(ctx, prop_id: int):
    user_id = ctx.author.id
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    cursor.execute("SELECT property_name, current_value FROM real_estate WHERE id = ? AND user_id = ?", (prop_id, user_id))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return await ctx.send("❌ Không tìm thấy bất động sản với ID này trong danh mục của bạn!")
        
    name, val = row
    cursor.execute("DELETE FROM real_estate WHERE id = ?", (prop_id,))
    conn.commit()
    conn.close()
    
    player = get_player(user_id)
    player['money'] += val
    update_player(user_id, player)
    
    await ctx.send(f"💰 Đã bán thành công **{name}** (ID: {prop_id}) và thu về **${val:,.2f}** tiền mặt!")

@bot.command(name="tech_tree")
async def show_tech_tree(ctx):
    player = get_player(ctx.author.id)
    embed = discord.Embed(title="🔬 CÂY CÔNG NGHỆ QUÂN SỰ - CÔNG NGHIỆP", color=discord.Color.blue())
    embed.description = (
        f"Cấp độ nghiên cứu hiện tại: **Cấp {player['tech']}**\n\n"
        "🚀 **Nâng cấp Công nghệ Cấp 2**\n"
        "   - Yêu cầu: 50 Thép (Steel) + $5,000\n"
        "   - Hiệu quả: Tăng 2x hiệu suất sản xuất toàn nhà máy!\n"
        "   - Lệnh nghiên cứu: `!research`"
    )
    await ctx.send(embed=embed)

@bot.command(name="research")
async def research_tech(ctx):
    player = get_player(ctx.author.id)
    if player['tech'] >= 2:
        return await ctx.send("🔥 Đã đạt cấp độ công nghệ tối đa hiện tại!")
    
    cost_money, cost_steel = 5000, 50
    if player['money'] < cost_money or player['steel'] < cost_steel:
        return await ctx.send(f"❌ Không đủ nguyên liệu! Cần `${cost_money}` và `{cost_steel} Thép`.")

    player['money'] -= cost_money
    player['steel'] -= cost_steel
    player['tech'] += 1
    update_player(ctx.author.id, player)
    await ctx.send("🎉 Nghiên cứu thành công! Đế chế của bạn đã bước vào kỷ nguyên công nghệ Cấp 2!")

@bot.command(name="pay_debt")
async def pay_debt(ctx, amount: float):
    player = get_player(ctx.author.id)
    if player['money'] < amount: return await ctx.send("❌ Không đủ tiền mặt!")
    actual = min(amount, player['debt'])
    player['money'] -= actual
    player['debt'] -= actual
    update_player(ctx.author.id, player)
    await ctx.send(f"✅ Đã trả bớt `${actual:,.2f}` tiền nợ. Còn lại: `${player['debt']:,.2f}`.")

@bot.command(name="shop")
async def shop(ctx):
    player = get_player(ctx.author.id)
    embed = discord.Embed(title="🛒 CỬA HÀNG QUÂN SỰ", description="!buy_item sungluc ($1500) | !buy_item giap ($2500) | !buy_item thapphao ($6000)", color=discord.Color.gold())
    embed.add_field(name="Chỉ số", value=f"⚔️ Sức mạnh: {player['weapon']} | 🛡️ Giáp: {player['defense']}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="buy_item")
async def buy_item(ctx, code: str):
    player, code = get_player(ctx.author.id), code.lower()
    cost, w, d, name = (1500, 10, 0, "Súng lục") if code=="sungluc" else (2500, 0, 15, "Áo giáp") if code=="giap" else (6000, 25, 15, "Tháp pháo") if code=="thapphao" else (0,0,0,"")
    if not cost or player['money'] < cost: return await ctx.send("❌ Không đủ tiền hoặc sai mã vật phẩm!")
    player['money'] -= cost
    player['weapon'] += w
    player['defense'] += d
    update_player(ctx.author.id, player)
    file = create_vn_image((30, 45, 30), "Quản gia Alfred", f"Đã trang bị {name}! Sẵn sàng chiến đấu.")
    await ctx.send(file=file)

@bot.command(name="transfer")
async def transfer_money(ctx, member: discord.Member, amount: float):
    sender_id = ctx.author.id
    if sender_id == member.id: return await ctx.send("❌ Không thể chuyển tiền cho chính mình!")
    if amount <= 0: return await ctx.send("❌ Số tiền không hợp lệ!")
    
    sender = get_player(sender_id)
    if sender['daily_transferred'] + amount > 5000:
        remaining = 5000 - sender['daily_transferred']
        return await ctx.send(f"⚠️ Vượt hạn mức chuyển tiền trong ngày! Bạn chỉ còn có thể chuyển tối đa `${max(0, remaining)}` nữa hôm nay.")

    if sender['money'] < amount: return await ctx.send("❌ Không đủ tiền mặt trong ví!")
    
    receiver = get_player(member.id)
    sender['money'] -= amount
    sender['daily_transferred'] += amount
    receiver['money'] += amount
    
    update_player(sender_id, sender)
    update_player(member.id, receiver)
    await ctx.send(f"💸 Đã chuyển thành công **${amount:,.2f}** cho {member.mention}! (Đã dùng: `${sender['daily_transferred']}/$5,000` hạn mức ngày)")

@bot.command(name="raid")
async def raid_player(ctx, member: discord.Member):
    attacker_id = ctx.author.id
    if attacker_id == member.id: return await ctx.send("❌ Không thể tự cướp nhà máy của mình!")
    
    attacker = get_player(attacker_id)
    defender = get_player(member.id)
    
    att_power = attacker['weapon'] * 2 + attacker['defense']
    def_power = defender['weapon'] + defender['defense'] * 2
    
    if att_power <= 0:
        return await ctx.send("❌ Quân lực quá yếu! Hãy dùng `!shop` mua súng lục hoặc tháp pháo trước.")
        
    if att_power > def_power:
        loot = min(defender['money'], random.randint(100, 500))
        defender['money'] -= loot
        attacker['money'] += loot
        update_player(attacker_id, attacker)
        update_player(member.id, defender)
        await ctx.send(f"⚔️ **ĐỘT KÍCH THÀNH CÔNG!** Cướp được **${loot}** từ {member.mention}!")
    else:
        fine = min(attacker['money'], 150)
        attacker['money'] -= fine
        update_player(attacker_id, attacker)
        await ctx.send(f"🛡️ **PHÒNG THỦ THÀNH CÔNG!** {member.mention} đã đánh bật cuộc tập kích. Bị phạt **${fine}**!")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
