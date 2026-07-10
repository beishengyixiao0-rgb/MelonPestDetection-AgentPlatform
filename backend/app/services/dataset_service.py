import os
import json
import uuid
import shutil
from typing import List, Optional, Dict, Tuple

import cv2
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import HTTPException
from app.entity.db_models import Dataset, DatasetImage, DatasetLabel
from app.storage.minio_client import MinIOClient

minio_client = MinIOClient()
from app.config.settings import settings


class DatasetService:
    """数据集管理服务"""

    PLANT_DISEASE_CLASSES = {
        0: {"name": "Tomato leaf", "name_cn": "番茄健康叶片"},
        1: {"name": "Apple leaf", "name_cn": "苹果健康叶片"},
        2: {"name": "Grape leaf", "name_cn": "葡萄健康叶片"},
        3: {"name": "Strawberry leaf", "name_cn": "草莓健康叶片"},
        4: {"name": "Peach leaf", "name_cn": "桃树健康叶片"},
        5: {"name": "Cherry leaf", "name_cn": "樱桃健康叶片"},
        6: {"name": "Soyabean leaf", "name_cn": "大豆健康叶片"},
        7: {"name": "Blueberry leaf", "name_cn": "蓝莓健康叶片"},
        8: {"name": "Raspberry leaf", "name_cn": "树莓健康叶片"},
        9: {"name": "Bell pepper leaf", "name_cn": "甜椒健康叶片"},
        10: {"name": "Potato leaf", "name_cn": "马铃薯健康叶片"},
        11: {"name": "Apple rust leaf", "name_cn": "苹果锈病"},
        12: {"name": "Apple Scab Leaf", "name_cn": "苹果黑星病"},
        13: {"name": "Bell pepper leaf spot", "name_cn": "甜椒叶斑病"},
        14: {"name": "Corn Gray leaf spot", "name_cn": "玉米灰斑病"},
        15: {"name": "Corn leaf blight", "name_cn": "玉米大斑病"},
        16: {"name": "Corn rust leaf", "name_cn": "玉米锈病"},
        17: {"name": "Grape leaf black rot", "name_cn": "葡萄黑腐病"},
        18: {"name": "Potato leaf early blight", "name_cn": "马铃薯早疫病"},
        19: {"name": "Potato leaf late blight", "name_cn": "马铃薯晚疫病"},
        20: {"name": "Squash Powdery mildew leaf", "name_cn": "南瓜白粉病"},
        21: {"name": "Tomato Early blight leaf", "name_cn": "番茄早疫病"},
        22: {"name": "Tomato leaf bacterial spot", "name_cn": "番茄细菌性斑点病"},
        23: {"name": "Tomato leaf late blight", "name_cn": "番茄晚疫病"},
        24: {"name": "Tomato leaf mosaic virus", "name_cn": "番茄花叶病毒病"},
        25: {"name": "Tomato leaf yellow virus", "name_cn": "番茄黄化病毒病"},
        26: {"name": "Tomato mold leaf", "name_cn": "番茄叶霉病"},
        27: {"name": "Tomato Septoria leaf spot", "name_cn": "番茄白星病"},
        28: {"name": "Tomato two spotted spider mites leaf", "name_cn": "番茄二斑叶螨危害"},
        29: {"name": "Tomato Target Spot leaf", "name_cn": "番茄靶斑病"},
    }

    def __init__(self):
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "temp/datasets")
        os.makedirs(self.temp_dir, exist_ok=True)

    def create_dataset(
        self,
        db: Session,
        name: str,
        display_name: str,
        description: Optional[str],
        category: str = "agriculture",
        format_type: str = "yolo",
        user_id: int = 1,
    ) -> Dataset:
        """创建数据集"""
        existing = db.query(Dataset).filter(Dataset.name == name).first()
        if existing:
            raise HTTPException(status_code=400, detail="数据集名称已存在")

        dataset = Dataset(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            format_type=format_type,
            user_id=user_id,
            class_names=[item["name"] for item in self.PLANT_DISEASE_CLASSES.values()],
            class_names_cn={
                item["name"]: item["name_cn"]
                for item in self.PLANT_DISEASE_CLASSES.values()
            },
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        return dataset

    def get_dataset(self, db: Session, dataset_id: int) -> Dataset:
        """获取数据集"""
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="数据集不存在")
        return dataset

    def list_datasets(
        self, db: Session, page: int = 1, page_size: int = 20, user_id: Optional[int] = None
    ) -> Tuple[List[Dataset], int]:
        """分页查询数据集列表"""
        query = db.query(Dataset)
        if user_id:
            query = query.filter(Dataset.user_id == user_id)

        total = query.count()
        datasets = (
            query.order_by(Dataset.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return datasets, total

    def upload_images(
        self, db: Session, dataset_id: int, images: List, user_id: int = 1
    ) -> Dict:
        """上传图片"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        uploaded_count = 0
        for image in images:
            image_bytes = image.file.read()
            image_name = image.filename
            file_size = len(image_bytes)

            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue

            height, width = img.shape[:2]

            minio_path = f"datasets/{dataset_id}/images/{uuid.uuid4().hex}_{image_name}"
            minio_url = minio_client.upload_image(image_bytes, minio_path)

            dataset_image = DatasetImage(
                dataset_id=dataset_id,
                image_name=image_name,
                image_path=minio_path,
                image_url=minio_url,
                image_width=width,
                image_height=height,
                file_size=file_size,
            )
            db.add(dataset_image)

            dataset.total_images += 1
            dataset.data_size += file_size
            uploaded_count += 1

        db.commit()
        self._update_dataset_statistics(db, dataset)

        return {"uploaded": uploaded_count, "dataset_id": dataset_id}

    def upload_labels(
        self, db: Session, dataset_id: int, labels: List, user_id: int = 1
    ) -> Dict:
        """上传标签文件"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        parsed_count = 0
        for label_file in labels:
            label_content = label_file.file.read().decode("utf-8")
            label_name = label_file.filename
            image_name = label_name.replace(".txt", "")

            image = (
                db.query(DatasetImage)
                .filter(
                    DatasetImage.dataset_id == dataset_id,
                    DatasetImage.image_name.like(f"%{image_name}%"),
                )
                .first()
            )

            if not image:
                continue

            labels_data = self._parse_yolo_label(label_content)
            if labels_data:
                image.has_label = True
                image.label_count = len(labels_data)

                for label in labels_data:
                    class_info = self.PLANT_DISEASE_CLASSES.get(label["class_id"])
                    class_name = class_info["name"] if class_info else str(label["class_id"])
                    class_name_cn = class_info["name_cn"] if class_info else None

                    bbox_x1 = int((label["x"] - label["width"] / 2) * image.image_width)
                    bbox_y1 = int((label["y"] - label["height"] / 2) * image.image_height)
                    bbox_x2 = int((label["x"] + label["width"] / 2) * image.image_width)
                    bbox_y2 = int((label["y"] + label["height"] / 2) * image.image_height)

                    dataset_label = DatasetLabel(
                        dataset_id=dataset_id,
                        image_id=image.id,
                        class_id=label["class_id"],
                        class_name=class_name,
                        class_name_cn=class_name_cn,
                        bbox_x=label["x"],
                        bbox_y=label["y"],
                        bbox_width=label["width"],
                        bbox_height=label["height"],
                        bbox_x1=bbox_x1,
                        bbox_y1=bbox_y1,
                        bbox_x2=bbox_x2,
                        bbox_y2=bbox_y2,
                    )
                    db.add(dataset_label)
                    dataset.total_labels += 1

                parsed_count += 1

        db.commit()
        self._update_dataset_statistics(db, dataset)

        return {"parsed": parsed_count, "dataset_id": dataset_id}

    def _parse_yolo_label(self, content: str) -> List[Dict]:
        """解析YOLO格式标签"""
        labels = []
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    labels.append(
                        {
                            "class_id": int(parts[0]),
                            "x": float(parts[1]),
                            "y": float(parts[2]),
                            "width": float(parts[3]),
                            "height": float(parts[4]),
                        }
                    )
                except ValueError:
                    continue
        return labels

    def auto_parse_yolo(
        self, db: Session, dataset_id: int, user_id: int = 1
    ) -> Dict:
        """自动解析YOLO格式数据集"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        images = db.query(DatasetImage).filter(DatasetImage.dataset_id == dataset_id).all()
        parsed_count = 0

        for image in images:
            if image.has_label:
                continue

            label_name = os.path.splitext(image.image_name)[0] + ".txt"
            label_path = f"datasets/{dataset_id}/labels/{label_name}"

            try:
                label_bytes = minio_client.get_object(label_path)
                label_content = label_bytes.decode("utf-8")

                labels_data = self._parse_yolo_label(label_content)
                if labels_data:
                    image.has_label = True
                    image.label_count = len(labels_data)

                    for label in labels_data:
                        class_info = self.PLANT_DISEASE_CLASSES.get(label["class_id"])
                        class_name = (
                            class_info["name"] if class_info else str(label["class_id"])
                        )
                        class_name_cn = class_info["name_cn"] if class_info else None

                        bbox_x1 = int(
                            (label["x"] - label["width"] / 2) * image.image_width
                        )
                        bbox_y1 = int(
                            (label["y"] - label["height"] / 2) * image.image_height
                        )
                        bbox_x2 = int(
                            (label["x"] + label["width"] / 2) * image.image_width
                        )
                        bbox_y2 = int(
                            (label["y"] + label["height"] / 2) * image.image_height
                        )

                        dataset_label = DatasetLabel(
                            dataset_id=dataset_id,
                            image_id=image.id,
                            class_id=label["class_id"],
                            class_name=class_name,
                            class_name_cn=class_name_cn,
                            bbox_x=label["x"],
                            bbox_y=label["y"],
                            bbox_width=label["width"],
                            bbox_height=label["height"],
                            bbox_x1=bbox_x1,
                            bbox_y1=bbox_y1,
                            bbox_x2=bbox_x2,
                            bbox_y2=bbox_y2,
                        )
                        db.add(dataset_label)
                        dataset.total_labels += 1

                    parsed_count += 1
            except Exception:
                continue

        db.commit()
        self._update_dataset_statistics(db, dataset)

        return {"parsed": parsed_count, "dataset_id": dataset_id}

    def _update_dataset_statistics(self, db: Session, dataset: Dataset):
        """更新数据集统计信息"""
        if dataset.total_images > 0:
            labeled_count = (
                db.query(DatasetImage)
                .filter(DatasetImage.dataset_id == dataset.id, DatasetImage.has_label == True)
                .count()
            )
            dataset.label_quality = round(labeled_count / dataset.total_images, 4)

        class_dist = (
            db.query(
                DatasetLabel.class_name, func.count(DatasetLabel.class_name)
            )
            .filter(DatasetLabel.dataset_id == dataset.id)
            .group_by(DatasetLabel.class_name)
            .all()
        )
        class_distribution = {name: count for name, count in class_dist}
        dataset.class_distribution = class_distribution
        dataset.total_classes = len(class_distribution)

        dataset.status = "ready" if dataset.total_images > 0 else "uploading"

        db.commit()

    def get_images(
        self,
        db: Session,
        dataset_id: int,
        page: int = 1,
        page_size: int = 20,
        split_type: Optional[str] = None,
        has_label: Optional[bool] = None,
        user_id: int = 1,
    ) -> Tuple[List[DatasetImage], int]:
        """分页查询图片列表"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        query = db.query(DatasetImage).filter(DatasetImage.dataset_id == dataset_id)

        if split_type:
            query = query.filter(DatasetImage.split_type == split_type)
        if has_label is not None:
            query = query.filter(DatasetImage.has_label == has_label)

        total = query.count()
        images = (
            query.order_by(DatasetImage.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return images, total

    def get_image(self, db: Session, image_id: int, user_id: int = 1) -> DatasetImage:
        """获取图片详情"""
        image = db.query(DatasetImage).filter(DatasetImage.id == image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        if image.dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该图片")

        return image

    def get_labels(
        self,
        db: Session,
        dataset_id: int,
        image_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        user_id: int = 1,
    ) -> Tuple[List[DatasetLabel], int]:
        """查询标签列表"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        query = db.query(DatasetLabel).filter(DatasetLabel.dataset_id == dataset_id)

        if image_id:
            query = query.filter(DatasetLabel.image_id == image_id)

        total = query.count()
        labels = (
            query.order_by(DatasetLabel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return labels, total

    def get_class_statistics(self, db: Session, dataset_id: int, user_id: int = 1) -> Dict:
        """获取类别统计信息"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        class_dist = (
            db.query(
                DatasetLabel.class_id,
                DatasetLabel.class_name,
                DatasetLabel.class_name_cn,
                func.count(DatasetLabel.class_id),
            )
            .filter(DatasetLabel.dataset_id == dataset.id)
            .group_by(
                DatasetLabel.class_id,
                DatasetLabel.class_name,
                DatasetLabel.class_name_cn,
            )
            .order_by(func.count(DatasetLabel.class_id).desc())
            .all()
        )

        stats = {
            "total_classes": len(class_dist),
            "total_labels": dataset.total_labels,
            "total_images": dataset.total_images,
            "label_quality": dataset.label_quality or 0,
            "class_distribution": [
                {
                    "class_id": row[0],
                    "class_name": row[1],
                    "class_name_cn": row[2],
                    "sample_count": row[3],
                    "percentage": round(row[3] / dataset.total_labels * 100, 2)
                    if dataset.total_labels > 0
                    else 0,
                }
                for row in class_dist
            ],
        }

        return stats

    def split_dataset(
        self,
        db: Session,
        dataset_id: int,
        train_ratio: float = 0.7,
        val_ratio: float = 0.2,
        user_id: int = 1,
    ) -> Dict:
        """自动划分数据集"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        images = (
            db.query(DatasetImage)
            .filter(DatasetImage.dataset_id == dataset_id)
            .all()
        )

        import random

        shuffled = random.sample(images, len(images))
        total = len(shuffled)

        train_end = int(total * train_ratio)
        val_end = train_end + int(total * val_ratio)

        dataset.train_count = 0
        dataset.val_count = 0
        dataset.test_count = 0

        for i, image in enumerate(shuffled):
            if i < train_end:
                image.split_type = "train"
                dataset.train_count += 1
            elif i < val_end:
                image.split_type = "val"
                dataset.val_count += 1
            else:
                image.split_type = "test"
                dataset.test_count += 1

        db.commit()

        return {
            "dataset_id": dataset_id,
            "train_count": dataset.train_count,
            "val_count": dataset.val_count,
            "test_count": dataset.test_count,
            "total": total,
        }

    def export_dataset(
        self,
        db: Session,
        dataset_id: int,
        format_type: str = "yolo",
        split_type: str = "all",
        user_id: int = 1,
    ) -> str:
        """导出数据集"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        export_dir = os.path.join(self.temp_dir, f"dataset_{dataset_id}_{uuid.uuid4().hex}")
        os.makedirs(export_dir, exist_ok=True)

        for split_name in ["train", "val", "test"]:
            if split_type == "all" or split_type == split_name:
                os.makedirs(os.path.join(export_dir, split_name, "images"), exist_ok=True)
                os.makedirs(os.path.join(export_dir, split_name, "labels"), exist_ok=True)

        query = db.query(DatasetImage).filter(DatasetImage.dataset_id == dataset_id)
        if split_type != "all":
            query = query.filter(DatasetImage.split_type == split_type)

        images = query.all()

        for image in images:
            try:
                image_split = image.split_type or "train"
                
                image_bytes = minio_client.get_object(image.image_path)
                image_dest = os.path.join(
                    export_dir, image_split, "images", image.image_name
                )
                with open(image_dest, "wb") as f:
                    f.write(image_bytes)

                if image.has_label:
                    labels = (
                        db.query(DatasetLabel)
                        .filter(DatasetLabel.image_id == image.id)
                        .all()
                    )
                    label_lines = []
                    for label in labels:
                        label_lines.append(
                            f"{label.class_id} {label.bbox_x} {label.bbox_y} {label.bbox_width} {label.bbox_height}"
                        )
                    label_dest = os.path.join(
                        export_dir,
                        image_split,
                        "labels",
                        os.path.splitext(image.image_name)[0] + ".txt",
                    )
                    with open(label_dest, "w") as f:
                        f.write("\n".join(label_lines))
            except Exception as e:
                print(f"Export image error: {e}")
                continue

        if format_type == "yolo":
            data_yaml = {
                "path": f"dataset_{dataset_id}",
                "train": "train/images",
                "val": "val/images",
                "test": "test/images",
                "nc": len(dataset.class_names) if dataset.class_names else 30,
                "names": dataset.class_names or [c["name"] for c in self.PLANT_DISEASE_CLASSES.values()],
            }
            yaml_lines = []
            for k, v in data_yaml.items():
                if isinstance(v, str):
                    yaml_lines.append(f"{k}: {v}")
                elif isinstance(v, int) or isinstance(v, float):
                    yaml_lines.append(f"{k}: {v}")
                else:
                    yaml_lines.append(f"{k}:")
                    for item in v:
                        yaml_lines.append(f"  - {item}")
            with open(os.path.join(export_dir, "data.yaml"), "w") as f:
                f.write("\n".join(yaml_lines))

        zip_path = shutil.make_archive(export_dir, "zip", export_dir)
        shutil.rmtree(export_dir)

        return zip_path

    def get_disease_classes(self) -> List[Dict]:
        """获取病害类别列表"""
        return [
            {
                "class_id": class_id,
                "class_name": info["name"],
                "class_name_cn": info["name_cn"],
            }
            for class_id, info in self.PLANT_DISEASE_CLASSES.items()
        ]

    def delete_dataset(self, db: Session, dataset_id: int, user_id: int = 1) -> bool:
        """删除数据集"""
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权删除该数据集")

        images = db.query(DatasetImage).filter(DatasetImage.dataset_id == dataset_id).all()
        for image in images:
            try:
                minio_client.delete_object(image.image_path)
            except Exception:
                pass

        db.delete(dataset)
        db.commit()

        return True

    def delete_image(self, db: Session, image_id: int, user_id: int = 1) -> bool:
        """删除图片"""
        image = self.get_image(db, image_id, user_id)

        try:
            minio_client.delete_object(image.image_path)
        except Exception:
            pass

        dataset = image.dataset
        dataset.total_images -= 1
        dataset.total_labels -= image.label_count
        dataset.data_size -= image.file_size or 0

        db.delete(image)
        db.commit()
        self._update_dataset_statistics(db, dataset)

        return True

    def upload_dataset_zip(
        self,
        db: Session,
        dataset_id: int,
        zip_file,
        user_id: int = 1,
    ) -> Dict:
        """
        上传数据集压缩包并自动解析

        支持的压缩包结构（YOLO格式）：
        - train/images/*.jpg
        - train/labels/*.txt
        - val/images/*.jpg
        - val/labels/*.txt
        - test/images/*.jpg
        - test/labels/*.txt

        也支持简单结构：
        - images/*.jpg
        - labels/*.txt

        Args:
            db: 数据库会话
            dataset_id: 数据集ID
            zip_file: 上传的zip文件对象
            user_id: 用户ID

        Returns:
            解析结果
        """
        dataset = self.get_dataset(db, dataset_id)
        if dataset.user_id != user_id and user_id != 1:
            raise HTTPException(status_code=403, detail="无权访问该数据集")

        import zipfile

        zip_content = zip_file.file.read()
        temp_zip_path = os.path.join(self.temp_dir, f"upload_{uuid.uuid4().hex}.zip")

        with open(temp_zip_path, "wb") as f:
            f.write(zip_content)

        uploaded_images = 0
        parsed_labels = 0
        skipped_files = []

        with zipfile.ZipFile(temp_zip_path, "r") as zf:
            print(f"Zip file contains {len(zf.infolist())} entries")
            
            for file_info in zf.infolist():
                if file_info.is_dir():
                    continue

                file_name = file_info.filename
                file_ext = os.path.splitext(file_name)[1].lower()

                parts = file_name.replace("\\", "/").split("/")
                parts = [p for p in parts if p]
                
                split_type = "train"
                file_type = None
                base_name = file_name

                if len(parts) >= 3 and parts[0] in ["train", "val", "test"]:
                    split_type = parts[0]
                    file_type = parts[1]
                    base_name = "/".join(parts[2:])
                elif len(parts) >= 2 and parts[0] in ["images", "labels"]:
                    file_type = parts[0]
                    base_name = "/".join(parts[1:])

                if file_type not in ["images", "labels"]:
                    skipped_files.append(f"Unknown type: {file_name}")
                    continue

                try:
                    file_bytes = zf.read(file_info)

                    if file_type == "images" and file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                        nparr = np.frombuffer(file_bytes, np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img is None:
                            skipped_files.append(f"Invalid image: {file_name}")
                            continue

                        height, width = img.shape[:2]
                        file_size = len(file_bytes)

                        minio_path = f"datasets/{dataset_id}/{split_type}/images/{uuid.uuid4().hex}_{base_name}"
                        minio_url = minio_client.upload_image(file_bytes, minio_path)

                        dataset_image = DatasetImage(
                            dataset_id=dataset_id,
                            image_name=base_name,
                            image_path=minio_path,
                            image_url=minio_url,
                            image_width=width,
                            image_height=height,
                            file_size=file_size,
                            split_type=split_type,
                        )
                        db.add(dataset_image)
                        dataset.total_images += 1
                        dataset.data_size += file_size
                        uploaded_images += 1

                    elif file_type == "labels" and file_ext == ".txt":
                        label_content = file_bytes.decode("utf-8", errors="ignore")
                        image_name = os.path.splitext(base_name)[0]

                        image = (
                            db.query(DatasetImage)
                            .filter(
                                DatasetImage.dataset_id == dataset_id,
                                DatasetImage.image_name.like(f"%{image_name}%"),
                            )
                            .first()
                        )

                        if not image:
                            skipped_files.append(f"No image found for label: {file_name}")
                            continue

                        labels_data = self._parse_yolo_label(label_content)
                        if labels_data:
                            image.has_label = True
                            image.label_count = len(labels_data)

                            for label in labels_data:
                                class_info = self.PLANT_DISEASE_CLASSES.get(label["class_id"])
                                class_name = class_info["name"] if class_info else str(label["class_id"])
                                class_name_cn = class_info["name_cn"] if class_info else None

                                bbox_x1 = int((label["x"] - label["width"] / 2) * image.image_width)
                                bbox_y1 = int((label["y"] - label["height"] / 2) * image.image_height)
                                bbox_x2 = int((label["x"] + label["width"] / 2) * image.image_width)
                                bbox_y2 = int((label["y"] + label["height"] / 2) * image.image_height)

                                dataset_label = DatasetLabel(
                                    dataset_id=dataset_id,
                                    image_id=image.id,
                                    class_id=label["class_id"],
                                    class_name=class_name,
                                    class_name_cn=class_name_cn,
                                    bbox_x=label["x"],
                                    bbox_y=label["y"],
                                    bbox_width=label["width"],
                                    bbox_height=label["height"],
                                    bbox_x1=bbox_x1,
                                    bbox_y1=bbox_y1,
                                    bbox_x2=bbox_x2,
                                    bbox_y2=bbox_y2,
                                )
                                db.add(dataset_label)
                                dataset.total_labels += 1

                            parsed_labels += 1

                except Exception as e:
                    skipped_files.append(f"Error processing {file_name}: {str(e)}")
                    continue

        os.remove(temp_zip_path)
        db.commit()
        self._update_dataset_statistics(db, dataset)

        print(f"Upload completed: {uploaded_images} images, {parsed_labels} labels")
        if skipped_files:
            print(f"Skipped {len(skipped_files)} files")

        return {
            "dataset_id": dataset_id,
            "uploaded_images": uploaded_images,
            "parsed_labels": parsed_labels,
            "total_images": dataset.total_images,
            "total_labels": dataset.total_labels,
        }


dataset_service = DatasetService()