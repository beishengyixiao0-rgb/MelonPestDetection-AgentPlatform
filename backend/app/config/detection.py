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

    # 显示配置：改为 "en" 即可恢复英文类别名；未配置中文映射的类别自动回退英文。
    display_language = "zh"
    font_path = ""  # 可指定自定义 CJK 字体；留空时自动查找系统字体。

    # Plant Disease Detection 数据集的显示名称。模型内部类别名仍保留英文，
    # 仅在 API 返回、标注框和前端列表中使用 display_name。
    class_names_cn = {
        "Tomato leaf": "番茄健康叶片",
        "Apple leaf": "苹果健康叶片",
        "Grape leaf": "葡萄健康叶片",
        "Strawberry leaf": "草莓健康叶片",
        "Peach leaf": "桃树健康叶片",
        "Cherry leaf": "樱桃健康叶片",
        "Soyabean leaf": "大豆健康叶片",
        "Blueberry leaf": "蓝莓健康叶片",
        "Raspberry leaf": "树莓健康叶片",
        "Bell pepper leaf": "甜椒健康叶片",
        "Potato leaf": "马铃薯健康叶片",
        "Apple rust leaf": "苹果锈病",
        "Apple Scab Leaf": "苹果黑星病",
        "Bell pepper leaf spot": "甜椒叶斑病",
        "Corn Gray leaf spot": "玉米灰斑病",
        "Corn leaf blight": "玉米大斑病",
        "Corn rust leaf": "玉米锈病",
        "Grape leaf black rot": "葡萄黑腐病",
        "Potato leaf early blight": "马铃薯早疫病",
        "Potato leaf late blight": "马铃薯晚疫病",
        "Squash Powdery mildew leaf": "南瓜白粉病",
        "Tomato Early blight leaf": "番茄早疫病",
        "Tomato leaf bacterial spot": "番茄细菌性斑点病",
        "Tomato leaf late blight": "番茄晚疫病",
        "Tomato leaf mosaic virus": "番茄花叶病毒病",
        "Tomato leaf yellow virus": "番茄黄化病毒病",
        "Tomato mold leaf": "番茄叶霉病",
        "Tomato Septoria leaf spot": "番茄白星病",
        "Tomato two spotted spider mites leaf": "番茄二斑叶螨危害",
        "Tomato Target Spot leaf": "番茄靶斑病",
    }

    @classmethod
    def display_class_name(
        cls,
        class_name: str,
        class_names_cn: dict | None = None,
    ) -> str:
        """根据显示语言和场景映射返回用户可见的类别名。"""
        if cls.display_language.lower() != "zh":
            return class_name
        scene_mapping = class_names_cn or {}
        return scene_mapping.get(class_name) or cls.class_names_cn.get(class_name) or class_name
