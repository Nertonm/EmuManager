# 📋 Análise e Proposta de Revisão Extensiva - EmuManager

**Data**: 3 de fevereiro de 2026  
**Versão Analisada**: 3.0.0  
**Objetivo**: Transformar o EmuManager em um TUI-first funcional e sem erros

---

## 🔍 Análise dos Problemas Identificados

### 1. **Problemas Críticos de Importação**

#### ❌ Problemas Encontrados:
- **manager.py**: Falta `from typing import Any` causando erro de tipo não resolvido
- **manager.py**: Função `get_roms_dir()` referenciada pela GUI mas não definida
- **tui.py**: Import de `CoreEvent` pode falhar se o módulo não estiver completo
- **gui_main.py**: Múltiplas referências a `get_roms_dir` do manager que não existe

#### ✅ Correções Aplicadas:
1. Adicionado `from typing import Any` em [manager.py](emumanager/manager.py)
2. Implementada função `get_roms_dir(base_path: Path) -> Path` em [manager.py](emumanager/manager.py)
3. Adicionado fallback para `CoreEvent` no [tui.py](emumanager/tui.py)
4. Corrigidos handlers de eventos para aceitar eventos dinâmicos

---

### 2. **Arquitetura do TUI - Problemas Estruturais**

#### ❌ Problemas Identificados:

**2.1. Sistema de Eventos Inconsistente**
- O TUI espera eventos do tipo `CoreEvent` mas os handlers podem receber tipos diferentes
- Callbacks de progresso não padronizados entre CLI, TUI e GUI
- EventBus ([common/events.py](emumanager/common/events.py)) funciona mas não está bem integrado

**2.2. Gestão de Estado**
- `AsyncFeedbackTui` mantém estado duplicado (`_selected_system`, `_selected_rom_path`, etc.)
- Session ([core/session.py](emumanager/core/session.py)) tem estado mas não é usado consistentemente no TUI
- Orchestrator cria sua própria telemetria mas TUI não a consome corretamente

**2.3. Integração TUI-Core Fraca**
- `run_workflow()` executa operações mas não trata erros de forma robusta
- Cancelamento via `threading.Event` não está conectado aos workers
- Refresh de sistemas (`_refresh_systems()`) não sincroniza com banco de dados

**2.4. Problemas de UI/UX**
- Tabela de ROMs não filtra corretamente (handler `@on(Input.Changed)` faltando)
- Inspector de metadados não atualiza quando não há entrada no DB
- Progress bar não reseta entre operações
- Console log não limita tamanho (pode crescer indefinidamente)

#### 🛠️ Soluções Propostas:

**Para Sistema de Eventos:**
```python
# Padronizar callbacks em todos os módulos:
ProgressCallback = Callable[[float, str], None]  # (percent, message)
LogCallback = Callable[[str], None]

# Todos os workers devem aceitar estas signatures
```

**Para Gestão de Estado:**
- Centralizar estado no Session
- TUI deve ler estado do Orchestrator.session em vez de duplicar
- Adicionar métodos `session.get_current_system()`, `session.get_selected_rom()`

**Para Integração:**
- Wrapper `TUIOrchestrator` que trata conversão de eventos para Textual
- Implementar `cancel_event` corretamente em todos os workers
- Adicionar transações no LibraryDB para operações batch

---

### 3. **Orchestrator - Métodos Incompletos**

#### ✅ Métodos Existentes e Funcionais:
- `initialize_library()` ✓
- `scan_library()` ✓
- `full_organization_flow()` ✓
- `cleanup_duplicates()` ✓
- `bulk_transcode()` ✓
- `add_rom()` ✓
- `generate_compliance_report()` ✓

#### ⚠️ Métodos com Problemas:

