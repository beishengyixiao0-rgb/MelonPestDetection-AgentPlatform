"""
导入项目固定使用的已训练模型。

这个脚本不会训练模型。它只做一件事：把仓库中已经存在的
`backend/runs/train/task_001` 登记进数据库，让 Day06/Day07 的训练与模型接口
可以围绕这个已完成任务正常工作。

为什么需要这个脚本：
- Git 可以提交模型文件和 results.csv，但不能提交 PostgreSQL 里的表数据。
- 当前训练接口依赖 `training_tasks` 查任务状态、模型路径和 results.csv。
- 前端曲线依赖 `training_metrics`，需要把 results.csv 的每个 epoch 导入表。
- 正式检测/导出依赖 `model_versions`，需要登记默认模型版本。

幂等性：
- 重复运行不会重复创建场景、任务、指标或模型版本。
- 如果记录已存在，会更新路径、指标和默认模型标记。

使用方式：
    cd backend
    .venv\\Scripts\\activate
    python tools\\import_existing_model.py
"""

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 允许直接从 backend/tools 运行脚本时导入 app 包。
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import SessionLocal  # noqa: E402
from app.entity.db_models import (  # noqa: E402
    DetectionScene,
    ModelVersion,
    TrainingTask,
    User,
)
from app.services.user_service import user_service  # noqa: E402
from app.training.training_service import TrainingService  # noqa: E402


DEFAULT_SCENE_NAME = "plant_disease"
DEFAULT_TASK_UUID = "001"
DEFAULT_VERSION = "v1.0.0"
DEFAULT_MODEL_NAME = "plant_disease_best"


def project_path(path_value: str | Path) -> Path:
    """把项目相对路径解析为本机路径；不在代码中写死盘符绝对路径。"""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def relative_to_project(path: Path) -> str:
    """数据库中保存项目相对路径，方便不同成员在不同目录拉取项目。"""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_class_names(data_yaml: Path) -> list[str]:
    """
    从 data.yaml 读取类别名称。

    项目当前 data.yaml 使用 YOLO 常见写法：
        names:
          0: xxx
          1: yyy
    这里用轻量解析，避免为了一个导入脚本增加额外 YAML 依赖。
    """
    names: dict[int, str] = {}
    in_names = False
    for raw_line in data_yaml.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "names:":
            in_names = True
            continue
        if in_names and not raw_line.startswith(" "):
            break
        if in_names and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key.strip().isdigit():
                names[int(key.strip())] = value.strip().strip("'\"")
    return [names[i] for i in sorted(names)]


def read_final_metrics(results_csv: Path) -> dict:
    """读取 results.csv 最后一行，作为当前模型版本的最终指标。"""
    if not results_csv.exists():
        return {}
    with results_csv.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    last_row = {k.strip(): v.strip() for k, v in rows[-1].items()}
    return {
        "precision": TrainingService._safe_float(last_row.get("metrics/precision(B)")),
        "recall": TrainingService._safe_float(last_row.get("metrics/recall(B)")),
        "map50": TrainingService._safe_float(last_row.get("metrics/mAP50(B)")),
        "map50_95": TrainingService._safe_float(
            last_row.get("metrics/mAP50-95(B)")
        ),
    }


