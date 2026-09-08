"""Errores controlados de las herramientas permitidas."""


class ToolError(RuntimeError):
    """Base para errores que pueden traducirse sin revelar detalles internos."""


class InvalidToolArgumentsError(ToolError):
    """Los argumentos no cumplen el contrato cerrado de la herramienta."""


class InvalidRiskMatrixError(ToolError):
    """La matriz no existe, no es JSON válido o incumple su contrato."""


class RequiredToolCallError(ToolError):
    """El proveedor intentó finalizar sin consultar la herramienta requerida."""


class ToolStepLimitError(ToolError):
    """El proveedor solicitó más acciones de herramienta de las permitidas."""
