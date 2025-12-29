# Uso

## Interface Gráfica (GUI)

Para iniciar a interface gráfica:

```bash
python -m emumanager.gui
```

### Primeiros Passos

1. **Abrir Biblioteca**: Clique em "Open Library" e selecione a pasta raiz onde você deseja organizar seus jogos.
2. **Inicializar**: Se for a primeira vez, clique em "Init" para criar a estrutura de pastas padrão (`roms/`, `bios/`, etc.).
3. **Adicionar Jogos**: Clique em "Add ROM" para adicionar um jogo à sua biblioteca. O sistema tentará detectar automaticamente o console.
4. **Organizar**: Clique em "Organize" para organizar automaticamente os jogos nas pastas corretas e renomeá-los.

### Verificação de Integridade

1. **Selecionar DAT**: Vá para a aba "Verification" e selecione um arquivo `.dat` (No-Intro ou Redump).
2. **Verificar**: Clique em "Verify DAT" para verificar seus jogos contra o arquivo DAT.
3. **Resultados**: A tabela mostrará quais jogos estão verificados (verde) e quais têm problemas (vermelho).

## Linha de Comando (CLI)

O `emumanager` também pode ser usado via linha de comando.

```bash
# Ver ajuda
emumanager --help

# Inicializar biblioteca
emumanager init /caminho/para/biblioteca

# Listar sistemas
emumanager list /caminho/para/biblioteca

# Adicionar ROM
emumanager add /caminho/para/rom.iso /caminho/para/biblioteca --system ps2
```
