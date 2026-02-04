"""Hierarquia de exceções customizadas do EmuManager.

Este módulo centraliza todas as exceções específicas do projeto,
fornecendo uma hierarquia clara e semântica para tratamento de erros.
"""

from __future__ import annotations
from typing import Optional, Any


# ============================================================================
# BASE EXCEPTIONS
# ============================================================================

class EmuManagerError(Exception):
    """Exceção base para todos os erros do EmuManager.
    
    Todas as exceções customizadas do projeto devem herdar desta classe.
    """
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# ============================================================================
# CONFIGURATION & INITIALIZATION ERRORS
# ============================================================================

class ConfigurationError(EmuManagerError):
    """Erro relacionado à configuração do sistema."""
    pass


class InitializationError(EmuManagerError):
    """Erro durante a inicialização da biblioteca ou componentes."""
    pass


class DependencyError(EmuManagerError):
    """Erro quando uma dependência externa não está disponível."""
    
    def __init__(self, tool_name: str, message: str = None):
        msg = message or f"Ferramenta necessária não encontrada: {tool_name}"
        super().__init__(msg, {"tool": tool_name})
        self.tool_name = tool_name


# ============================================================================
# FILE OPERATION ERRORS
# ============================================================================

class FileOperationError(EmuManagerError):
    """Erro base para operações com ficheiros."""
    
    def __init__(self, path: str, message: str, details: Optional[dict] = None):
        details = details or {}
        details["path"] = path
        super().__init__(message, details)
        self.path = path


class FileNotFoundError(FileOperationError):
    """Ficheiro não encontrado."""
    
    def __init__(self, path: str):
        super().__init__(path, f"Ficheiro não encontrado: {path}")


class FileReadError(FileOperationError):
    """Erro ao ler ficheiro."""
    pass


class FileWriteError(FileOperationError):
    """Erro ao escrever ficheiro."""
    pass


class FileMoveError(FileOperationError):
    """Erro ao mover ficheiro."""
    pass


class FileDeleteError(FileOperationError):
    """Erro ao eliminar ficheiro."""
    pass


class InsufficientSpaceError(FileOperationError):
    """Espaço em disco insuficiente."""
    
    def __init__(self, path: str, required: int, available: int):
        super().__init__(
            path,
            f"Espaço insuficiente: necessário {required} bytes, disponível {available} bytes",
            {"required": required, "available": available}
        )


# ============================================================================
# VALIDATION & INTEGRITY ERRORS
# ============================================================================

class ValidationError(EmuManagerError):
    """Erro de validação de dados ou ficheiros."""
    pass


class IntegrityError(ValidationError):
    """Erro de integridade de ficheiro (hash mismatch, corrupção)."""
    
    def __init__(self, path: str, expected: str, actual: str, hash_type: str = "hash"):
        super().__init__(
            f"Falha de integridade em {path}: {hash_type} esperado {expected}, obtido {actual}",
            {"path": path, "expected": expected, "actual": actual, "hash_type": hash_type}
        )


class CorruptedFileError(ValidationError):
    """Ficheiro corrompido ou malformado."""
    
    def __init__(self, path: str, reason: str = ""):
        msg = f"Ficheiro corrompido: {path}"
        if reason:
            msg += f" - {reason}"
        super().__init__(msg, {"path": path, "reason": reason})


# ============================================================================
# SYSTEM PROVIDER ERRORS
# ============================================================================

class ProviderError(EmuManagerError):
    """Erro base para providers de sistemas."""
    
    def __init__(self, system: str, message: str, details: Optional[dict] = None):
        details = details or {}
        details["system"] = system
        super().__init__(message, details)
        self.system = system


class UnsupportedSystemError(ProviderError):
    """Sistema não suportado."""
    
    def __init__(self, system: str):
        super().__init__(system, f"Sistema não suportado: {system}")


class MetadataExtractionError(ProviderError):
    """Erro ao extrair metadados de ficheiro."""
    
    def __init__(self, system: str, path: str, reason: str = ""):
        msg = f"Falha ao extrair metadados de {path}"
        if reason:
            msg += f": {reason}"
        super().__init__(system, msg, {"path": path, "reason": reason})


