#!/usr/bin/env python3
import os
import sys
import warnings

# ==========================================
# 修复 Windows MINGW 崩溃的核心代码
# ==========================================
os.environ["OPENCV_OPENCL_RUNTIME"] = ""
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "0"
warnings.filterwarnings("ignore")
# ==========================================

import argparse
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# --- 修改后的路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

DEFAULT_DATASET_DIR = os.path.join(PROJECT_ROOT, "datasets", "PlantDiseaseDetection")
DEFAULT_OUTPUT_DIR = os.path.join(
    PROJECT_ROOT, "datasets", "PlantDiseaseDetection", "vis_output"
)
# -----------------------

# BGR 颜色调色板
COLORS = [
    (0, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
    (255, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
    (128, 255, 0),
    (255, 128, 0),
    (0, 128, 255),
    (128, 0, 255),
    (255, 255, 128),
    (128, 255, 255),
    (255, 128, 255),
    (0, 128, 128),
    (128, 0, 128),
    (128, 128, 0),
    (64, 255, 64),
    (255, 64, 64),
    (64, 64, 255),
    (255, 200, 0),
]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def load_class_names(dataset_dir: str) -> Dict[int, str]:
    """从 data.yaml 加载类别名称"""
    yaml_path = os.path.join(dataset_dir, "data.yaml")
    names = {}
    if not os.path.exists(yaml_path):
        print(f"[警告] 未找到 data.yaml: {yaml_path}")
        return names
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            in_names = False
            for line in f:
                line = line.strip()
                if line.startswith("names:"):
                    in_names = True
                    continue
                if in_names and line:
                    if line[0].isdigit():
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            names[int(parts[0].strip())] = parts[1].strip()
                    elif not line:
                        break
    except Exception as e:
        print(f"[错误] 解析 data.yaml 失败: {e}")
    return names


def draw_yolo_annotations(
    image: np.ndarray,
    label_file: str,
    class_names: Dict[int, str],
    thickness: int = 2,
    font_scale: float = 0.6,
) -> np.ndarray:
    if image is None:
        return np.zeros((640, 640, 3), dtype=np.uint8)
    img_h, img_w = image.shape[:2]
    if not os.path.exists(label_file):
        return image
    try:
        with open(label_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                class_id, x_center, y_center, width, height = map(float, parts)
                class_id = int(class_id)
            except ValueError:
                continue
            x1 = int((x_center - width / 2) * img_w)
            y1 = int((y_center - height / 2) * img_h)
            x2 = int((x_center + width / 2) * img_w)
            y2 = int((y_center + height / 2) * img_h)
            x1, y1, x2, y2 = (
                max(0, min(x1, img_w - 1)),
                max(0, min(y1, img_h - 1)),
                max(0, min(x2, img_w - 1)),
                max(0, min(y2, img_h - 1)),
            )
            color = COLORS[class_id % len(COLORS)]
            class_name = class_names.get(class_id, f"class_{class_id}")
            cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
            (text_w, text_h), _ = cv2.getTextSize(
                class_name, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
            )
            label_y = max(y1, text_h + 10)
            cv2.rectangle(
                image, (x1, label_y - text_h - 10), (x1 + text_w, label_y), color, -1
            )
            cv2.putText(
                image,
                class_name,
                (x1, label_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                1,
            )
    except Exception:
        pass
    return image


def collect_image_label_pairs(
    dataset_dir: str, splits: Optional[List[str]] = None
) -> List[Tuple[str, str, str, str]]:
    if splits is None:
        splits = ["train", "val", "test"]
    pairs = []
    for split in splits:
        img_dir = os.path.join(dataset_dir, "images", split)
        lbl_dir = os.path.join(dataset_dir, "labels", split)
        if not os.path.exists(img_dir):
            continue
        for fname in os.listdir(img_dir):
            if Path(fname).suffix.lower() not in IMAGE_EXTS:
                continue
            pairs.append(
                (
                    os.path.join(img_dir, fname),
                    os.path.join(lbl_dir, f"{Path(fname).stem}.txt"),
                    split,
                    fname,
                )
            )
    return pairs


def visualize_random_samples(
    dataset_dir: str,
    output_dir: Optional[str] = None,
    count: int = 5,
    splits: Optional[List[str]] = None,
    class_names: Optional[Dict[int, str]] = None,
):
    if class_names is None:
        class_names = load_class_names(dataset_dir)
    pairs = collect_image_label_pairs(dataset_dir, splits)
    if not pairs:
        print("[错误] 未找到任何图像-标注配对文件")
        return
    samples = random.sample(pairs, min(count, len(pairs)))
    print(f"\n共找到 {len(pairs)} 张图像，随机抽样 {len(samples)} 张进行可视化\n")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    for img_path, lbl_path, split, fname in samples:
        image = cv2.imread(img_path)
        if image is None:
            print(f" [跳过] 无法读取图像: {img_path}")
            continue
        annotated = draw_yolo_annotations(image, lbl_path, class_names)
        cv2.putText(
            annotated,
            f"split: {split} | file: {fname}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        if output_dir:
            cv2.imwrite(os.path.join(output_dir, f"vis_{split}_{fname}"), annotated)
            print(f" [保存] {os.path.join(output_dir, f'vis_{split}_{fname}')}")
        else:
            cv2.imshow(f"{split} {fname}", annotated)
            print(f" [显示] {fname} - 按任意键继续, 按 q 退出")
            if cv2.waitKey(0) & 0xFF == ord("q"):
                break
            cv2.destroyAllWindows()
    if output_dir:
        print(f"\n可视化完成，结果保存到: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="YOLO 数据集标注可视化工具")
    parser.add_argument(
        "--dataset", "-d", type=str, default=DEFAULT_DATASET_DIR, help="数据集目录"
    )
    parser.add_argument("--count", "-n", type=int, default=5, help="随机抽样数量")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出目录")
    parser.add_argument(
        "--image", "-i", type=str, default=None, help="查看指定图像的相对路径"
    )
    parser.add_argument("--grid", action="store_true", help="生成概览网格图")
    parser.add_argument(
        "--splits", nargs="+", default=["train", "val"], help="要可视化的 split"
    )
    args = parser.parse_args()
    if not os.path.exists(args.dataset):
        print(f"[错误] 数据集目录不存在: {args.dataset}")
        sys.exit(1)
    class_names = load_class_names(args.dataset)
    if class_names:
        print(f"加载类别: {class_names}")
    else:
        print("[警告] 未找到 data.yaml")
    # 执行对应功能
    if args.grid:
        generate_overview_grid(
            args.dataset,
            args.output or os.path.join(DEFAULT_OUTPUT_DIR, "overview.jpg"),
            grid_size=(4, 4),
            splits=args.splits,
            class_names=class_names,
        )
    elif args.image:
        visualize_single_image(
            args.dataset, args.image, output_path=args.output, class_names=class_names
        )
    else:
        visualize_random_samples(
            args.dataset,
            output_dir=args.output,
            count=args.count,
            splits=args.splits,
            class_names=class_names,
        )


def visualize_single_image(
    dataset_dir: str,
    image_relpath: str,
    output_path: Optional[str] = None,
    class_names: Optional[Dict[int, str]] = None,
):
    if class_names is None:
        class_names = load_class_names(dataset_dir)
    parts = image_relpath.replace("\\", "/").split("/")
    if len(parts) != 2:
        print("[错误] 请指定包含 split 名称的路径，如 train/xxx.jpg")
        return
    split, fname = parts[0], parts[1]
    img_path = os.path.join(dataset_dir, "images", split, fname)
    lbl_path = os.path.join(dataset_dir, "labels", split, f"{Path(fname).stem}.txt")
    if not os.path.exists(img_path):
        print(f"[错误] 图像不存在: {img_path}")
        return
    image = cv2.imread(img_path)
    if image is None:
        print(f"[错误] 无法读取图像: {img_path}")
        return
    annotated = draw_yolo_annotations(image, lbl_path, class_names)
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        cv2.imwrite(output_path, annotated)
        print(f"[已保存到] {output_path}")
    else:
        cv2.imshow(f"[{split}] {fname}", annotated)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def generate_overview_grid(
    dataset_dir: str,
    output_path: str,
    grid_size: Tuple[int, int] = (4, 4),
    splits: Optional[List[str]] = None,
    class_names: Optional[Dict[int, str]] = None,
):
    if class_names is None:
        class_names = load_class_names(dataset_dir)
    pairs = collect_image_label_pairs(dataset_dir, splits)
    if not pairs:
        print("[错误] 未找到任何图像-标注配对文件")
        return
    rows, cols = grid_size
    samples = random.sample(pairs, min(rows * cols, len(pairs)))
    thumb_w, thumb_h = 400, 300
    grid_img = np.zeros((rows * thumb_h, cols * thumb_w, 3), dtype=np.uint8)
    for idx, (img_path, lbl_path, split, fname) in enumerate(samples):
        image = cv2.imread(img_path)
        if image is None:
            continue
        thumb = cv2.resize(
            draw_yolo_annotations(
                image, lbl_path, class_names, thickness=1, font_scale=0.4
            ),
            (thumb_w, thumb_h),
        )
        cv2.putText(
            thumb,
            f"{split}/{fname[:15]}",
            (5, 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 255, 255),
            1,
        )
        r, c = divmod(idx, cols)
        grid_img[r * thumb_h : (r + 1) * thumb_h, c * thumb_w : (c + 1) * thumb_w] = (
            thumb
        )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cv2.imwrite(output_path, grid_img)
    print(f"概览网格图已保存到: {output_path}")


if __name__ == "__main__":
    main()
