# Sistemas Suportados

O EmuManager suporta uma ampla variedade de sistemas, com diferentes níveis de funcionalidade (organização, verificação, compressão). Abaixo está a lista detalhada dos sistemas e formatos suportados.

## Nintendo

### Nintendo Switch
- **Identificador**: `switch`
- **Formatos Suportados**: `.nsp`, `.nsz`, `.xci`, `.xcz`
- **Funcionalidades**:
    - **Organização**: Detecção via `nstool`/`hactool`. Renomeia baseando-se no Title ID e Versão.
    - **Compressão**: Suporte nativo para compressão/descompressão NSZ/XCZ.
    - **Verificação**: Verificação de integridade via `hactool`.

### GameCube
- **Identificador**: `gamecube`
- **Formatos Suportados**: `.iso`, `.rvz`, `.gcm`, `.ciso`
- **Funcionalidades**:
    - **Organização**: Detecção via cabeçalho interno (Game Code). Renomeia usando banco de dados GameTDB.
    - **Conversão**: Conversão de ISO para RVZ (formato moderno do Dolphin) para economizar espaço sem perda de dados.

### Wii
- **Identificador**: `wii`
- **Formatos Suportados**: `.iso`, `.wbfs`, `.rvz`, `.wad`
- **Funcionalidades**:
    - **Organização**: Similar ao GameCube, usa cabeçalho interno e GameTDB.
    - **Conversão**: Conversão de ISO/WBFS para RVZ.

### Wii U
- **Identificador**: `wiiu`
- **Formatos Suportados**: `.wud`, `.wux`, `.wua`, `.rpx`
- **Funcionalidades**:
    - **Organização**: Básica baseada em nome de arquivo.

### Portáteis (GB, GBC, GBA, NDS, 3DS)
- **Formatos**: `.gb`, `.gbc`, `.gba`, `.nds`, `.3ds`, `.cia`
- **Funcionalidades**:
    - **Organização**: Baseada em hash (CRC32/MD5) contra bancos de dados DAT (No-Intro).

## Sony

### PlayStation 1 (PSX)
- **Identificador**: `psx`
- **Formatos Suportados**: `.bin`/`.cue`, `.iso`, `.chd`, `.pbp`
- **Funcionalidades**:
    - **Organização**: Detecção de Serial (ex: `SLUS-00000`) dentro do arquivo binário.
    - **Conversão**: Conversão de BIN/CUE para CHD (Compressed Hunks of Data).

### PlayStation 2 (PS2)
- **Identificador**: `ps2`
- **Formatos Suportados**: `.iso`, `.bin`, `.cso`, `.chd`, `.gz`
- **Funcionalidades**:
    - **Organização**: Detecção de Serial (ex: `SLUS-20000`) no sistema de arquivos da ISO.
    - **Conversão**: Conversão de ISO para CHD ou CSO.

### PlayStation 3 (PS3)
- **Identificador**: `ps3`
- **Formatos Suportados**: `.iso`, Pasta JB (GAMES), `.pkg`
- **Funcionalidades**:
    - **Organização**: Detecção de Serial (ex: `BLUS12345`) via `PARAM.SFO`.

### PlayStation Portable (PSP)
- **Identificador**: `psp`
- **Formatos Suportados**: `.iso`, `.cso`, `.pbp`
- **Funcionalidades**:
    - **Organização**: Detecção de Serial (ex: `ULUS-10000`) via cabeçalho ISO.
    - **Conversão**: Conversão de ISO para CSO.

### PlayStation Vita
- **Identificador**: `psvita`
- **Formatos Suportados**: `.vpk`, `.zip` (NoNpDrm)
- **Funcionalidades**:
    - **Organização**: Detecção via `PARAM.SFO` dentro do pacote.

## Outros Sistemas

O EmuManager também suporta organização básica (baseada em extensão ou DATs) para:

- **Sega**: Master System, Mega Drive (Genesis), Dreamcast (`.gdi`, `.cdi`, `.chd`).
- **Microsoft**: Xbox Classic (`.xiso`), Xbox 360 (`.iso`, `.xex`).
- **Arcade**: MAME/FBNeo (`.zip` - requer validação via DAT para renomeação correta).
- **Retro**: Atari 2600, NES, SNES, N64.

## Ferramentas Externas Necessárias

Para habilitar todas as funcionalidades, certifique-se de ter as seguintes ferramentas instaladas (o script `bootstrap.sh` instala a maioria automaticamente no Linux):

| Sistema | Ferramenta | Função |
|---------|------------|--------|
| Switch | `hactool` / `nstool` | Leitura de metadados |
| Switch | `nsz` | Compressão NSZ/XCZ |
| GC/Wii | `dolphin-tool` | Conversão RVZ e leitura de metadados |
| PS2/PSP | `maxcso` | Compressão CSO |
| PS1/PS2 | `chdman` | Compressão CHD |
| Geral | `clamscan` | Verificação de vírus |
| Geral | `7z` | Extração de arquivos compactados |