def count_epochs(results_csv: Path) -> int:
    """统计训练日志里的 epoch 数，用于填充 training_tasks 进度字段。"""
    if not results_csv.exists():
        return 0
    with results_csv.open("r", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def validate_task_artifacts(task_dir: Path) -> tuple[Path, Path]:
    """
    校验固定训练产物是否存在。

    约定：
    - task_uuid = 001
    - 训练产物目录 = backend/runs/train/task_001
    - 模型权重 = backend/runs/train/task_001/weights/best.pt
    - 训练日志 = backend/runs/train/task_001/results.csv
    """
    weight_path = task_dir / "weights" / "best.pt"
    results_csv = task_dir / "results.csv"
    if not weight_path.exists():
        raise FileNotFoundError(f"模型权重不存在: {weight_path}")
    if not results_csv.exists():
        raise FileNotFoundError(f"训练日志不存在: {results_csv}")
    return weight_path, results_csv


def sync_export_dir(
    task_dir: Path,
    export_dir: Path,
    task: TrainingTask,
    scene: DetectionScene,
    version: str,
    metrics: dict,
) -> Path:
    """
    同步正式模型目录。

    `backend/runs/train/task_001` 是训练产物目录；
    `backend/models/plant_disease_v1.0.0` 是正式模型版本目录。
    后者用于模型版本管理、下载和后续检测服务选择默认模型。
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    exported_weight = export_dir / "best.pt"
    shutil.copy2(task_dir / "weights" / "best.pt", exported_weight)

    # 复制已有评估图表。当前训练产物里的 PR/F1 文件名来自 Ultralytics。
    copy_map = {
        "results.png": "results.png",
        "confusion_matrix.png": "confusion_matrix.png",
        "confusion_matrix_normalized.png": "confusion_matrix_normalized.png",
        "BoxPR_curve.png": "PR_curve.png",
        "BoxF1_curve.png": "F1_curve.png",
        "BoxP_curve.png": "P_curve.png",
        "BoxR_curve.png": "R_curve.png",
    }
    for source_name, target_name in copy_map.items():
        source_file = task_dir / source_name
        if source_file.exists():
            shutil.copy2(source_file, export_dir / target_name)

    report = {
        "version": version,
        "model_name": task.model_name,
        "scene": scene.name,
        "training_task": task.task_uuid,
        "evaluation": {
            "split": "val",
            "overall": metrics,
            "per_class": {},
        },
        "training_config": {
            "epochs": task.epochs,
            "batch_size": task.batch_size,
            "img_size": task.img_size,
            "optimizer": task.optimizer,
            "lr0": task.lr0,
            "device": task.device,
        },
        "exported_at": datetime.now().isoformat(),
        "source": relative_to_project(task_dir),
    }
    with (export_dir / "eval_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return exported_weight


def ensure_admin_user(db) -> User:
    """
    获取或创建平台管理员账号，并确保其拥有 admin 角色。

    已训练模型是平台级资产，归属于管理员账号而非导入专用账号。
    """
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        user = user_service.register(
            db=db,
            username="admin",
            email="admin@example.com",
            password="admin123",
        )
    user.is_active = True
    user_service.assign_single_role(db, user, "admin")
    db.commit()
    db.refresh(user)
    return user


def migrate_legacy_imported_owner(db, admin_user: User) -> dict[str, int]:
    """将旧导入账户关联的模型任务和场景迁移给管理员，并禁用旧账户。"""
    legacy_user = db.query(User).filter(User.username == "imported_model_user").first()
    if not legacy_user or legacy_user.id == admin_user.id:
        return {"training_tasks": 0, "scenes": 0}

    task_count = (
        db.query(TrainingTask)
        .filter(TrainingTask.user_id == legacy_user.id)
        .update({"user_id": admin_user.id}, synchronize_session=False)
    )
    scene_count = (
        db.query(DetectionScene)
        .filter(DetectionScene.created_by == legacy_user.id)
        .update({"created_by": admin_user.id}, synchronize_session=False)
    )
    legacy_user.is_active = False
    db.commit()
    return {"training_tasks": task_count, "scenes": scene_count}


def ensure_scene(db, user: User, scene_name: str, data_yaml: Path) -> DetectionScene:
    """创建或更新植物病害检测场景。"""
    scene = db.query(DetectionScene).filter(DetectionScene.name == scene_name).first()
    class_names = parse_class_names(data_yaml)
    if scene:
        scene.created_by = user.id
        scene.class_names = class_names
        scene.display_name = "植物病害检测"
        scene.category = "agriculture"
        scene.is_active = True
        db.commit()
        db.refresh(scene)
        return scene

    scene = DetectionScene(
        name=scene_name,
        display_name="植物病害检测",
        description="导入已有 YOLOv11 植物病害检测模型",
        category="agriculture",
        class_names=class_names,
        class_names_cn=None,
        is_active=True,
        created_by=user.id,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


def ensure_training_task(
    db,
    user: User,
    scene: DetectionScene,
    task_uuid: str,
    dataset_dir: Path,
    data_yaml: Path,
    results_csv: Path,
) -> TrainingTask:
    """
    创建或更新 completed 训练任务。

    这条记录不是为了重新训练，而是为了让 Day06/Day07 的接口能通过
    task_id/task_uuid 找到模型、日志和曲线指标。
    """
    task = db.query(TrainingTask).filter(TrainingTask.task_uuid == task_uuid).first()
    epochs = count_epochs(results_csv)
    if task:
        task.user_id = user.id
        task.scene_id = scene.id
        task.status = "completed"
        task.model_name = DEFAULT_MODEL_NAME
        task.epochs = epochs or task.epochs or 100
        task.current_epoch = epochs or task.current_epoch or task.epochs
        task.progress = 100
        task.img_size = 640
        task.batch_size = task.batch_size or 16
        task.device = "cpu"
        task.dataset_path = relative_to_project(dataset_dir)
        task.data_yaml = relative_to_project(data_yaml)
        task.completed_at = task.completed_at or datetime.now()
        db.commit()
        db.refresh(task)
        return task

    task = TrainingTask(
        user_id=user.id,
        scene_id=scene.id,
        task_uuid=task_uuid,
        status="completed",
        model_name=DEFAULT_MODEL_NAME,
        epochs=epochs or 100,
        current_epoch=epochs or 100,
        progress=100,
        img_size=640,
        batch_size=16,
        device="cpu",
        optimizer="SGD",
        lr0=0.01,
        dataset_path=relative_to_project(dataset_dir),
        data_yaml=relative_to_project(data_yaml),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def ensure_model_version(
    db,
    scene: DetectionScene,
    task: TrainingTask,
    version: str,
    exported_weight: Path,
    metrics: dict,
) -> ModelVersion:
    """
    创建或更新正式模型版本。

    model_versions 表用于“正式可用模型”的管理；training_tasks 表用于记录来源。
    这里把导入的 v1.0.0 标记为该场景默认模型。
    """
    model_version = (
        db.query(ModelVersion)
        .filter(ModelVersion.training_task_id == task.id)
        .first()
    )
    if not model_version:
        model_version = (
            db.query(ModelVersion)
            .filter(
                ModelVersion.scene_id == scene.id,
                ModelVersion.version == version,
            )
            .first()
        )

    values = {
        "training_task_id": task.id,
        "version": version,
        "model_name": f"{task.model_name}_{scene.name}_{version}",
        "model_type": task.model_name,
        "model_path": relative_to_project(exported_weight),
        "map50": metrics.get("map50"),
        "map50_95": metrics.get("map50_95"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "file_size": exported_weight.stat().st_size,
        "description": "导入已有训练模型",
        "is_default": True,
    }

    if model_version:
        for key, value in values.items():
            setattr(model_version, key, value)
    else:
        model_version = ModelVersion(scene_id=scene.id, **values)
        db.add(model_version)

    db.query(ModelVersion).filter(
        ModelVersion.scene_id == scene.id,
        ModelVersion.id != model_version.id,
    ).update({"is_default": False})
    db.commit()
    db.refresh(model_version)
    return model_version


def main():
    parser = argparse.ArgumentParser(
        description="导入仓库内固定的 YOLOv11 已训练模型"
    )
    parser.add_argument("--scene", default=DEFAULT_SCENE_NAME, help="场景标识")
    parser.add_argument("--task-uuid", default=DEFAULT_TASK_UUID, help="训练任务 UUID")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="模型版本号")
    parser.add_argument(
        "--dataset-dir",
        default=f"datasets/{DEFAULT_SCENE_NAME}",
        help="数据集目录，默认 datasets/plant_disease",
    )
    args = parser.parse_args()

    dataset_dir = project_path(args.dataset_dir)
    data_yaml = dataset_dir / "data.yaml"
    task_dir = BACKEND_DIR / "runs" / "train" / f"task_{args.task_uuid}"
    export_dir = BACKEND_DIR / "models" / f"{args.scene}_{args.version}"

    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml 不存在: {data_yaml}")
    _, results_csv = validate_task_artifacts(task_dir)

    db = SessionLocal()
    try:
        user = ensure_admin_user(db)
        migrated = migrate_legacy_imported_owner(db, user)
        scene = ensure_scene(db, user, args.scene, data_yaml)
        task = ensure_training_task(
            db,
            user,
            scene,
            args.task_uuid,
            dataset_dir,
            data_yaml,
            results_csv,
        )
        imported_metrics = TrainingService.import_results_csv(
            db,
            task.id,
            results_csv,
        )
        metrics = read_final_metrics(results_csv)
        exported_weight = sync_export_dir(
            task_dir,
            export_dir,
            task,
            scene,
            args.version,
            metrics,
        )
        model_version = ensure_model_version(
            db,
            scene,
            task,
            args.version,
            exported_weight,
            metrics,
        )
        summary = {
            "scene_name": scene.name,
            "scene_id": scene.id,
            "task_uuid": task.task_uuid,
            "task_id": task.id,
            "model_version": model_version.version,
            "model_version_id": model_version.id,
            "model_path": model_version.model_path,
            "export_dir": relative_to_project(export_dir),
            "migrated": migrated,
        }
    finally:
        db.close()

    print("导入完成")
    print(f"  场景: {summary['scene_name']} (id={summary['scene_id']})")
    print(f"  任务: task_{summary['task_uuid']} (id={summary['task_id']})")
    print(f"  新增指标: {imported_metrics}")
    print(
        "  模型版本: "
        f"{summary['model_version']} (id={summary['model_version_id']})"
    )
    print(f"  模型路径: {summary['model_path']}")
    print(f"  导出目录: {summary['export_dir']}")
    print(
        "  历史导入记录迁移: "
        f"训练任务 {summary['migrated']['training_tasks']} 个，"
        f"检测场景 {summary['migrated']['scenes']} 个"
    )


if __name__ == "__main__":
    main()
