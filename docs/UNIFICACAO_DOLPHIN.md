# Unificação GameCube + Wii → Dolphin

## 📋 Resumo

GameCube e Wii foram **unificados em um único sistema chamado "dolphin"**. Todos os jogos de ambas as plataformas agora residem na mesma pasta `roms/dolphin/`.

---

## 🎯 Motivação

1. **Emulador Comum**: Ambos usam o Dolphin Emulator
2. **Retrocompatibilidade**: Wii é retrocompatível com GameCube
3. **Formato Comum**: Ambos usam RVZ como formato ideal
4. **Simplicidade**: Reduz duplicação e facilita organização

---

## ✨ Mudanças Implementadas

### **1. Providers Unificados** ([gamecube/provider.py](emumanager/gamecube/provider.py), [wii/provider.py](emumanager/wii/provider.py))

#### **Antes:**
```python
# GameCube
def system_id(self) -> str: return "gamecube"
def display_name(self) -> str: return "GameCube"

# Wii  
def system_id(self) -> str: return "wii"
def display_name(self) -> str: return "Wii"
```

#### **Depois:**
```python
# Ambos retornam:
def system_id(self) -> str: return "dolphin"
def display_name(self) -> str: return "Dolphin (GC/Wii)"
```

**Benefícios:**
- ✅ Ambos compartilham a pasta `roms/dolphin/`
- ✅ Validação de magic bytes mantida separada (GameCube vs Wii)
- ✅ Metadata adiciona campo `platform` ("GameCube" ou "Wii")

### **2. Extensões Suportadas**

Ambos os providers agora aceitam todas as extensões:

```python
# GameCubeProvider
{".iso", ".gcm", ".rvz", ".wbfs"}

# WiiProvider  
{".iso", ".wbfs", ".rvz", ".gcm"}
```

**Detecção Automática:**
- `.gcm` → Sempre GameCube
- `.wbfs` → Sempre Wii
- `.iso` / `.rvz` → Validado por magic bytes

### **3. Registry Atualizado** ([common/registry.py](emumanager/common/registry.py))

```python
# Prioridade atualizada:
priority_order = ['ps2', 'dolphin', 'psx', 'psp', 'ps3', 'switch', '3ds']
```

### **4. Orchestrator** ([core/orchestrator.py](emumanager/core/orchestrator.py))

```python
# Worker map unificado:
worker_map = {
    "ps2": PS2Worker,
    "dolphin": DolphinWorker,  # Unificado
    "psp": PSPWorker
}
```

---

## 📂 Estrutura de Pastas

### **Antes:**
```
roms/
├── gamecube/
│   ├── Mario Kart Double Dash [GMKE01].iso
│   └── ...
└── wii/
    ├── Mario Kart Wii [RMCE01].wbfs
    └── ...
```

### **Depois:**
```
roms/
└── dolphin/
    ├── Mario Kart Double Dash [GMKE01].rvz  # GameCube
    ├── Mario Kart Wii [RMCE01].rvz         # Wii
    └── ...
```

---

## 🔄 Migração Automática

### **Opção 1: Script de Migração**

```bash
# Dry-run (simular sem fazer alterações)
python scripts/migrate_dolphin.py --dry-run

# Executar migração real
python scripts/migrate_dolphin.py
```

**O script:**
1. ✅ Move todos os arquivos de `gamecube/` e `wii/` para `dolphin/`
2. ✅ Atualiza todas as entradas no `library.db`
3. ✅ Corrige os caminhos dos arquivos no banco
4. ✅ Remove pastas antigas se estiverem vazias
5. ✅ Suporta dry-run para preview seguro

### **Opção 2: Migração Manual**

```bash
# 1. Criar pasta dolphin
mkdir -p roms/dolphin

# 2. Mover arquivos
mv roms/gamecube/* roms/dolphin/ 2>/dev/null || true
mv roms/wii/* roms/dolphin/ 2>/dev/null || true

# 3. Remover pastas antigas
rmdir roms/gamecube roms/wii 2>/dev/null || true

# 4. Atualizar biblioteca
emumanager scan
```

---

## 🎮 Uso no TUI

### **Lista de Sistemas:**
```
🎮 SISTEMAS
├── 🎮 dolphin  ← Unificado
├── 🎮 ps2
├── 🎮 psx
└── ...
```

### **Inspector de Metadata:**
```
TÍTULO: Mario Kart Double Dash
SERIAL: GMKE01
SISTEMA: dolphin
PLATFORM: GameCube  ← Distingue GC vs Wii
```

