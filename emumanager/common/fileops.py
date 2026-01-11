"""File operation helpers (Core Python Refactoring).

Uso exclusivo de pathlib.Path para garantir portabilidade e legibilidade.
Inclui tratamento atómico de ficheiros e verificação de duplicados.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable


def _is_exact_duplicate_fast(s: Path, d: Path) -> bool:
    """Verificação rápida de duplicados por metadados e prefixo de bytes."""
    try:
        s_stat = s.stat()
        d_stat = d.stat()
        
        if s_stat.st_size != d_stat.st_size:
            return False
        if s_stat.st_mtime != d_stat.st_mtime:
            return False

        # Comparação dos primeiros 4KiB
        with s.open("rb") as fs, d.open("rb") as fd:
            return fs.read(4096) == fd.read(4096)
    except Exception:
        return False


def _is_exact_duplicate_strict(
    s: Path, d: Path, get_file_hash: Callable[[Path], str]
) -> bool:
    """Verificação rigorosa de duplicados via Hash."""
    try:
        return get_file_hash(s) == get_file_hash(d)
    except Exception:
        return False


def _choose_duplicate_target(
    source: Path,
    dst: Path,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> Path | None:
    """Decide o destino em caso de colisão ou remove o original se for duplicado."""
    try:
        is_dup = False
        if getattr(args, "dup_check", "fast") == "strict":
            is_dup = _is_exact_duplicate_strict(source, dst, get_file_hash)
        else:
            is_dup = _is_exact_duplicate_fast(source, dst)

        if is_dup:
            logger.info(f"Duplicate detected; removing source: {source.name}")
            source.unlink(missing_ok=True)
            return None
    except Exception as e:
        logger.debug(f"Duplicate check failed: {e}")

    # Gerar nome único para cópia
    counter = 1
    new_dest = dst.parent / f"{dst.stem}_COPY_{counter}{dst.suffix}"
    while new_dest.exists():
        counter += 1
        new_dest = dst.parent / f"{dst.stem}_COPY_{counter}{dst.suffix}"
    return new_dest


def _copy_and_replace(
    source: Path,
    dest: Path,
    dest_parent: Path,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> bool:
    """Fallback para mover ficheiros entre diferentes sistemas de ficheiros."""
    tmp_path: Path | None = None
    try:
        # Criar ficheiro temporário no destino para garantir move atómico final
        with tempfile.NamedTemporaryFile(
            prefix=".emumgr_tmp_", dir=dest_parent, delete=False
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            shutil.copy2(source, tmp_path)
            # Garantir escrita no disco
            tmp_file.flush()
            # os.fsync(tmp_file.fileno()) # Opcional se quisermos ser paranoicos

        if getattr(args, "dup_check", "fast") == "strict":
            if get_file_hash(source) != get_file_hash(tmp_path):
                logger.error(f"Hash mismatch after copy: {source.name}")
                tmp_path.unlink(missing_ok=True)
                return False

        tmp_path.replace(dest)
        logger.info(f"Moved (copy+replace): {source.name} -> {dest.name}")
        source.unlink(missing_ok=True)
        return True
    except Exception as e:
        logger.exception(f"safe_move (copy) failed: {e}")
        if tmp_path:
            tmp_path.unlink(missing_ok=True)
        return False


def safe_unlink(path: Path, logger: Any) -> None:
    """Eliminação segura e logada de ficheiros."""
    try:
        if path.exists():
            path.unlink()
            logger.info(f"Deleted: {path.name}")
    except Exception as e:
        logger.warning(f"Failed to delete {path.name}: {e}")


def safe_move(
    source: Path,
    dest: Path,
    *,
    args: Any,
    get_file_hash: Callable[[Path], str],
    logger: Any,
) -> bool:
    """Orquestra um move seguro e atómico usando Pathlib puro."""
    if getattr(args, "dry_run", False):
        logger.info(f"[DRY-RUN] move {source.name} -> {dest.name}")
        return True

    try:
        source = Path(source).resolve()
        dest = Path(dest).resolve()
        
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Tratar caminhos demasiado longos (heurística simples)
        if len(dest.name) > 240:
            dest = dest.with_name(dest.stem[:200] + dest.suffix)

        if dest.exists() and source != dest:
            chosen = _choose_duplicate_target(source, dest, args, get_file_hash, logger)
            if chosen is None:
                return False
            dest = chosen

        # Tentativa de move atómico (mesmo FS)
        try:
            source.replace(dest)
            logger.info(f"Moved (atomic): {source.name} -> {dest.name}")
            return True
        except OSError:
            # Fallback para cross-device move
            return _copy_and_replace(source, dest, dest.parent, args, get_file_hash, logger)
            
    except Exception as e:
        logger.exception(f"safe_move failed for {source.name}: {e}")
        return False