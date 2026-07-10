#!/usr/bin/env python3
"""
YOLO 数据集验证脚本 (增强版 - 适配 PlantDiseaseDetection 项目)
修正了 Windows 下的路径查找逻辑。
"""

import os
import sys
from pathlib import Path

# ============================================
# 配置区域 (根据你的项目实际情况修改)
# ============================================

# 关键修改：获取当前脚本的绝对路径，然后找它的 父级目录的父级目录 (也就是 team 根目录)
# 不管你在哪里运行脚本，它都能正确找到 PROJECT_ROOT
CURRENT_FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE_PATH.parent.parent  # 结果指向 D:\Project\team

# 默认数据集目录 (你的实际路径)
DEFAULT_DATASET_DIR = PROJECT_ROOT / "datasets" / "PlantDiseaseDetection"

# 支持的图片扩展名
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def load_yaml_classes(dataset_path: Path) -> dict:
    """从 data.yaml 中读取类别名称映射"""
    yaml_path = dataset_path / "data.yaml"
    if not yaml_path.exists():
        print(f"[警告] data.yaml 文件不存在: {yaml_path}")
        return {}

    try:
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        names = config.get("names", {})
        # 处理 list 格式的 names (如: names: ['apple', 'banana'])
        if isinstance(names, list):
            return {i: name for i, name in enumerate(names)}
        # 处理 dict 格式的 names
        return names
    except Exception as e:
        print(f"[错误] 解析 data.yaml 失败: {e}")
        return {}


def verify_dataset(dataset_dir: str) -> dict:
    """验证 YOLO 数据集完整性，返回详细的验证结果"""
    dataset_path = Path(dataset_dir)
    results = {
        "total_images": 0,
        "total_labels": 0,
        "total_annotations": 0,
        "missing_labels": [],
        "missing_images": [],
        "empty_labels": 0,
        "invalid_format": [],
        "out_of_range": [],
        "class_distribution": {},
        "class_names": {},
        "bbox_stats": {
            "total": 0,
            "avg_width": 0,
            "avg_height": 0,
            "max_width": 0,
            "max_height": 0,
            "min_width": float("inf"),
            "min_height": float("inf"),
            "small_boxes": 0,
            "large_boxes": 0,
        },
        "split_stats": {},
        "has_warnings": False,
    }

    # 加载类别名称
    results["class_names"] = load_yaml_classes(dataset_path)

    # 遍历每个 split (train/val/test)
    for split in ["train", "val", "test"]:
        img_dir = dataset_path / "images" / split
        lbl_dir = dataset_path / "labels" / split

        split_result = {
            "images": 0,
            "labels": 0,
            "annotations": 0,
            "missing_labels": 0,
            "missing_images": 0,
            "class_distribution": {},
        }

        # 检查目录是否存在
        if not img_dir.exists():
            if split != "test":  # test 目录可选
                print(f"[警告] 缺少目录: {img_dir}")
            results["split_stats"][split] = split_result
            continue
        if not lbl_dir.exists():
            print(f"[警告] 缺少目录: {lbl_dir}")
            results["split_stats"][split] = split_result
            continue

        # 获取文件名(不含扩展名)
        image_files = {
            f.stem for f in img_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS
        }
        label_files = {f.stem for f in lbl_dir.iterdir() if f.suffix == ".txt"}

        # 找不匹配的文件
        missing_labels = image_files - label_files
        missing_images = label_files - image_files

        split_result["images"] = len(image_files)
        split_result["labels"] = len(label_files)
        split_result["missing_labels"] = len(missing_labels)
        split_result["missing_images"] = len(missing_images)

        results["missing_labels"].extend([f"{split}/{name}" for name in missing_labels])
        results["missing_images"].extend([f"{split}/{name}" for name in missing_images])
        results["total_images"] += len(image_files)
        results["total_labels"] += len(label_files)

        # 遍历标注文件检查格式
        bbox_widths, bbox_heights = [], []
        for label_file in lbl_dir.glob("*.txt"):
            content = label_file.read_text(encoding="utf-8").strip()
            if not content:
                results["empty_labels"] += 1
                continue

            for line_num, line in enumerate(content.split("\n"), 1):
                parts = line.strip().split()
                if len(parts) != 5:
                    results["invalid_format"].append(
                        f"{split}/{label_file.name}:{line_num} (期望5个值, 实际{len(parts)})"
                    )
                    continue

                try:
                    class_id = int(parts[0])
                except ValueError:
                    results["invalid_format"].append(
                        f"{split}/{label_file.name}:{line_num} (class_id 非整数)"
                    )
                    continue

                # 更新类别分布
                results["class_distribution"][class_id] = (
                    results["class_distribution"].get(class_id, 0) + 1
                )
                split_result["class_distribution"][class_id] = (
                    split_result["class_distribution"].get(class_id, 0) + 1
                )
                results["total_annotations"] += 1
                split_result["annotations"] += 1

                try:
                    coords = [float(v) for v in parts[1:]]
                    x_center, y_center, width, height = coords
                    # 检查归一化坐标是否在 [0, 1] 范围内
                    field_names = ["x_center", "y_center", "width", "height"]
                    for i, v in enumerate(coords):
                        if v < 0 or v > 1:
                            results["out_of_range"].append(
                                f"{split}/{label_file.name}:{line_num} {field_names[i]}={v:.6f}"
                            )
                            break
                    bbox_widths.append(width)
                    bbox_heights.append(height)
                except ValueError:
                    results["invalid_format"].append(
                        f"{split}/{label_file.name}:{line_num} (坐标值非浮点数)"
                    )

        # 更新边界框统计
        if bbox_widths:
            results["bbox_stats"]["total"] += len(bbox_widths)
            results["bbox_stats"]["avg_width"] += sum(bbox_widths)
            results["bbox_stats"]["avg_height"] += sum(bbox_heights)
            results["bbox_stats"]["max_width"] = max(
                results["bbox_stats"]["max_width"], max(bbox_widths)
            )
            results["bbox_stats"]["max_height"] = max(
                results["bbox_stats"]["max_height"], max(bbox_heights)
            )
            results["bbox_stats"]["min_width"] = min(
                results["bbox_stats"]["min_width"], min(bbox_widths)
            )
            results["bbox_stats"]["min_height"] = min(
                results["bbox_stats"]["min_height"], min(bbox_heights)
            )
            # 统计小目标和大目标
            results["bbox_stats"]["small_boxes"] += sum(
                1 for w, h in zip(bbox_widths, bbox_heights) if w * h < 0.001
            )
            results["bbox_stats"]["large_boxes"] += sum(
                1 for w, h in zip(bbox_widths, bbox_heights) if w * h > 0.5
            )

        results["split_stats"][split] = split_result

    # 计算平均值
    if results["bbox_stats"]["total"] > 0:
        results["bbox_stats"]["avg_width"] /= results["bbox_stats"]["total"]
        results["bbox_stats"]["avg_height"] /= results["bbox_stats"]["total"]

    return results


