"""Storage adapters for evaluation results."""

from .base import StorageAdapter
from .filesystem import FilesystemStorage


__all__ = ["StorageAdapter", "FilesystemStorage"]
