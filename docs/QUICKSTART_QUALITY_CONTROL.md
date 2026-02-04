# Quality Control - Guia Rápido de Início

## 🚀 Começando em 5 Minutos

### 1. Verificar Instalação

```bash
python -c "from emumanager.quality import QualityController; print('✅ OK')"
```

### 2. Ver Qualidade no TUI

```bash
emumanager tui
```

A coluna "Qualidade" mostra:
- ✓✓ = Perfeita
- ✓ = Boa
- ⚠ = Questionável
- ✗ = Danificada
- ✗✗ = Corrompida

### 3. Análise Completa

Menu TUI → `🏥 Quality Check`

Ou via CLI:
```bash
emumanager quality-check
```

### 4. Uso Programático

```python
from emumanager.quality import QualityController
from emumanager.library import LibraryDB

db = LibraryDB()
qc = QualityController(db)

# Estatísticas
stats = qc.get_quality_statistics()
print(f"Score médio: {stats['average_score']:.1f}/100")
print(f"Jogáveis: {stats['playable_percentage']:.1f}%")
```

## 📊 Interpretando Resultados

### Scores

| Score | Significado | Ação |
|-------|-------------|------|
| 95-100 | Perfeita | ✅ Manter |
| 80-94 | Boa | ✅ OK |
| 60-79 | Questionável | ⚠️ Investigar |
| 40-59 | Danificada | ❌ Substituir |
| 0-39 | Corrompida | ❌ Descartar |

### Ícones

- **✓✓** Verde → ROM perfeita, DAT verificado
- **✓** Ciano → ROM boa, sem problemas
- **⚠** Amarelo → Pequenos problemas, jogável
- **✗** Vermelho → Problemas graves
- **✗✗** Vermelho → Corrompida, não funciona

## 🔍 Checagens por Sistema

### GBA
✅ Entry point válido
✅ Nintendo logo presente
✅ Header checksum correto

### PS2
✅ ISO9660 válido
✅ SYSTEM.CNF presente
✅ Tamanho adequado

### PSX
✅ CUE/BIN consistente
✅ Setores 2352 bytes
✅ Sony license presente

### Switch
✅ NSP: PFS0 magic
✅ XCI: HEAD magic
✅ Estrutura válida

### GameCube
✅ Disc ID válido
✅ boot.bin presente
✅ Tamanho ~1.4 GB

## ⚡ Comandos Rápidos

```python
# Analisar sistema específico
results = qc.analyze_library(system="gba")

# Filtrar problemas
damaged = [r for r in results.values() if not r.is_playable]

# ROMs perfeitas
perfect = [r for r in results.values() if r.score >= 95]

# Não verificadas
unverified = [r for r in results.values() if not r.dat_verified]
```

## 🐛 Troubleshooting

### ROM marcada como danificada mas funciona
→ Pode ser ROM modificada (hack/tradução)
→ Verificar manualmente se é falso positivo

### Score baixo em ROM verificada
→ Metadata ausente é comum e inofensivo
→ Se jogável + DAT OK, geralmente é confiável

### Muitas ROMs não verificadas
→ Execute verificação DAT primeiro:
```bash
emumanager verify --system gba
```

## 📚 Documentação Completa

- **Guia Completo**: `docs/quality_control.md`
- **Resumo Executivo**: `QUALITY_CONTROL_SUMMARY.md`
- **Release Notes**: `RELEASE_NOTES_QUALITY_CONTROL.md`
- **Exemplos**: `examples/quality_control_example.py`

## 💡 Dicas Rápidas

1. Execute Quality Check após adicionar ROMs novas
2. Verifique ROMs corrompidas imediatamente
3. Use DAT verification antes para melhores scores
4. Monitore score médio ao longo do tempo
5. Priorize substituir ROMs danificadas

## ❓ FAQ

**P: Quanto tempo leva a análise?**
R: ~50ms por ROM, ~15s para 1000 ROMs

**P: Preciso executar toda vez?**
R: Não, resultados são mostrados automaticamente na tabela

**P: Como adicionar novo sistema?**
R: Crie health checker baseado em `BaseHealthChecker` (veja docs)

**P: Score perfeito = ROM original?**
R: Não necessariamente, use DAT verification para confirmar

---

**Pronto!** Agora você pode usar o sistema Quality Control para manter sua coleção de ROMs em perfeito estado! 🎮✨
