FROM python:3.10-slim

# Cài đặt các gói hệ thống cho OpenCV, Voice (libopus, libffi) và đồ họa
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libopus0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxcb1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy file requirements và cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn và thư mục assets vào container
COPY . .

# Chạy file chính của Nam (đã đổi đúng tên là main.py)
CMD ["python", "main.py"]
