"""
Storage module for file management.

Provides services for storing and retrieving files:
- AudioStorageService: Audio file storage and retrieval
- DocumentStorageService: Document file storage and retrieval
"""

from .audio import AudioStorageService, get_audio_storage_service
from .document import DocumentStorageService, get_document_storage_service

__all__ = [
    "AudioStorageService",
    "get_audio_storage_service",
    "DocumentStorageService",
    "get_document_storage_service",
]
