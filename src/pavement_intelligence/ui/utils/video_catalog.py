"""Catálogo controlado de videos locales para el Centro de Monitoreo."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable

import cv2


SUPPORTED_VIDEO_SUFFIXES = frozenset({".mp4", ".avi", ".mov", ".mkv"})
VIDEO_ROOTS = (Path("data/videos"), Path("data/videos/samples"))


@dataclass(frozen=True)
class LocalVideo:
    """Opción segura expuesta a la interfaz, siempre relativa al proyecto."""

    relative_path: str
    filename: str
    duration_seconds: float | None
    built_in: bool = False


def discover_local_videos(
    project_root: str | Path,
    *,
    built_in_video: str | Path | None = None,
    duration_reader: Callable[[Path], float | None] | None = None,
) -> tuple[LocalVideo, ...]:
    """Descubre videos permitidos sin seguir enlaces fuera de ``data/videos``.

    ``built_in_video`` permite conservar un único activo incorporado fuera de las
    raíces dinámicas. Debe ser una ruta relativa, existir dentro del proyecto y
    se valida por igualdad exacta; no amplía las carpetas que se recorren.
    """
    root = Path(project_root).resolve()
    reader = duration_reader or inspect_video_duration
    built_in_relative = (
        _relative_text(built_in_video) if built_in_video is not None else None
    )
    candidates: list[tuple[str, bool]] = []
    if built_in_relative is not None:
        resolve_video_path(root, built_in_relative, built_in_video=built_in_relative)
        candidates.append((built_in_relative, True))

    for relative_root in VIDEO_ROOTS:
        allowed_root = (root / relative_root).resolve()
        if not allowed_root.is_dir() or not _is_within(allowed_root, root):
            continue
        for candidate in allowed_root.rglob("*"):
            if candidate.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if not resolved.is_file() or not _is_within(resolved, allowed_root):
                continue
            candidates.append((resolved.relative_to(root).as_posix(), False))

    unique: dict[str, tuple[str, bool]] = {}
    for relative_path, built_in in candidates:
        key = relative_path.casefold()
        previous = unique.get(key)
        unique[key] = (relative_path, built_in or bool(previous and previous[1]))

    ordered = sorted(
        unique.values(), key=lambda item: (not item[1], item[0].casefold())
    )
    videos: list[LocalVideo] = []
    for relative_path, built_in in ordered:
        path = resolve_video_path(
            root, relative_path, built_in_video=built_in_relative
        )
        try:
            duration = reader(path)
        except (OSError, ValueError):
            duration = None
        videos.append(
            LocalVideo(
                relative_path=relative_path,
                filename=path.name,
                duration_seconds=duration,
                built_in=built_in,
            )
        )
    return tuple(videos)


def resolve_video_path(
    project_root: str | Path,
    relative_path: str | Path,
    *,
    built_in_video: str | Path | None = None,
) -> Path:
    """Resuelve una selección del catálogo y rechaza rutas externas o traversal."""
    root = Path(project_root).resolve()
    relative = _relative_text(relative_path)
    candidate = (root / Path(relative)).resolve(strict=True)
    if not candidate.is_file() or candidate.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        raise ValueError("La selección no corresponde a un video local permitido.")

    allowed_roots = tuple((root / item).resolve() for item in VIDEO_ROOTS)
    if any(_is_within(candidate, allowed_root) for allowed_root in allowed_roots):
        return candidate

    if built_in_video is not None:
        built_in_relative = _relative_text(built_in_video)
        built_in_path = (root / Path(built_in_relative)).resolve(strict=True)
        if candidate == built_in_path and _is_within(candidate, root):
            return candidate
    raise ValueError("El video seleccionado está fuera de las raíces permitidas.")


def inspect_video_duration(
    path: str | Path,
    *,
    capture_factory: Callable[[str], object] | None = None,
) -> float | None:
    """Lee solo FPS y número de frames y libera siempre el recurso de OpenCV."""
    factory = capture_factory or cv2.VideoCapture
    capture = factory(str(path))
    try:
        if not capture.isOpened():
            return None
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frames <= 0:
            return None
        return frames / fps
    finally:
        capture.release()


def stable_video_source_id(relative_path: str | Path) -> str:
    """Genera una identidad estable sin revelar rutas absolutas."""
    relative = _relative_text(relative_path)
    fingerprint = sha256(relative.casefold().encode("utf-8")).hexdigest()[:16]
    return f"local-video:{fingerprint}"


def _relative_text(value: str | Path) -> str:
    path = Path(value)
    if path.is_absolute() or path.drive or ".." in path.parts:
        raise ValueError("La ruta del video debe ser relativa y no admitir traversal.")
    text = path.as_posix().lstrip("./")
    if not text or text == ".":
        raise ValueError("La ruta del video no puede estar vacía.")
    return text


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


__all__ = [
    "LocalVideo",
    "SUPPORTED_VIDEO_SUFFIXES",
    "VIDEO_ROOTS",
    "discover_local_videos",
    "inspect_video_duration",
    "resolve_video_path",
    "stable_video_source_id",
]
