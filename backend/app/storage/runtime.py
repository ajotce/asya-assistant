from app.core.config import get_settings
from app.storage.file_store import SessionFileStore
from app.storage.object_storage import LocalObjectStorage, ObjectStorage, S3ObjectStorage
from app.storage.reasoning_cache import ReasoningProbeCache
from app.storage.usage_store import UsageStore
from app.storage.vector_store import create_vector_store

# Process-local runtime stores (ephemeral). Safe to lose on restart.
file_store = SessionFileStore(base_tmp_dir=get_settings().tmp_dir)


def _build_object_storage() -> ObjectStorage:
    settings = get_settings()
    backend = settings.object_storage_backend.strip().lower()
    if backend == "s3":
        missing = [
            name
            for name, value in [
                ("S3_BUCKET", settings.s3_bucket),
                ("S3_ACCESS_KEY", settings.s3_access_key),
                ("S3_SECRET_KEY", settings.s3_secret_key),
            ]
            if not value.strip()
        ]
        if missing:
            raise ValueError(f"S3 backend selected but required settings are missing: {', '.join(missing)}")
        return S3ObjectStorage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint.strip() or None,
            region=settings.s3_region,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )
    return LocalObjectStorage(root_dir=settings.object_storage_local_dir)


blob_storage = _build_object_storage()
vector_store = create_vector_store(db_url=get_settings().asya_db_url)
usage_store = UsageStore()
reasoning_probe_cache = ReasoningProbeCache()
