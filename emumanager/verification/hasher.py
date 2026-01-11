from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional

def calculate_hashes(

    path: Path, 
    algorithms: tuple[str, ...] = ("crc32", "sha1"),
    chunk_size: int = 1024 * 1024 # Buffer de 1MB para eficiência de cache L3
) -> dict[str, str]:
    """
    Calcula múltiplos hashes em paralelo sobre o mesmo stream de leitura.
    Usa memoryview para reduzir overhead de memória em ficheiros gigantes.
    """
    hash_objs = {alg: hashlib.new(alg) if alg != "crc32" else None for alg in algorithms}
    
    # Para CRC32 usamos zlib por ser ordens de magnitude mais rápido que hashlib
    import zlib
    crc_val = 0
    
    try:
        with open(path, "rb") as f:
            # Buffer pré-alocado
            buf = bytearray(chunk_size)
            mv = memoryview(buf)
            
            while n := f.readinto(mv):
                data = mv[:n]
                if "crc32" in hash_objs:
                    crc_val = zlib.crc32(data, crc_val)
                for alg, obj in hash_objs.items():
                    if obj:
                        obj.update(data)
                        
        results = {}
        if "crc32" in hash_objs:
            results["crc32"] = format(crc_val & 0xFFFFFFFF, "08x")
        for alg, obj in hash_objs.items():
            if obj:
                results[alg] = obj.hexdigest()
        return results
    except Exception:
        return {}

def get_file_hash(path: Path, algo: str = "sha1") -> str:
    """Legacy alias para o novo motor de hashing."""
    res = calculate_hashes(path, algorithms=(algo,))
    return res.get(algo, "")