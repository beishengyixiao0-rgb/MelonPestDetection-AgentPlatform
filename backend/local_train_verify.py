# 文件名: local_train_verify.py（本地训练验证脚本）
# 路径: D:\Project\team\backend\local_train_verify.py

import os

from ultralytics import YOLO

# 1. 配置你的路径
# 假设你的本地数据集放在 D:\Project\team\datasets\PlantDiseaseDetection\
# 请根据你的实际绝对路径修改下面的路径
DATA_YAML = "D:/Project/team/datasets/PlantDiseaseDetection/data.yaml"
OUTPUT_DIR = "runs/local_verify"  # 输出到 backend/runs/local_verify

# 检查文件是否存在
if not os.path.exists(DATA_YAML):
    print(f"❌ 错误: 找不到 data.yaml! 请检查路径: {DATA_YAML}")
    exit(1)

print("✅ 找到 data.yaml，准备加载模型...")

# 2. 加载预训练模型
# 确保 D:\Project\team\backend\models\ 下有 yolov11n.pt
model = YOLO("models/yolov11n.pt")

print("🔥 开始本地 CPU 训练 (5个 Epoch，预计10-15分钟)...")
print("训练参数: epochs=5, batch_size=4, device=cpu")

# 3. 开始训练
results = model.train(
    data=DATA_YAML,
    epochs=5,  # 训练5轮
    imgsz=640,
    batch=4,  # CPU 显存/内存小，batch 设小点
    device="cpu",  # 强制指定 CPU
    project=OUTPUT_DIR,
    name="local_5_epoch_test",  # 实验名称
    exist_ok=True,
    optimizer="SGD",
    lr0=0.01,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=15.0,
    translate=0.1,
    scale=0.5,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.0,
)

print("🎉 本地 5 轮训练验证完成！")
print(f"📁 模型保存在: {OUTPUT_DIR}/local_5_epoch_test/weights/best.pt")