def print_report(results: dict):
    """打印格式化的验证报告"""
    print("\n" + "=" * 70)
    print(" YOLO 数据集验证报告")
    print("=" * 70)

    # 总体统计
    print("\n [总体统计]")
    print(f"  图像总数: {results['total_images']}")
    print(f"  标注文件数: {results['total_labels']}")
    print(f"  标注目标数: {results['total_annotations']}")
    print(f"  空标注文件: {results['empty_labels']}")
    if results["total_images"] > 0:
        print(
            f"  平均每图标注: {results['total_annotations'] / results['total_images']:.2f}"
        )

    # Split 统计
    print("\n [Split 统计]")
    for split in ["train", "val", "test"]:
        stats = results["split_stats"].get(split, {})
        print(
            f"  {split}: {stats.get('images', 0)} 图像, {stats.get('labels', 0)} 标注, {stats.get('annotations', 0)} 目标"
        )

    # 警告检查
    if results["missing_labels"]:
        print(f"\n [警告] 缺少标注文件 {len(results['missing_labels'])} 个 (前5个):")
        for name in results["missing_labels"][:5]:
            print(f"   - {name}")
        if len(results["missing_labels"]) > 5:
            print(f"   ... 还有 {len(results['missing_labels']) - 5} 个")
        results["has_warnings"] = True

    if results["missing_images"]:
        print(f"\n [警告] 缺少图像文件 {len(results['missing_images'])} 个 (前5个):")
        for name in results["missing_images"][:5]:
            print(f"   - {name}")
        if len(results["missing_images"]) > 5:
            print(f"   ... 还有 {len(results['missing_images']) - 5} 个")
        results["has_warnings"] = True

    if results["invalid_format"]:
        print(f"\n [错误] 格式错误 {len(results['invalid_format'])} 处 (前5处):")
        for item in results["invalid_format"][:5]:
            print(f"   - {item}")
        if len(results["invalid_format"]) > 5:
            print(f"   ... 还有 {len(results['invalid_format']) - 5} 处")
        results["has_warnings"] = True

    if results["out_of_range"]:
        print(f"\n [警告] 坐标越界 {len(results['out_of_range'])} 处 (前5处):")
        for item in results["out_of_range"][:5]:
            print(f"   - {item}")
        if len(results["out_of_range"]) > 5:
            print(f"   ... 还有 {len(results['out_of_range']) - 5} 处")
        results["has_warnings"] = True

    # 类别分布
    print("\n [类别分布]")
    class_names = results["class_names"]
    total = results["total_annotations"] or 1
    dist = results["class_distribution"]
    if dist:
        max_count = max(dist.values())
        min_count = min(dist.values())
        imbalance_ratio = max_count / min_count if min_count > 0 else 0

        for class_id in sorted(dist.keys()):
            count = dist[class_id]
            percentage = (count / total) * 100
            # 获取类别名，并统一转换为字符串（支持数字和文字）
            raw_name = class_names.get(class_id, f"class_{class_id}")
            # 关键修改：用 {raw_name!s:<12} 强制转字符串并靠左占12位，不再区分 int/str
            class_name_display = f"{raw_name!s:<12}"

            bar_length = int((count / max_count) * 40) if max_count > 0 else 0
            bar = "█" * bar_length
            print(
                f"  {class_id:2d}. {class_name_display} {count:6d} 个 ({percentage:5.2f}%) {bar}"
            )

        if imbalance_ratio > 10:
            print(f"\n [警告] 类别严重不平衡! 最大/最小比例 = {imbalance_ratio:.1f}:1")
            print("   建议: 增加少数类样本或使用数据增强技术")
            results["has_warnings"] = True
        elif imbalance_ratio > 5:
            print(f"\n [提示] 类别存在一定不平衡, 比例 = {imbalance_ratio:.1f}:1")

    # 边界框统计
    print("\n [边界框统计]")
    bbox = results["bbox_stats"]
    if bbox["total"] > 0:
        print(f"  边界框总数: {bbox['total']}")
        print(f"  平均宽度: {bbox['avg_width']:.4f}")
        print(f"  平均高度: {bbox['avg_height']:.4f}")
        print(f"  最小宽度: {bbox['min_width']:.4f}")
        print(f"  最小高度: {bbox['min_height']:.4f}")
        print(f"  最大宽度: {bbox['max_width']:.4f}")
        print(f"  最大高度: {bbox['max_height']:.4f}")
        print(
            f"  小目标 (面积<0.001): {bbox['small_boxes']} 个 ({bbox['small_boxes'] / bbox['total'] * 100:.1f}%)"
        )
        print(
            f"  大目标 (面积>0.5): {bbox['large_boxes']} 个 ({bbox['large_boxes'] / bbox['total'] * 100:.1f}%)"
        )
        if bbox["small_boxes"] / bbox["total"] > 0.3:
            print("\n [提示] 小目标占比较高 (>30%), 建议使用合适的锚框配置")

    # 最终结论
    print(f"\n{'=' * 70}")
    if results["has_warnings"]:
        print(" 结果: 数据集存在问题或警告, 请根据上述信息修复")
    else:
        print(" 结果: 数据验证通过, 可以开始训练")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    # 优先使用命令行参数，否则使用默认配置
    if len(sys.argv) > 1:
        dataset_dir = sys.argv[1]
    else:
        dataset_dir = str(DEFAULT_DATASET_DIR)
        print(f"[信息] 未指定数据集路径，使用默认路径: {dataset_dir}")
        print(
            "[信息] 如需指定其他路径，请使用: python ../tools/verify_dataset.py <你的数据集路径>"
        )

    if not os.path.exists(dataset_dir):
        print(f"[错误] 数据集目录不存在: {dataset_dir}")
        print("请检查目录路径是否正确")
        sys.exit(1)

    results = verify_dataset(dataset_dir)
    print_report(results)
