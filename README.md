# EmuManager

![CI](https://github.com/Nertonm/EmuManager/actions/workflows/ci.yml/badge.svg?branch=main)

**EmuManager** é uma ferramenta completa para organizar, validar e gerenciar coleções de emulação. Originalmente focado em Nintendo Switch, agora evoluiu para suportar múltiplos sistemas (GameCube, Wii, PS2, PS3, PSP) e oferecer uma interface gráfica moderna.

## Documentação Completa

A documentação completa está disponível na pasta `docs/` e pode ser visualizada online (se hospedada) ou localmente.

- [Instalação](docs/installation.md)
- [Guia de Uso](docs/usage.md)
- [Sistemas Suportados](docs/supported_systems.md)
- [Solução de Problemas](docs/troubleshooting.md)
- [Configuração](docs/configuration.md)

## Recursos Principais

### Interface Gráfica (GUI)
- **Tema Escuro Moderno**: Interface limpa e organizada com abas.
- **Gerenciamento de Biblioteca**:
    - Inicialize a estrutura de pastas padrão (`roms/`, `bios/`, etc.).
    - Liste e adicione ROMs facilmente (com detecção automática de sistema).
    - Suporte a subpastas (ex: `A-M/`, `N-Z/`).
- **Ferramentas de Manutenção**:
    - **Organize**: Move e renomeia ROMs automaticamente baseando-se em metadados.
        - **Switch**: Baseado em `nstool`/`hactool`.
        - **GameCube/Wii**: Baseado em cabeçalho interno e banco de dados (GameTDB).
        - **PS2**: Identifica Serial (ex: `SLUS-20002`) e renomeia.
    - **Health Check**: Verifica integridade de arquivos e escaneia por vírus (ClamAV).
    - **Deep Verify**: Verificação profunda de hash (MD5/SHA1) para garantir integridade 1:1.
        - **Suporte a DATs**: Validação contra arquivos `.dat` (No-Intro/Redump) com tabela de resultados detalhada (Status, CRC32, SHA1).
    - **Clean Junk**: Remove arquivos desnecessários (`.txt`, `.nfo`, `.url`) e pastas vazias.
- **Configurações Avançadas**:
    - **Processamento Seletivo**: Aplique ações apenas aos arquivos selecionados na lista.
    - **Padronização de Nomes**: Force um padrão de nomenclatura estrito (ex: adicionar Região ao nome do arquivo).
- **Compressão e Conversão**:
    - **Switch**: Comprima/Descomprima (`.nsp` <-> `.nsz`, `.xci` <-> `.xcz`).
    - **GameCube/Wii**: Converta ISO para RVZ (formato moderno do Dolphin).
    - **PS1**: Converta BIN/CUE/ISO para CHD.
    - **PS2**: Converta ISO/CSO para CHD.
    - **PSP**: Converta ISO para CSO.

    ### Interface TUI/CLI
    - **Modo Terminal Completo**: `emumanager-tui` oferece um menu interativo para as mesmas ações da GUI diretamente no shell.
    - **Subcomandos dedicados**: organize Switch, verifique com DATs, limpe lixo, atualize DATs, adicione ROMs e faça health check sem abrir a GUI.
    - **Modo fullscreen**: `emumanager-tui tui-full` abre um dashboard com painéis ao vivo de log e progresso.
    - **Baseada em Typer + Rich/Textual**: ajuda colorida (`--help`), tabelas e logs legíveis no terminal.

        Consulte `docs/cli.md` para instruções detalhadas do TUI/CLI. Um resumo rápido:

        - Menu simples (interativo):
            ```bash
            python -m emumanager.tui tui --base /path/to/library
            ```

        - Dashboard fullscreen (Textual):
            ```bash
            python -m emumanager.tui tui-full --base /path/to/library --keys /path/keys.txt --dats-root /path/dats
            ```

#### Barra de Menu, Toolbar e Atalhos
- **Menu superior (File / Tools / View)**: ações reutilizáveis entre menu e toolbar.
- **Toolbar**: botões rápidos para Abrir Biblioteca, Atualizar Lista, Init, Add ROM, Verificar DAT, Cancelar, Alternar Log e Focar Filtro.
- **Atalhos de teclado**:
  - Ctrl+O: Abrir Biblioteca
  - F5: Atualizar Lista
  - Ctrl+I: Inicializar Estrutura
  - Ctrl+A: Adicionar ROM
  - Ctrl+Shift+V: Verificar DAT
  - Esc: Cancelar tarefa atual
  - Ctrl+L: Alternar visibilidade do Log (dock)
  - Ctrl+F: Focar o filtro de ROMs
  - Enter/Return na lista de ROMs: Comprimir ROM selecionada
  - Duplo clique na ROM: Comprimir
  - Duplo clique em resultado de verificação: Abrir pasta do arquivo

#### Persistência do Layout e Estado
- **QSettings**: janela, estado dos docks, visibilidade da toolbar, posição do splitter, larguras das colunas da verificação, texto do filtro e último sistema selecionado são restaurados entre sessões.
- **View > Reset Layout**: limpa as preferências salvas e restaura o layout padrão.

#### Verificação (DAT) e CSV
- **Tabela de resultados** com ordenação (clicar no cabeçalho) e filtros rápidos: All, VERIFIED, UNKNOWN.
- **Export CSV**: exporta respeitando o filtro atual e inclui caminho completo do arquivo.
- **Abrir local**: duplo clique em uma linha abre a pasta do ROM.

#### Verificação e Hashing (detalhes)
- **Hashes calculados**: por padrão `CRC32` e `SHA1` para desempenho e precisão.
- **Deep Verify**: ativa também `MD5` e `SHA256` para validação mais forte.
- **Status MISMATCH**: se o `CRC32` corresponde a entradas do DAT mas `MD5/SHA1` não, o arquivo é marcado como MISMATCH e o nome esperado é exibido quando disponível.
- **Atalhos de contexto** na tabela de verificação:
    - Abrir pasta do arquivo
    - Copiar `CRC32`, `SHA1`, `MD5`, `SHA256`
    
Nota adicional sobre verificações/formatos específicos:

- **Decompress CSO**: opção de trabalho que permite descomprimir `.cso` temporariamente (usa `maxcso`) para leitura de cabeçalhos ou cálculo de hashes. Pode ser ativada no fluxo de processamento (`args.decompress_cso = True`) ou via GUI quando exposto.
- **Verify CHD (chdman verify)**: o projeto agora inclui uma verificação integrada para `.chd` usando `chdman verify -i <file>`; por padrão esta checagem é aplicada antes de extrair ou processar CHDs. Se `chdman` não estiver disponível, o comportamento atual é conservador — o arquivo será marcado como `UNKNOWN`/skip. Esta opção pode ser desativada via `args.verify_chd = False` em fluxos programáticos.

 
## Audit and hash preservation

EmuManager registra ações importantes que realiza na sua biblioteca em uma tabela de auditoria (`library_actions`) dentro do banco de dados da biblioteca. Exemplos de ações gravadas:

- `SKIPPED_COMPRESSED` — arquivo marcado como comprimido foi ignorado durante processamento.
- `RENAMED` — arquivo renomeado para o padrão (por worker ou via GUI).
- `COMPRESSED` — arquivo comprimido (por exemplo, ISO -> CSO) e a transformação foi registrada.

Quando o aplicativo comprime ou converte arquivos, ele tenta preservar os dados de verificação (MD5 e SHA1) para que você ainda possa verificar o jogo mesmo se o original for removido:

- Antes de transformar/remover um arquivo original o EmuManager calcula MD5 e SHA1 (se ainda não existirem) e os grava no índice da biblioteca.
- Após conversão/compressão bem-sucedida, a entrada da biblioteca para o arquivo resultante é atualizada com os hashes originais e o `status` é definido como `COMPRESSED`.
- Todas essas ações são escritas em `library_actions` com uma mensagem de detalhe curta para auditoria.

Observação: esse comportamento é "best-effort" — o cálculo de hashes em arquivos grandes pode ser demorado. Se a gravação no DB falhar, a operação continuará, mas será registrado um aviso no log. No GUI você pode acompanhar o progresso em operações de lote.

### CLI (Linha de Comando)
O módulo `emumanager` também pode ser usado via terminal para automação e scripts. O script legado `switch_organizer.py` ainda está disponível para compatibilidade, mas o foco agora é o pacote `emumanager`.

---

## Instalação e Uso

### Pré-requisitos
- **Python 3.8+**
- **Ferramentas Externas** (necessárias para recursos específicos):
    - **Switch**: `nstool` ou `hactool` (Metadados), `nsz` (Compressão).
    - **GameCube/Wii**: `dolphin-tool` (parte do emulador Dolphin).
    - **PS2**: `maxcso` e `chdman` (parte do MAME).
    - **Antivírus**: `clamscan` (ClamAV).

### Configuração Rápida (Automática)

O projeto inclui um script de bootstrap que instala dependências do sistema (**Debian/Ubuntu** e **Arch Linux**), compila ferramentas necessárias (como `hactool`) e configura o ambiente Python.

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/Nertonm/EmuManager.git
   cd EmuManager
   ```

2. **Execute o script de instalação:**
   ```bash
   chmod +x scripts/bootstrap.sh
   ./scripts/bootstrap.sh
   ```
   *O script solicitará senha `sudo` para instalar pacotes do sistema e copiar binários para `/usr/local/bin`.*

3. **Ative o ambiente e execute:**
   ```bash
   source .venv/bin/activate
   python -m emumanager.gui
   ```

### Configuração Manual

Caso prefira configurar manualmente ou use outro sistema operacional:

1. **Crie um ambiente virtual e instale as dependências:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   pip install nsz>=4.0.0
   ```

2. **Instale as ferramentas externas** (veja Pré-requisitos acima) e garanta que estejam no PATH.

3. **Execute a Interface Gráfica:**
   ```bash
   python emumanager/gui.py
   ```

Opcional (headless): para executar os testes de fumaça da GUI em ambientes sem display, use Xvfb.

#### Verificação com DAT (passo a passo)
1. Abra sua biblioteca e selecione o sistema na aba Library.
2. Na aba Verification, clique em “Select DAT File” e escolha um arquivo `.dat`/`.xml` (No-Intro/Redump).
3. Opcional: ative “Deep Verify” em Settings para incluir `MD5` e `SHA256`.
4. Clique em “Verify Library against DAT”.
5. Filtre, ordene e exporte CSV conforme necessário; clique com o botão direito para copiar hashes ou abrir a pasta.

---

## Suporte a PlayStation 1 (PS1)

Recursos disponíveis na aba Tools → PS1:

- Converter: BIN/CUE/ISO → CHD (usa `chdman`).
- Verificar: extrai o Serial do jogo (ex.: `SLUS-00594`); com “Deep Verify” calcula também MD5.
- Organizar: renomeia para `Título [Serial].ext` usando um banco opcional `psx_db.csv`.

Requisitos:

- `chdman` no PATH para conversão (parte do MAME).
- Opcional: `psx_db.csv` na raiz da biblioteca com linhas `Serial,Título` (cabeçalho opcional). Um exemplo está em `docs/examples/psx_db.csv`.

Pastas e formatos suportados:

- PS1 é escaneado em `roms/psx` ou `psx` dentro da sua biblioteca.
- Extração de serial funciona com `.bin`, `.iso`, `.gz` e `.chd`.

## Estrutura do Projeto

- `emumanager/`: Pacote principal Python.
    - `gui.py`: Ponto de entrada da interface gráfica.
    - `workers/`: Módulos de trabalho para cada sistema (Switch, Dolphin, PS2, etc.).
    - `converters/`: Conversores de formato.
- `roms/`: Diretório padrão para sua coleção (criado via "Init Structure").
- `tests/`: Testes automatizados (`pytest`).

---

## Desenvolvimento e Testes

Para rodar os testes automatizados:

```bash
source .venv/bin/activate
python -m pytest
```

Para rodar o teste de fumaça da GUI (requer ambiente gráfico ou Xvfb):

```bash
python -m pytest tests/test_gui_smoke.py
```

### Cenário de Teste (Mock)

Para criar uma biblioteca de testes com arquivos fictícios (mock) para validar a interface e a organização:

```bash
./scripts/create_mock_roms.py mock_library
```

Isso criará uma pasta `mock_library` com a estrutura completa e arquivos de 1KB simulando ROMs de Switch, PS2, GameCube, etc. Você pode abrir essa pasta na GUI para testar as funcionalidades sem precisar de jogos reais.

Consulte `CONTRIBUTING.md` para mais detalhes sobre como contribuir.

### CI/CD
- **Matriz de Python**: 3.10, 3.11, 3.12, 3.13.
- **Cache de pip**: habilitado para instalações mais rápidas.
- **Cobertura**: `pytest-cov` gera `coverage.xml` que é salvo como artefato.
- **Lint não bloqueante**: `flake8` e `isort` reportam problemas de estilo sem falhar o build.
- **GUI headless**: testes com `xvfb-run` para checagem básica da GUI.
- **Publicação opcional**: job de publicação no PyPI por tag, quando `PYPI_API_TOKEN` está configurado.

### Solução de Problemas
- Erro “tool nsz not found”: instale o utilitário `nsz` e garanta que esteja no `PATH`.
- Erro de GUI em ambiente headless: use `xvfb-run` ou desative testes de GUI.
- Chaves do Switch (prod.keys): coloque `keys.txt` ou `prod.keys` na raiz da biblioteca.

---

## Legal Disclaimer

**EmuManager** is a file management and organization tool. It **does not** contain, distribute, or promote the use of copyrighted material such as ROMs, ISOs, BIOS files, or proprietary keys.

- **No ROMs Included**: You must provide your own legally obtained game backups.
- **No BIOS/Keys Included**: System files required for emulation (like `boot9.bin` for 3DS or `prod.keys` for Switch) must be dumped from your own hardware.
- **Usage**: This tool is intended for personal backup management. The developers are not responsible for any misuse of this software.

## Copyright

All trademarks, logos, and brand names are the property of their respective owners. All company, product, and service names used in this software are for identification purposes only. Use of these names, trademarks, and brands does not imply endorsement.

---

## Licença
Este projeto é licenciado sob a licença MIT. Veja o arquivo `LICENSE` para detalhes.
