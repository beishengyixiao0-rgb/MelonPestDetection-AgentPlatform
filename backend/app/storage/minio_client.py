"""
MinIO 对象存储客户端封装
用于存储检测图像、训练模型等文件
"""

import io

from app.config.settings import settings
from minio import Minio
from minio.error import S3Error


class MinIOClient:
    """MinIO 客户端封装"""

    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket_name = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        """确保存储桶存在，不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            print(f"MinIO bucket 初始化警告: {e}")

    def upload_file(
        self,
        object_name: str,
        file_path: str,
        content_type: str | None = None,
    ) -> str:
        """
        上传本地文件到 MinIO


        Args:
            object_name: MinIO 中的对象名称（路径）
            file_path: 本地文件路径
            content_type: 可选的 MIME 类型


        Returns:
            预签名 URL
        """
        self.client.fput_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            file_path=file_path,
            content_type=content_type,
        )
        return self.get_presigned_url(object_name)

    def upload_bytes(
        self, object_name: str, data: bytes, content_type: str = "image/jpeg"
    ) -> str:
        """
        上传字节数据到 MinIO


        Args:
            object_name: MinIO 中的对象名称
            data: 字节数据
            content_type: MIME 类型


        Returns:
            预签名 URL
        """
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return self.get_presigned_url(object_name)

    def get_presigned_url(self, object_name: str) -> str:
        """获取对象的预签名访问 URL（有效期 7 天）"""
        from datetime import timedelta

        url = self.client.presigned_get_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            expires=timedelta(days=7),
        )
        return url

    def delete_file(self, object_name: str):
        """删除 MinIO 中的文件"""
        self.client.remove_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
        )

    def upload_image(self, data: bytes, object_name: str) -> str:
        """
        上传图片到 MinIO

        Args:
            data: 图片字节数据
            object_name: MinIO 中的对象名称（路径）

        Returns:
            预签名 URL
        """
        import os

        ext = os.path.splitext(object_name)[1].lower()
        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
        }
        content_type = content_type_map.get(ext, "image/jpeg")
        return self.upload_bytes(object_name, data, content_type)

    def get_object(self, object_name: str) -> bytes:
        """
        获取 MinIO 中的对象内容

        Args:
            object_name: MinIO 中的对象名称（路径）

        Returns:
            对象字节数据
        """
        response = self.client.get_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, object_name: str):
        """
        删除 MinIO 中的对象

        Args:
            object_name: MinIO 中的对象名称（路径）
        """
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
        except S3Error:
            pass
