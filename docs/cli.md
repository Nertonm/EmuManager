# Guia do CLI do EmuManager

Este documento explica como usar as interfaces de linha de comando (CLI) fornecidas pelo EmuManager. O guia foca em executar os entry-points do pacote, exemplos práticos, dependências externas e dicas de solução de problemas.

> Local do repositório: suponho que você esteja na raiz do projeto e usando o virtualenv `.venv` criado pelo repositório.

## Entradas (entry-points)
O `pyproject.toml` do projeto expõe os seguintes scripts:

- `emumanager` → `emumanager.manager:main` (gerenciador CLI principal)
- `emumanager-arch` → `emumanager.architect:main` (inicialização da estrutura da biblioteca)
- `ps2-convert` → `emumanager.converters.ps2_converter:_main` (conversor CSO → CHD)
- `emumanager-gui` → `emumanager.gui:main` (abre a interface gráfica)

Se você instalou o pacote com `pip install .`, esses comandos ficam disponíveis no PATH. Caso contrário, rode-os via `python -m` usando o Python do virtualenv.

---

## Executando no virtualenv (recomendado)

Ative o ambiente virtual do repositório:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\\Scripts\\Activate.ps1
```

Depois de ativar, é possível rodar:

```bash
# Gerenciador CLI
python -m emumanager.manager --help

# GUI
python -m emumanager.gui

# Conversor PS2
python -m emumanager.converters.ps2_converter --help
```

Se você instalou o pacote globalmente, os nomes de script também funcionam diretamente:

```bash
emumanager --help
emumanager-gui
ps2-convert --help
```

---

## `emumanager` (manager) — subcomandos úteis

Sintaxe básica:

```bash
emumanager <subcommand> [args...]
# ou
python -m emumanager.manager <subcommand> [args...]
```

Subcomandos principais:

- `init [base_dir] [--dry-run]`
  - Cria a estrutura padrão (`roms/`, `bios/`, `dats/`, etc.).
  - Exemplo:
    ```bash
    emumanager init /home/usuario/EmuLibrary
    emumanager init --dry-run
    ```

- `list-systems [base_dir]`
  - Lista pastas de sistema dentro de `roms/`.

- `add-rom <src> [base_dir] [--system SYSTEM] [--move] [--dry-run]`
  - Adiciona ou move um ROM para a biblioteca (tenta detectar o sistema automaticamente se `--system` não for dado).

- `update-dats [base_dir] [--source no-intro|redump]`
  - Baixa/atualiza os DATs usados pela verificação.

- `switch -- [args passed to switch organizer]`
  - Repassa argumentos para o organizador do Switch (módulo `emumanager.switch.cli`).
  - Exemplo:
    ```bash
    emumanager switch -- --organize --compress --dir /path/to/switch/roms
    ```

Use `emumanager --help` para ver todas as opções.

---

## `emumanager-arch` / `emumanager.architect`

Usado principalmente para inicializar a estrutura da biblioteca e gerar README por sistema.

```bash
emumanager-arch --help
emumanager-arch init /home/usuario/EmuLibrary
```

`emumanager init` delega a `architect` internamente, então normalmente você usa apenas `emumanager init`.

---

## Switch Organizer (módulo `emumanager.switch.cli`)

Este CLI é rico em opções e atende operações de organização, compressão, verificação e limpeza para Switch.

Para ver ajuda completa:

```bash
python -m emumanager.switch.cli --help
# ou via manager
emumanager switch -- --help
```

Exemplos comuns:

```bash
# Organizar tudo e remover lixo
python -m emumanager.switch.cli --dir /path/to/switch --organize --clean-junk

# Comprimir (NSZ) e remover originais quando bem-sucedido
python -m emumanager.switch.cli --dir /path/to/switch --compress --rm-originals --level 3

