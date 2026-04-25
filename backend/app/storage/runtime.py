from app.core.config import get_settings
from app.storage.file_store import SessionFileStore
from app.storage.session_store import SessionStore

# In-memory runtime store for MVP backend sessions.
session_store = SessionStore()
file_store = SessionFileStore(base_tmp_dir=get_settings().tmp_dir)