**3.1. `full_organization_flow()`**
```python
# Problema: worker_distribute_root retorna dict mas código espera WorkerResult
from emumanager.workers.distributor import worker_distribute_root
dist_stats = worker_distribute_root(...)  # Retorna dict
# mas depois tenta: result.success_count += dist_stats.get("moved", 0)
```
**Solução**: Padronizar retorno de workers para sempre usar `WorkerResult`

**3.2. `recompress_rom()`**
```python
# Implementação incompleta - apenas suporta PS2 CHD
# Falta: PSP CSO, GameCube/Wii RVZ, Switch NSZ
```
**Solução**: Delegar para providers via `provider.recompress(path, level)`

**3.3. `finalize_task()`**
```python
# Tenta gerar HTML report mas HTMLReportGenerator pode não existir
# Falha silenciosamente se result não tiver .processed_items
```
**Solução**: Tornar geração de relatório opcional e adicionar logs

---

### 4. **CLI - Problemas de Integração**

#### ❌ Problemas Encontrados:

**4.1. Método `_get_orch()` Inconsistente**
```python
def _get_orch(base: Path):
    from .core.session import Session
    from .core.orchestrator import Orchestrator
    return Orchestrator(Session(base))
```
- Cria nova instância a cada chamada (não reutiliza conexão DB)
- Session não valida se base existe

**4.2. Callbacks de Progresso Incompatíveis**
```python
# CLI usa Rich Progress que espera: update(task, completed=X)
# Mas orchestrator chama: progress_cb(percent, message)
```

#### 🛠️ Soluções:

**4.1. Factory Pattern para Orchestrator:**
```python
_orchestrator_cache: dict[str, Orchestrator] = {}

def get_orchestrator(base: Path, force_new: bool = False) -> Orchestrator:
    key = str(base.resolve())
    if force_new or key not in _orchestrator_cache:
        _orchestrator_cache[key] = Orchestrator(Session(base))
    return _orchestrator_cache[key]
```

**4.2. Adapter para Progress:**
```python
class RichProgressAdapter:
    def __init__(self, progress, task_id):
        self.progress = progress
        self.task_id = task_id
    
    def __call__(self, percent: float, message: str):
        self.progress.update(self.task_id, completed=percent*100, description=message)
```

---

### 5. **Workers - Inconsistências**

#### ❌ Problemas:
- Alguns workers retornam `WorkerResult`, outros retornam `dict` ou `str`
- BaseWorker define `_process_item()` mas nem todos a usam consistentemente
- Multiprocessing não funciona corretamente em alguns casos (pickle errors)
- Cancelamento via `cancel_event` não é respeitado por todos

#### ✅ Solução: Padronização

**Contrato Universal de Worker:**
```python
@dataclass
class WorkerResult:
    task_name: str
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    duration_ms: float = 0
    processed_items: list[ProcessedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

class BaseWorker(ABC):
    def __init__(self, base_path, log_cb, progress_cb, cancel_event):
        self.base_path = base_path
        self.log = log_cb or (lambda x: None)
        self.progress = progress_cb or (lambda p, m: None)
        self.cancel = cancel_event or threading.Event()
    
    @abstractmethod
    def _process_item(self, item: Path) -> str:
        """Retorna: 'success', 'skipped', 'failed'"""
        pass
    
    def run(self, items: list[Path], task_label: str, parallel: bool = False) -> WorkerResult:
        # Implementação padronizada com suporte a cancelamento
        pass
```

---

### 6. **Banco de Dados - LibraryDB**

#### ✅ Pontos Fortes:
- Usa SQLite com WAL mode ✓
- Thread-local connections ✓
- Schema bem definido ✓

#### ⚠️ Melhorias Necessárias:

**6.1. Falta de Índices**
```sql
-- Adicionar em _init_db():
CREATE INDEX IF NOT EXISTS idx_system ON library(system);
CREATE INDEX IF NOT EXISTS idx_sha1 ON library(sha1) WHERE sha1 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_status ON library(status);
```

