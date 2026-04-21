from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from emumanager.library import LibraryEntry
from emumanager.verification import hasher

HASH_RETRIES = 2
HASH_RETRY_DELAY = 0.5
VERIFY_TIMEOUT_SECONDS = 60
DOLPHIN_SYSTEMS = ("gamecube", "wii", "dolphin")
PSX_SYSTEMS = ("psx", "ps1", "playstation")


class ScannerVerificationMixin:
    def _verify_system_specific_integrity(
        self,
        path: Path,
        system_name: str,
    ) -> Optional[bool]:
        ext = path.suffix.lower()
        if system_name in DOLPHIN_SYSTEMS and ext == ".rvz":
            try:
                from emumanager.converters.dolphin_converter import DolphinConverter

                converter = DolphinConverter(logger=self.logger)
                if not converter.check_tool():
                    self.logger.debug("dolphin-tool não disponível - pulando verificação RVZ")
                    return None
                self.logger.info("Verificando integridade RVZ: %s", path.name)
                result = converter.verify_rvz(path)
                if result:
                    self.logger.info("RVZ verificado com sucesso: %s", path.name)
                else:
                    self.logger.warning("RVZ falhou na verificação: %s", path.name)
                return result
            except Exception as exc:
                self.logger.warning("Erro ao verificar RVZ %s: %s", path.name, exc)
                return None

        if system_name == "ps2" and ext == ".chd":
            return self._verify_chd(path, "CHD")

        if system_name in PSX_SYSTEMS and ext == ".chd":
            return self._verify_chd(path, "CHD PSX")

        return None

    def _verify_chd(self, path: Path, label: str) -> Optional[bool]:
        try:
            from emumanager.common.execution import find_tool, run_cmd

            chdman = find_tool("chdman")
            if not chdman:
                self.logger.debug("chdman não disponível - pulando verificação %s", label)
                return None

            self.logger.info("Verificando integridade %s: %s", label, path.name)
            result = run_cmd(
                [str(chdman), "verify", "-i", str(path)],
                timeout=VERIFY_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                self.logger.info("%s verificado com sucesso: %s", label, path.name)
                return True
            self.logger.warning("%s falhou na verificação: %s", label, path.name)
            return False
        except Exception as exc:
            self.logger.warning("Erro ao verificar %s %s: %s", label, path.name, exc)
            return None

    def _handle_verification(
        self,
        path: Path,
        entry: Optional[LibraryEntry],
        dat_db: Any,
        needs_hashing: bool,
        metadata: dict,
        system_name: str,
    ) -> tuple[dict, dict]:
        del metadata
        hashes = {
            "crc32": entry.crc32 if entry else None,
            "md5": entry.md5 if entry else None,
            "sha1": entry.sha1 if entry else None,
        }
        match_info: dict[str, Any] = {}

        integrity_check = self._verify_system_specific_integrity(path, system_name)
        if integrity_check is False:
            return hashes, {"status": "CORRUPT", "match_name": "Failed integrity check"}
        if integrity_check is True:
            match_info["integrity_verified"] = True

        if needs_hashing and dat_db:
            self.logger.debug("Calculando hashes para %s...", path.name)
            for attempt in range(HASH_RETRIES):
                try:
                    hashes = hasher.calculate_hashes(
                        path,
                        algorithms=("crc32", "sha1", "md5"),
                    )
                    break
                except Exception as exc:
                    if attempt < HASH_RETRIES - 1:
                        self.logger.warning(
                            "Tentativa %s/%s falhou ao hashear %s: %s",
                            attempt + 1,
                            HASH_RETRIES,
                            path.name,
                            exc,
                        )
                        time.sleep(HASH_RETRY_DELAY)
                    else:
                        self.logger.error(
                            "Erro crítico ao calcular hash após %s tentativas: %s",
                            HASH_RETRIES,
                            path.name,
                        )
                        return hashes, {"status": "ERROR"}

            try:
                matches = dat_db.lookup(
                    crc=hashes.get("crc32"),
                    sha1=hashes.get("sha1"),
                    md5=hashes.get("md5"),
                )
                if matches:
                    match = matches[0]
                    match_info = {
                        "status": "VERIFIED",
                        "match_name": match.name,
                        "dat_name": match.serial or match.name,
                    }
                    self.logger.debug("Correspondência DAT encontrada: %s", match.name)
            except Exception as exc:
                self.logger.warning("Erro ao consultar DAT para %s: %s", path.name, exc)

        return hashes, match_info
