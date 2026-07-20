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

    # 仅作为未提供用户偏好时的默认值。请求不可修改该类属性。
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

    # 明确维护植物/病害拆分，避免 Bell pepper、Target Spot 等多词类别被错误按空格切分。
    class_metadata = {
        "Tomato leaf": ("Tomato", "番茄", "Healthy leaf", "健康叶片"),
        "Apple leaf": ("Apple", "苹果", "Healthy leaf", "健康叶片"),
        "Grape leaf": ("Grape", "葡萄", "Healthy leaf", "健康叶片"),
        "Strawberry leaf": ("Strawberry", "草莓", "Healthy leaf", "健康叶片"),
        "Peach leaf": ("Peach", "桃树", "Healthy leaf", "健康叶片"),
        "Cherry leaf": ("Cherry", "樱桃", "Healthy leaf", "健康叶片"),
        "Soyabean leaf": ("Soyabean", "大豆", "Healthy leaf", "健康叶片"),
        "Blueberry leaf": ("Blueberry", "蓝莓", "Healthy leaf", "健康叶片"),
        "Raspberry leaf": ("Raspberry", "树莓", "Healthy leaf", "健康叶片"),
        "Bell pepper leaf": ("Bell pepper", "甜椒", "Healthy leaf", "健康叶片"),
        "Potato leaf": ("Potato", "马铃薯", "Healthy leaf", "健康叶片"),
        "Apple rust leaf": ("Apple", "苹果", "Rust", "锈病"),
        "Apple Scab Leaf": ("Apple", "苹果", "Scab", "黑星病"),
        "Bell pepper leaf spot": ("Bell pepper", "甜椒", "Leaf spot", "叶斑病"),
        "Corn Gray leaf spot": ("Corn", "玉米", "Gray leaf spot", "灰斑病"),
        "Corn leaf blight": ("Corn", "玉米", "Leaf blight", "大斑病"),
        "Corn rust leaf": ("Corn", "玉米", "Rust", "锈病"),
        "Grape leaf black rot": ("Grape", "葡萄", "Black rot", "黑腐病"),
        "Potato leaf early blight": ("Potato", "马铃薯", "Early blight", "早疫病"),
        "Potato leaf late blight": ("Potato", "马铃薯", "Late blight", "晚疫病"),
        "Squash Powdery mildew leaf": ("Squash", "南瓜", "Powdery mildew", "白粉病"),
        "Tomato Early blight leaf": ("Tomato", "番茄", "Early blight", "早疫病"),
        "Tomato leaf bacterial spot": ("Tomato", "番茄", "Bacterial spot", "细菌性斑点病"),
        "Tomato leaf late blight": ("Tomato", "番茄", "Late blight", "晚疫病"),
        "Tomato leaf mosaic virus": ("Tomato", "番茄", "Mosaic virus", "花叶病毒病"),
        "Tomato leaf yellow virus": ("Tomato", "番茄", "Yellow virus", "黄化病毒病"),
        "Tomato mold leaf": ("Tomato", "番茄", "Leaf mold", "叶霉病"),
        "Tomato Septoria leaf spot": ("Tomato", "番茄", "Septoria leaf spot", "白星病"),
        "Tomato two spotted spider mites leaf": ("Tomato", "番茄", "Two spotted spider mites", "二斑叶螨危害"),
        "Tomato Target Spot leaf": ("Tomato", "番茄", "Target Spot", "靶斑病"),
    }

    @classmethod
    def display_class_name(
        cls,
        class_name: str,
        class_names_cn: dict | None = None,
        display_language: str | None = None,
    ) -> str:
        """根据显示语言和场景映射返回用户可见的类别名。"""
        language = (display_language or cls.display_language).lower()
        if language != "zh":
            return class_name
        scene_mapping = class_names_cn or {}
        return (
            scene_mapping.get(class_name)
            or cls.class_names_cn.get(class_name)
            or class_name
        )

    @classmethod
    def class_display_info(
        cls,
        class_name: str,
        class_names_cn: dict | None = None,
        display_language: str | None = None,
    ) -> dict:
        """返回类别、植物和病害的统一显示字段，供历史、检测和分析接口复用。"""
        plant_name = None
        plant_name_cn = None
        disease_name = None
        disease_name_cn = None
        metadata = cls.class_metadata.get(class_name)
        if metadata:
            plant_name, plant_name_cn, disease_name, disease_name_cn = metadata

        language = (display_language or cls.display_language).lower()
        class_name_display = cls.display_class_name(
            class_name, class_names_cn, display_language
        )
        return {
            "class_name": class_name,
            "class_name_display": class_name_display,
            "plant_name": plant_name,
            "plant_name_display": plant_name_cn if language == "zh" else plant_name,
            "disease_name": disease_name,
            "disease_name_display": disease_name_cn if language == "zh" else disease_name,
        }

    @classmethod
    def class_names_for_plant(cls, plant_name: str) -> list[str]:
        """按植物英文名或中文名返回所有对应 YOLO 类别，用于历史筛选。"""
        normalized = plant_name.strip().lower()
        matches = []
        for class_name, (plant_en, plant_cn, _disease_en, _disease_cn) in cls.class_metadata.items():
            if normalized in {plant_en.lower(), plant_cn.lower()}:
                matches.append(class_name)
        return matches
