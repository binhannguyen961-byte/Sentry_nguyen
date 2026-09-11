import asyncio
import json
import os
import textwrap
import threading
import io

from discord.ext import commands
from discord.ui import Button, View
import discord
from flask import Flask
from PIL import Image, ImageDraw, ImageFont

# --- CẤU HÌNH BOT CƠ BẢN ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)

ASSETS_DIR = "assets"
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

def get_asset(filename):
    return os.path.join(ASSETS_DIR, filename)

app = Flask(__name__)
@app.route("/")
def home():
    return "DDLC Offline Story Engine Online!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- CẤU HÌNH MÀU SẮC NHÂN VẬT ---
CHAR_COLORS = {
    "Sayori": (255, 160, 180),
    "Yuri": (180, 140, 230),
    "Natsuki": (255, 130, 170),
    "Monika": (120, 220, 160),
    "Bác sĩ": (100, 200, 255),
    "Nội tâm": (180, 180, 180),
    "System": (200, 200, 200),
}

# --- CÂY CỐT TRUYỆN (CẬP NHẬT THEO ASSETS GITHUB) ---
STORY_TREE = {
    "ch1_start": {
        "chapter": 1,
        "speaker": "Nội tâm",
        "location": "Phòng Bệnh 404",
        "bg": "hospital.jpg",
        "text": "Tiếng 'tít... tít...' vang lên đều đặn. Mùi thuốc sát trùng xộc vào mũi. Bạn tỉnh dậy với cơ thể nặng trĩu sau vụ tai nạn hôm qua...",
        "choices": [
            {"label": "Cố gắng mở hẳn mắt ra và ngồi dậy", "next": "ch1_end"},
            {"label": "Nhấn nút gọi y tá ở đầu giường", "next": "ch1_end"}
        ]
    },
    "ch1_end": {
        "chapter": 1,
        "speaker": "Bác sĩ",
        "location": "Phòng Bệnh 404",
        "bg": "hospital.jpg",
        "text": "Cậu tỉnh rồi à? May mắn là không có chấn thương nghiêm trọng. Cậu có thể xuất viện ngay chiều nay. Có mấy cô bé đang đợi cậu ngoài kia đấy.",
        "choices": [
            {"label": "Làm thủ tục xuất viện", "next": "ch2_start"}
        ]
    },
    "ch2_start": {
        "chapter": 2,
        "speaker": "Sayori",
        "location": "Đường Về Nhà",
        "bg": "street_sayori.JPEG",
        "text": "Y/N!!! Cậu ngốc nghếch này! Tớ đã lo muốn chết đi được! Để tớ dìu cậu về nhà nhé, bác sĩ bảo cậu vẫn cần đi lại cẩn thận đấy.",
        "choices": [
            {"label": "Đồng ý để Sayori dìu về", "next": "ch2_sayori"},
            {"label": "Trêu Sayori, bảo rằng mình tự đi được", "next": "ch2_natsuki"}
        ]
    },
    "ch2_sayori": {
        "chapter": 2,
        "speaker": "Sayori",
        "location": "Đường Về Nhà",
        "bg": "street_sayori.JPEG",
        "text": "Ehehe... Tớ hứa sẽ không bao giờ để cậu đi bộ về một mình nữa! Cậu mau khỏe lại để còn tham gia sinh hoạt Câu Lạc Bộ nhé.",
        "choices": [
            {"label": "Về đến nhà và nghỉ ngơi đến cuối tuần", "next": "ch3_start"}Based on the screenshots you shared, it looks like you're viewing a GitHub repository on a mobile browser. The files appear to be game or visual novel assets—specifically, character sprites or backgrounds featuring characters from *Doki Doki Literature Club* (Monika, Natsuki, Sayori, and Yuri) across various locations. 

Here is the combined list of files visible across both `image_2.png` and `image_3.png`:

**Images (.JPEG, .jpg)**
*   `cafe_monika.JPEG`
*   `cafe_natsuki.JPEG`
*   `cafe_sayori.JPEG`
*   `cafe_yuri.JPEG`
*   `club_monika.JPEG`
*   `club_natsuki.JPEG`
*   `club_sayori.jpg`
*   `club_yuri.jpg`
*   `hospital.jpg` (uploaded "now")
*   `park_monika.JPEG`
*   `park_natsuki.JPEG`
*   `park_sayori.JPEG`
*   `park_yuri.JPEG`
*   `street_monika.JPEG`
*   `street_natsuki.JPEG`
*   `street_sayori.JPEG`
*   `street_yuri.JPEG`

**Audio (.mp3)**
*   `club.mp3`
*   `romance.mp3`
*   `street.mp3`

**Other Files**
*   `font_regular.ttf`
*   `README.md`

How would you like me to help you with these? For example, I can format this list into a specific data type (like JSON or CSV), help you organize them into folders, or assist with a script you might be writing for these assets.
