from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.registry import registry
from emumanager.logging_cfg import set_correlation_id


class OrchestratorMaintenanceMixin:
    """Integrity, duplicate cleanup, transcoding, and reports."""

    def maintain_integrity(self, dry_run: bool = False) -> dict[str, int]:
        """Workflow de Sanidade: Isola corrupção e limpa duplicados."""
        set_correlation_id()
        self.logger.info("Executando manutenção de integridade...")

        q_stats = self.quarantine_corrupt_files(dry_run)
        d_stats = self.cleanup_duplicates(dry_run)
        return {**q_stats, **d_stats}

    def quarantine_corrupt_files(self, dry_run: bool = False) -> dict[str, int]:
        """Isola ficheiros marcados como corrompidos."""
        entries = [entry for entry in self.db.get_all_entries() if entry.status == "CORRUPT"]
        stats = {"quarantined": 0, "errors": 0}

        for entry in entries:
            if dry_run:
                self.logger.info(f"[DRY-RUN] Seria isolado: {Path(entry.path).name}")
                stats["quarantined"] += 1
                continue

            res = self.integrity.quarantine_file(
                Path(entry.path),
                entry.system,
                "Corruption",
                "Hash mismatch",
            )
            if res:
                stats["quarantined"] += 1
            else:
                stats["errors"] += 1
        return stats

    def _score_duplicate_entry(self, entry: Any) -> tuple[int, int]:
        """Atribui uma pontuação de preferência para um ficheiro duplicado."""
        preferred_exts = {".chd", ".rvz", ".cso", ".z64", ".nsp", ".nsz"}
        ext = Path(entry.path).suffix.lower()
        return (1 if ext in preferred_exts else 0, entry.size)

    def _remove_duplicate_entry(self, entry: Any, stats: dict[str, int]):
        """Remove fisicamente e logicamente um ficheiro duplicado."""
        try:
            Path(entry.path).unlink(missing_ok=True)
            self.db.remove_entry(entry.path)
            stats["removed"] += 1
            return True
        except Exception as e:
            self.logger.error(f"Erro ao remover duplicado {entry.path}: {e}")
            stats["errors"] += 1
            return False

    def cleanup_duplicates(self, dry_run: bool = False) -> dict[str, int]:
        """Remove duplicados baseados em hash, preservando a melhor versão."""
        self.logger.info("Verificando duplicados globais...")
        entries = self.db.get_all_entries()
        by_hash = {}
        for entry in entries:
            if entry.sha1:
                by_hash.setdefault(entry.sha1, []).append(entry)

        stats = {"removed": 0, "errors": 0}
        for _sha1, group in by_hash.items():
            if len(group) <= 1:
                continue

            group.sort(key=self._score_duplicate_entry, reverse=True)
            keep = group[0]
            to_remove = group[1:]

            for entry in to_remove:
                if dry_run:
                    self.logger.info(
                        "[DRY-RUN] Duplicado removido: "
                        f"{Path(entry.path).name} (Mantido {Path(keep.path).name})"
                    )
                    stats["removed"] += 1
                else:
                    self._remove_duplicate_entry(entry, stats)

        return stats

    def generate_m3u_playlists(self, system_id: str, hide_discs: bool = True) -> dict[str, int]:
        """Agrupa jogos multi-disco e cria playlists .m3u."""
        system_root = self.session.roms_path / system_id
        if not system_root.exists():
            return {"error": "Pasta não encontrada"}

        all_files = [path for path in system_root.iterdir() if path.is_file()]
        groups = self.multidisc.group_discs(all_files)

        stats = {"created_m3u": 0, "moved_discs": 0}
        for base_title, discs in groups.items():
            self.multidisc.create_m3u(base_title, discs, system_root, hide_discs)
            stats["created_m3u"] += 1
            if hide_discs:
                stats["moved_discs"] += len(discs)

        self.scan_library()
        return stats

    def bulk_transcode(
        self,
        dry_run: bool = False,
        progress_cb: Optional[Callable] = None,
    ):
        """Workflow de Modernização: Transcoding massivo para formatos eficientes."""
        set_correlation_id()
        self.logger.info("Iniciando transcoding massivo...")

        entries = self.db.get_all_entries()
        to_convert = {}

        for entry in entries:
            provider = registry.get_provider(entry.system)
            if provider:
                try:
                    if provider.needs_conversion(Path(entry.path)):
                        to_convert.setdefault(entry.system, []).append(Path(entry.path))
                except Exception as e:
                    self.logger.warning(f"Erro ao verificar conversão para {entry.path}: {e}")

        if not to_convert:
            self.logger.info("Nenhum arquivo requer conversão.")
            return {"converted": 0, "failed": 0, "skipped": 0}

        from emumanager.workers.dolphin import DolphinWorker
        from emumanager.workers.ps2 import PS2Worker
        from emumanager.workers.psp import PSPWorker

        worker_map = {
            "ps2": PS2Worker,
            "dolphin": DolphinWorker,
            "psp": PSPWorker,
        }

        total = {"converted": 0, "failed": 0, "skipped": 0}

        for sys_id, paths in to_convert.items():
            if sys_id not in worker_map:
                self.logger.warning(f"Worker não disponível para {sys_id}, pulando...")
                total["skipped"] += len(paths)
                continue

            if dry_run:
                total["skipped"] += len(paths)
                for path in paths:
                    self.logger.info(f"[DRY-RUN] Conversão ignorada: {path}")
                continue

            try:
                worker_class = worker_map[sys_id]
                worker = worker_class(
                    self.session.base_path,
                    self.logger.info,
                    progress_cb,
                    None,
                )
                res = worker.run(paths, task_label=f"Transcoding {sys_id}", parallel=True)
                total["converted"] += res.success_count
                total["failed"] += res.failed_count
            except Exception as e:
                self.logger.error(f"Erro no transcoding de {sys_id}: {e}")
                total["failed"] += len(paths)

        return total

    def generate_compliance_report(self, output_path: Path) -> bool:
        """Gera um diagnóstico completo do acervo em CSV."""
        self.logger.info(f"A gerar relatório de conformidade: {output_path}")
        entries = self.db.get_all_entries()
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(
                    ["Sistema", "Status", "Título", "ID/Serial", "Tamanho", "Caminho", "SHA1"]
                )
                for entry in entries:
                    full = self.db.get_entry(entry.path)
                    if full:
                        writer.writerow(
                            [
                                full.system,
                                full.status,
                                full.match_name,
                                full.dat_name,
                                full.size,
                                full.path,
                                full.sha1,
                            ]
                        )
            return True
        except Exception as e:
            self.logger.error(f"Erro relatório: {e}")
            return False
