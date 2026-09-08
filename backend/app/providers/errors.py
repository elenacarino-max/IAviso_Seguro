"""Errores esperados de los adaptadores de modelos."""


class ProviderError(RuntimeError):
    """Base para fallos conocidos que no deben filtrar detalles internos."""


class ProviderConnectionError(ProviderError):
    """El proveedor no está disponible o agotó su tiempo de espera."""


class ProviderRateLimitError(ProviderError):
    """El proveedor rechazó temporalmente la petición por límite de uso."""

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        if retry_after_seconds is not None and (
            isinstance(retry_after_seconds, bool)
            or not isinstance(retry_after_seconds, int)
            or retry_after_seconds < 0
        ):
            raise ValueError("retry_after_seconds debe ser un entero no negativo.")
        super().__init__("El proveedor ha alcanzado su límite de peticiones.")
        self.retry_after_seconds = retry_after_seconds
