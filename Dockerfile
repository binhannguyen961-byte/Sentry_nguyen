# Sử dụng Python 3.10 mỏng nhẹ
FROM python:3.10-slim

# Cài đặt các công cụ hệ thống bắt buộc: FFmpeg, Opus (Cho Voice), OpenCV dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy requirement và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Chạy Bot
CMD ["python", "main.py"]
