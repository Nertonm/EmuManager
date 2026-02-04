# Quality Control

Sistema avançado de verificação de integridade e qualidade de ROMs com detecção de corrupção e validação específica por plataforma.

## Visão Geral

O sistema **Quality Control** analisa a integridade de ROMs usando verificações específicas de cada sistema, detectando problemas como headers inválidos, checksums incorretos, arquivos truncados, e corrupção de dados.

## Funcionalidades

### Níveis de Qualidade

O sistema classifica ROMs em 6 níveis:

| Nível | Ícone | Cor | Descrição | Jogável |
|-------|-------|-----|-----------|---------|
| **PERFECT** | ✓✓ | Verde | ROM perfeita, verificada com DAT | ✅ |
| **GOOD** | ✓ | Ciano | ROM boa, todas verificações passaram | ✅ |
| **QUESTIONABLE** | ⚠ | Amarelo | ROM com pequenos problemas | ✅ |
| **DAMAGED** | ✗ | Vermelho | ROM danificada, pode não funcionar | ❌ |
| **CORRUPT** | ✗✗ | Vermelho | ROM corrompida, não funcionará | ❌ |
| **UNKNOWN** | ? | Cinza | Não foi possível determinar qualidade | ❓ |

### Score de Qualidade

Cada ROM recebe um score de 0-100 baseado em:

- **Estrutura básica** (+30): Arquivo não vazio, tamanho adequado
- **Header válido** (+30): Header do sistema reconhecido
- **Checksums corretos** (+20): Checksums internos válidos
- **Verificação DAT** (+20): Match com banco de dados DAT

### Tipos de Problemas Detectados

#### Críticos
- `INVALID_HEADER` - Header da ROM inválido
- `INVALID_CHECKSUM` - Checksum incorreto
- `TRUNCATED_FILE` - Arquivo incompleto/truncado
- `ZERO_BYTES` - Arquivo vazio ou só zeros
- `CORRUPT_DATA` - Dados corrompidos detectados

#### Alta Severidade
- `MODIFIED_ROM` - ROM modificada/alterada
- `REGION_MISMATCH` - Região não corresponde ao esperado

#### Média Severidade
- `SUSPICIOUS_SIZE` - Tamanho suspeito para o sistema
- `WEAK_DUMP` - Dump de baixa qualidade
- `BAD_SECTORS` - Setores ruins detectados

#### Baixa Severidade
- `METADATA_MISSING` - Metadados ausentes
- `NON_STANDARD_FORMAT` - Formato não padrão
- `UNVERIFIED` - Não verificado com DAT

## Health Checkers por Sistema

### Game Boy Advance (GBA)

Valida:
- **Entry Point**: Instrução B no offset 0x00
- **Nintendo Logo**: 156 bytes @ 0x04
- **Game Title**: 12 bytes @ 0xA0
- **Header Checksum**: Cálculo @ 0xBD
- **Tamanho**: 1-32 MB

```python
from emumanager.quality import GBAHealthChecker

checker = GBAHealthChecker()
checker.check(rom_path, quality)
```

### PlayStation 2 (PS2)

Valida:
- **ISO9660 Descriptor**: "CD001" @ 0x8000
- **SYSTEM.CNF**: Arquivo de boot presente
- **Tamanho**: 100 MB - 9 GB (DVD-9)

```python
from emumanager.quality import PS2HealthChecker

checker = PS2HealthChecker()
checker.check(rom_path, quality)
```

### PlayStation (PSX)

Valida:
- **CUE Sheet**: Referências BIN corretas
- **Sector Size**: 2352 bytes (Mode 2)
- **Sony License**: String @ 0x9340
- **Tamanho**: 50-700 MB

```python
from emumanager.quality import PSXHealthChecker

checker = PSXHealthChecker()
checker.check(rom_path, quality)
```

### Nintendo Switch

Valida:
- **NSP**: Magic "PFS0", contagem de arquivos
- **XCI**: Magic "HEAD", estrutura válida
- **Tamanho**: >100 MB

```python
from emumanager.quality import SwitchHealthChecker

checker = SwitchHealthChecker()
checker.check(rom_path, quality)
```

### Nintendo GameCube

Valida:
- **Disc ID**: 6 bytes @ 0x00, começa com 'G'
- **Game Title**: @ 0x20
- **boot.bin**: Header presente
- **Tamanho**: ~1.4 GB

```python
from emumanager.quality import GameCubeHealthChecker

checker = GameCubeHealthChecker()
checker.check(rom_path, quality)
```

## Uso no TUI

### Visualização na Tabela

A coluna "Qualidade" mostra o ícone com cor para cada ROM:

```
┌──────────┬─────────────────────┬─────────┬──────────┐
│ Qualidade│ Ficheiro            │ Estado  │ Compat.  │
├──────────┼─────────────────────┼─────────┼──────────┤
│ ✓✓       │ Super Mario 64.z64  │ OK      │ ★★★★★    │
│ ✓        │ Zelda OOT.z64       │ OK      │ ★★★★★    │
│ ⚠        │ Mario Kart 64.z64   │ Warn    │ ★★★★☆    │
│ ✗        │ DK64.z64            │ Damaged │ ★★☆☆☆    │
│ ✗✗       │ Corrupt.z64         │ Bad     │ ☆☆☆☆☆    │
└──────────┴─────────────────────┴─────────┴──────────┘
```

