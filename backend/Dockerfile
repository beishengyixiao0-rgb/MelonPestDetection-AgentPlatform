 # =============================================================
 # 后端 — Python + PyTorch CPU（避免 CUDA 镜像 ~4GB 体积）
 # 最终镜像约 ~2GB（主要是 PyTorch CPU 约 800MB）
 # =============================================================

 FROM python:3.11-slim

 WORKDIR /app

 # 安装系统依赖（OpenCV 等需要）
 RUN apt-get update && apt-get install -y \
     libgl1 \
     libglib2.0-0 \
     && rm -rf /var/lib/apt/lists/*

 # 先安装 CPU-only PyTorch（缩小镜像体积）
 RUN pip install --no-cache-dir torch torchvision \
     --index-url https://download.pytorch.org/whl/cpu

 # 复制依赖文件并安装其余 Python 包
 COPY requirements.txt .
 RUN pip install --no-cache-dir -r requirements.txt

 # 复制项目代码
 COPY . .

 EXPOSE 8000

 CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
