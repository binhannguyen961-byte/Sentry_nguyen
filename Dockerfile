FROM python:3.10-slim

# Cài đặt các gói hệ thống cần thiết cho voice và biên dịch thư viện Python
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libopus0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements và cài đặt python packages (đảm bảo có discord.py[voice] hoặc PyNaCl)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
