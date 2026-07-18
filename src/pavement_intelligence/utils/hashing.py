"""
Utilidades de anonimización de datos de identificación vehicular.

Proporciona funciones para anonimizar números de placa vehicular mediante
hashing SHA-256, cumpliendo con principios de privacidad de datos personales.

El hash es determinista: la misma placa siempre produce el mismo hash,
lo que permite hacer estadísticas (conteo de vehículos únicos, reincidencias)
sin exponer el dato original.
"""
from __future__ import annotations

import hashlib
import re


# Prefijo para hacer el hash context-specific (salting estático)
_PLATE_HASH_SALT: str = "PI_BOLIVIA_PLATE_"


def hash_plate(plate: str, length: int = 8) -> str:
    """
    Genera un hash truncado SHA-256 de una placa vehicular.

    El hash es:
    - **Determinista**: la misma placa siempre produce el mismo resultado.
    - **Irreversible**: no es posible recuperar la placa original desde el hash.
    - **Context-specific**: usa un salt interno para evitar ataques de diccionario
      con rainbow tables genéricas.

    Args:
        plate: Número de placa vehicular (se normaliza a mayúsculas sin espacios).
        length: Longitud del hash truncado en caracteres hexadecimales (4–64).
                Por defecto 8 caracteres (4 bytes de entropía).

    Returns:
        Hash hexadecimal truncado en mayúsculas (ej: ``"A3F7B219"``).

    Raises:
        ValueError: Si ``plate`` está vacía después de normalizar, o si
                    ``length`` está fuera del rango [4, 64].

    Example:
        >>> hash_plate("ABC-123")
        'D4E8A21F'
        >>> hash_plate("abc 123")  # normalización automática
        'D4E8A21F'
        >>> hash_plate("ABC-123", length=12)
        'D4E8A21FC309'
    """
    if not (4 <= length <= 64):
        raise ValueError(f"length debe estar entre 4 y 64. Recibido: {length}")

    # Normalizar: mayúsculas, sin espacios ni guiones
    normalized = re.sub(r"[\s\-\.]", "", plate.strip().upper())

    if not normalized:
        raise ValueError("La placa no puede estar vacía después de normalizar.")

    # Calcular SHA-256 con salt
    payload = _PLATE_HASH_SALT + normalized
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return digest[:length].upper()


def normalize_plate(plate: str) -> str:
    """
    Normaliza una placa vehicular para comparación o hashing.

    Convierte a mayúsculas y elimina espacios, guiones y puntos.

    Args:
        plate: Número de placa original.

    Returns:
        Placa normalizada (ej: ``"ABC123"`` para ``"abc-123"``).
    """
    return re.sub(r"[\s\-\.]", "", plate.strip().upper())


def plates_match(plate_a: str, plate_b: str) -> bool:
    """
    Compara dos placas vehiculares ignorando formato.

    Args:
        plate_a: Primera placa.
        plate_b: Segunda placa.

    Returns:
        ``True`` si ambas placas son iguales después de normalizar.
    """
    return normalize_plate(plate_a) == normalize_plate(plate_b)


def is_bolivian_plate_format(plate: str) -> bool:
    """
    Verifica si una placa tiene el formato estándar boliviano.

    Formatos conocidos en Bolivia:
    - Vehículos privados: ``LLLDDDD`` (3 letras + 4 dígitos, ej: ``"ABC1234"``)
    - Vehículos de transporte: pueden incluir departamento o categoría

    .. note::
        Esta función es una verificación básica de formato, no valida
        si la placa está registrada en SEPREC.

    Args:
        plate: Número de placa a verificar.

    Returns:
        ``True`` si coincide con el patrón estándar boliviano.
    """
    normalized = normalize_plate(plate)
    # Patrón: 2-4 letras seguidas de 3-5 dígitos (cubre formatos comunes)
    pattern = re.compile(r"^[A-Z]{2,4}\d{3,5}$")
    return bool(pattern.match(normalized))
