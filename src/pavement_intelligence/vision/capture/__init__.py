"""
Submódulo de captura de video para Pavement Intelligence.
Proporciona fuentes abstractas e implementaciones concretas
para archivos, cámaras en vivo y streams RTSP.
"""

from .base import AbstractVideoSource, FrameResult, FrameSource, SourceInfo
from .camera_source import CameraSource
from .file_source import FileVideoSource, VideoFileSource

__all__ = [
    "AbstractVideoSource", "CameraSource", "FileVideoSource", "FrameResult",
    "FrameSource", "SourceInfo", "VideoFileSource",
]