# Simulação
python -m emumanager.switch.cli --dir /path --organize --dry-run
```

Principais flags: `--dir`, `--keys`, `--dry-run`, `--compress`, `--decompress`, `--organize`, `--clean-junk`, `--level`, `--deep-verify`.

---

## `ps2-convert` (CSO → CHD)

Converte arquivos `.cso` para `.chd` usando `maxcso` + `chdman`.

Uso:

```bash
ps2-convert --help
# ou
python -m emumanager.converters.ps2_converter --dir ./cso_files --backup-dir _LIXO_CSO --remove-original
```

Opções importantes: `--dir`, `--backup-dir`, `--dry-run`, `--remove-original`.

Requisitos: `maxcso` e `chdman` no PATH — o script aborta com mensagem clara se faltarem.

---

## Iniciar a GUI via CLI

```bash
python -m emumanager.gui
# ou
emumanager-gui
```

Para ambientes sem display (apenas para testes):

```bash
export QT_QPA_PLATFORM=offscreen
python -m emumanager.gui
```

---

## Fluxo de uso típico (exemplo rápido)

1. Inicializar biblioteca:

```bash
emumanager init /home/usuario/EmuLibrary
```

2. Atualizar DATs:

```bash
emumanager update-dats /home/usuario/EmuLibrary --source no-intro
```

3. Adicionar ROM:

```bash
emumanager add-rom ~/Downloads/Game.cso /home/usuario/EmuLibrary --move
```

4. Converter CSO → CHD (PS2):

```bash
ps2-convert --dir /home/usuario/EmuLibrary/roms/ps2 --remove-original
```

5. Organizar/Comprimir Switch:

```bash
emumanager switch -- --dir /home/usuario/EmuLibrary/roms/switch --organize --compress --clean-junk
```

---

## Dependências externas importantes

Algumas funcionalidades exigem ferramentas de terceiros (devem estar no PATH):

- `chdman` (parte do pacote MAME / mame-tools) — usado para CHD (extrair/criar). Fundamental para PS1/PS2 manipulações.
- `maxcso` — descompressão CSO → ISO (usado em `ps2-convert`).
- `nsz` — compressão para NSZ (Switch). Pode ser instalado via `pip install nsz` ou pelo pacote do sistema.
- `hactool`, `nstool` — extrair/ler metadados do Switch quando necessário.
- `clamscan`/`clamd` — opcionais para health checks.

Instalação (exemplo Debian/Ubuntu):

```bash
sudo apt update
sudo apt install mame-tools
# maxcso pode não estar nos repositórios; procure pacote ou compile/instale binário
pip install nsz
```

---

## Troubleshooting (erros comuns)

- "No serial found" em arquivos `.chd` (PS2):
  - Verifique se `chdman` está instalado e funcional.
  - Algumas versões de `chdman` não suportam saída por stdout (`-o -`) ou certas flags; o EmuManager tenta estratégias (extração parcial com `--inputbytes` ou extração completa para arquivo temporário). Caso falhe, execute manualmente:

    ```bash
    chdman extractdvd -i "God of War II.chd" -o /tmp/out.iso
    head -c 65536 /tmp/out.iso | strings | egrep -i 'SLUS|SLES|BOOT'
    ```

  - Se `chdman` imprimir mensagens de "Usage" ou "Option is missing parameter", verifique a versão e mostre o stderr para diagnóstico.

- Ferramentas não encontradas (`nsz`, `chdman`, `maxcso`): instale-as e garanta que estejam no PATH. Os CLIs exibem mensagens claras indicando o binário faltante.

- Erros de GUI em ambiente headless: use `QT_QPA_PLATFORM=offscreen` para testes automatizados; para uso interativo, execute com display.

- Logs e verbosidade: use `--verbose` nas ferramentas que suportam, ou passe `--log-file`/`--log-max-bytes` quando disponível.

---

## Comandos práticos rápidos

```bash
# Adicionar um ROM
emumanager add-rom ~/Downloads/game.iso /home/usuario/EmuLibrary

# Listar sistemas
emumanager list-systems /home/usuario/EmuLibrary

# Converter todos CSO em uma pasta
ps2-convert --dir /home/usuario/EmuLibrary/roms/ps2 --backup-dir /home/usuario/backup_cso --remove-original

# Organizar e comprimir Switch (simulação)
emumanager switch -- --dir /home/usuario/EmuLibrary/roms/switch --organize --compress --dry-run
```

---

## Próximos passos (opcionais)

Se você quiser, posso:

- Fornecer um pequeno script de diagnóstico (`scripts/debug_chd.py`) que tenta as estratégias de extração do `chdman` (parcial e completa) e grava o stderr para facilitar depuração; ou
- Adicionar instruções detalhadas de instalação das dependências no `README.md` (com comandos por distribuição).

Diga qual prefere que eu faça a seguir: gerar o script de diagnóstico (A) ou adicionar instruções de instalação detalhadas ao README (B).