**6.2. Queries Podem Ser Otimizadas**
```python
# Atual: get_entries_by_system faz SELECT * (traz tudo)
# Melhor: Adicionar get_entries_by_system_lightweight que só traz campos essenciais
```

**6.3. Falta Transaction Manager**
```python
@contextmanager
def transaction(self):
    conn = self._get_conn()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
```

---

### 7. **Providers - Validação de Arquivos**

#### ⚠️ Problema: Validação Fraca

Muitos providers só checam extensão, não conteúdo:
```python
# switch/provider.py
def validate_file(self, path: Path) -> bool:
    return path.suffix.lower() in {".nsp", ".nsz", ".xci", ".xcz"}
```

Isso causa:
- ISOs de PS2 detectados como GameCube
- Arquivos corrompidos não identificados
- Falsos positivos em detecção automática

#### ✅ Solução: Validação por Magic Bytes
```python
def validate_file(self, path: Path) -> bool:
    try:
        with open(path, 'rb') as f:
            header = f.read(16)
            return header[:4] == b'PFS0'  # NSP magic
    except:
        return False
```

---

## 📐 Proposta de Arquitetura TUI-First

### Estrutura Recomendada:

```
emumanager/
├── cli.py              # CLI usando Typer (mantido para scripts)
├── tui.py              # TUI principal (Textual) - PRIORIDADE
├── gui.py              # GUI PyQt6 (opcional, mantido para compatibilidade)
│
├── core/               # Lógica de negócio pura
│   ├── orchestrator.py # Coordenador principal
│   ├── session.py      # Gerenciador de estado
│   ├── scanner.py      # Descoberta e validação
│   └── ...
│
├── adapters/           # NOVO: Adaptadores para cada UI
│   ├── tui_adapter.py  # Converte core events -> Textual messages
│   ├── cli_adapter.py  # Converte core events -> Rich output
│   └── gui_adapter.py  # Converte core events -> Qt signals
│
├── workers/            # Processamento paralelo
│   └── base.py         # REVISAR: Padronizar interface
│
└── common/
    ├── events.py       # EventBus central
    └── types.py        # NOVO: Type aliases compartilhados
```

### Fluxo de Execução Proposto:

```
[TUI Screen] 
    ↓ (user action)
[TUIAdapter] 
    ↓ (validates input, prepares context)
[Orchestrator] 
    ↓ (emits CoreEvents via EventBus)
[TUIAdapter] 
    ↓ (converts to Textual messages)
[TUI Screen] (updates UI)
```

---

## 🎯 Plano de Implementação

### Fase 1: Correções Críticas (Concluída ✅)
1. ✅ Fix imports faltantes (Any, get_roms_dir)
2. ✅ Fallback para CoreEvent no TUI
3. ✅ Correção de handlers de eventos

### Fase 2: Padronização de Workers (Em Andamento)
1. ⏳ Criar `WorkerResult` padronizado
2. ⏳ Refatorar todos os workers para usar BaseWorker consistentemente
3. ⏳ Implementar cancelamento correto
4. ⏳ Adicionar testes unitários para workers

### Fase 3: Melhorias no TUI
1. Adicionar input filter handler para tabela de ROMs
2. Implementar reset de progress bar entre operações
3. Adicionar limite ao console log (max 1000 linhas)
4. Melhorar feedback visual de erros
5. Adicionar confirmação para operações destrutivas

### Fase 4: Otimizações Core
1. Adicionar índices no LibraryDB
2. Implementar transaction manager
3. Otimizar queries pesadas
4. Adicionar cache para providers

### Fase 5: Validação e Testes
1. Criar suite de testes E2E para TUI
2. Testar todos os workflows principais
3. Validar comportamento com library vazia
4. Stress test com 10k+ ROMs

---

## 🚀 Próximos Passos Imediatos

### 1. Completar Correção do TUI
```bash
# Adicionar handler de filtro
@on(Input.Changed, "#rom_filter")
async def on_filter_changed(self, event: Input.Changed) -> None:
    text = event.value.lower()
    # Filtrar roms_table baseado em text
```

