"""Configuration and constants for EmuManager package.

This module centralizes all configuration values, providing validation
and type-safe access to settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field


# ============================================================================
# APPLICATION METADATA
# ============================================================================

APP_NAME = "EmuManager"
APP_VERSION = "3.0.0"
APP_AUTHOR = "EmuManager Engineers"


# ============================================================================
# DEFAULT PATHS
# ============================================================================

# Default base directory for collections
BASE_DEFAULT = "./Acervo_Games_Ultimate"

# Date format used across modules
DATE_FMT = "%d/%m/%Y às %H:%M"


# ============================================================================
# PERFORMANCE & RESOURCE LIMITS
# ============================================================================

@dataclass
class PerformanceConfig:
    """Configurações de performance e recursos."""
    
    # Número máximo de workers paralelos (None = auto-detectar)
    max_workers: Optional[int] = None
    
    # Tamanho do buffer para operações de I/O (bytes)
    io_buffer_size: int = 64 * 1024  # 64 KB
    
    # Tamanho máximo de chunk para processar em memória (bytes)
    max_chunk_size: int = 100 * 1024 * 1024  # 100 MB
    
    # Timeout padrão para operações externas (segundos)
    default_timeout: int = 300  # 5 minutos
    
    # Espaço livre mínimo em disco (bytes) - 5GB
    min_free_space: int = 5 * 1024 * 1024 * 1024
    
    # Intervalo para atualização de progresso (segundos)
    progress_update_interval: float = 0.1
    
    def __post_init__(self):
        """Valida configurações após inicialização."""
        if self.max_workers is not None and self.max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {self.max_workers}")
        if self.io_buffer_size < 1024:
            raise ValueError(f"io_buffer_size too small: {self.io_buffer_size}")
        if self.max_chunk_size < 1024 * 1024:
            raise ValueError(f"max_chunk_size too small: {self.max_chunk_size}")
        if self.default_timeout < 1:
            raise ValueError(f"default_timeout must be >= 1, got {self.default_timeout}")
        if self.progress_update_interval <= 0:
            raise ValueError(f"progress_update_interval must be > 0, got {self.progress_update_interval}")
    
    def get_workers_count(self) -> int:
        """Retorna o número ideal de workers.
        
        Returns:
            Número de workers (mínimo 1)
        """
        if self.max_workers:
            return max(1, self.max_workers)
        
        try:
            import multiprocessing
            return max(1, multiprocessing.cpu_count() - 1)
        except Exception:
            return 4  # Fallback conservador


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

@dataclass
class LoggingConfig:
    """Configurações de logging."""
    
    # Nível de log padrão
    default_level: str = "INFO"
    
    # Tamanho máximo do ficheiro de log (bytes)
    max_log_size: int = 10 * 1024 * 1024  # 10 MB
    
    # Número de backups rotativos
    backup_count: int = 5
    
    # Formato de log
    log_format: str = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    # Se deve usar log JSON (para parsing automático)
    json_logging: bool = False
    
    def __post_init__(self):
        """Valida configurações após inicialização."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.default_level.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {self.default_level}. Must be one of {valid_levels}")
        if self.max_log_size < 1024:
            raise ValueError(f"max_log_size too small: {self.max_log_size}")
        if self.backup_count < 0:
            raise ValueError(f"backup_count must be >= 0, got {self.backup_count}")
    
    def get_level_int(self) -> int:
        """Converte string de nível para int.
        
        Returns:
            Valor inteiro do nível de logging
        """
        import logging
        return getattr(logging, self.default_level.upper(), logging.INFO)


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

@dataclass
class DatabaseConfig:
    """Configurações da base de dados."""
    
    # Nome do ficheiro de base de dados
    db_filename: str = "library.db"
    
    # Timeout para operações de DB (segundos)
    db_timeout: int = 30
    
    # Journal mode (WAL, DELETE, TRUNCATE, PERSIST, MEMORY, OFF)
    journal_mode: str = "WAL"
    
    # Synchronous mode (OFF, NORMAL, FULL, EXTRA)
    synchronous: str = "NORMAL"
    
    # Cache size (páginas negativas = KB)
    cache_size: int = -20000  # 20 MB
    
    # Se deve fazer VACUUM automático
    auto_vacuum: bool = False


# ============================================================================
# EXTENSION MAPPINGS
# ============================================================================



