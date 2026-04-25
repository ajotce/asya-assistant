from __future__ import annotations

from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.models.schemas import SessionUploadedFileInfo
from app.storage.file_store import SessionFileStore, StoredSessionFile
from app.storage.session_store import SessionStore

_ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
_ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".heic",
}
_ALLOWED_IMAGE_CONTENT_PREFIX = "image/"
_READ_CHUNK_SIZE = 1024 * 1024


class FileValidationError(Exception):
    def __init__(self, user_message: str, status_code: int = 400) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


class FileService:
    def __init__(self, settings: Settings, session_store: SessionStore, file_store: SessionFileStore) -> None:
        self._settings = settings
        self._session_store = session_store
        self._file_store = file_store

    async def upload_files(self, session_id: str, files: List[UploadFile]) -> List[SessionUploadedFileInfo]:
        if not self._session_store.has_session(session_id):
            raise FileValidationError("Сессия не найдена.", status_code=404)
        if not files:
            raise FileValidationError("Не выбраны файлы для загрузки.")
        if len(files) > self._settings.max_files_per_message:
            raise FileValidationError(
                f"Можно загрузить не более {self._settings.max_files_per_message} файлов за одно сообщение."
            )

        pending_files: List[StoredSessionFile] = []
        try:
            for upload in files:
                pending = await self._save_single_upload(session_id=session_id, upload=upload)
                pending_files.append(pending)
        except FileValidationError:
            self._cleanup_pending_files(pending_files)
            raise
        finally:
            for upload in files:
                await upload.close()

        self._file_store.register_files(session_id, pending_files)
        for pending in pending_files:
            self._session_store.bind_file(session_id=session_id, file_id=pending.file_id)

        return [
            SessionUploadedFileInfo(
                file_id=file.file_id,
                filename=file.filename,
                content_type=file.content_type,
                size_bytes=file.size_bytes,
            )
            for file in pending_files
        ]

    async def _save_single_upload(self, session_id: str, upload: UploadFile) -> StoredSessionFile:
        filename = Path(upload.filename or "").name.strip()
        if not filename:
            raise FileValidationError("У файла отсутствует имя.")

        content_type = (upload.content_type or "application/octet-stream").strip()
        self._validate_supported_type(filename=filename, content_type=content_type)

        file_id = str(uuid4())
        session_dir = self._file_store.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        target_path = session_dir / f"{file_id}_{filename}"

        max_file_size_bytes = self._settings.max_file_size_mb * 1024 * 1024
        total_size = 0

        with target_path.open("wb") as out:
            while True:
                chunk = await upload.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_file_size_bytes:
                    out.close()
                    target_path.unlink(missing_ok=True)
                    raise FileValidationError(
                        f"Файл '{filename}' превышает лимит {self._settings.max_file_size_mb} МБ."
                    )
                out.write(chunk)

        if total_size == 0:
            target_path.unlink(missing_ok=True)
            raise FileValidationError(f"Файл '{filename}' пустой.")

        return StoredSessionFile(
            file_id=file_id,
            session_id=session_id,
            filename=filename,
            content_type=content_type,
            size_bytes=total_size,
            path=str(target_path),
        )

    @staticmethod
    def _cleanup_pending_files(files: List[StoredSessionFile]) -> None:
        for file in files:
            Path(file.path).unlink(missing_ok=True)

    @staticmethod
    def _validate_supported_type(filename: str, content_type: str) -> None:
        suffix = Path(filename).suffix.lower()
        if suffix in _ALLOWED_DOC_EXTENSIONS:
            return
        if suffix in _ALLOWED_IMAGE_EXTENSIONS:
            return
        if content_type.lower().startswith(_ALLOWED_IMAGE_CONTENT_PREFIX):
            return
        raise FileValidationError(
            f"Файл '{filename}' не поддерживается. Разрешены типы: PDF, DOCX, XLSX и изображения."
        )
