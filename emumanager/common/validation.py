"""Utilitários de validação robusta para entrada de dados.

Este módulo centraliza todas as validações de entrada do projeto,
fornecendo funções reutilizáveis e type-safe.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar, Optional

from .exceptions import ValidationError, FileNotFoundError, ConfigurationError


T = TypeVar('T')


# ============================================================================
# PATH VALIDATION
# ============================================================================

def validate_path_exists(
    path: Path | str,
    name: str = "path",
    must_be_file: bool = False,
    must_be_dir: bool = False
) -> Path:
    """Valida que um caminho existe.
    
    Args:
        path: Caminho a validar
        name: Nome do parâmetro (para mensagens de erro)
        must_be_file: Se True, valida que é um ficheiro
        must_be_dir: Se True, valida que é um diretório
        
    Returns:
        Path validado e resolvido
        
    Raises:
        ValidationError: Se o caminho não existe ou tipo incorreto
    """
    if not path:
        raise ValidationError(f"{name} não pode estar vazio")
    
    p = Path(path).resolve()
    
    if not p.exists():
        raise FileNotFoundError(str(p))
    
    if must_be_file and not p.is_file():
        raise ValidationError(f"{name} deve ser um ficheiro: {p}")
    
    if must_be_dir and not p.is_dir():
        raise ValidationError(f"{name} deve ser um diretório: {p}")
    
    return p


def validate_writable_directory(path: Path | str, name: str = "directory") -> Path:
    """Valida que um diretório existe e é gravável.
    
    Args:
        path: Diretório a validar
        name: Nome do parâmetro
        
    Returns:
        Path validado
        
    Raises:
        ValidationError: Se não existir ou não for gravável
    """
    p = validate_path_exists(path, name, must_be_dir=True)
    
    # Tentar criar ficheiro temporário para testar escrita
    test_file = p / ".emumanager_write_test"
    try:
        test_file.touch()
        test_file.unlink()
    except (PermissionError, OSError) as e:
        raise ValidationError(f"{name} não é gravável: {p}", {"error": str(e)})
    
    return p


def validate_file_extension(
    path: Path | str,
    allowed_extensions: Iterable[str],
    case_sensitive: bool = False
) -> Path:
    """Valida que um ficheiro tem uma extensão permitida.
    
    Args:
        path: Ficheiro a validar
        allowed_extensions: Conjunto de extensões permitidas (ex: {'.iso', '.chd'})
        case_sensitive: Se a comparação deve ser case-sensitive
        
    Returns:
        Path validado
        
    Raises:
        ValidationError: Se extensão não for permitida
    """
    p = Path(path)
    ext = p.suffix if case_sensitive else p.suffix.lower()
    
    allowed = set(allowed_extensions)
    if not case_sensitive:
        allowed = {e.lower() for e in allowed}
    
    if ext not in allowed:
        raise ValidationError(
            f"Extensão {ext} não suportada. Permitidas: {', '.join(sorted(allowed))}"
        )
    
    return p


# ============================================================================
# NUMERIC VALIDATION
# ============================================================================

def validate_positive(value: int | float, name: str = "value") -> int | float:
    """Valida que um número é positivo (> 0).
    
    Args:
        value: Número a validar
        name: Nome do parâmetro
        
    Returns:
        Valor validado
        
    Raises:
        ValidationError: Se não for positivo
    """
    if value <= 0:
        raise ValidationError(f"{name} deve ser positivo, obtido: {value}")
    return value


def validate_non_negative(value: int | float, name: str = "value") -> int | float:
    """Valida que um número é não-negativo (>= 0).
    
    Args:
        value: Número a validar
        name: Nome do parâmetro
        
    Returns:
        Valor validado
        
    Raises:
        ValidationError: Se for negativo
    """
    if value < 0:
        raise ValidationError(f"{name} não pode ser negativo, obtido: {value}")
    return value


def validate_range(
    value: int | float,
    min_val: Optional[int | float] = None,
    max_val: Optional[int | float] = None,
    name: str = "value"
) -> int | float:
    """Valida que um número está dentro de um intervalo.
    
    Args:
        value: Número a validar
        min_val: Valor mínimo (inclusivo), None = sem limite
        max_val: Valor máximo (inclusivo), None = sem limite
        name: Nome do parâmetro
        
    Returns:
        Valor validado
        
    Raises:
        ValidationError: Se fora do intervalo
    """
    if min_val is not None and value < min_val:
        raise ValidationError(f"{name} deve ser >= {min_val}, obtido: {value}")
    
    if max_val is not None and value > max_val:
        raise ValidationError(f"{name} deve ser <= {max_val}, obtido: {value}")
    
    return value


def validate_percentage(value: float, name: str = "percentage") -> float:
    """Valida que um valor é uma percentagem válida (0.0 - 1.0).
    
    Args:
        value: Percentagem a validar
        name: Nome do parâmetro
        
    Returns:
        Valor validado
        
    Raises:
        ValidationError: Se fora do intervalo [0, 1]
    """
    return validate_range(value, 0.0, 1.0, name)


# ============================================================================
# STRING VALIDATION
# ============================================================================

def validate_not_empty(value: str, name: str = "value") -> str:
    """Valida que uma string não está vazia.
    
    Args:
        value: String a validar
        name: Nome do parâmetro
        
    Returns:
        String validada
        
    Raises:
        ValidationError: Se vazia
    """
    if not value or not value.strip():
        raise ValidationError(f"{name} não pode estar vazio")
    return value


def validate_regex(value: str, pattern: str, name: str = "value", flags: int = 0) -> str:
    """Valida que uma string corresponde a um padrão regex.
    
    Args:
        value: String a validar
        pattern: Padrão regex
        name: Nome do parâmetro
        flags: Flags do regex (ex: re.IGNORECASE)
        
    Returns:
        String validada
        
    Raises:
        ValidationError: Se não corresponder ao padrão
    """
    if not re.match(pattern, value, flags):
        raise ValidationError(f"{name} não corresponde ao padrão esperado: {pattern}")
    return value


def validate_max_length(value: str, max_len: int, name: str = "value") -> str:
    """Valida que uma string não excede comprimento máximo.
    
    Args:
        value: String a validar
        max_len: Comprimento máximo
        name: Nome do parâmetro
        
    Returns:
        String validada
        
    Raises:
        ValidationError: Se exceder o comprimento
    """
    if len(value) > max_len:
        raise ValidationError(f"{name} excede comprimento máximo de {max_len} caracteres")
    return value


# ============================================================================
# COLLECTION VALIDATION
# ============================================================================

def validate_not_empty_list(value: list[T], name: str = "list") -> list[T]:
    """Valida que uma lista não está vazia.
    
    Args:
        value: Lista a validar
        name: Nome do parâmetro
        
    Returns:
        Lista validada
        
    Raises:
        ValidationError: Se vazia
    """
    if not value:
        raise ValidationError(f"{name} não pode estar vazia")
    return value


def validate_all(
    items: Iterable[T],
    validator: Callable[[T], bool],
    name: str = "items",
    error_msg: str = "validação falhou"
) -> list[T]:
    """Valida que todos os itens de uma coleção satisfazem um predicado.
    
    Args:
        items: Itens a validar
        validator: Função que retorna True se item é válido
        name: Nome do parâmetro
        error_msg: Mensagem de erro
        
    Returns:
        Lista validada
        
    Raises:
        ValidationError: Se algum item falhar validação
    """
    items_list = list(items)
    invalid = [i for i in items_list if not validator(i)]
    
    if invalid:
        raise ValidationError(
            f"{name}: {error_msg} para {len(invalid)} item(s)",
            {"invalid_items": invalid[:5]}  # Mostrar apenas primeiros 5
        )
    
    return items_list


def validate_unique(items: Iterable[T], name: str = "items") -> list[T]:
    """Valida que todos os itens são únicos.
    
    Args:
        items: Itens a validar
        name: Nome do parâmetro
        
    Returns:
        Lista validada
        
    Raises:
        ValidationError: Se houver duplicados
    """
    items_list = list(items)
    unique_items = set(items_list)
    
    if len(items_list) != len(unique_items):
        raise ValidationError(f"{name} contém elementos duplicados")
    
    return items_list


# ============================================================================
# TYPE VALIDATION
# ============================================================================

def validate_type(value: Any, expected_type: type, name: str = "value") -> Any:
    """Valida que um valor é de um tipo específico.
    
    Args:
        value: Valor a validar
        expected_type: Tipo esperado
        name: Nome do parâmetro
        
    Returns:
        Valor validado
        
    Raises:
        ValidationError: Se tipo incorreto
    """
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"{name} deve ser {expected_type.__name__}, obtido {type(value).__name__}"
        )
    return value


def validate_callable(value: Any, name: str = "callback") -> Callable:
    """Valida que um valor é callable.
    
    Args:
        value: Valor a validar
        name: Nome do parâmetro
        
    Returns:
        Callable validado
        
    Raises:
        ValidationError: Se não for callable
    """
    if not callable(value):
        raise ValidationError(f"{name} deve ser callable")
    return value


# ============================================================================
# SYSTEM-SPECIFIC VALIDATION
# ============================================================================

def validate_system_id(system_id: str, available_systems: Iterable[str]) -> str:
    """Valida que um ID de sistema é válido.
    
    Args:
        system_id: ID do sistema a validar
        available_systems: Conjunto de sistemas disponíveis
        
    Returns:
        ID validado
        
    Raises:
        ValidationError: Se sistema não existe
    """
    validate_not_empty(system_id, "system_id")
    
    systems_set = set(available_systems)
    if system_id not in systems_set:
        raise ValidationError(
            f"Sistema desconhecido: {system_id}. Disponíveis: {', '.join(sorted(systems_set))}"
        )
    
    return system_id


def validate_serial_format(serial: str, pattern: str = r"^[A-Z]{4}[-_]?\d{5}$") -> str:
    """Valida formato de serial de jogo (ex: SLUS-12345).
    
    Args:
        serial: Serial a validar
        pattern: Padrão regex do formato
        
    Returns:
        Serial validado e normalizado
        
    Raises:
        ValidationError: Se formato inválido
    """
    validate_not_empty(serial, "serial")
    validate_regex(serial, pattern, "serial", re.IGNORECASE)
    return serial.upper()


def validate_hash_format(
    hash_value: str,
    hash_type: str = "md5",
    allow_empty: bool = False
) -> str:
    """Valida formato de hash (MD5, SHA1, SHA256, CRC32).
    
    Args:
        hash_value: Hash a validar
        hash_type: Tipo de hash ('md5', 'sha1', 'sha256', 'crc32')
        allow_empty: Se permite string vazia
        
    Returns:
        Hash validado (lowercase)
        
    Raises:
        ValidationError: Se formato inválido
    """
    if allow_empty and not hash_value:
        return ""
    
    validate_not_empty(hash_value, f"{hash_type} hash")
    
    expected_lengths = {
        "md5": 32,
        "sha1": 40,
        "sha256": 64,
        "crc32": 8,
    }
    
    if hash_type not in expected_lengths:
        raise ConfigurationError(f"Tipo de hash desconhecido: {hash_type}")
    
    expected_len = expected_lengths[hash_type]
    
    if len(hash_value) != expected_len:
        raise ValidationError(
            f"{hash_type.upper()} hash deve ter {expected_len} caracteres, obtido: {len(hash_value)}"
        )
    
    if not re.match(r"^[0-9a-fA-F]+$", hash_value):
        raise ValidationError(f"{hash_type.upper()} hash contém caracteres inválidos")
    
    return hash_value.lower()


# ============================================================================
# COMPOSITE VALIDATORS
# ============================================================================

class ValidationContext:
    """Context manager para acumular múltiplos erros de validação."""
    
    def __init__(self, raise_on_exit: bool = True):
        self.errors: list[str] = []
        self.raise_on_exit = raise_on_exit
    
    def add_error(self, message: str):
        """Adiciona um erro ao contexto."""
        self.errors.append(message)
    
    def validate(self, validator: Callable[[], None], error_msg: str = None):
        """Executa um validador e captura exceções."""
        try:
            validator()
        except ValidationError as e:
            self.add_error(error_msg or str(e))
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.raise_on_exit and self.errors:
            raise ValidationError(
                f"Validação falhou com {len(self.errors)} erro(s):\n  " +
                "\n  ".join(self.errors)
            )
        return False
    
    @property
    def is_valid(self) -> bool:
        """Retorna True se não há erros."""
        return len(self.errors) == 0


def validate_dict_schema(
    data: dict[str, Any],
    schema: dict[str, Callable[[Any], Any]],
    strict: bool = False
) -> dict[str, Any]:
    """Valida que um dicionário segue um schema.
    
    Args:
        data: Dicionário a validar
        schema: Dicionário com validadores para cada chave
        strict: Se True, rejeita chaves extra não no schema
        
    Returns:
        Dicionário validado
        
    Raises:
        ValidationError: Se validação falhar
    """
    if strict:
        extra_keys = set(data.keys()) - set(schema.keys())
        if extra_keys:
            raise ValidationError(f"Chaves não esperadas: {', '.join(extra_keys)}")
    
    validated = {}
    with ValidationContext() as ctx:
        for key, validator in schema.items():
            if key not in data:
                ctx.add_error(f"Chave obrigatória ausente: {key}")
                continue
            
            try:
                validated[key] = validator(data[key])
            except Exception as e:
                ctx.add_error(f"Validação falhou para {key}: {e}")
    
    return validated
