"""Validación y ciclo de vida temporal para videos cargados por el usuario."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Protocol
from uuid import uuid4

from pavement_intelligence.ui.utils.video_catalog import inspect_video_duration


MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024
MAX_UPLOAD_SIZE_MIB = 500
ALLOWED_UPLOAD_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv"})
ALLOWED_MIME_TYPES = {
    ".mp4": frozenset({"video/mp4", "application/mp4"}),
    ".avi": frozenset({"video/avi", "video/x-msvideo"}),
    ".mov": frozenset({"video/quicktime"}),
    ".mkv": frozenset({"video/mkv", "video/x-matroska"}),
}
GENERIC_MIME_TYPES = frozenset({"", "application/octet-stream"})


class UploadedVideoLike(Protocol):
    name: str
    type: str | None
    size: int

    def getvalue(self) -> bytes: ...


class UploadedVideoError(ValueError):
    """Error controlado de validación o persistencia de un video cargado."""


@dataclass(frozen=True)
class UploadedVideoHandle:
    original_name: str
    safe_name: str
    temporary_path: Path
    sha256: str
    size_bytes: int
    extension: str
    duration_seconds: float
    source_id: str
    cleanup_token: str
    _temporary_directory: TemporaryDirectory[str] = field(
        repr=False, compare=False
    )

    @property
    def is_available(self) -> bool:
        return self.temporary_path.is_file()


def store_uploaded_video(
    uploaded: UploadedVideoLike,
    *,
    previous: UploadedVideoHandle | None = None,
    max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES,
    temporary_parent: str | Path | None = None,
    duration_reader: Callable[[Path], float | None] | None = None,
) -> UploadedVideoHandle:
    """Valida, deduplica y persiste un upload dentro de un temporal controlado."""
    try:
        original_name, extension, content, digest = _validated_content(
            uploaded, max_size_bytes=max_size_bytes
        )
    except Exception:
        cleanup_uploaded_video(previous)
        raise

    if (
        previous is not None
        and previous.sha256 == digest
        and previous.is_available
    ):
        return previous

    cleanup_uploaded_video(previous)
    parent = Path(temporary_parent).resolve() if temporary_parent is not None else None
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    directory = TemporaryDirectory(
        prefix="pavement-traffic-upload-",
        dir=str(parent) if parent is not None else None,
    )
    safe_name = f"video-{uuid4().hex}{extension}"
    temporary_path = Path(directory.name) / safe_name
    try:
        with temporary_path.open("xb") as output:
            output.write(content)
        reader = duration_reader or inspect_video_duration
        duration = reader(temporary_path)
        if duration is None or duration <= 0:
            raise UploadedVideoError(
                "OpenCV no pudo abrir el video cargado o sus metadatos son inválidos."
            )
        return UploadedVideoHandle(
            original_name=original_name,
            safe_name=safe_name,
            temporary_path=temporary_path,
            sha256=digest,
            size_bytes=len(content),
            extension=extension,
            duration_seconds=float(duration),
            source_id=f"uploaded-video:{digest[:16]}",
            cleanup_token=uuid4().hex,
            _temporary_directory=directory,
        )
    except Exception:
        directory.cleanup()
        raise


def cleanup_uploaded_video(handle: UploadedVideoHandle | None) -> None:
    """Elimina idempotentemente el directorio temporal asociado al handle."""
    if handle is None:
        return
    handle._temporary_directory.cleanup()


def uploaded_video_digest(
    uploaded: UploadedVideoLike,
    *,
    max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES,
) -> str:
    """Valida metadatos y contenido y devuelve la huella sin escribir archivos."""
    return _validated_content(uploaded, max_size_bytes=max_size_bytes)[3]


def _validated_content(
    uploaded: UploadedVideoLike,
    *,
    max_size_bytes: int,
) -> tuple[str, str, bytes, str]:
    if max_size_bytes <= 0:
        raise ValueError("max_size_bytes debe ser positivo.")
    if uploaded is None:
        raise UploadedVideoError("No se recibió un archivo de video.")

    raw_name = str(getattr(uploaded, "name", "") or "")
    normalized_name = raw_name.replace("\\", "/")
    original_name = normalized_name.rsplit("/", 1)[-1]
    if not original_name or normalized_name != original_name or ".." in Path(original_name).parts:
        raise UploadedVideoError("El nombre del archivo no puede contener una ruta.")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise UploadedVideoError(
            "Formato no permitido. Usa únicamente MP4, AVI, MOV o MKV."
        )

    declared_size = getattr(uploaded, "size", None)
    if not isinstance(declared_size, int) or isinstance(declared_size, bool):
        raise UploadedVideoError("El archivo no informa un tamaño válido.")
    if declared_size <= 0:
        raise UploadedVideoError("El archivo cargado está vacío.")
    if declared_size > max_size_bytes:
        raise UploadedVideoError(
            f"El archivo supera el límite de {max_size_bytes / 1024 / 1024:.0f} MiB."
        )

    mime_type = str(getattr(uploaded, "type", "") or "").lower().strip()
    if (
        mime_type not in GENERIC_MIME_TYPES
        and mime_type not in ALLOWED_MIME_TYPES[extension]
    ):
        raise UploadedVideoError(
            f"El tipo MIME {mime_type!r} no corresponde al formato {extension}."
        )

    content = uploaded.getvalue()
    if not isinstance(content, bytes):
        content = bytes(content)
    if not content:
        raise UploadedVideoError("El archivo cargado está vacío.")
    if len(content) > max_size_bytes:
        raise UploadedVideoError(
            f"El archivo supera el límite de {max_size_bytes / 1024 / 1024:.0f} MiB."
        )
    if len(content) != declared_size:
        raise UploadedVideoError("El tamaño declarado no coincide con el contenido.")
    return original_name, extension, content, sha256(content).hexdigest()


__all__ = [
    "ALLOWED_MIME_TYPES",
    "ALLOWED_UPLOAD_EXTENSIONS",
    "MAX_UPLOAD_SIZE_BYTES",
    "MAX_UPLOAD_SIZE_MIB",
    "UploadedVideoError",
    "UploadedVideoHandle",
    "cleanup_uploaded_video",
    "store_uploaded_video",
    "uploaded_video_digest",
]
