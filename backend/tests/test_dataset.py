import io

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.entity.db_models import Dataset


class TestDatasetCreate:
    def test_create_dataset_success(self, client):
        response = client.post(
            "/api/dataset/create",
            json={
                "name": "plant_disease_test",
                "display_name": "植物病害测试数据集",
                "description": "测试用数据集",
                "category": "agriculture",
                "format_type": "yolo",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "plant_disease_test"

    def test_create_dataset_duplicate_name(self, client):
        client.post(
            "/api/dataset/create",
            json={
                "name": "duplicate_dataset",
                "display_name": "重复数据集",
                "category": "agriculture",
            },
        )
        response = client.post(
            "/api/dataset/create",
            json={
                "name": "duplicate_dataset",
                "display_name": "重复数据集",
                "category": "agriculture",
            },
        )
        assert response.status_code == 400


@pytest.fixture
def test_dataset(db_session: Session) -> Dataset:
    import uuid
    unique_name = f"test_dataset_{uuid.uuid4().hex[:8]}"
    dataset = Dataset(
        name=unique_name,
        display_name="测试数据集",
        description="测试用数据集",
        category="agriculture",
        format_type="yolo",
        user_id=1,
        class_names=["Tomato leaf", "Apple leaf"],
        class_names_cn={"Tomato leaf": "番茄健康叶片", "Apple leaf": "苹果健康叶片"},
    )
    db_session.add(dataset)
    db_session.commit()
    db_session.refresh(dataset)
    yield dataset
    db_session.delete(dataset)
    db_session.commit()


class TestDatasetList:
    def test_list_datasets(self, client, test_dataset):
        response = client.get("/api/dataset/list?page=1&page_size=20")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)


class TestDatasetDetail:
    def test_get_dataset_detail(self, client, test_dataset):
        response = client.get(f"/api/dataset/detail/{test_dataset.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_dataset.id
        assert data["name"] == test_dataset.name

    def test_get_dataset_not_found(self, client):
        response = client.get("/api/dataset/detail/9999")
        assert response.status_code == 404


class TestUploadImages:
    def test_upload_images(self, client, test_dataset):
        img = Image.new("RGB", (640, 640), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        response = client.post(
            f"/api/dataset/{test_dataset.id}/upload/images",
            files={"images": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestUploadLabels:
    def test_upload_labels(self, client, test_dataset):
        response = client.post(
            f"/api/dataset/{test_dataset.id}/upload/labels",
            files={"labels": ("test.txt", b"0 0.5 0.5 0.2 0.2", "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestConvertYolo:
    def test_convert_yolo(self, client, test_dataset):
        response = client.post(f"/api/dataset/{test_dataset.id}/convert")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestGetImages:
    def test_get_images(self, client, test_dataset):
        response = client.get(f"/api/dataset/{test_dataset.id}/images?page=1&page_size=20")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data


class TestGetLabels:
    def test_get_labels(self, client, test_dataset):
        response = client.get(f"/api/dataset/{test_dataset.id}/labels?page=1&page_size=20")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data


class TestStatistics:
    def test_get_statistics(self, client, test_dataset):
        response = client.get(f"/api/dataset/{test_dataset.id}/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestSummary:
    def test_get_summary(self, client, test_dataset):
        response = client.get(f"/api/dataset/{test_dataset.id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_images" in data


class TestSplitDataset:
    def test_split_dataset(self, client, test_dataset):
        response = client.post(
            f"/api/dataset/{test_dataset.id}/split",
            json={"train_ratio": 0.7, "val_ratio": 0.2},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestDiseaseClasses:
    def test_get_disease_classes(self, client):
        response = client.get("/api/dataset/disease/class")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 30


class TestDeleteDataset:
    def test_delete_dataset(self, client, test_dataset):
        response = client.delete(f"/api/dataset/{test_dataset.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200