from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote

import boto3  # type: ignore[import-untyped]
from botocore.client import BaseClient  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]


class ObjectStorage(ABC):
    def put_bytes(self, key: str, payload: bytes, content_type: str | None = None) -> str:
        return self.put(key, payload, content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        return self.get(key)

    @abstractmethod
    def put(self, key: str, payload: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def presigned_url(self, key: str, expires_in_seconds: int = 86_400) -> str:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root_dir: str, base_url: str = "http://localhost") -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._base_url = base_url.rstrip("/")

    def put(self, key: str, payload: bytes, content_type: str | None = None) -> str:
        target = self._resolve_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return key

    def get(self, key: str) -> bytes:
        return self._resolve_key(key).read_bytes()

    def delete(self, key: str) -> None:
        self._resolve_key(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._resolve_key(key).exists()

    def presigned_url(self, key: str, expires_in_seconds: int = 86_400) -> str:
        # Local fallback URL for dev/debug flows without S3.
        del expires_in_seconds
        return f"{self._base_url}/local-object/{quote(key.lstrip('/'))}"

    def _resolve_key(self, key: str) -> Path:
        safe_key = key.lstrip("/").replace("..", "_")
        return self._root / safe_key


class S3ObjectStorage(ObjectStorage):
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None,
        presign_endpoint_url: str | None,
        region: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        session = boto3.session.Session()
        self._client: BaseClient = session.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._presign_client: BaseClient = session.client(
            "s3",
            endpoint_url=presign_endpoint_url or endpoint_url or None,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = bucket

    def put(self, key: str, payload: bytes, content_type: str | None = None) -> str:
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        self._client.put_object(Bucket=self._bucket, Key=key, Body=payload, **extra)
        return key

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def presigned_url(self, key: str, expires_in_seconds: int = 86_400) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )
