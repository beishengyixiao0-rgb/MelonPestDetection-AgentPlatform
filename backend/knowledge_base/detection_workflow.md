# 植物病害检测平台使用与结果说明

## 平台能力

本平台提供以下检测方式：

1. 单张图片检测：识别一张叶片图片并返回检测框、类别、置信度和标注图。
2. 批量图片检测：一次处理多张图片并汇总类别数量。
3. ZIP 图片检测：解压 ZIP 中的图片后执行批量检测。
4. 视频检测：按采样间隔处理视频帧，生成标注视频和关键帧结果。
5. Agent 检测：用户使用自然语言和附件，Agent 根据附件类型调用对应检测工具。

## Agent 工具

- `detect_single_image`：单张图片。
- `detect_batch_images`：多张图片。
- `detect_zip_images_file`：ZIP 图片包。
- `detect_video_file`：视频文件。

当没有配置外部 LLM 时，系统可以根据附件扩展名进入本地降级路径。视频附件只能单独上传，不能与图片或其他视频混合上传。

## 单图结果字段

常见结果字段包括：

- `total_objects`：图片中检测到的目标数量。
- `detections`：每个目标的类别、置信度和边界框。
- `class_counts`：按模型内部类别名统计。
- `class_counts_display`：按当前显示语言统计。
- `annotated_image_base64` 或 `annotated_image_url`：带检测框的图片。
- `inference_time`：本次推理耗时，单位为毫秒。

## 检测框如何阅读

边界框通常表示为 `[x1, y1, x2, y2]`：

- `(x1, y1)` 是左上角坐标。
- `(x2, y2)` 是右下角坐标。
- 坐标原点位于图片左上角，单位是像素。
- 框上的中文类别名是用户显示名，后面的数值是置信度。

## 结果可靠性

检测结果受图片清晰度、拍摄角度、叶片遮挡、光照和训练数据覆盖范围影响。不能仅凭单张检测结果做药剂选择。建议结合原图、标注图、置信度和专业人员意见判断。

## Agent 路径的视频播放

视频检测会分别生成源视频地址和标注视频地址。为了兼容浏览器，后端会尽量将源视频转换为 H.264/AAC 格式后提供播放。标注视频包含检测框，源视频不包含检测框。

## 参考来源

- 本项目 `backend/app/agent/detection_agent.py` 的工具选择逻辑。
- 本项目 `backend/app/services/detection_service.py` 的检测结果结构。
- 本项目 `frontend/src/components/DetectionResultCard.vue` 的结果展示逻辑。
