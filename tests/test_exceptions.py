"""Testes para o sistema de exceções customizadas."""

import pytest
from pathlib import Path

from emumanager.common.exceptions import (
    EmuManagerError,
    ConfigurationError,
    FileOperationError,
    FileNotFoundError,
    ValidationError,
    IntegrityError,
    ProviderError,
    ConversionError,
    DatabaseError,
    WorkflowCancelledError,
    format_exception_chain,
)


class TestBaseException:
    """Testes para a exceção base."""
    
    def test_basic_creation(self):
        exc = EmuManagerError("test error")
        assert str(exc) == "test error"
        assert exc.message == "test error"
        assert exc.details == {}
    
    def test_with_details(self):
        exc = EmuManagerError("test error", {"key": "value", "count": 42})
        assert "key=value" in str(exc)
        assert "count=42" in str(exc)
    
    def test_inheritance(self):
        exc = ConfigurationError("config error")
        assert isinstance(exc, EmuManagerError)
        assert isinstance(exc, Exception)


class TestFileOperationErrors:
    """Testes para erros de operações de ficheiros."""
    
    def test_file_operation_error(self):
        exc = FileOperationError("/path/to/file", "failed to process")
        assert exc.path == "/path/to/file"
        assert "failed to process" in str(exc)
        assert "path=/path/to/file" in str(exc)
    
    def test_file_not_found(self):
        exc = FileNotFoundError("/missing/file.txt")
        assert exc.path == "/missing/file.txt"
        assert "não encontrado" in str(exc).lower()


class TestValidationErrors:
    """Testes para erros de validação."""
    
    def test_validation_error(self):
        exc = ValidationError("invalid input")
        assert str(exc) == "invalid input"
    
    def test_integrity_error(self):
        exc = IntegrityError(
            "/path/to/file",
            expected="abc123",
            actual="def456",
            hash_type="md5"
        )
        assert exc.details["path"] == "/path/to/file"
        assert exc.details["expected"] == "abc123"
        assert exc.details["actual"] == "def456"
        assert "md5" in str(exc).lower()


class TestProviderErrors:
    """Testes para erros de providers."""
    
    def test_provider_error(self):
        exc = ProviderError("ps2", "failed to load")
        assert exc.system == "ps2"
        assert "ps2" in str(exc)
    
    def test_unsupported_system(self):
        exc = ProviderError("unknown_system", "not supported")
        assert exc.system == "unknown_system"


class TestWorkflowErrors:
    """Testes para erros de workflow."""
    
    def test_workflow_cancelled(self):
        exc = WorkflowCancelledError("scan_workflow")
        assert "scan_workflow" in str(exc)
        assert "cancelado" in str(exc).lower()


class TestExceptionChainFormatting:
    """Testes para formatação de cadeia de exceções."""
    
    def test_single_exception(self):
        exc = ValidationError("test error")
        formatted = format_exception_chain(exc)
        assert "test error" in formatted
    
    def test_exception_chain(self):
        inner = ValueError("inner error")
        outer = ConfigurationError("outer error")
        outer.__cause__ = inner
        
        formatted = format_exception_chain(outer)
        assert "outer error" in formatted
        assert "inner error" in formatted
        assert "→" in formatted
    
    def test_with_traceback(self):
        try:
            raise ValidationError("test with traceback")
        except ValidationError as e:
            formatted = format_exception_chain(e, include_traceback=True)
            assert "Traceback" in formatted
            assert "test with traceback" in formatted