# Minimal extension -> system mapping for guessing where to put ROMs
EXT_TO_SYSTEM: Dict[str, str] = {
    # Nintendo
    ".nes": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".z64": "n64",
    ".n64": "n64",
    ".gba": "gba",
    ".nds": "nds",
    ".3ds": "3ds",
    ".cia": "3ds",
    ".cci": "3ds",
    ".gcm": "dolphin",  # Unified GameCube/Wii
    ".rvz": "dolphin",  # Dolphin RVZ format
    ".gcz": "dolphin",  # Legacy Dolphin compressed
    ".wbfs": "dolphin",  # Wii Backup File System
    ".wad": "wii",      # WiiWare (still needs special handling)
    ".wud": "wiiu",
    ".wux": "wiiu",
    ".wua": "wiiu",
    ".rpx": "wiiu",
    # Sony
    ".iso": "ps2",  # Ambiguous: could be psx, psp, gc, wii, ps3, xbox
    ".chd": "ps2",  # Ambiguous: could be psx, dc, saturn, etc.
    ".bin": "psx",  # Ambiguous
    ".cue": "psx",
    ".cso": "psp",
    ".pbp": "psp",
    ".pkg": "ps3",  # Ambiguous: ps3, ps4, psvita
    ".vpk": "psvita",
    # Sega
    ".md": "megadrive",
    ".gen": "megadrive",
    ".sms": "mastersystem",
    ".gdi": "dreamcast",
    ".cdi": "dreamcast",
    # Switch/Xbox
    ".xci": "switch",
    ".nsp": "switch",
    ".nsz": "switch",
    ".xiso": "xbox_classic",
    ".xex": "xbox360",
    # Retro/Arcade
    ".a26": "atari2600",
    ".zip": "mame",  # Highly ambiguous (could be any retro system)
}


# ============================================================================
# GLOBAL CONFIGURATION INSTANCES
# ============================================================================

# Singleton de configuração (pode ser sobrescrito por testes)
_performance_config: Optional[PerformanceConfig] = None
_logging_config: Optional[LoggingConfig] = None
_database_config: Optional[DatabaseConfig] = None


def get_performance_config() -> PerformanceConfig:
    """Retorna a configuração de performance global."""
    global _performance_config
    if _performance_config is None:
        _performance_config = PerformanceConfig()
    return _performance_config


def get_logging_config() -> LoggingConfig:
    """Retorna a configuração de logging global."""
    global _logging_config
    if _logging_config is None:
        _logging_config = LoggingConfig()
    return _logging_config


def get_database_config() -> DatabaseConfig:
    """Retorna a configuração de base de dados global."""
    global _database_config
    if _database_config is None:
        _database_config = DatabaseConfig()
    return _database_config


def set_performance_config(config: PerformanceConfig):
    """Define a configuração de performance global."""
    global _performance_config
    _performance_config = config


def set_logging_config(config: LoggingConfig):
    """Define a configuração de logging global."""
    global _logging_config
    _logging_config = config


def set_database_config(config: DatabaseConfig):
    """Define a configuração de base de dados global."""
    global _database_config
    _database_config = config


# ============================================================================
# ENVIRONMENT VARIABLE OVERRIDES
# ============================================================================

def load_config_from_env():
    """Carrega configurações de variáveis de ambiente.
    
    Variáveis suportadas:
    - EMUMANAGER_BASE_DIR: Diretório base padrão
    - EMUMANAGER_LOG_LEVEL: Nível de log (DEBUG, INFO, WARNING, ERROR)
    - EMUMANAGER_MAX_WORKERS: Número máximo de workers
    - EMUMANAGER_TIMEOUT: Timeout padrão para operações (segundos)
    """
    perf_config = get_performance_config()
    log_config = get_logging_config()
    
    # Base directory
    if base_dir := os.getenv("EMUMANAGER_BASE_DIR"):
        global BASE_DEFAULT
        BASE_DEFAULT = base_dir
    
    # Log level
    if log_level := os.getenv("EMUMANAGER_LOG_LEVEL"):
        log_config.default_level = log_level.upper()
    
    # Max workers
    if max_workers := os.getenv("EMUMANAGER_MAX_WORKERS"):
        try:
            perf_config.max_workers = int(max_workers)
        except ValueError:
            pass
    
    # Timeout
    if timeout := os.getenv("EMUMANAGER_TIMEOUT"):
        try:
            perf_config.default_timeout = int(timeout)
        except ValueError:
            pass


# Auto-load configuration from environment on module import
load_config_from_env()

