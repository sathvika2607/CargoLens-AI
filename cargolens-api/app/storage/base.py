import abc
from typing import AsyncIterator


class StorageService(abc.ABC):
    """
    Provider-neutral storage abstraction interface.
    Allows swappable backends (local disk, AWS S3, GCS, Azure Blob)
    without modifying document domain or ingestion business logic.
    """

    @abc.abstractmethod
    async def save_file(self, content_stream: AsyncIterator[bytes], storage_key: str) -> int:
        """
        Streams bytes into storage under the given storage key.
        Returns total bytes written.
        """
        pass

    @abc.abstractmethod
    async def get_file_stream(self, storage_key: str) -> AsyncIterator[bytes]:
        """
        Yields chunks of the stored file for streaming download.
        """
        pass

    @abc.abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """
        Removes file associated with the storage key.
        Returns True if deleted or already absent, False on failure.
        """
        pass

    @abc.abstractmethod
    async def file_exists(self, storage_key: str) -> bool:
        """
        Checks whether the file exists in storage.
        """
        pass

    @abc.abstractmethod
    def get_safe_storage_key(self, extension: str) -> str:
        """
        Generates an unguessable UUID-based storage key with the given extension.
        """
        pass
