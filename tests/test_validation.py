"""Testes para o sistema de validação."""

import pytest
from pathlib import Path
import tempfile
import os

from emumanager.common.validation import (
    validate_path_exists,
    validate_writable_directory,
    validate_file_extension,
    validate_positive,
    validate_non_negative,
    validate_range,
    validate_percentage,
    validate_not_empty,
    validate_regex,
    validate_max_length,
    validate_not_empty_list,
    validate_all,
    validate_unique,
    validate_type,
    validate_callable,
    validate_system_id,
    validate_serial_format,
    validate_hash_format,
    ValidationContext,
    validate_dict_schema,
)
from emumanager.common.exceptions import ValidationError, FileNotFoundError


class TestPathValidation:
    """Testes para validação de caminhos."""
    
    def test_validate_existing_path(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        result = validate_path_exists(test_file)
        assert result.exists()
        assert result == test_file.resolve()
    
    def test_validate_nonexistent_path(self):
        with pytest.raises(FileNotFoundError):
            validate_path_exists("/nonexistent/path")
    
    def test_validate_must_be_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        # Should pass for file
        validate_path_exists(test_file, must_be_file=True)
        
        # Should fail for directory
        with pytest.raises(ValidationError, match="deve ser um ficheiro"):
            validate_path_exists(tmp_path, must_be_file=True)
    
    def test_validate_must_be_dir(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        # Should pass for directory
        validate_path_exists(tmp_path, must_be_dir=True)
        
        # Should fail for file
        with pytest.raises(ValidationError, match="deve ser um diretório"):
            validate_path_exists(test_file, must_be_dir=True)
    
    def test_validate_writable_directory(self, tmp_path):
        result = validate_writable_directory(tmp_path)
        assert result.exists()
        assert result.is_dir()


class TestNumericValidation:
    """Testes para validação numérica."""
    
    def test_validate_positive(self):
        assert validate_positive(5) == 5
        assert validate_positive(0.1) == 0.1
        
        with pytest.raises(ValidationError):
            validate_positive(0)
        
        with pytest.raises(ValidationError):
            validate_positive(-5)
    
    def test_validate_non_negative(self):
        assert validate_non_negative(0) == 0
        assert validate_non_negative(5) == 5
        
        with pytest.raises(ValidationError):
            validate_non_negative(-1)
    
    def test_validate_range(self):
        assert validate_range(5, 0, 10) == 5
        assert validate_range(0, 0, 10) == 0
        assert validate_range(10, 0, 10) == 10
        
        with pytest.raises(ValidationError):
            validate_range(-1, 0, 10)
        
        with pytest.raises(ValidationError):
            validate_range(11, 0, 10)
    
    def test_validate_percentage(self):
        assert validate_percentage(0.0) == 0.0
        assert validate_percentage(0.5) == 0.5
        assert validate_percentage(1.0) == 1.0
        
        with pytest.raises(ValidationError):
            validate_percentage(-0.1)
        
        with pytest.raises(ValidationError):
            validate_percentage(1.1)


class TestStringValidation:
    """Testes para validação de strings."""
    
    def test_validate_not_empty(self):
        assert validate_not_empty("test") == "test"
        
        with pytest.raises(ValidationError):
            validate_not_empty("")
        
        with pytest.raises(ValidationError):
            validate_not_empty("   ")
    
    def test_validate_regex(self):
        assert validate_regex("ABC123", r"^[A-Z]+\d+$") == "ABC123"
        
        with pytest.raises(ValidationError):
            validate_regex("abc123", r"^[A-Z]+\d+$")
    
    def test_validate_max_length(self):
        assert validate_max_length("test", 10) == "test"
        
        with pytest.raises(ValidationError):
            validate_max_length("test", 3)


class TestCollectionValidation:
    """Testes para validação de coleções."""
    
    def test_validate_not_empty_list(self):
        assert validate_not_empty_list([1, 2, 3]) == [1, 2, 3]
        
        with pytest.raises(ValidationError):
            validate_not_empty_list([])
    
    def test_validate_all(self):
        is_positive = lambda x: x > 0
        
        assert validate_all([1, 2, 3], is_positive) == [1, 2, 3]
        
        with pytest.raises(ValidationError):
            validate_all([1, -1, 3], is_positive)
    
    def test_validate_unique(self):
        assert validate_unique([1, 2, 3]) == [1, 2, 3]
        
        with pytest.raises(ValidationError):
            validate_unique([1, 2, 2, 3])


class TestTypeValidation:
    """Testes para validação de tipos."""
    
    def test_validate_type(self):
        assert validate_type("test", str) == "test"
        assert validate_type(123, int) == 123
        
        with pytest.raises(ValidationError):
            validate_type("test", int)
    
    def test_validate_callable(self):
        def func():
            pass
        
        assert validate_callable(func) == func
        assert validate_callable(lambda: None)
        
        with pytest.raises(ValidationError):
            validate_callable("not a function")


class TestSystemSpecificValidation:
    """Testes para validações específicas do sistema."""
    
    def test_validate_system_id(self):
        systems = ["ps2", "switch", "psx"]
        
        assert validate_system_id("ps2", systems) == "ps2"
        
        with pytest.raises(ValidationError):
            validate_system_id("unknown", systems)
    
    def test_validate_serial_format(self):
        assert validate_serial_format("SLUS-12345") == "SLUS-12345"
        assert validate_serial_format("slus-12345") == "SLUS-12345"
        assert validate_serial_format("SLUS_12345") == "SLUS_12345"
        
        with pytest.raises(ValidationError):
            validate_serial_format("INVALID")
    
    def test_validate_hash_format(self):
        # MD5
        md5 = "d41d8cd98f00b204e9800998ecf8427e"
        assert validate_hash_format(md5, "md5") == md5
        
        # SHA1
        sha1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        assert validate_hash_format(sha1, "sha1") == sha1
        
        # SHA256
        sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert validate_hash_format(sha256, "sha256") == sha256
        
        # CRC32
        crc = "00000000"
        assert validate_hash_format(crc, "crc32") == crc
        
        # Invalid length
        with pytest.raises(ValidationError):
            validate_hash_format("short", "md5")
        
        # Invalid characters
        with pytest.raises(ValidationError):
            validate_hash_format("g" * 32, "md5")


class TestValidationContext:
    """Testes para ValidationContext."""
    
    def test_no_errors(self):
        with ValidationContext() as ctx:
            ctx.validate(lambda: validate_positive(5))
        
        assert ctx.is_valid
        assert len(ctx.errors) == 0
    
    def test_single_error(self):
        with pytest.raises(ValidationError) as exc_info:
            with ValidationContext() as ctx:
                ctx.validate(lambda: validate_positive(-1))
        
        assert "1 erro" in str(exc_info.value)
    
    def test_multiple_errors(self):
        with pytest.raises(ValidationError) as exc_info:
            with ValidationContext() as ctx:
                ctx.validate(lambda: validate_positive(-1))
                ctx.validate(lambda: validate_not_empty(""))
                ctx.validate(lambda: validate_range(100, 0, 10))
        
        assert "3 erro" in str(exc_info.value)
    
    def test_no_raise_on_exit(self):
        with ValidationContext(raise_on_exit=False) as ctx:
            ctx.validate(lambda: validate_positive(-1))
        
        assert not ctx.is_valid
        assert len(ctx.errors) > 0


class TestDictSchemaValidation:
    """Testes para validação de schema de dicionário."""
    
    def test_valid_schema(self):
        schema = {
            "name": validate_not_empty,
            "age": lambda x: validate_range(x, 0, 150),
            "email": lambda x: validate_regex(x, r".+@.+\..+"),
        }
        
        data = {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com",
        }
        
        result = validate_dict_schema(data, schema)
        assert result["name"] == "John Doe"
        assert result["age"] == 30
        assert result["email"] == "john@example.com"
    
    def test_missing_key(self):
        schema = {"required_key": validate_not_empty}
        data = {}
        
        with pytest.raises(ValidationError, match="obrigatória ausente"):
            validate_dict_schema(data, schema)
    
    def test_extra_keys_strict(self):
        schema = {"name": validate_not_empty}
        data = {"name": "Test", "extra": "value"}
        
        with pytest.raises(ValidationError, match="não esperadas"):
            validate_dict_schema(data, schema, strict=True)
    
    def test_extra_keys_non_strict(self):
        schema = {"name": validate_not_empty}
        data = {"name": "Test", "extra": "value"}
        
        # Should not raise in non-strict mode
        result = validate_dict_schema(data, schema, strict=False)
        assert result["name"] == "Test"
