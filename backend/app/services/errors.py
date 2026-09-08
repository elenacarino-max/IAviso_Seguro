"""Errores controlados de la capa de servicios."""


class InvalidProviderOutputError(RuntimeError):
    """La salida no cumplió el contrato tras agotar la reparación."""

    def __init__(self, attempts: int) -> None:
        super().__init__("La respuesta del proveedor no cumple el contrato de triaje.")
        self.attempts = attempts
