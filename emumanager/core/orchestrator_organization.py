from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

from emumanager.common.fileops import safe_move
from emumanager.common.registry import registry
from emumanager.logging_cfg import set_correlation_id


class OrchestratorOrganizationMixin:
    """Naming, distribution, and organization workflows."""

    def run_performance_benchmark(self, progress_cb: Optional[Callable] = None) -> dict[str, Any]:
        """Simula uma carga pesada de processamento para validar a concorrência."""
        self.logger.info("Iniciando Benchmark de Performance (Stress Test)...")

        import os
        from emumanager.workers.common import BaseWorker

        class BenchmarkWorker(BaseWorker):
            def _process_item(self, item: Path) -> str:
                import hashlib

                data = os.urandom(1024 * 1024 * 10)
                for _ in range(5):
                    hashlib.sha512(data).hexdigest()
                return "success"

        worker = BenchmarkWorker(self.session.base_path, self.logger.info, progress_cb, None)
        items = [Path(f"virtual_task_{i}") for i in range(50)]

        start = datetime.now()
        res = worker.run(items, task_label="Benchmark CPU", parallel=True)
        duration = (datetime.now() - start).total_seconds()

        return {
            "tasks": res.success_count,
            "duration": f"{duration:.2f}s",
            "cores": os.cpu_count(),
        }

    def _get_ideal_path(self, entry: Any, provider: Any, full_entry: Any) -> Path:
        """Resolve o caminho ideal canónico para um ficheiro."""
        ideal_rel = provider.get_ideal_filename(Path(full_entry.path), full_entry.extra_metadata)
        system_root = self.session.roms_path / entry.system
        parts = Path(ideal_rel).parts
        clean_parts = [
            "".join([c for c in part if c not in '<>:"/\\|?*']).strip()
            for part in parts
        ]
        return system_root / Path(*clean_parts)

    def _perform_organization_move(
        self,
        entry: Any,
        full_entry: Any,
        dest_path: Path,
        result: Any,
        item_start: datetime,
    ):
        """Executa a movimentação física e lógica de uma entrada."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        args = SimpleNamespace(dry_run=False, dup_check="fast")
        orig_path = Path(full_entry.path)

        if safe_move(orig_path, dest_path, args=args, get_file_hash=lambda p: "", logger=self.logger):
            self.db.remove_entry(full_entry.path)
            full_entry.path = str(dest_path)
            self.db.update_entry(full_entry)
            result.add_item_result(
                orig_path,
                "success",
                (datetime.now() - item_start).total_seconds(),
                system=entry.system,
            )
            result.success_count += 1
            return True

        result.failed_count += 1
        return False

    def organize_names(
        self,
        system_id: Optional[str] = None,
        dry_run: bool = False,
        progress_cb: Optional[Callable] = None,
    ):
        """Workflow de Organização: Aplica nomes canónicos e hierarquia por sistema."""
        set_correlation_id()
        start_time = datetime.now()
        entries = self.db.get_entries_by_system(system_id) if system_id else self.db.get_all_entries()

        from emumanager.workers.common import WorkerResult

        result = WorkerResult(task_name=f"Organize {system_id or 'All'}")

        for i, entry in enumerate(entries):
            if progress_cb and len(entries) > 0:
                progress_cb(i / len(entries), f"Organizando {entry.system}...")

            item_start = datetime.now()
            provider = registry.get_provider(entry.system)
            full_entry = self.db.get_entry(entry.path)
            if not provider or not full_entry:
                continue

            try:
                dest_path = self._get_ideal_path(entry, provider, full_entry)

                if Path(full_entry.path).resolve() == dest_path.resolve():
                    result.skipped_count += 1
                    continue

                if dry_run:
                    self.logger.info(
                        f"[DRY-RUN] Organize: {Path(full_entry.path).name} -> {dest_path}"
                    )
                    result.add_item_result(
                        Path(full_entry.path),
                        "success",
                        (datetime.now() - item_start).total_seconds(),
                        system=entry.system,
                    )
                    result.success_count += 1
                else:
                    self._perform_organization_move(
                        entry,
                        full_entry,
                        dest_path,
                        result,
                        item_start,
                    )

            except Exception as e:
                self.logger.error(f"Falha ao organizar {full_entry.path}: {e}")
                result.failed_count += 1

        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result

    def _merge_organization_stats(self, result: Any, dist_stats: dict, org_stats: Any):
        """Funde as estatísticas de distribuição e organização no resultado final."""
        if hasattr(org_stats, "processed_items"):
            result.processed_items.extend(org_stats.processed_items)
            result.success_count = org_stats.success_count
            result.failed_count = org_stats.failed_count
            result.skipped_count = org_stats.skipped_count
        else:
            result.success_count = dist_stats.get("moved", 0) + org_stats.get("renamed", 0)
            result.failed_count = dist_stats.get("errors", 0) + org_stats.get("errors", 0)
            result.skipped_count = dist_stats.get("skipped", 0) + org_stats.get("skipped", 0)

    def full_organization_flow(
        self,
        dry_run: bool = False,
        progress_cb: Optional[Callable] = None,
    ):
        """Workflow Mestre: Move da raiz para pastas e renomeia tudo."""
        set_correlation_id()
        start_time = datetime.now()
        self.logger.info("Iniciando Fluxo de Organização Global...")

        from emumanager.workers.common import WorkerResult
        from emumanager.workers.distributor import worker_distribute_root

        result = WorkerResult(task_name="Global Organization")

        dist_result = worker_distribute_root(
            self.session.roms_path,
            log_cb=self.logger.info,
            progress_cb=progress_cb,
            library_db=self.db,
        )

        result.success_count += dist_result.success_count
        result.skipped_count += dist_result.skipped_count
        result.failed_count += dist_result.failed_count
        result.processed_items.extend(dist_result.processed_items)

        self.scan_library(progress_cb=progress_cb)

        org_result = self.organize_names(dry_run=dry_run, progress_cb=progress_cb)

        if isinstance(org_result, WorkerResult):
            result.processed_items.extend(org_result.processed_items)
            result.success_count += org_result.success_count
            result.failed_count += org_result.failed_count
            result.skipped_count += org_result.skipped_count

        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result
