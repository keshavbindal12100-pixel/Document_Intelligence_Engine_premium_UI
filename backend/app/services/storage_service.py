import os
import uuid

import aiofiles
from backend.app.core.config import settings
from backend.app.core.exceptions import FileStorageException


class StorageService:
    """Service handling local filesystem operations for uploaded documents."""

    def __init__(self, base_dir: str = settings.STORAGE_LOCAL_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_workspace_dir(self, workspace_id: uuid.UUID) -> str:
        workspace_dir = os.path.join(self.base_dir, str(workspace_id))
        os.makedirs(workspace_dir, exist_ok=True)
        return workspace_dir

    async def save_file(
        self,
        workspace_id: uuid.UUID,
        file_bytes: bytes,
        extension: str,
    ) -> tuple[str, str]:
        """Save file bytes to disk under the workspace isolation directory.
        Returns: (generated_filename, relative_or_absolute_file_path)
        """
        try:
            workspace_dir = self._get_workspace_dir(workspace_id)
            unique_name = f"{uuid.uuid4().hex}.{extension}"
            file_path = os.path.join(workspace_dir, unique_name)

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_bytes)

            return unique_name, os.path.abspath(file_path)
        except Exception as e:
            raise FileStorageException(f"Failed to save file: {str(e)}") from e

    async def read_file(self, file_path: str) -> bytes:
        """Read file bytes from path."""
        if not os.path.exists(file_path):
            raise FileStorageException(f"File at {file_path} not found.")
        try:
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except Exception as e:
            raise FileStorageException(f"Failed to read file: {str(e)}") from e

    async def delete_file(self, file_path: str) -> bool:
        """Remove file from storage."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            raise FileStorageException(f"Failed to delete file: {str(e)}") from e


storage_service = StorageService()
