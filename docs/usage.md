# Uso

## Interface Gráfica (GUI)

Para iniciar a interface gráfica:

```bash
python -m emumanager.gui
```

### Fluxo de Trabalho Recomendado

O EmuManager foi desenhado para seguir um fluxo lógico de organização de biblioteca:

1.  **Inicialização**: Definir onde sua biblioteca vai morar.
2.  **Ingestão**: Adicionar novos jogos (ROMs/ISOs) de várias fontes.
3.  **Identificação e Organização**: O sistema identifica o jogo e o move para a pasta correta.
4.  **Verificação**: Garantir que o jogo está íntegro (sem corrupção).
5.  **Otimização**: Comprimir ou converter para economizar espaço.

### Passo a Passo Detalhado

#### 1. Abrir e Inicializar Biblioteca
1.  Clique em **"Open Library"** (ou `Ctrl+O`) e selecione a pasta raiz (ex: `/home/user/Games`).
2.  Se a pasta estiver vazia ou desorganizada, clique em **"Init"** (`Ctrl+I`). Isso criará a estrutura padrão:
    ```
    Games/
    ├── roms/
    │   ├── ps2/
    │   ├── switch/
    │   └── ...
    ├── bios/
    └── ...
    ```

#### 2. Adicionar Jogos (Ingestão)
Você pode adicionar jogos de duas formas:
-   **Botão "Add ROM" (`Ctrl+A`)**: Selecione um arquivo ou pasta. O EmuManager copiará/moverá o arquivo para a pasta de entrada e tentará processá-lo.
-   **Arrastar e Soltar**: Arraste arquivos diretamente para a janela do aplicativo (se suportado pelo seu OS/ambiente).
-   **Manual**: Copie arquivos para dentro das pastas `roms/<sistema>` manualmente e clique em **"Refresh"** (`F5`).

#### 3. Organizar (Organize)
A função "Organize" é o coração do EmuManager.
1.  Selecione os jogos que deseja organizar na lista (ou `Ctrl+A` para selecionar todos).
2.  Clique no botão **"Organize"**.
3.  O sistema irá:
    -   Ler o cabeçalho do arquivo para identificar o jogo real (independente do nome do arquivo).
    -   Buscar o nome correto em bancos de dados internos (GameTDB, etc.).
    -   Renomear o arquivo para o padrão configurado (ex: `Nome do Jogo (USA) (v1.0).iso`).
    -   Mover para a subpasta correta (ex: `roms/ps2/`).

#### 4. Verificação de Integridade (Verification)
Para garantir que seus jogos são cópias perfeitas (1:1):
1.  Vá para a aba **"Verification"**.
2.  Carregue um arquivo DAT (No-Intro ou Redump) correspondente ao sistema.
3.  Clique em **"Verify DAT"**.
4.  O EmuManager calculará o hash (CRC32/MD5/SHA1) de cada arquivo e comparará com o DAT.
    -   **Verde**: Cópia perfeita (Verified).
    -   **Vermelho**: Arquivo corrompido, alterado ou desconhecido (Bad Dump / No Match).

Nota: nas configurações (Settings) você pode habilitar opções que afetam o comportamento de verificação e leitura de cabeçalhos:

- **Deep Verify**: calcula MD5/SHA256 além de SHA1/CRC32.
- **Decompress CSO**: quando ativado, arquivos `.cso` serão descomprimidos temporariamente para ler cabeçalhos ou calcular hashes (requer `maxcso` no PATH).
- **Verify CHD**: quando ativado, arquivos `.chd` serão validados com `chdman verify` antes de qualquer tentativa de extração; se `chdman` não estiver disponível a verificação falhará por segurança.

#### 5. Otimização (Compressão/Conversão)
Para economizar espaço:
1.  Selecione os jogos na lista.
2.  Clique com o botão direito ou use o menu de contexto para ver as opções de compressão disponíveis para aquele sistema.
    -   **Switch**: Compress to NSZ.
    -   **PS2**: Convert to CHD.
    -   **GameCube/Wii**: Convert to RVZ.
3.  Acompanhe o progresso na barra de status ou na aba de Logs.

---

## Linha de Comando (CLI)

O `emumanager` oferece uma interface de linha de comando poderosa para automação e uso em servidores (headless).

### Comandos Básicos

```bash
# Ver ajuda geral
emumanager --help

# Ver ajuda de um comando específico
emumanager organize --help
```

### Exemplos de Uso

#### 1. Inicializar uma nova biblioteca
```bash
emumanager init /mnt/dados/MeusJogos
```

#### 2. Organizar uma pasta de downloads solta
Suponha que você baixou vários jogos de PS2 e Switch para `~/Downloads/Novos`.

```bash
# Tenta identificar e mover para a biblioteca correta
emumanager organize --source ~/Downloads/Novos --dest /mnt/dados/MeusJogos --recursive
```

#### 3. Adicionar um jogo específico especificando o sistema
Se a detecção automática falhar, você pode forçar o sistema:

```bash
emumanager add ~/Downloads/jogo_estranho.bin /mnt/dados/MeusJogos --system psx
```

#### 4. Verificar integridade usando um DAT
```bash
emumanager verify --dat /path/to/ps2_redump.dat --folder /mnt/dados/MeusJogos/roms/ps2
```

#### 5. Converter jogos em lote (Batch Conversion)
Converter todos os ISOs de GameCube para RVZ:

```bash
emumanager compress --format rvz --folder /mnt/dados/MeusJogos/roms/gamecube
```