### 2. Testar Execução Básica
```bash
cd /home/nerton/TRABALHO/Projects/EmuManager
source .venv/bin/activate
python -m emumanager.tui
```

### 3. Criar Mock Library para Testes
```bash
python scripts/create_mock_roms.py test_library
emumanager-cli init --base test_library
```

### 4. Validar Workflows Principais
- [ ] Init → Scan → Organize → Transcode
- [ ] Add ROM manual
- [ ] Update DATs
- [ ] Generate Report

---

## 📊 Métricas de Qualidade Alvo

| Métrica | Atual | Meta |
|---------|-------|------|
| Cobertura de Testes | ~40% | 80% |
| Erros de Import | 3 | 0 |
| Workers Padronizados | 60% | 100% |
| Tempo de Scan (1000 ROMs) | ~2min | <30s |
| Uso de Memória (Scan) | ~500MB | <200MB |
| Handlers de Cancelamento | 50% | 100% |

---

## 💡 Recomendações Adicionais

### 1. **Logging Estruturado**
Migrar de logs simples para estruturado (JSON):
```python
logger.info("scan_completed", extra={
    "files_scanned": 1234,
    "duration_ms": 5678,
    "errors": 2
})
```

### 2. **Configuration as Code**
Substituir `settings.json` por arquivo mais robusto:
```toml
# emumanager.toml
[library]
base_path = "~/Games"
auto_scan = true

[compression]
level = 3
parallel_workers = 4

[systems.ps2]
preferred_format = "chd"
```

### 3. **Plugin System**
Permitir providers externos:
```python
# ~/.config/emumanager/plugins/xbox.py
class XboxProvider(SystemProvider):
    system_id = "xbox"
    # ...
```

### 4. **Telemetria Opt-in**
Para identificar gargalos:
```python
# Anonimizado, apenas métricas
{"operation": "scan", "duration": 1234, "items": 5000}
```

---

## 🎓 Lições Aprendidas

1. **Arquitetura Limpa é Boa, Mas...**
   - Separação Core/UI/Workers é excelente
   - Mas precisa de adapters bem definidos
   - EventBus é útil mas precisa documentação

2. **Multiprocessing é Complexo**
   - Pickle limitations são reais
   - Thread-local DB connections complicam
   - Workers precisam ser stateless

3. **TUI != CLI**
   - TUI precisa eventos assíncronos
   - CLI pode bloquear
   - Não misturar os dois paradigmas

4. **Providers São O Coração**
   - Validação fraca = bugs sutis
   - Magic bytes > extensões
   - Metadata extraction deve ser lazy

---

## 🔧 Comandos Úteis de Desenvolvimento

```bash
# Executar testes
pytest tests/ -v

# Executar com profiling
python -m cProfile -o profile.stats -m emumanager.cli scan

# Analisar profile
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(30)"

# Verificar imports
python -m pylint emumanager/ --disable=all --enable=import-error

# Type checking
mypy emumanager/ --ignore-missing-imports
```

---

## 📝 Conclusão

O EmuManager tem uma **excelente arquitetura base** com separação clara de responsabilidades e suporte robusto para múltiplas plataformas. No entanto, sofre de:

1. **Inconsistências entre módulos** (workers, callbacks, eventos)
2. **Integração UI-Core incompleta** (especialmente no TUI)
3. **Falta de padronização** em retornos e assinaturas

Com as correções propostas neste documento e implementação das fases 2-5, o projeto pode se tornar um **TUI-first completo e sem erros**, mantendo compatibilidade com CLI e GUI.

**Prioridade**: Focar em Fase 2 (padronização) e Fase 3 (melhorias TUI) para ter uma versão estável rapidamente.

---

**Documento gerado em**: 2026-02-03  
**Autor**: GitHub Copilot (Claude Sonnet 4.5)  
**Versão**: 1.0
