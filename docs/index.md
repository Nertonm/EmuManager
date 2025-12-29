# EmuManager

![CI](https://github.com/Nertonm/EmuManager/actions/workflows/ci.yml/badge.svg?branch=main)

**EmuManager** é uma ferramenta completa para organizar, validar e gerenciar coleções de emulação. Originalmente focado em Nintendo Switch, agora evoluiu para suportar múltiplos sistemas (GameCube, Wii, PS2, PS3, PSP) e oferecer uma interface gráfica moderna.

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


### CLI (Linha de Comando)
O módulo `emumanager` também pode ser usado via terminal para automação e scripts. O script legado `switch_organizer.py` ainda está disponível para compatibilidade, mas o foco agora é o pacote `emumanager`.