class UnsupportedFormatError(ProviderError):
    """Formato de ficheiro não suportado pelo sistema."""
    
    def __init__(self, system: str, extension: str):
        super().__init__(
            system,
            f"Formato {extension} não suportado pelo sistema {system}",
            {"extension": extension}
        )


# ============================================================================
# CONVERSION & COMPRESSION ERRORS
# ============================================================================

class ConversionError(EmuManagerError):
    """Erro durante conversão/compressão de ficheiro."""
    
    def __init__(self, source: str, target_format: str, reason: str = ""):
        msg = f"Falha ao converter {source} para {target_format}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, {"source": source, "format": target_format, "reason": reason})


class CompressionError(ConversionError):
    """Erro específico de compressão."""
    pass


class DecompressionError(ConversionError):
    """Erro específico de descompressão."""
    pass


# ============================================================================
# DATABASE ERRORS
# ============================================================================

class DatabaseError(EmuManagerError):
    """Erro relacionado à base de dados."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Erro ao conectar à base de dados."""
    pass


class DatabaseIntegrityError(DatabaseError):
    """Erro de integridade na base de dados."""
    pass


class EntryNotFoundError(DatabaseError):
    """Entrada não encontrada na base de dados."""
    
    def __init__(self, key: str, table: str = "library"):
        super().__init__(
            f"Entrada não encontrada: {key} em {table}",
            {"key": key, "table": table}
        )


# ============================================================================
# WORKFLOW & ORCHESTRATION ERRORS
# ============================================================================

class WorkflowError(EmuManagerError):
    """Erro durante execução de workflow."""
    pass


class WorkflowCancelledError(WorkflowError):
    """Workflow foi cancelado pelo utilizador."""
    
    def __init__(self, workflow_name: str = ""):
        msg = f"Workflow cancelado: {workflow_name}" if workflow_name else "Workflow cancelado"
        super().__init__(msg, {"workflow": workflow_name})


class WorkflowTimeoutError(WorkflowError):
    """Workflow excedeu tempo limite."""
    
    def __init__(self, workflow_name: str, timeout: float):
        super().__init__(
            f"Workflow {workflow_name} excedeu timeout de {timeout}s",
            {"workflow": workflow_name, "timeout": timeout}
        )


# ============================================================================
# METADATA & DAT ERRORS
# ============================================================================

class DATError(EmuManagerError):
    """Erro relacionado a ficheiros DAT."""
    pass


class DATParseError(DATError):
    """Erro ao fazer parse de ficheiro DAT."""
    
    def __init__(self, path: str, reason: str = ""):
        msg = f"Falha ao processar DAT {path}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, {"path": path, "reason": reason})


class DATNotFoundError(DATError):
    """Ficheiro DAT não encontrado."""
    
    def __init__(self, system: str):
        super().__init__(
            f"DAT não encontrado para sistema {system}",
            {"system": system}
        )


# ============================================================================
# NETWORKING ERRORS
# ============================================================================

class NetworkError(EmuManagerError):
    """Erro relacionado a operações de rede."""
    pass


class DownloadError(NetworkError):
    """Erro ao fazer download de ficheiro."""
    
    def __init__(self, url: str, reason: str = ""):
        msg = f"Falha ao descarregar {url}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, {"url": url, "reason": reason})


class MetadataServiceError(NetworkError):
    """Erro ao comunicar com serviço de metadados externo."""
    
    def __init__(self, service: str, reason: str = ""):
        msg = f"Falha ao comunicar com {service}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, {"service": service, "reason": reason})


# ============================================================================
# GUI ERRORS
# ============================================================================

class GUIError(EmuManagerError):
    """Erro relacionado à interface gráfica."""
    pass


class GUIInitializationError(GUIError):
    """Erro ao inicializar a GUI."""
    pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_exception_chain(exc: Exception, include_traceback: bool = False) -> str:
    """Formata uma exceção com toda a cadeia de causas.
    
    Args:
        exc: Exceção a formatar
        include_traceback: Se deve incluir o traceback completo
        
    Returns:
        String formatada com a exceção e suas causas
    """
    import traceback
    
    if include_traceback:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    messages = []
    current = exc
    while current is not None:
        if isinstance(current, EmuManagerError):
            messages.append(str(current))
        else:
            messages.append(f"{type(current).__name__}: {current}")
        current = getattr(current, "__cause__", None)
    
    return " → ".join(messages)
