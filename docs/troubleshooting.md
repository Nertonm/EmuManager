# Solução de Problemas (Troubleshooting)

## Problemas Comuns

### 1. Ferramentas não encontradas
**Sintoma**: O log mostra erros como `FileNotFoundError: [Errno 2] No such file or directory: 'hactool'` ou avisos de que ferramentas externas estão faltando.

**Solução**:
- Certifique-se de que as ferramentas externas estão instaladas e no seu `PATH`.
- No Linux, execute `./scripts/bootstrap.sh` para instalar dependências.
- Verifique se você consegue executar o comando (ex: `hactool --version`) no seu terminal.

### 2. Jogos não são detectados
**Sintoma**: Ao adicionar uma pasta ou arquivo, ele não aparece na lista ou vai para "Unknown".

**Solução**:
- Verifique se a extensão do arquivo é suportada (veja [Sistemas Suportados](supported_systems.md)).
- Para sistemas baseados em CD/DVD (PS1, PS2), certifique-se de que os arquivos não estão corrompidos.
- Tente renomear o arquivo para incluir o nome do sistema (ex: `God of War (PS2).iso`) para ajudar na detecção heurística.

### 3. Erros de Permissão
**Sintoma**: `PermissionError` ao tentar mover ou renomear arquivos.

**Solução**:
- Verifique se o usuário que está executando o EmuManager tem permissão de escrita na pasta da biblioteca.
- Evite executar o EmuManager como `root` se a biblioteca pertencer a um usuário comum, ou vice-versa.

### 4. Falha na Verificação de DAT
**Sintoma**: Jogos aparecem como "No Match" ou "Bad Dump" mesmo sendo cópias legítimas.

**Solução**:
- Certifique-se de que está usando o DAT correto (No-Intro para cartuchos, Redump para discos).
- Verifique se o arquivo não contém cabeçalhos (headers) que alteram o hash (comum em ROMs de NES/Famicom).
- Se o arquivo estiver comprimido (zip/7z), o EmuManager tentará verificar o conteúdo, mas arquivos sólidos podem causar problemas de performance ou leitura.

### 5. Interface Gráfica não abre
**Sintoma**: Erro `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`.

**Solução**:
- Faltam dependências do Qt no seu sistema Linux.
- Instale `libxcb-cursor0` ou pacote similar (ex: `sudo apt install libxcb-cursor0` no Ubuntu 24.04+).

## Logs

O EmuManager gera logs detalhados que podem ajudar a diagnosticar problemas.

- **Na GUI**: Pressione `Ctrl+L` ou vá em `View -> Toggle Log` para ver o log em tempo real.
- **Arquivos de Log**: Os logs são salvos na pasta `logs/` dentro do diretório do projeto. Verifique o arquivo mais recente para detalhes de erros (stack traces).

## Reportando Bugs

Se você encontrar um bug não listado aqui, por favor abra uma issue no GitHub com:
1. Descrição do problema.
2. Passos para reproduzir.
3. Trecho relevante do log (remova informações sensíveis se houver).
4. Sistema Operacional e versão do Python.
