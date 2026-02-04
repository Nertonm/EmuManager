# Exemplos de Código EmuManager

Esta pasta contém exemplos práticos de como usar e estender o EmuManager.

## Disponíveis

### [provider_migration_example.py](provider_migration_example.py)
Exemplo completo de como um provider deve ser implementado usando:
- Sistema de exceções customizadas
- Framework de validação
- Logging estruturado
- Error handling profissional

Este exemplo foi usado como referência durante a migração dos providers PS2, Switch e PSX.

## Como Usar

Os exemplos podem ser executados diretamente:

```bash
python docs/examples/provider_migration_example.py
```

Ou usados como referência para implementar novos providers ou features.

## Estrutura Recomendada

Todo provider deve seguir o padrão:

1. **Imports organizados** - stdlib, third-party, local
2. **Validação de entrada** - usar `validation.py`
3. **Exceções específicas** - usar `exceptions.py`
4. **Logging estruturado** - contexto rico
5. **Documentação completa** - docstrings com Args/Returns/Raises
6. **Type hints** - sempre que possível

---
*Para mais detalhes, veja a [documentação de migração](../migration-history/)*