### Inspector de ROM

Ao selecionar uma ROM, o inspector mostra:

```
═══════════════════════════════════════════════════════════
Ficheiro: Super Mario 64.z64
Sistema: n64
Tamanho: 8.0 MB
Modificado: 2024-01-15 14:30:22

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏥 Qualidade: ✓✓ PERFECT
Score: 100/100

ROM em perfeitas condições, verificada com DAT.
Totalmente jogável.

RetroArch: ★★★★★ (Excelente)
Estado: VERIFIED
DAT Match: Nintendo - N64 (Official)
═══════════════════════════════════════════════════════════
```

Com problemas detectados:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏥 Qualidade: ⚠ QUESTIONABLE
Score: 65/100

ROM com problemas menores, mas jogável.

Problemas detectados:
  ⚠ SUSPICIOUS_SIZE (medium)
    Tamanho 6.5 MB é incomum para GBA
    → Verificar se ROM está completa

  ⚠ METADATA_MISSING (low)
    Metadados ausentes
    → Verificar com DAT database

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Operação Quality Check

Menu TUI → `🏥 Quality Check`

Executa análise completa da coleção:

```
═══════════════════════════════════════════════════════════
🏥 Análise de Qualidade da Coleção
═══════════════════════════════════════════════════════════

📊 Estatísticas Gerais
────────────────────────────────────────────────────────────
Total de ROMs: 1,234
Score médio: 82.5/100
Jogáveis: 1,180 (95.6%)
Danificadas/Corrompidas: 54 (4.4%)

📈 Distribuição por Nível
────────────────────────────────────────────────────────────
✓✓ PERFECT:       456 (37.0%) ████████████░░░░░░░░░░░░░░░
✓  GOOD:          587 (47.6%) ███████████████░░░░░░░░░░░░
⚠  QUESTIONABLE:  137 (11.1%) ████░░░░░░░░░░░░░░░░░░░░░░░
✗  DAMAGED:        38 (3.1%)  █░░░░░░░░░░░░░░░░░░░░░░░░░░
✗✗ CORRUPT:        16 (1.3%)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░

⚠️ Top 10 Problemas
────────────────────────────────────────────────────────────
1. UNVERIFIED (327 ocorrências)
2. METADATA_MISSING (156 ocorrências)
3. SUSPICIOUS_SIZE (89 ocorrências)
4. WEAK_DUMP (45 ocorrências)
5. INVALID_CHECKSUM (23 ocorrências)
...

🔴 ROMs Corrompidas
────────────────────────────────────────────────────────────
1. roms/gba/broken_game.gba
   └─ INVALID_HEADER: Header GBA inválido

2. roms/ps2/corrupt_dump.iso
   └─ TRUNCATED_FILE: Arquivo incompleto (3.2 GB de 4.7 GB)

...
═══════════════════════════════════════════════════════════
```

## API Programática

### Análise Individual

```python
from pathlib import Path
from emumanager.library import LibraryDB, LibraryEntry
from emumanager.quality import QualityController

# Inicializar
db = LibraryDB()
controller = QualityController(db)

# Criar entrada
entry = LibraryEntry(
    path="/roms/game.gba",
    system="gba",
    size=8*1024*1024,
    mtime=1234567890.0,
    status="VERIFIED"
)

# Analisar qualidade
quality = controller.analyze_rom(entry)

print(f"Nível: {quality.quality_level.value}")
print(f"Score: {quality.score}/100")
print(f"Jogável: {quality.is_playable}")
print(f"Ícone: {quality.icon}")

# Verificar problemas
for issue in quality.issues:
    print(f"- [{issue.severity}] {issue.description}")
    if issue.location:
        print(f"  @ {issue.location}")
    if issue.recommendation:
        print(f"  → {issue.recommendation}")
```

### Análise de Biblioteca

```python
# Analisar todos os GBAs
results = controller.analyze_library(system="gba")

for path, quality in results.items():
    if not quality.is_playable:
        print(f"❌ {path}: {quality.get_summary()}")
```

### Estatísticas

```python
# Obter estatísticas
stats = controller.get_quality_statistics(system="ps2")

print(f"Total: {stats['total']}")
print(f"Score médio: {stats['average_score']:.1f}")
print(f"Jogáveis: {stats['playable']} ({stats['playable_percentage']:.1f}%)")

# Distribuição por nível
for level, count in stats['by_level'].items():
    print(f"{level}: {count}")

# Issues mais comuns
for issue_type, count in stats['top_issues']:
    print(f"{issue_type}: {count}")
```

## Criando Health Checkers Customizados

Para adicionar suporte a novos sistemas:

```python
from pathlib import Path
from emumanager.quality.checkers import BaseHealthChecker
from emumanager.quality import RomQuality, QualityIssue, IssueType

class N64HealthChecker(BaseHealthChecker):
    """Health checker para Nintendo 64."""
    
    def check(self, rom_path: Path, quality: RomQuality) -> None:
        """Valida ROM N64."""
        try:
            with rom_path.open('rb') as f:
                # Ler header (64 bytes)
                header = f.read(64)
                
                if len(header) < 64:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.TRUNCATED_FILE,
                        severity='critical',
                        description="ROM N64 truncada",
                        location="0x00",
                    ))
                    quality.score = 0
                    return
                
                # Verificar magic number
                if header[0:4] not in [b'\x80\x37\x12\x40', b'\x37\x80\x40\x12']:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.INVALID_HEADER,
                        severity='critical',
                        description="Magic number inválido",
                    ))
                    quality.score -= 40
                else:
                    quality.checks_performed.append("magic_number")
                    quality.score += 30
                
                # Verificar game name
                name = header[32:52].decode('ascii', errors='ignore').strip('\x00')
                if name:
                    quality.checks_performed.append("game_name")
                else:
                    quality.issues.append(QualityIssue(
                        issue_type=IssueType.METADATA_MISSING,
                        severity='low',
                        description="Nome do jogo ausente",
                    ))
                    quality.score -= 5
                
        except Exception as e:
            quality.issues.append(QualityIssue(
                issue_type=IssueType.TRUNCATED_FILE,
                severity='critical',
                description=f"Erro ao ler ROM: {e}",
            ))
            quality.score = 0
```

Registrar no factory:

```python
# Em checkers.py
def get_checker_for_system(system: str) -> Optional[BaseHealthChecker]:
    """Factory para obter checker do sistema."""
    checkers = {
        'ps2': PS2HealthChecker,
        'psx': PSXHealthChecker,
        'gba': GBAHealthChecker,
        'switch': SwitchHealthChecker,
        'gamecube': GameCubeHealthChecker,
        'n64': N64HealthChecker,  # Novo
    }
    
    checker_class = checkers.get(system.lower())
    return checker_class() if checker_class else None
```

## Integração com DAT Verification

O sistema Quality Control integra-se com o sistema de verificação DAT existente:

- ROMs com `status="VERIFIED"` recebem **+20 score**
- Nível PERFECT requer verificação DAT + score alto
- Problemas DAT são reportados como issues

## Performance

O sistema é otimizado para grandes coleções:

- **Verificações incrementais**: Apenas arquivos modificados
- **Análise assíncrona**: Não bloqueia UI
- **Cache de resultados**: Reutiliza verificações anteriores
- **Validações específicas**: Só o necessário para cada sistema

### Benchmarks

| Operação | 100 ROMs | 1000 ROMs | 10000 ROMs |
|----------|----------|-----------|------------|
| Análise básica | 2s | 15s | 2m30s |
| Com DAT | 5s | 45s | 7m |
| Inspector (1 ROM) | 50ms | 50ms | 50ms |

## Boas Práticas

1. **Execute Quality Check regularmente** para detectar corrupção precoce
2. **Verifique ROMs corrompidas** imediatamente - podem indicar problemas no disco
3. **Use verificação DAT** para garantir dumps autênticos
4. **Monitore score médio** - quedas indicam problemas sistemáticos
5. **Investigue QUESTIONABLE** - podem ser falsos positivos ou realmente problemáticos
6. **Substitua CORRUPT/DAMAGED** - não são jogáveis

## Troubleshooting

### ROM marcada como DAMAGED mas funciona

Pode ser:
- **Formato não padrão**: ROM modificada mas funcional
- **Header customizado**: Tradução/hack
- **Tamanho incomum**: Versão especial

**Solução**: Verificar manualmente, adicionar exceção se necessário

### Score baixo em ROM verificada

Possíveis causas:
- **Metadata ausente**: Normal em alguns dumps
- **Tamanho suspeito**: Diferentes versões têm tamanhos variados
- **Checksum interno**: Pode estar errado em dumps antigos

**Solução**: Se jogável e verificada com DAT, considerar confiável

### Health checker não encontrado

Sistema não tem checker específico ainda.

**Solução**: Contribuir implementando novo checker (veja seção acima)

## Próximas Melhorias

- [ ] Health checkers para mais sistemas (N64, SNES, NES, etc)
- [ ] Detecção de bad dumps conhecidos
- [ ] Integração com No-Intro/Redump databases
- [ ] Reparo automático de headers simples
- [ ] Histórico de qualidade por ROM
- [ ] Alertas de degradação de dados

## Referências

- [No-Intro DAT-o-MATIC](https://datomatic.no-intro.org/)
- [Redump](http://redump.org/)
- [GBA Header Format](http://problemkaputt.de/gbatek.htm#gbacartridgeheader)
- [ISO9660 Specification](https://wiki.osdev.org/ISO_9660)
- [PSX Disc Format](https://problemkaputt.de/psx-spx.htm#cdromfileformats)