---

## 🔍 Validação de Arquivos

Ambos os providers mantêm validação específica:

### **GameCube Magic Bytes:**
```python
# Game ID ASCII nos primeiros 6 bytes
# Exemplo: "GMKE01" para Mario Kart
game_id = header[:6]
if all(32 <= b < 127 for b in game_id):
    return True

# RVZ Magic
if header[:3] == b'RVZ':
    return True
```

### **Wii Magic Bytes:**
```python
# Game ID ASCII (similar ao GameCube)
# Exemplo: "RMCE01" para Mario Kart Wii
game_id = header[:6]

# WBFS Magic (exclusivo Wii)
if header[:4] == b'WBFS':
    return True

# RVZ Magic
if header[:3] == b'RVZ':
    return True
```

---

## 📊 Workflows Atualizados

### **1. Auditoria Global (`emumanager scan`)**
```bash
Scanning dolphin/
  ✅ Mario Kart Double Dash.rvz → GameCube
  ✅ Mario Kart Wii.wbfs → Wii
  ✅ Super Smash Bros Brawl.iso → Wii (magic bytes)
```

### **2. Organização (`organize`)**
```bash
dolphin/
├── GameCube/
│   └── Mario Kart Double Dash [GMKE01].rvz
└── Wii/
    └── Mario Kart Wii [RMCE01].rvz
```
*Opcional: Organizar por subpastas de plataforma*

### **3. Transcoding (`transcode`)**
```bash
Dolphin Worker:
  ✅ Converting Mario Kart.iso → Mario Kart.rvz (GC)
  ✅ Converting Zelda.wbfs → Zelda.rvz (Wii)
```

---

## 🛠️ Desenvolvimento

### **Adicionar Novo Provider Dolphin-Based:**

```python
class MyDolphinProvider(SystemProvider):
    @property
    def system_id(self) -> str:
        return "dolphin"  # Unificado
    
    def extract_metadata(self, path: Path) -> dict[str, Any]:
        return {
            "serial": ...,
            "title": ...,
            "system": "dolphin",
            "platform": "GameCube"  # ou "Wii"
        }
```

### **Distinção GameCube vs Wii:**

```python
# No metadata:
if entry.extra_metadata.get("platform") == "GameCube":
    # Lógica específica GameCube
elif entry.extra_metadata.get("platform") == "Wii":
    # Lógica específica Wii
```

---

## ⚠️ Considerações

### **Compatibilidade:**
- ✅ Biblioteca existente: Use script de migração
- ✅ Novos scans: Detectam automaticamente
- ✅ DATs: No-Intro GameCube + Wii funcionam normalmente

### **Reversão (se necessário):**
```sql
-- Reverter no banco de dados
UPDATE library 
SET system = 'gamecube' 
WHERE system = 'dolphin' AND extra_json LIKE '%GameCube%';

UPDATE library 
SET system = 'wii' 
WHERE system = 'dolphin' AND extra_json LIKE '%Wii%';
```

### **Organização por Subpastas:**
```python
# Em get_ideal_filename():
platform = metadata.get("platform", "")
if platform in ["GameCube", "Wii"]:
    return f"{platform}/{title} [{serial}]{ext}"
```

---

## 📈 Benefícios

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Pastas** | 2 separadas | 1 unificada |
| **Workers** | 2 referências | 1 referência |
| **Conversão** | .iso→.rvz (2x) | .iso/.wbfs→.rvz |
| **Organização** | Duplicada | Simplificada |
| **Validação** | Separada ✅ | Mantida ✅ |

---

## ✅ Checklist de Migração

- [x] Providers unificados com system_id "dolphin"
- [x] Validação por magic bytes mantida
- [x] Registry atualizado com prioridade
- [x] Orchestrator worker_map atualizado
- [x] Script de migração automática
- [x] Documentação completa
- [ ] Executar migração: `python scripts/migrate_dolphin.py`
- [ ] Rescan biblioteca: `emumanager scan`

---

## 🚀 Próximos Passos

1. **Executar Migração:**
   ```bash
   python scripts/migrate_dolphin.py --dry-run  # Preview
   python scripts/migrate_dolphin.py            # Executar
   ```

2. **Validar:**
   ```bash
   emumanager scan
   ```

3. **Verificar TUI:**
   ```bash
   emumanager
   ```

---

**Data:** 3 de fevereiro de 2026  
**Versão:** 3.0.2  
**Status:** ✅ Implementado e pronto para uso
