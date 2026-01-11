from __future__ import annotations

import logging
import csv
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Any, Iterable
from types import SimpleNamespace

from emumanager.config import DATE_FMT
from emumanager.core.session import Session
from emumanager.core.scanner import Scanner
from emumanager.core.dat_manager import DATManager
from emumanager.core.integrity import IntegrityManager
from emumanager.core.reporting import HTMLReportGenerator
from emumanager.core.multidisc import MultiDiscManager
from emumanager.library import LibraryDB


from emumanager.logging_cfg import get_logger, set_correlation_id
from emumanager.common.registry import registry
from emumanager.common.fileops import safe_move
from emumanager.common.events import bus


class Orchestrator:
    """
    O Coração do EmuManager (Arquiteto Principal).
    
    Coordena os workflows de alto nível da aplicação, emitindo eventos
    via EventBus para feedback assíncrono.
    """

    def __init__(self, session: Session):
        """Inicializa o motor core com base numa sessão ativa."""
        self.session = session
        
        # Infraestrutura de Dados
        self.db = LibraryDB(self.session.base_path / "library.db")
        self.logger = get_logger("core.orchestrator")
        
        # Especialistas (Managers)
        self.dat_manager = DATManager(self.session.base_path / "dats")
        self.integrity = IntegrityManager(self.session.base_path, self.db)
        self.scanner = Scanner(self.db, dat_manager=self.dat_manager)
        self.multidisc = MultiDiscManager()


        # Telemetria
        self._start_time: Optional[float] = None
        self._items_processed = 0

    def get_telemetry(self) -> dict[str, Any]:
        """Retorna métricas de performance atuais."""
        import os, time
        elapsed = time.time() - self._start_time if self._start_time else 0
        speed = self._items_processed / elapsed if elapsed > 0 else 0
        
        import psutil
        try:
            process = psutil.Process(os.getpid())
            mem = process.memory_info().rss / 1024 / 1024
        except Exception:
            mem = 0

        return {
            "speed": f"{speed:.1f} it/s",
            "memory": f"{mem:.1f} MB",
            "uptime": f"{elapsed:.0f}s"
        }


    def _emit_progress(self, percent: float, message: str):
        bus.emit("progress_update", percent=percent, message=message)

    def _emit_task_start(self, task_name: str):
        bus.emit("task_started", name=task_name)


    # --- Workflow: Inicialização ---

    def initialize_library(self, dry_run: bool = False) -> None:
        """Prepara a estrutura física e documental do acervo."""
        set_correlation_id()
        base = self.session.base_path
        self.logger.info(f"A arquitetar biblioteca em: {base}")
        
        if not dry_run:
            self._prepare_physical_structure(base)
            
        for sys_id in registry.list_systems():
            provider = registry.get_provider(sys_id)
            if provider:
                self._setup_system_node(provider, dry_run)

        self.logger.info("Arquitetura da biblioteca concluída.")

    def _prepare_physical_structure(self, base: Path):
        base.mkdir(parents=True, exist_ok=True)
        for folder in ["bios", "dats", "roms", "logs", "_QUARANTINE"]:
            (base / folder).mkdir(exist_ok=True)
        
        # Log de Provisionamento
        dt = datetime.now().strftime(DATE_FMT)
        (base / "_INSTALL_LOG.txt").write_text(f"Provisionamento Core: {dt}\n", encoding="utf-8")

    def _setup_system_node(self, provider: Any, dry_run: bool):
        """Configura uma consola individual no acervo."""
        path = self.session.roms_path / provider.system_id
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
            info = provider.get_technical_info()
            content = self._render_technical_guide(provider, info)
            (path / "_INFO_TECNICA.txt").write_text(content, encoding="utf-8")

    def _render_technical_guide(self, provider: Any, info: dict) -> str:
        return f"""
==============================================================================
   GUIA TÉCNICO: {provider.display_name}
==============================================================================
Gerado por: EmuManager Core Engine

[ FORMATOS RECOMENDADOS ]
{info.get('formats', 'N/A')}

[ REQUER BIOS? ]
{info.get('bios', 'Não')}

[ DOCUMENTAÇÃO OFICIAL ]
Wiki: {info.get('wiki', 'N/A')}

[ NOTAS ]
{info.get('notes', 'Mantenha os ficheiros organizados por pastas se necessário.')}
==============================================================================
"""

    # --- Workflow: Descoberta e Validação ---

    def scan_library(self, progress_cb: Optional[Callable] = None, cancel_event: Any = None):
        """Workflow de Auditoria: Descobre ficheiros e valida contra DATs oficiais."""
        set_correlation_id()
        self.logger.info("A iniciar auditoria global do acervo...")
        return self.scanner.scan_directory(self.session.roms_path, progress_cb, cancel_event)

    def update_dats(self, progress_cb: Optional[Callable] = None):
        return self.dat_manager.update_all_sources(progress_cb)

    def finalize_task(self, result: Any) -> Optional[Path]:
        """Gera o relatório visual final para uma tarefa concluída."""
        if not hasattr(result, 'processed_items') or not result.processed_items:
            return None
            
        logs_dir = self.session.base_path / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        generator = HTMLReportGenerator()
        return generator.generate(result, logs_dir)


    def _fetch_single_cover(self, entry: Any, system_id: str, provider: Any, cache_dir: Path) -> bool:
        """Tenta descarregar uma capa individual."""
        import requests
        url = provider.get_cover_url(system_id, None, entry.match_name or Path(entry.path).stem)
        if not url:
            return False

        try:
            target = cache_dir / f"{Path(entry.path).stem}.png"
            if target.exists():
                return False
                
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                target.write_bytes(resp.content)
                return True
        except Exception as e:
            self.logger.debug(f"Falha ao descarregar capa para {entry.path}: {e}")
            
        return False

    def fetch_covers_for_system(self, system_id: str, progress_cb: Optional[Callable] = None):
        """Descarrega capas para todos os jogos de um sistema (Headless)."""
        from emumanager.metadata_providers import LibretroProvider
        provider = LibretroProvider()
        entries = self.db.get_entries_by_system(system_id)
        
        cache_dir = self.session.base_path / ".covers" / system_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        success = 0
        for i, entry in enumerate(entries):
            if progress_cb:
                progress_cb(i / len(entries), f"Capas: {Path(entry.path).name}")
            
            if self._fetch_single_cover(entry, system_id, provider, cache_dir):
                success += 1
        return success

    def recompress_rom(self, path: Path, target_level: int) -> bool:
        """Força a recompressão de um ficheiro existente."""
        # Delegação para worker específico baseada na extensão
        ext = path.suffix.lower()
        self.logger.info(f"Recomprimindo {path.name} para nível {target_level}")
        
        # Exemplo simplificado: PS2 CHD
        if ext == ".chd":
            from emumanager.workers.psx import PSXWorker
            worker = PSXWorker(self.session.base_path, self.logger.info, None, None)
            # A lógica de recompressão CHD usaria chdman internamente
            return worker._process_item(path) == "success"
        return False


    def identify_single_file(self, path: Path) -> dict[str, Any]:
        """Tenta identificar um ficheiro específico contra os DATs carregados."""
        provider = registry.find_provider_for_file(path)
        system_id = provider.system_id if provider else "unknown"
        
        dat_path = self.dat_manager.find_dat_for_system(system_id)
        from emumanager.verification import dat_parser, hasher
        
        metadata = provider.extract_metadata(path) if provider else {}
        if dat_path:
            db = dat_parser.parse_dat_file(dat_path)
            h = hasher.calculate_hashes(path, algorithms=("crc32", "sha1"))
            matches = db.lookup(crc=h.get("crc32"), sha1=h.get("sha1"))
            if matches:
                metadata.update({"match": matches[0].game_name, "verified": True})
        
        return metadata

    def delete_rom_file(self, path: Path) -> bool:
        """Remove fisicamente e logicamente uma ROM."""
        try:
            if path.exists():
                path.unlink()
            self.db.remove_entry(str(path.resolve()))
            return True
        except Exception:
            return False


    def run_performance_benchmark(self, progress_cb: Optional[Callable] = None) -> dict[str, Any]:
        """Simula uma carga pesada de processamento para validar a concorrência."""
        self.logger.info("Iniciando Benchmark de Performance (Stress Test)...")
        
        # Criamos uma lista de tarefas fictícias (cálculo de hashes complexos)
        # para forçar o uso de multiprocessing ao máximo.
        import os
        from emumanager.workers.common import BaseWorker
        
        class BenchmarkWorker(BaseWorker):
            def _process_item(self, item: Path) -> str:
                # Simula processamento intensivo de 0.5s
                import hashlib
                data = os.urandom(1024 * 1024 * 10) # 10MB
                for _ in range(5):
                    hashlib.sha512(data).hexdigest()
                return "success"

        worker = BenchmarkWorker(self.session.base_path, self.logger.info, progress_cb, None)
        # Criamos 50 itens virtuais
        items = [Path(f"virtual_task_{i}") for i in range(50)]
        
        start = datetime.now()
        res = worker.run(items, task_label="Benchmark CPU", parallel=True)
        duration = (datetime.now() - start).total_seconds()
        
        return {
            "tasks": res.success_count,
            "duration": f"{duration:.2f}s",
            "cores": os.cpu_count()
        }


    # --- Workflow: Transformação e Manutenção ---

    def _get_ideal_path(self, entry: Any, provider: Any, full_entry: Any) -> Path:
        """Resolve o caminho ideal canónico para um ficheiro."""
        ideal_rel = provider.get_ideal_filename(Path(full_entry.path), full_entry.extra_metadata)
        system_root = self.session.roms_path / entry.system
        
        # Limpeza de caracteres proibidos em cada segmento do caminho
        parts = Path(ideal_rel).parts
        clean_parts = ["".join([c for c in p if c not in '<>:\"/\\|?*']).strip() for p in parts]
        return system_root / Path(*clean_parts)

    def _perform_organization_move(self, entry: Any, full_entry: Any, dest_path: Path, result: Any, item_start: datetime):
        """Executa a movimentação física e lógica de uma entrada."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        args = SimpleNamespace(dry_run=False, dup_check="fast")
        orig_path = Path(full_entry.path)
        
        if safe_move(orig_path, dest_path, args=args, get_file_hash=lambda p: "", logger=self.logger):
            self.db.remove_entry(full_entry.path)
            full_entry.path = str(dest_path)
            self.db.update_entry(full_entry)
            result.add_item_result(orig_path, "success", (datetime.now()-item_start).total_seconds(), system=entry.system)
            result.success_count += 1
            return True
        
        result.failed_count += 1
        return False

    def organize_names(self, system_id: Optional[str] = None, dry_run: bool = False, progress_cb: Optional[Callable] = None):
        """Workflow de Organização: Aplica nomes canónicos e hierarquia por sistema."""
        set_correlation_id()
        start_time = datetime.now()
        entries = self.db.get_entries_by_system(system_id) if system_id else self.db.get_all_entries()
        
        from emumanager.workers.common import WorkerResult
        result = WorkerResult(task_name=f"Organize {system_id or 'All'}")

        for i, entry in enumerate(entries):
            if progress_cb:
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
                    self.logger.info(f"[DRY-RUN] Organize: {Path(full_entry.path).name} -> {dest_path}")
                    result.add_item_result(Path(full_entry.path), "success", (datetime.now()-item_start).total_seconds(), system=entry.system)
                    result.success_count += 1
                else:
                    self._perform_organization_move(entry, full_entry, dest_path, result, item_start)

            except Exception as e:
                self.logger.error(f"Falha ao organizar {full_entry.path}: {e}")
                result.failed_count += 1
        
        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result

    def _merge_organization_stats(self, result: Any, dist_stats: dict, org_stats: Any):
        """Funde as estatísticas de distribuição e organização no resultado final."""
        # Considerar o organize_names como a fonte principal de itens processados se for um WorkerResult
        if hasattr(org_stats, 'processed_items'):
            result.processed_items.extend(org_stats.processed_items)
            result.success_count = org_stats.success_count
            result.failed_count = org_stats.failed_count
            result.skipped_count = org_stats.skipped_count
        else:
            # Fallback se organize_names retornar dict simples
            result.success_count = dist_stats.get("moved", 0) + org_stats.get("renamed", 0)
            result.failed_count = dist_stats.get("errors", 0) + org_stats.get("errors", 0)
            result.skipped_count = dist_stats.get("skipped", 0) + org_stats.get("skipped", 0)

    def full_organization_flow(self, dry_run: bool = False, progress_cb: Optional[Callable] = None):
        """Workflow Mestre: Move da raiz para pastas e renomeia tudo."""
        set_correlation_id()
        start_time = datetime.now()
        self.logger.info("Iniciando Fluxo de Organização Global...")
        
        from emumanager.workers.common import WorkerResult
        result = WorkerResult(task_name="Global Organization")
        
        # 1. Distribuir ficheiros da raiz para pastas de sistema
        from emumanager.workers.distributor import worker_distribute_root
        dist_stats = worker_distribute_root(self.session.roms_path, log_cb=self.logger.info, progress_cb=progress_cb)
        result.success_count += dist_stats.get("moved", 0)
        result.skipped_count += dist_stats.get("skipped", 0)
        result.failed_count += dist_stats.get("errors", 0)

        # 2. Scan para detetar novos ficheiros e atualizar DB
        self.scan_library(progress_cb=progress_cb)
        
        # 3. Organizar nomes
        org_stats = self.organize_names(dry_run=dry_run, progress_cb=progress_cb)
        
        self._merge_organization_stats(result, dist_stats, org_stats)

        result.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return result

    def maintain_integrity(self, dry_run: bool = False) -> dict[str, int]:
        """Workflow de Sanidade: Isola corrupção e limpa duplicados."""
        set_correlation_id()
        self.logger.info("Executando manutenção de integridade...")
        
        # 1. Quarentena
        q_stats = self.quarantine_corrupt_files(dry_run)
        
        # 2. Deduplicação
        d_stats = self.cleanup_duplicates(dry_run)
        
        return {**q_stats, **d_stats}

    def quarantine_corrupt_files(self, dry_run: bool = False) -> dict[str, int]:
        """Isola ficheiros marcados como corrompidos."""
        entries = [e for e in self.db.get_all_entries() if e.status == "CORRUPT"]
        stats = {"quarantined": 0, "errors": 0}
        
        for entry in entries:
            if dry_run:
                self.logger.info(f"[DRY-RUN] Seria isolado: {Path(entry.path).name}")
                stats["quarantined"] += 1
                continue

            res = self.integrity.quarantine_file(Path(entry.path), entry.system, "Corruption", "Hash mismatch")
            if res: stats["quarantined"] += 1
            else: stats["errors"] += 1
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
        for e in entries:
            if e.sha1:
                by_hash.setdefault(e.sha1, []).append(e)
        
        stats = {"removed": 0, "errors": 0}
        for sha1, group in by_hash.items():
            if len(group) <= 1:
                continue
            
            # Ordenar: Preferidos primeiro, depois por tamanho
            group.sort(key=self._score_duplicate_entry, reverse=True)
            keep = group[0]
            to_remove = group[1:]
            
            for entry in to_remove:
                if dry_run:
                    self.logger.info(f"[DRY-RUN] Duplicado removido: {Path(entry.path).name} (Mantido {Path(keep.path).name})")
                    stats["removed"] += 1
                else:
                    self._remove_duplicate_entry(entry, stats)
                    
        return stats

    def generate_m3u_playlists(self, system_id: str, hide_discs: bool = True) -> dict[str, int]:
        """Agrupa jogos multi-disco e cria playlists .m3u."""
        system_root = self.session.roms_path / system_id
        if not system_root.exists(): return {"error": "Pasta não encontrada"}
        
        all_files = [p for p in system_root.iterdir() if p.is_file()]

        groups = self.multidisc.group_discs(all_files)
        
        stats = {"created_m3u": 0, "moved_discs": 0}
        for base_title, discs in groups.items():
            self.multidisc.create_m3u(base_title, discs, system_root, hide_discs)
            stats["created_m3u"] += 1
            if hide_discs: stats["moved_discs"] += len(discs)
            
        # Forçar re-scan após mover ficheiros
        self.scan_library()
        return stats

    def bulk_transcode(self, dry_run: bool = False, progress_cb: Optional[Callable] = None):
        """Workflow de Modernização: Transcoding massivo para formatos eficientes."""
        set_correlation_id()
        entries = self.db.get_all_entries()
        to_convert = {}
        for entry in entries:
            provider = registry.get_provider(entry.system)
            if provider and provider.needs_conversion(Path(entry.path)):
                to_convert.setdefault(entry.system, []).append(Path(entry.path))

        # Workers Paralelos
        from emumanager.workers.ps2 import PS2Worker
        from emumanager.workers.dolphin import DolphinWorker
        from emumanager.workers.psp import PSPWorker
        
        worker_map = {"ps2": PS2Worker, "gamecube": DolphinWorker, "wii": DolphinWorker, "psp": PSPWorker}
        total = {"converted": 0, "failed": 0}
        
        for sys_id, paths in to_convert.items():
            if sys_id in worker_map:
                worker = worker_map[sys_id](self.session.base_path, self.logger.info, progress_cb, None)
                res = worker.run(paths, task_label=f"Transcoding {sys_id}", parallel=True)
                total["converted"] += res.success_count
                total["failed"] += res.failed_count
        return total

    # --- Utilitários de Relatório ---

    def generate_compliance_report(self, output_path: Path) -> bool:
        """Gera um diagnóstico completo do acervo em CSV."""
        self.logger.info(f"A gerar relatório de conformidade: {output_path}")
        entries = self.db.get_all_entries()
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Sistema", "Status", "Título", "ID/Serial", "Tamanho", "Caminho", "SHA1"])
                for e in entries:
                    full = self.db.get_entry(e.path)
                    if full:
                        writer.writerow([full.system, full.status, full.match_name, full.dat_name, full.size, full.path, full.sha1])
            return True
        except Exception as e:
            self.logger.error(f"Erro relatório: {e}")
            return False

    def add_rom(self, src: Path, system: Optional[str] = None, move: bool = False):
        """Injeta uma nova ROM no ecossistema Core."""
        set_correlation_id()
        provider = registry.get_provider(system) if system else registry.find_provider_for_file(src)
        if not provider: raise ValueError(f"Sistema não identificado para: {src.name}")
            
        dest = self.session.roms_path / provider.system_id / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Importando {provider.display_name}: {src.name}")
        if move: shutil.move(str(src), str(dest))
        else: shutil.copy2(str(src), str(dest))
            
        try:
            meta = provider.extract_metadata(dest)
            entry = self.scanner._build_entry(dest, provider.system_id, meta)
            self.db.update_entry(entry)
        except Exception as e:
            self.logger.warning(f"Metadados não persistidos: {e}")
        return dest
    