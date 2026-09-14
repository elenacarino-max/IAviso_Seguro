"""Normalización compartida de zonas textuales, sin fuzzy matching."""

import unicodedata

MISSING_LOCATION_LABEL = "Sin ubicación"


def normalize_location(location: str | None) -> str | None:
    """Devuelve una clave NFKC estable, insensible a caja y espacios externos."""

    if location is None:
        return None
    collapsed = " ".join(unicodedata.normalize("NFKC", location).split())
    return collapsed.casefold() or None


def location_display_label(normalized_location: str | None) -> str:
    """Convierte la clave normalizada en una etiqueta breve y reproducible."""

    if normalized_location is None:
        return MISSING_LOCATION_LABEL
    return normalized_location[:1].upper() + normalized_location[1:]

