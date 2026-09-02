FROM python:3.10-slim

# Cài đặt ffmpeg và các công cụ hệ thống cần thiết cho voice
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libffi-dev \
    libnacl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sao chép requirements và cài đặt thư viện python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn bot vào container
COPY . .

# Chạy bot
CMD ["python", "main.py"]
