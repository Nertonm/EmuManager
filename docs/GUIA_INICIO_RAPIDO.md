# 🎮 EmuManager - Guia de Início Rápido (v3.0 Revisado)

**Status**: ✅ Sistema Funcional | TUI-First | Correções Aplicadas  
**Data da Revisão**: 3 de fevereiro de 2026

---

## 📋 Documentação

- **[README Original](README.md)** - Visão geral do projeto
- **[Análise e Revisão Extensiva](ANALISE_E_REVISAO.md)** - Análise técnica completa dos problemas e soluções
- **[Sumário Executivo](SUMARIO_EXECUTIVO.md)** - Resumo das correções aplicadas
- **Este documento** - Guia prático de uso

---

## ⚡ Quick Start (5 minutos)

### 1. Instalar
```bash
cd /home/nerton/TRABALHO/Projects/EmuManager

# Criar ambiente virtual (se ainda não existe)
python -m venv .venv
source .venv/bin/activate

# Instalar projeto
pip install -e .
```

### 2. Validar Instalação
```bash
# Executar suite de testes básicos
python test_basic_functionality.py

# Esperado:
# ✅ PASS - Imports
# ✅ PASS - Manager Functions  
# ✅ PASS - LibraryDB
# ✅ PASS - Types Module
# ✅ PASS - TUI Creation
```

### 3. Criar Biblioteca de Teste
```bash
# Gerar ROMs mock para testar
python scripts/create_mock_roms.py ./test_library

# Inicializar estrutura
emumanager-cli init --base ./test_library
```

### 4. Executar TUI (Interface Principal)
```bash
emumanager  # ou: python -m emumanager.tui
```

---

## 🎨 Usando o TUI

### Interface
```
┌─────────────────────────────────────────────────────────────────┐
│ 📂 ACERVO: /path/to/library                         🕐 HH:MM:SS │
├───────────────┬─────────────────────────┬──────────────────────┤
│ 🚀 OPERAÇÕES  │   BIBLIOTECA           │   INSPECTOR          │
│               │                         │                      │
│ • Auditoria   │ [Filter: ___]          │ TÍTULO: Mario 64     │
│ • Organizar   │                         │ STATUS: Verified     │
│ • Transcode   │ ┌──────┬────┬────┐    │ SHA1: abc123...      │
│ • Update DATs │ │ ROM  │ ST │ RA │    │ PATH: /full/path     │
│               │ ├──────┼────┼────┤    │                      │
│ ⚙ CONFIG      │ │ ...  │ .. │ .. │    │                      │
│ □ Dry Run     │ └──────┴────┴────┘    │                      │
│               │                         │                      │
│ 🎮 SISTEMAS   │                         │                      │
│ • PS2         │                         │                      │
│ • GameCube    │                         │                      │
│ • ...         │                         │                      │
├───────────────┴─────────────────────────┴──────────────────────┤
│ [████████████████████░░░░░░░░] 80% - Scanning...               │
│ Console Log:                                                   │
│ > ▶ Iniciando scan...                                          │
│ > ✔ Workflow finalizado: 1234 files scanned                   │
└─────────────────────────────────────────────────────────────────┘
 q Sair │ c Cancelar │ d Dry Run │ f Filtrar │ r Refresh
```

### Atalhos de Teclado
- `q` - Sair do TUI
- `c` - Cancelar operação em andamento
- `d` - Toggle modo Dry Run (simulação)
- `f` - Focar no campo de filtro
- `r` - Refresh lista de sistemas

### Workflow Típico
1. **Selecionar Sistema** → Clique em um sistema na sidebar esquerda
2. **Ver ROMs** → Tabela central mostra todos os arquivos
3. **Filtrar** → Digite no campo de busca para filtrar
4. **Executar Operação** → Clique em uma operação na sidebar
5. **Acompanhar Progresso** → Progress bar e console log mostram status

---

## 🖥️ Usando o CLI (Automação)

### Comandos Principais

#### Init - Inicializar Biblioteca
```bash
emumanager-cli init --base ~/MeuAcervo
```

#### Scan - Auditar e Validar
```bash
# Escanear todos os sistemas
emumanager-cli scan --base ~/MeuAcervo

# Com profile de performance
emumanager-cli --profile scan --base ~/MeuAcervo
```

#### Organize - Renomear e Organizar
```bash
# Organizar tudo
emumanager-cli organize --base ~/MeuAcervo

# Dry run (simulação)
emumanager-cli organize --base ~/MeuAcervo --dry-run
```

#### Transcode - Modernizar Formatos
```bash
# Converter ISO -> CHD, RVZ, etc
emumanager-cli transcode --base ~/MeuAcervo

# Dry run
emumanager-cli transcode --base ~/MeuAcervo --dry-run
```

#### Maintain - Manutenção
```bash
# Quarentena de corrompidos + remoção de duplicados
emumanager-cli maintain --base ~/MeuAcervo
```

#### Report - Gerar Relatório
```bash
# Exportar CSV completo
emumanager-cli report --base ~/MeuAcervo --out report.csv
```

---

## 🔧 Configuração

### settings.json (Auto-gerado)
```json
{
    "base_dir": "/home/user/MeuAcervo",
    "keys_path": "/home/user/MeuAcervo/bios/switch/prod.keys",
    "compression_level": 3,
    "auto_scan_on_startup": true,
    "use_multiprocessing": true
}
```

