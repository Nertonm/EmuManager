# Guia de Desenvolvimento :: EmuManager

Bem-vindo ao desenvolvimento do EmuManager v3. O projeto segue princípios de **Clean Architecture** e **SOLID** para garantir escalabilidade e performance.

## 🏗 Arquitetura do Sistema

### 1. O Core (`emumanager/core/`)
Contém a lógica de negócio pura.
- **`Orchestrator`**: O maestro que coordena as ações. Nada na UI deve ignorar o Orquestrador.
- **`Session`**: Gere o estado atual (caminhos, contexto) de forma thread-safe.
- **`IntegrityManager`**: Gere quarentena e emite eventos de sanidade.

### 2. O Motor de Workers (`emumanager/workers/`)
Baseado em `multiprocessing`.
- Toda a tarefa pesada (Hash, Transcode) **deve** ser um worker que herda de `BaseWorker`.
- **Regra de Ouro**: Workers não devem conhecer a UI. Eles recebem um `log_cb` e um `progress_cb`.

### 3. Plugins de Sistema (`emumanager/common/`)
- Se queres adicionar suporte a uma nova consola (ex: Sega Saturn), deves implementar o protocolo `SystemProvider` em `emumanager/common/system.py` e registá-lo no `SystemRegistry`.

## 📋 Checklist: Novo Sistema (Provider)

Ao adicionar uma nova consola, garante que:
1. Criaste a pasta `emumanager/<system_id>/`.
2. Implementaste `provider.py` herdando de `SystemProvider`.
3. Adicionaste o método `get_technical_info()` com URLs da Wiki e detalhes de BIOS.
4. Definiste as extensões em `get_supported_extensions()`.
5. Registaste a classe em `emumanager/common/registry.py`.
6. Adicionaste um worker correspondente se o sistema suportar compressão CHD/RVZ.


## 🧪 Testes

Não aceitamos código sem testes. Para as novas funcionalidades do Core, utiliza `tests/test_orchestrator_core.py` como base.
Correr os testes:
```bash
.venv/bin/pytest
```

## 📜 Padrões de Código
- **Type Hinting**: Obrigatório em todas as assinaturas de funções.
- **Pathlib**: Nunca uses `os.path`. Usa `pathlib.Path`.
- **Zero Shims**: Não cries camadas de compatibilidade temporárias. Implementa nativamente no Core.