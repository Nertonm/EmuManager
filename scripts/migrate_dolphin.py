#!/usr/bin/env python3
"""
Script de migração para unificar GameCube e Wii em uma única pasta Dolphin.

Este script:
1. Encontra as pastas 'gamecube' e 'wii' no diretório roms
2. Cria uma nova pasta 'dolphin' se não existir
3. Move todos os arquivos de gamecube/ e wii/ para dolphin/
4. Atualiza as entradas no banco de dados library.db
5. Remove as pastas antigas (opcional)

Uso:
    python scripts/migrate_dolphin.py [--dry-run]
"""

import argparse
import logging
import sqlite3
from pathlib import Path
import sys
import shutil

# Adicionar o diretório pai ao path para importar emumanager
sys.path.insert(0, str(Path(__file__).parent.parent))

from emumanager.config import BASE_DEFAULT
from emumanager.core.config_manager import ConfigManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_files(source_dir: Path, dest_dir: Path, dry_run: bool = False) -> int:
    """Move todos os arquivos de source_dir para dest_dir."""
    if not source_dir.exists():
        logger.info(f"⏭️  Pasta {source_dir.name} não existe, pulando...")
        return 0
    
    files = list(source_dir.rglob('*'))
    files = [f for f in files if f.is_file()]
    
    if not files:
        logger.info(f"⏭️  Nenhum arquivo em {source_dir.name}, pulando...")
        return 0
    
    logger.info(f"📂 Encontrados {len(files)} arquivo(s) em {source_dir.name}")
    
    moved_count = 0
    for file in files:
        relative_path = file.relative_to(source_dir)
        dest_file = dest_dir / relative_path
        
        if dry_run:
            logger.info(f"[DRY-RUN] Moveria: {file.name} -> dolphin/{relative_path}")
            moved_count += 1
        else:
            try:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Se o arquivo já existe no destino, adicionar sufixo
                if dest_file.exists():
                    counter = 1
                    while dest_file.exists():
                        dest_file = dest_dir / f"{relative_path.stem}_{counter}{relative_path.suffix}"
                        counter += 1
                    logger.warning(f"⚠️  Arquivo duplicado, renomeando para: {dest_file.name}")
                
                shutil.move(str(file), str(dest_file))
                logger.info(f"✅ Movido: {file.name} -> dolphin/{dest_file.relative_to(dest_dir)}")
                moved_count += 1
            except Exception as e:
                logger.error(f"❌ Erro ao mover {file.name}: {e}")
    
    return moved_count


def update_database(db_path: Path, old_system: str, dry_run: bool = False) -> int:
    """Atualiza as entradas do banco de dados para o novo system_id."""
    if not db_path.exists():
        logger.warning(f"⚠️  Banco de dados não encontrado: {db_path}")
        return 0
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Contar entradas a serem atualizadas
        cursor.execute("SELECT COUNT(*) FROM library WHERE system = ?", (old_system,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info(f"⏭️  Nenhuma entrada de {old_system} no banco de dados")
            conn.close()
            return 0
        
        logger.info(f"📊 Encontradas {count} entrada(s) de {old_system} no banco de dados")
        
        if dry_run:
            logger.info(f"[DRY-RUN] Atualizaria {count} entrada(s) de {old_system} -> dolphin")
            conn.close()
            return count
        
        # Atualizar system de gamecube/wii para dolphin
        cursor.execute(
            "UPDATE library SET system = 'dolphin' WHERE system = ?",
            (old_system,)
        )
        
        # Atualizar caminhos dos arquivos
        cursor.execute(
            "SELECT path FROM library WHERE system = 'dolphin' AND path LIKE ?",
            (f"%/{old_system}/%",)
        )
        paths_to_update = cursor.fetchall()
        
        for (old_path,) in paths_to_update:
            new_path = old_path.replace(f"/{old_system}/", "/dolphin/")
            cursor.execute(
                "UPDATE library SET path = ? WHERE path = ?",
                (new_path, old_path)
            )
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Atualizadas {count} entrada(s) no banco de dados")
        return count
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar banco de dados: {e}")
        return 0


def cleanup_old_dirs(roms_dir: Path, dry_run: bool = False):
    """Remove as pastas antigas gamecube/ e wii/ se estiverem vazias."""
    for old_dir in ["gamecube", "wii"]:
        dir_path = roms_dir / old_dir
        if not dir_path.exists():
            continue
        
        # Verificar se está vazia
        remaining_files = list(dir_path.rglob('*'))
        remaining_files = [f for f in remaining_files if f.is_file()]
        
        if remaining_files:
            logger.warning(f"⚠️  {old_dir}/ ainda contém {len(remaining_files)} arquivo(s), não será removida")
            continue
        
        if dry_run:
            logger.info(f"[DRY-RUN] Removeria pasta vazia: {old_dir}/")
        else:
            try:
                shutil.rmtree(dir_path)
                logger.info(f"🗑️  Removida pasta vazia: {old_dir}/")
            except Exception as e:
                logger.error(f"❌ Erro ao remover {old_dir}/: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Migra GameCube e Wii para pasta unificada Dolphin"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a migração sem fazer alterações"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        help="Diretório base do EmuManager (padrão: config)"
    )
    
    args = parser.parse_args()
    
    # Obter diretório base
    if args.base_dir:
        base_dir = args.base_dir
    else:
        try:
            config = ConfigManager()
            base_dir = Path(config.get("base_dir"))
        except:
            base_dir = BASE_DEFAULT
    
    logger.info(f"🚀 Iniciando migração Dolphin (GameCube + Wii)")
    logger.info(f"📁 Diretório base: {base_dir}")
    
    if args.dry_run:
        logger.info("🔍 MODO DRY-RUN: Nenhuma alteração será feita")
    
    # Preparar diretórios
    roms_dir = base_dir / "roms"
    if not roms_dir.exists():
        logger.error(f"❌ Diretório roms não encontrado: {roms_dir}")
        return 1
    
    gamecube_dir = roms_dir / "gamecube"
    wii_dir = roms_dir / "wii"
    dolphin_dir = roms_dir / "dolphin"
    
    # Criar pasta dolphin
    if not args.dry_run:
        dolphin_dir.mkdir(exist_ok=True)
        logger.info(f"✅ Pasta dolphin criada/verificada: {dolphin_dir}")
    else:
        logger.info(f"[DRY-RUN] Criaria pasta: {dolphin_dir}")
    
    # Migrar arquivos
    total_moved = 0
    total_moved += migrate_files(gamecube_dir, dolphin_dir, args.dry_run)
    total_moved += migrate_files(wii_dir, dolphin_dir, args.dry_run)
    
    # Atualizar banco de dados
    db_path = base_dir / "library.db"
    total_updated = 0
    total_updated += update_database(db_path, "gamecube", args.dry_run)
    total_updated += update_database(db_path, "wii", args.dry_run)
    
    # Limpar pastas antigas
    cleanup_old_dirs(roms_dir, args.dry_run)
    
    # Resumo
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 RESUMO DA MIGRAÇÃO")
    logger.info("=" * 60)
    logger.info(f"Arquivos movidos: {total_moved}")
    logger.info(f"Entradas atualizadas no DB: {total_updated}")
    
    if args.dry_run:
        logger.info("")
        logger.info("ℹ️  Este foi um DRY-RUN. Execute sem --dry-run para aplicar as mudanças.")
    else:
        logger.info("")
        logger.info("✅ Migração concluída com sucesso!")
        logger.info("ℹ️  Execute 'emumanager scan' para atualizar a biblioteca")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
