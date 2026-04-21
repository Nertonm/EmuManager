from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from emumanager.common.exceptions import WorkflowError
from emumanager.common.registry import registry
from emumanager.config import DATE_FMT
from emumanager.core.reporting import HTMLReportGenerator
from emumanager.logging_cfg import set_correlation_id


class OrchestratorLibraryMixin:
    """Library bootstrap, ingest, discovery, and metadata helpers."""

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

        dt = datetime.now().strftime(DATE_FMT)
        (base / "_INSTALL_LOG.txt").write_text(
            f"Provisionamento Core: {dt}\n",
            encoding="utf-8",
        )

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

    def scan_library(
        self,
        progress_cb: Optional[Callable] = None,
        cancel_event: Any = None,
    ):
        """Workflow de Auditoria: Descobre ficheiros e valida contra DATs oficiais."""
        set_correlation_id()
        self.logger.info("A iniciar auditoria global do acervo...")
        return self.scanner.scan_directory(self.session.roms_path, progress_cb, cancel_event)

    def update_dats(self, progress_cb: Optional[Callable] = None):
        return self.dat_manager.update_all_sources(progress_cb)

    def finalize_task(self, result: Any) -> Optional[Path]:
        """Gera o relatório visual final para uma tarefa concluída."""
        if not hasattr(result, "processed_items") or not result.processed_items:
            return None

        logs_dir = self.session.base_path / "logs"
        logs_dir.mkdir(exist_ok=True)

        generator = HTMLReportGenerator()
        return generator.generate(result, logs_dir)

    def _fetch_single_cover(
        self,
        entry: Any,
        system_id: str,
        provider: Any,
        cache_dir: Path,
    ) -> bool:
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
            if progress_cb and len(entries) > 0:
                progress_cb(i / len(entries), f"Capas: {Path(entry.path).name}")

            if self._fetch_single_cover(entry, system_id, provider, cache_dir):
                success += 1
        return success

    def recompress_rom(self, path: Path, target_level: int) -> bool:
        """Força a recompressão de um ficheiro existente."""
        ext = path.suffix.lower()
        self.logger.info(f"Recomprimindo {path.name} para nível {target_level}")

        if ext == ".chd":
            from emumanager.workers.psx import PSXWorker

            worker = PSXWorker(self.session.base_path, self.logger.info, None, None)
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
            hashes = hasher.calculate_hashes(path, algorithms=("crc32", "sha1"))
            matches = db.lookup(crc=hashes.get("crc32"), sha1=hashes.get("sha1"))
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

    def add_rom(self, src: Path, system: Optional[str] = None, move: bool = False):
        """Injeta uma nova ROM no ecossistema Core."""
        set_correlation_id()

        if not src.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {src}")

        provider = registry.get_provider(system) if system else registry.find_provider_for_file(src)
        if not provider:
            raise ValueError(f"Sistema não identificado para: {src.name}")

        if not provider.validate_file(src):
            raise ValueError(f"Arquivo inválido para sistema {provider.system_id}: {src.name}")

        dest_dir = self.session.roms_path / provider.system_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / src.name

        if dest_path.exists():
            raise FileExistsError(f"Arquivo já existe: {dest_path}")

        try:
            if move:
                src.rename(dest_path)
                self.logger.info(f"ROM movida: {src.name} -> {provider.system_id}/")
            else:
                import shutil

                shutil.copy2(src, dest_path)
                self.logger.info(f"ROM copiada: {src.name} -> {provider.system_id}/")
        except Exception as e:
            raise WorkflowError(f"Erro ao adicionar ROM: {e}") from e

        try:
            meta = provider.extract_metadata(dest_path)
            entry = self.scanner._build_entry(dest_path, provider.system_id, meta)
            self.db.update_entry(entry)
        except Exception as e:
            self.logger.warning(f"Metadados não persistidos: {e}")

        self.scan_library()
        return dest_path
