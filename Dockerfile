FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    libreoffice \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 浏览器
RUN python -m playwright install --with-deps chromium

# 复制项目
COPY . .

# 创建下载目录
RUN mkdir -p downloads

EXPOSE 7860

CMD ["python", "app.py"]
