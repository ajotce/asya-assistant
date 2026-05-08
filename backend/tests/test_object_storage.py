from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import boto3
import httpx
from moto import mock_aws
from moto.server import ThreadedMotoServer

from app.storage.object_storage import LocalObjectStorage, S3ObjectStorage


def test_local_object_storage_round_trip(tmp_path) -> None:
    storage = LocalObjectStorage(root_dir=str(tmp_path / "objects"), base_url="http://localhost:8000")
    key = "exports/user-1/archive.json"
    payload = b'{"ok": true}'

    assert storage.exists(key) is False
    storage.put(key, payload, content_type="application/json")
    assert storage.exists(key) is True
    assert storage.get(key) == payload
    assert storage.presigned_url(key).startswith("http://localhost:8000/local-object/")

    storage.delete(key)
    assert storage.exists(key) is False


@mock_aws
def test_s3_object_storage_round_trip_and_presigned_url() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="asya-dev")

    storage = S3ObjectStorage(
        bucket="asya-dev",
        endpoint_url=None,
        presign_endpoint_url=None,
        region="us-east-1",
        access_key="test",
        secret_key="test",
    )

    key = "diary/user-1/entry.webm"
    payload = b"audio-data"

    assert storage.exists(key) is False
    storage.put(key, payload, content_type="audio/webm")
    assert storage.exists(key) is True
    assert storage.get(key) == payload

    presigned = storage.presigned_url(key, expires_in_seconds=86_400)
    parsed = urlparse(presigned)
    query = parse_qs(parsed.query)
    assert parsed.scheme in {"http", "https"}
    assert "X-Amz-Expires" in query
    assert query["X-Amz-Expires"][0] == "86400"

    storage.delete(key)
    assert storage.exists(key) is False


def test_s3_presigned_url_is_downloadable_over_http() -> None:
    server = ThreadedMotoServer(port=0)
    server.start()
    host, port = server.get_host_and_port()
    endpoint = f"http://{host}:{port}"

    try:
        boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        ).create_bucket(Bucket="asya-dev")

        storage = S3ObjectStorage(
            bucket="asya-dev",
            endpoint_url=endpoint,
            presign_endpoint_url=endpoint,
            region="us-east-1",
            access_key="test",
            secret_key="test",
        )
        key = "exports/user-1/archive.zip"
        payload = b"archive-payload"
        storage.put(key, payload, content_type="application/zip")

        presigned = storage.presigned_url(key, expires_in_seconds=86_400)
        response = httpx.get(presigned, timeout=10.0)
        assert response.status_code == 200
        assert response.content == payload
    finally:
        server.stop()
