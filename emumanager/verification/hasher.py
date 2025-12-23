import hashlib
import zlib
import os
from pathlib import Path
from typing import Dict, Tuple, Optional, Callable

def calculate_hashes(file_path: Path, algorithms: Tuple[str, ...] = ("crc32", "md5", "sha1"), block_size: int = 65536, progress_cb: Optional[Callable[[float], None]] = None) -> Dict[str, str]:
    """
    Calculate hashes for a file.
    Supported algorithms: 'crc32', 'md5', 'sha1', 'sha256'.
    Returns a dictionary with algorithm names as keys and hex strings as values.
    """
    hashes = {}
    hash_objs = _init_hash_objects(algorithms)
    
    total_size = file_path.stat().st_size
    processed = 0
            
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(block_size)
                if not chunk:
                    break
                _update_hashes(hash_objs, chunk)
                
                if progress_cb and total_size > 0:
                    processed += len(chunk)
                    progress_cb(processed / total_size)
                        
        hashes = _finalize_hashes(hash_objs)
                
    except Exception:
        return {}
        
    return hashes

def _init_hash_objects(algorithms: Tuple[str, ...]) -> Dict:
    objs = {}
    for alg in algorithms:
        if alg == "crc32":
            objs["crc32"] = 0
        elif alg == "md5":
            objs["md5"] = hashlib.md5()
        elif alg == "sha1":
            objs["sha1"] = hashlib.sha1()
        elif alg == "sha256":
            objs["sha256"] = hashlib.sha256()
    return objs

def _update_hashes(objs: Dict, chunk: bytes):
    for alg, obj in objs.items():
        if alg == "crc32":
            objs["crc32"] = zlib.crc32(chunk, objs["crc32"])
        else:
            obj.update(chunk)

def _finalize_hashes(objs: Dict) -> Dict[str, str]:
    res = {}
    for alg, obj in objs.items():
        if alg == "crc32":
            res["crc32"] = f"{obj & 0xFFFFFFFF:08x}"
        else:
            res[alg] = obj.hexdigest()
    return res

def get_file_hash(filepath: Path, algo: str = "sha256") -> str:
    """Get a single hash for a file, with fallback to size."""
    try:
        res = calculate_hashes(filepath, algorithms=(algo,))
        val = res.get(algo)
        if val:
            return val
    except Exception:
        pass
        
    # fallback
    try:
        return f"size:{os.path.getsize(filepath)}"
    except Exception:
        return "unknown"
