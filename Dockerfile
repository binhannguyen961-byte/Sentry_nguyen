# Sử dụng Python 3.10 mỏng nhẹ
FROM python:3.10-slim

# Cài đặt các thư viện hệ thống (Đã thay libgl1-mesa-glx thành libgl1)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libgl1 \
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
