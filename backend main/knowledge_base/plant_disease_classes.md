# 植物病害检测类别说明

## 文档用途

本项目当前模型使用植物叶片数据集类别。模型内部保留英文类别名，用户界面默认使用中文类别名。中文名称用于展示，不改变模型权重中的类别 ID。

## 当前类别映射

| 类别 ID | 模型类别名 | 中文显示名 |
|---:|---|---|
| 0 | Tomato leaf | 番茄健康叶片 |
| 1 | Apple leaf | 苹果健康叶片 |
| 2 | Grape leaf | 葡萄健康叶片 |
| 3 | Strawberry leaf | 草莓健康叶片 |
| 4 | Peach leaf | 桃树健康叶片 |
| 5 | Cherry leaf | 樱桃健康叶片 |
| 6 | Soyabean leaf | 大豆健康叶片 |
| 7 | Blueberry leaf | 蓝莓健康叶片 |
| 8 | Raspberry leaf | 树莓健康叶片 |
| 9 | Bell pepper leaf | 甜椒健康叶片 |
| 10 | Potato leaf | 马铃薯健康叶片 |
| 11 | Apple rust leaf | 苹果锈病 |
| 12 | Apple Scab Leaf | 苹果黑星病 |
| 13 | Bell pepper leaf spot | 甜椒叶斑病 |
| 14 | Corn Gray leaf spot | 玉米灰斑病 |
| 15 | Corn leaf blight | 玉米大斑病 |
| 16 | Corn rust leaf | 玉米锈病 |
| 17 | Grape leaf black rot | 葡萄黑腐病 |
| 18 | Potato leaf early blight | 马铃薯早疫病 |
| 19 | Potato leaf late blight | 马铃薯晚疫病 |
| 20 | Squash Powdery mildew leaf | 南瓜白粉病 |
| 21 | Tomato Early blight leaf | 番茄早疫病 |
| 22 | Tomato leaf bacterial spot | 番茄细菌性斑点病 |
| 23 | Tomato leaf late blight | 番茄晚疫病 |
| 24 | Tomato leaf mosaic virus | 番茄花叶病毒病 |
| 25 | Tomato leaf yellow virus | 番茄黄化病毒病 |
| 26 | Tomato mold leaf | 番茄叶霉病 |
| 27 | Tomato Septoria leaf spot | 番茄白星病 |
| 28 | Tomato two spotted spider mites leaf | 番茄二斑叶螨危害 |
| 29 | Tomato Target Spot leaf | 番茄靶斑病 |

## 结果字段说明

- `class_name`：模型内部英文类别名，便于代码和数据库保持稳定。
- `class_name_cn`：中文类别名，没有映射时可能为空。
- `class_name_display`：根据 `DetectionConfig.display_language` 选择的用户显示名。
- `class_counts`：内部类别名统计。
- `class_counts_display`：用户显示语言对应的类别统计。

默认配置为中文显示。将 `backend/app/config/detection.py` 中的 `DetectionConfig.display_language` 改为 `"en"` 可以切换为英文显示。未配置映射的类别会回退到模型原始类别名。

## 使用边界

“健康叶片”是训练数据中的类别名，不表示整株植物一定健康。“病害”类别是模型对图像外观的识别结果，不等同于经过实验室或农技人员确认的最终诊断。实际判断还应考虑作物品种、生育期、环境、病虫害历史和现场症状。

## 参考来源

- 本项目 `backend/app/services/dataset_service.py` 的 `PLANT_DISEASE_CLASSES`。
- 本项目 `backend/app/config/detection.py` 的中文显示映射。
- 具体病害防治应以当地农业技术部门、农药登记标签和权威植保资料为准。
