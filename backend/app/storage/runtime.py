from app.core.config import get_settings
from app.storage.blob_provider import LocalBlobStorageProvider
from app.storage.file_store import SessionFileStore
from app.storage.reasoning_cache import ReasoningProbeCache
from app.storage.usage_store import UsageStore
from app.storage.vector_store import SessionVectorStore

# Process-local runtime stores (ephemeral). Safe to lose on restart.
file_store = SessionFileStore(base_tmp_dir=get_settings().tmp_dir)
blob_storage = LocalBlobStorageProvider(root_dir=get_settings().file_storage_local_dir)
vector_store = SessionVectorStore()
usage_store = UsageStore()
reasoning_probe_cache = ReasoningProbeCache()
