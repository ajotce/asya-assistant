from app.core.config import get_settings
from app.storage.file_store import SessionFileStore
from app.storage.session_store import SessionStore
from app.storage.usage_store import UsageStore
from app.storage.vector_store import SessionVectorStore

# In-memory runtime store for MVP backend sessions.
session_store = SessionStore()
file_store = SessionFileStore(base_tmp_dir=get_settings().tmp_dir)
vector_store = SessionVectorStore()
usage_store = UsageStore()
