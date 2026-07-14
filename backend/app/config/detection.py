# 文件路径: D:\Project\team\backend\app\config\detection.py


class DetectionConfig:
    """检测配置"""

    # 核心：直接指向下载好的云端模型
    model_path = "models/plant_disease_best.pt"

    # 推理参数
    conf_threshold = 0.25
    iou_threshold = 0.45
    device = "cpu"  # 本地如果没显卡，必须写 cpu
    image_size = 640
    max_batch_size = 50
