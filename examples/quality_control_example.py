#!/usr/bin/env python3
"""
Exemplo de uso do sistema Quality Control.

Este script demonstra como usar o sistema de verificação de qualidade
de ROMs para analisar uma coleção e gerar relatórios.
"""

from pathlib import Path
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.quality import QualityController, QualityLevel


def exemplo_analise_individual():
    """Demonstra análise de uma ROM individual."""
    print("=" * 70)
    print("EXEMPLO 1: Análise de ROM Individual")
    print("=" * 70)
    
    db = LibraryDB()
    controller = QualityController(db)
    
    # Criar entrada de exemplo (normalmente viria do banco)
    entry = LibraryEntry(
        path="/roms/gba/Pokemon Emerald.gba",
        system="gba",
        size=16 * 1024 * 1024,  # 16 MB
        mtime=1234567890.0,
        status="VERIFIED"
    )
    
    # Analisar qualidade
    quality = controller.analyze_rom(entry)
    
    # Mostrar resultados
    print(f"\n🎮 ROM: {Path(entry.path).name}")
    print(f"📁 Sistema: {entry.system.upper()}")
    print(f"💾 Tamanho: {entry.size / (1024*1024):.1f} MB")
    print()
    print(f"🏥 Qualidade: {quality.icon} {quality.quality_level.value}")
    print(f"📊 Score: {quality.score}/100")
    print(f"🎯 Jogável: {'✅ Sim' if quality.is_playable else '❌ Não'}")
    print()
    
    if quality.checks_performed:
        print("✓ Verificações realizadas:")
        for check in quality.checks_performed:
            print(f"  • {check}")
        print()
    
    if quality.issues:
        print("⚠️ Problemas detectados:")
        for issue in quality.issues:
            severity_icon = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🔵'
            }.get(issue.severity, '⚪')
            
            print(f"  {severity_icon} [{issue.severity.upper()}] {issue.description}")
            if issue.location:
                print(f"     @ {issue.location}")
            if issue.recommendation:
                print(f"     → {issue.recommendation}")
        print()
    else:
        print("✅ Nenhum problema detectado!")
        print()


def exemplo_analise_biblioteca():
    """Demonstra análise de toda a biblioteca."""
    print("=" * 70)
    print("EXEMPLO 2: Análise de Biblioteca Completa")
    print("=" * 70)
    
    db = LibraryDB()
    controller = QualityController(db)
    
    # Analisar apenas GBA (pode omitir system para analisar tudo)
    print("\n🔍 Analisando biblioteca de GBA...")
    results = controller.analyze_library(system="gba")
    
    print(f"\n📊 Resultados: {len(results)} ROMs analisadas\n")
    
    # Agrupar por nível de qualidade
    by_level = {}
    for path, quality in results.items():
        level = quality.quality_level
        if level not in by_level:
            by_level[level] = []
        by_level[level].append((path, quality))
    
    # Mostrar cada grupo
    for level in QualityLevel:
        roms = by_level.get(level, [])
        if not roms:
            continue
        
        icon = "✓✓" if level == QualityLevel.PERFECT else \
               "✓" if level == QualityLevel.GOOD else \
               "⚠" if level == QualityLevel.QUESTIONABLE else \
               "✗" if level == QualityLevel.DAMAGED else \
               "✗✗" if level == QualityLevel.CORRUPT else "?"
        
        print(f"{icon} {level.value}: {len(roms)} ROMs")
        
        # Mostrar até 3 exemplos de cada nível
        for path, quality in roms[:3]:
            rom_name = Path(path).name
            print(f"  • {rom_name} (score: {quality.score}/100)")
            
            # Mostrar primeiro issue se houver
            if quality.issues:
                issue = quality.issues[0]
                print(f"    └─ {issue.description}")
        
        if len(roms) > 3:
            print(f"  ... e mais {len(roms) - 3} ROMs")
        print()