### Estrutura de Diretórios
```
MeuAcervo/
├── bios/           # BIOS files
│   └── ps2/
│       └── SCPH-XXXXX.bin
├── dats/           # No-Intro/Redump DAT files
│   ├── ps2.dat
│   └── gamecube.dat
├── roms/           # Organized ROMs
│   ├── ps2/
│   │   ├── Game 1.chd
│   │   └── Game 2.chd
│   ├── gamecube/
│   │   └── Game.rvz
│   └── ...
├── logs/           # Operation logs
│   └── scan_2026-02-03.html
├── _QUARANTINE/    # Corrupted files
└── library.db      # SQLite database
```

---

## 🎯 Casos de Uso

### 1. Organizar Downloads Caóticos
```bash
# Você tem uma pasta ~/Downloads com ISOs misturados

# 1. Copiar para base
cp ~/Downloads/*.iso ~/MeuAcervo/roms/

# 2. Scan para identificar sistemas
emumanager-cli scan --base ~/MeuAcervo

# 3. Organizar automaticamente
emumanager-cli organize --base ~/MeuAcervo

# Resultado: Cada ISO vai para sua pasta correta e renomeado
```

### 2. Validar Coleção Contra DATs
```bash
# 1. Baixar DATs oficiais
emumanager-cli update-dats --base ~/MeuAcervo

# 2. Auditar tudo
emumanager-cli scan --base ~/MeuAcervo

# 3. Ver resultados
emumanager-cli report --base ~/MeuAcervo --out validation.csv

# CSV terá coluna "Status": VERIFIED, UNKNOWN, CORRUPT
```

### 3. Modernizar Formatos Antigos
```bash
# Converter todos ISOs para formatos modernos
emumanager-cli transcode --base ~/MeuAcervo

# PS2: ISO → CHD (50-70% economia)
# GC/Wii: ISO → RVZ (30-50% economia)
# PSP: ISO → CSO (40-60% economia)
```

### 4. Limpar Duplicados
```bash
# Remove duplicados baseado em SHA1, mantendo melhor versão
emumanager-cli maintain --base ~/MeuAcervo

# Preferência: .chd > .iso, .rvz > .iso, .nsz > .nsp
```

---

## 🐛 Troubleshooting

### Problema: "ModuleNotFoundError: No module named 'typer'"
**Solução**:
```bash
source .venv/bin/activate
pip install -e .
```

### Problema: TUI não inicia
**Solução**:
```bash
# Testar imports
python test_basic_functionality.py

# Se falhar, reinstalar
pip install --force-reinstall textual rich typer
```

### Problema: "Base path não configurado"
**Solução**:
```bash
# Configurar manualmente
python -c "
from emumanager.core.config_manager import ConfigManager
cm = ConfigManager()
cm.set('base_dir', '/home/user/MeuAcervo')
cm.save()
"
```

### Problema: Banco de dados travado
**Solução**:
```bash
# Verificar processos
lsof ~/MeuAcervo/library.db

# Forçar checkpoint WAL
sqlite3 ~/MeuAcervo/library.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

### Problema: Workers não cancelam
**Solução**: Pressione `c` múltiplas vezes. Se persistir, use `Ctrl+C` para forçar saída.

---

## 📊 Performance

### Benchmarks Típicos
| Operação | 1000 ROMs | 10000 ROMs |
|----------|-----------|------------|
| Scan | ~30s | ~5min |
| Organize | ~10s | ~1min |
| Transcode PS2 | ~2h | ~20h |
| Report | ~2s | ~10s |

### Otimizações
- **Multiprocessing**: Usa todos os CPUs disponíveis
- **SQLite WAL**: Concorrência sem locks
- **Índices DB**: Queries otimizadas
- **Streaming**: Não carrega tudo na RAM

---

## 🔬 Para Desenvolvedores

### Executar Testes
```bash
# Testes básicos
python test_basic_functionality.py

# Suite completa (quando implementada)
pytest tests/ -v

# Com coverage
pytest tests/ --cov=emumanager --cov-report=html
```

### Profile de Performance
```bash
# CLI com profile
emumanager-cli --profile scan --base ~/test_library

# Manual
python -m cProfile -o profile.stats -m emumanager.cli scan
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(30)"
```

### Type Checking
```bash
mypy emumanager/ --ignore-missing-imports
```

### Linting
```bash
ruff check emumanager/
black emumanager/ --check
```

---

## 📚 Arquitetura (Resumo)

```
┌─────────────┐
│   TUI/CLI   │ ← Interface do usuário
└──────┬──────┘
       │ chama
┌──────▼──────┐
│  Manager    │ ← Facade simplificada
└──────┬──────┘
       │ usa
┌──────▼──────┐
│ Orchestrator│ ← Coordenador principal
└──────┬──────┘
       │ delega
┌──────▼──────┬────────┬─────────┐
│  Scanner    │ Workers│ Providers│ ← Lógica específica
└─────────────┴────────┴─────────┘
       │
┌──────▼──────┐
│  LibraryDB  │ ← Persistência SQLite
└─────────────┘
```

**Princípios**:
- Core agnóstico de UI
- Workers stateless e paralelizáveis
- Providers modulares por sistema
- EventBus para comunicação assíncrona

---

## 🎓 Recursos Adicionais

- **[docs/](docs/)** - Documentação detalhada
- **[ANALISE_E_REVISAO.md](ANALISE_E_REVISAO.md)** - Análise técnica profunda
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guia de contribuição
- **[CHANGELOG.md](CHANGELOG.md)** - Histórico de mudanças

---

## ✨ Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o repositório
2. Crie branch para feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Add: nova feature'`)
4. Push para branch (`git push origin feature/nova-feature`)
5. Abra Pull Request

---

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

**Mantido por**: EmuManager Engineers  
**Última Atualização**: 2026-02-03  
**Versão**: 3.0.0 (Revisado)
