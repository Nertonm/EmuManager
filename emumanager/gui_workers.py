from __future__ import annotations

# Re-export everything from the new worker modules
from emumanager.workers.common import GuiLogger, GuiLogHandler, worker_clean_junk
from emumanager.workers.switch import (
    worker_organize, 
    worker_health_check, 
    worker_switch_compress, 
    worker_switch_decompress,
    worker_recompress_single,
    worker_decompress_single,
    worker_compress_single
)
from emumanager.workers.ps2 import (
    worker_ps2_convert, 
    worker_ps2_verify, 
    worker_ps2_organize
)
from emumanager.workers.ps3 import (
    worker_ps3_verify, 
    worker_ps3_organize
)
from emumanager.workers.psp import (
    worker_psp_verify,
    worker_psp_organize,
    worker_psp_compress
)
from emumanager.workers.dolphin import (
    worker_dolphin_convert, 
    worker_dolphin_verify, 
    worker_dolphin_organize,
    DOLPHIN_CONVERTIBLE_EXTENSIONS
)
from emumanager.workers.verification import worker_hash_verify

__all__ = [
    "GuiLogger",
    "GuiLogHandler",
    "worker_clean_junk",
    "worker_organize",
    "worker_health_check",
    "worker_switch_compress",
    "worker_switch_decompress",
    "worker_recompress_single",
    "worker_decompress_single",
    "worker_compress_single",
    "worker_ps2_convert",
    "worker_ps2_verify",
    "worker_ps2_organize",
    "worker_ps3_verify",
    "worker_ps3_organize",
    "worker_psp_verify",
    "worker_psp_organize",
    "worker_psp_compress",
    "worker_dolphin_convert",
    "worker_dolphin_verify",
    "worker_dolphin_organize",
    "DOLPHIN_CONVERTIBLE_EXTENSIONS",
    "worker_hash_verify",
]