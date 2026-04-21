from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Optional


class MainWindowVerificationRehashMixin:
    def _get_rehash_targets(self):
        """Identifica os itens da tabela de verificação que devem ser re-hashados."""
        try:
            table = self.ui.table_results
            filtered = self._get_filtered_verification_results()
            indexes = table.selectedIndexes()
            sel_rows = sorted({idx.row() for idx in indexes})

            if sel_rows:
                return [filtered[r] for r in sel_rows if 0 <= r < len(filtered)]

            return [r for r in filtered if getattr(r, "status", None) == "HASH_FAILED"]
        except Exception as e:
            logging.error(f"Failed to get rehash targets: {e}")
            return []

    def _rehash_single_item(self, target: Any, dat_path: Optional[Path]):
        """Executa o re-hash ou re-identificação de um único arquivo."""
        try:
            path = Path(target.full_path) if getattr(target, "full_path", None) else None
            if not path or not path.exists():
                return str(path), "missing"

            if dat_path:
                return self._reidentify_with_dat(path, dat_path)

            return self._recalculate_hashes_to_db(path)
        except Exception as e:
            logging.debug(f"Rehash failed for {target}: {e}")
            return str(target), f"error:{e}"

    def _reidentify_with_dat(self, path: Path, dat_path: Path):
        op = uuid.uuid4().hex
        log_cb = self._make_op_log_cb(op)
        try:
            self.status.showMessage(f"Operation {op} started", 3000)
        except Exception:
            pass
        out = self._run_identify_single_worker(path, dat_path, log_cb, None)
        return str(path), out

    def _recalculate_hashes_to_db(self, path: Path):
        algos = ("crc32", "sha1")
        if getattr(self, "chk_deep_verify", None) and self.chk_deep_verify.isChecked():
            algos = ("crc32", "md5", "sha1", "sha256")

        hashes = self._calculate_hashes_for_path(path, algorithms=algos)
        try:
            from emumanager.library import LibraryEntry

            stat_result = path.stat()
            new_entry = LibraryEntry(
                path=str(path.resolve()),
                system="unknown",
                size=stat_result.st_size,
                mtime=stat_result.st_mtime,
                crc32=hashes.get("crc32"),
                md5=hashes.get("md5"),
                sha1=hashes.get("sha1"),
                sha256=hashes.get("sha256"),
                status="UNKNOWN",
            )
            self.library_db.update_entry(new_entry)
            return str(path), "rehash_ok"
        except Exception as e:
            return str(path), f"error:{e}"

    def _update_in_memory_results(self, rehash_results: list[tuple[str, str]]):
        """Atualiza os resultados cacheados com os novos dados do banco de dados."""
        for path_str, _ in rehash_results:
            for result_row in getattr(self, "_last_verify_results", []):
                if getattr(result_row, "full_path", None) == path_str:
                    try:
                        entry = self.library_db.get_entry(path_str)
                        if entry:
                            result_row.crc, result_row.sha1, result_row.md5, result_row.sha256 = (
                                entry.crc32,
                                entry.sha1,
                                entry.md5,
                                entry.sha256,
                            )
                            result_row.status, result_row.match_name = (
                                entry.status,
                                entry.match_name,
                            )
                    except Exception as exc:
                        logging.debug(f"Failed to sync memory result for {path_str}: {exc}")

    def on_try_rehash(self):
        """Try re-hash selected verification rows or all HASH_FAILED rows."""
        targets = self._get_rehash_targets()
        if not targets:
            self.log_msg("No files selected for rehash")
            return

        dat_path = getattr(self, "_current_dat_path", None)

        def _work():
            return [self._rehash_single_item(target, dat_path) for target in targets]

        def _done(res):
            self._set_ui_enabled(True)
            if isinstance(res, Exception):
                self.log_msg(f"Rehash error: {res}")
                return

            self.log_msg(f"Rehash complete. Processed: {len(res)} items")
            if dat_path:
                try:
                    self.on_verify_dat()
                except Exception as e:
                    logging.debug(f"Refresh after rehash failed: {e}")
            else:
                self._update_in_memory_results(res)
                self.on_verification_filter_changed()

        self._set_ui_enabled(False)
        self._run_in_background(_work, _done)
