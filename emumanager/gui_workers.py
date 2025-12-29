from __future__ import annotations

# Re-export everything from the new worker modules
from emumanager.workers.common import GuiLogger, GuiLogHandler, worker_clean_junk
from emumanager.workers.dolphin import (
    DOLPHIN_CONVERTIBLE_EXTENSIONS,
    worker_dolphin_convert,
    worker_dolphin_decompress_single,
    worker_dolphin_organize,
    worker_dolphin_recompress_single,
    worker_dolphin_verify,
)
from emumanager.workers.n3ds import (
    worker_n3ds_compress,
    worker_n3ds_compress_single,
    worker_n3ds_convert_cia,
    worker_n3ds_decompress,
    worker_n3ds_decompress_single,
    worker_n3ds_decrypt,
    worker_n3ds_organize,
    worker_n3ds_verify,
)
from emumanager.workers.ps2 import (
    worker_ps2_convert,
    worker_ps2_organize,
    worker_ps2_verify,
)
from emumanager.workers.ps3 import worker_ps3_organize, worker_ps3_verify
from emumanager.workers.psp import (
    worker_psp_compress,
    worker_psp_organize,
    worker_psp_verify,
)
from emumanager.workers.psx import (
    worker_psx_convert,
    worker_psx_organize,
    worker_psx_verify,
)
from emumanager.workers.switch import (
    worker_compress_single,
    worker_decompress_single,
    worker_health_check,
    worker_organize,
    worker_recompress_single,
    worker_switch_compress,
    worker_switch_decompress,
)
from emumanager.workers.verification import (
    worker_hash_verify,
    worker_identify_all,
    worker_identify_single_file,
)

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
    "worker_psx_convert",
    "worker_psx_verify",
    "worker_psx_organize",
    "worker_ps3_verify",
    "worker_ps3_organize",
    "worker_psp_verify",
    "worker_psp_organize",
    "worker_psp_compress",
    "worker_n3ds_verify",
    "worker_n3ds_organize",
    "worker_n3ds_compress",
    "worker_n3ds_compress_single",
    "worker_n3ds_decompress",
    "worker_n3ds_decompress_single",
    "worker_n3ds_convert_cia",
    "worker_n3ds_decrypt",
    "worker_dolphin_convert",
    "worker_dolphin_verify",
    "worker_dolphin_organize",
    "worker_dolphin_decompress_single",
    "worker_dolphin_recompress_single",
    "DOLPHIN_CONVERTIBLE_EXTENSIONS",
    "worker_hash_verify",
    "worker_identify_single_file",
    "worker_identify_all",
]
