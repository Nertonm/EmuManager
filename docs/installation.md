# Instalação

## Pré-requisitos
- **Python 3.8+**
- **Ferramentas Externas** (necessárias para recursos específicos):
    - **Switch**: `nstool` ou `hactool` (Metadados), `nsz` (Compressão).
    - **GameCube/Wii**: `dolphin-tool` (parte do emulador Dolphin).
    - **PS2**: `maxcso` e `chdman` (parte do MAME).
    - **Antivírus**: `clamscan` (ClamAV).

## Configuração Rápida (Automática)

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

## Instalação Manual

Se preferir não usar o script de bootstrap:

1. **Crie um ambiente virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Instale as ferramentas externas:**
   - **Debian/Ubuntu:**
     ```bash
     sudo apt install clamav dolphin-emu-utils mame-tools
     ```
   - **Arch Linux:**
     ```bash
     sudo pacman -S clamav dolphin-emu mame-tools
     ```
   - **Switch Tools:** Você precisará compilar ou baixar `hactool`, `nstool` e `nsz` manualmente e colocá-los no PATH.
