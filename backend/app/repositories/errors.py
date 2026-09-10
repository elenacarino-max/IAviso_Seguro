"""Errores controlados de persistencia y transición."""


class RepositoryError(RuntimeError):
    """Base segura para fallos conocidos de persistencia."""


class NoticeNotFoundError(RepositoryError):
    """El aviso solicitado no existe."""


class ReviewConflictError(RepositoryError):
    """La propuesta ya cambió o no admite otra revisión."""


class PersistenceError(RepositoryError):
    """SQLite no pudo completar una operación esperada."""