def exemplo_estatisticas():
    """Demonstra geração de estatísticas."""
    print("=" * 70)
    print("EXEMPLO 3: Estatísticas da Coleção")
    print("=" * 70)
    
    db = LibraryDB()
    controller = QualityController(db)
    
    # Obter estatísticas
    stats = controller.get_quality_statistics()
    
    print("\n📈 Estatísticas Gerais")
    print("─" * 70)
    print(f"Total de ROMs: {stats['total']}")
    print(f"Score médio: {stats['average_score']:.1f}/100")
    print(f"Jogáveis: {stats['playable']} ({stats['playable_percentage']:.1f}%)")
    print(f"Danificadas/Corrompidas: {stats['damaged']} ({stats['damaged_percentage']:.1f}%)")
    print()
    
    print("📊 Distribuição por Nível")
    print("─" * 70)
    
    total = stats['total']
    for level, count in stats['by_level'].items():
        if count == 0:
            continue
        
        percentage = (count / total) * 100
        bar_length = int(percentage / 2)  # 50 chars = 100%
        bar = "█" * bar_length + "░" * (50 - bar_length)
        
        icon = "✓✓" if level == QualityLevel.PERFECT else \
               "✓" if level == QualityLevel.GOOD else \
               "⚠" if level == QualityLevel.QUESTIONABLE else \
               "✗" if level == QualityLevel.DAMAGED else \
               "✗✗" if level == QualityLevel.CORRUPT else "?"
        
        print(f"{icon} {level.value:15} {count:4} ({percentage:5.1f}%) {bar}")
    print()
    
    print("⚠️ Top 10 Problemas Mais Comuns")
    print("─" * 70)
    
    for i, (issue_type, count) in enumerate(stats['top_issues'][:10], 1):
        print(f"{i:2}. {issue_type.value:20} ({count} ocorrências)")
    print()
    
    if stats['corrupted_roms']:
        print(f"🔴 ROMs Corrompidas/Danificadas ({len(stats['corrupted_roms'])})")
        print("─" * 70)
        
        for rom in stats['corrupted_roms'][:5]:
            rom_name = Path(rom['path']).name
            print(f"• {rom_name}")
            print(f"  └─ {rom['first_critical_issue']}")
        
        if len(stats['corrupted_roms']) > 5:
            print(f"  ... e mais {len(stats['corrupted_roms']) - 5} ROMs")
        print()


def exemplo_filtros_avancados():
    """Demonstra uso de filtros e queries avançadas."""
    print("=" * 70)
    print("EXEMPLO 4: Filtros e Queries Avançadas")
    print("=" * 70)
    
    db = LibraryDB()
    controller = QualityController(db)
    
    # Obter todos os resultados
    results = controller.analyze_library()
    
    # Filtro 1: ROMs perfeitas
    perfect_roms = [
        (path, q) for path, q in results.items()
        if q.quality_level == QualityLevel.PERFECT
    ]
    print(f"\n✨ ROMs Perfeitas: {len(perfect_roms)}")
    for path, _ in perfect_roms[:5]:
        print(f"  • {Path(path).name}")
    if len(perfect_roms) > 5:
        print(f"  ... e mais {len(perfect_roms) - 5}")
    print()
    
    # Filtro 2: ROMs que precisam atenção
    needs_attention = [
        (path, q) for path, q in results.items()
        if not q.is_playable
    ]
    print(f"⚠️ ROMs que Precisam Atenção: {len(needs_attention)}")
    for path, quality in needs_attention[:5]:
        print(f"  • {Path(path).name}")
        print(f"    Score: {quality.score}/100, Nível: {quality.quality_level.value}")
        if quality.issues:
            print(f"    Problema: {quality.issues[0].description}")
    if len(needs_attention) > 5:
        print(f"  ... e mais {len(needs_attention) - 5}")
    print()
    
    # Filtro 3: ROMs sem verificação DAT
    unverified = [
        (path, q) for path, q in results.items()
        if not q.dat_verified
    ]
    print(f"🔍 ROMs Não Verificadas com DAT: {len(unverified)}")
    print("   (Recomenda-se executar verificação DAT)")
    print()
    
    # Filtro 4: ROMs com score baixo mas jogáveis
    questionable = [
        (path, q) for path, q in results.items()
        if q.is_playable and q.score < 70
    ]
    print(f"❓ ROMs Questionáveis: {len(questionable)}")
    print("   (Jogáveis mas com problemas menores)")
    for path, quality in questionable[:3]:
        print(f"  • {Path(path).name} (score: {quality.score}/100)")
    if len(questionable) > 3:
        print(f"  ... e mais {len(questionable) - 3}")
    print()


def main():
    """Executa todos os exemplos."""
    print("\n" + "🏥" * 35)
    print("  SISTEMA DE QUALITY CONTROL - EXEMPLOS DE USO")
    print("🏥" * 35 + "\n")
    
    try:
        exemplo_analise_individual()
        print("\n" + "─" * 70 + "\n")
        
        exemplo_analise_biblioteca()
        print("\n" + "─" * 70 + "\n")
        
        exemplo_estatisticas()
        print("\n" + "─" * 70 + "\n")
        
        exemplo_filtros_avancados()
        
        print("=" * 70)
        print("✅ Exemplos executados com sucesso!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Erro ao executar exemplos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
