#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== EmuManager Bootstrap Script ===${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. System Dependencies
echo -e "\n${YELLOW}[1/4] Checking system dependencies...${NC}"

# Detect Distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    DISTRO="unknown"
fi

install_debian_deps() {
    MISSING_PACKAGES=""
    if ! command_exists clamscan; then MISSING_PACKAGES="$MISSING_PACKAGES clamav"; fi
    if ! command_exists dolphin-tool; then MISSING_PACKAGES="$MISSING_PACKAGES dolphin-emu"; fi
    if ! command_exists chdman; then MISSING_PACKAGES="$MISSING_PACKAGES mame-tools"; fi
    if ! command_exists maxcso; then MISSING_PACKAGES="$MISSING_PACKAGES maxcso"; fi
    if ! command_exists git; then MISSING_PACKAGES="$MISSING_PACKAGES git"; fi
    if ! command_exists make; then MISSING_PACKAGES="$MISSING_PACKAGES build-essential"; fi

    if [ ! -z "$MISSING_PACKAGES" ]; then
        echo -e "Installing missing packages: ${RED}$MISSING_PACKAGES${NC}"
        echo "Sudo access required for installation."
        sudo apt-get update
        sudo apt-get install -y $MISSING_PACKAGES
    else
        echo -e "${GREEN}All system packages installed.${NC}"
    fi
}

install_arch_deps() {
    MISSING_PACKAGES=""
    if ! command_exists clamscan; then MISSING_PACKAGES="$MISSING_PACKAGES clamav"; fi
    if ! command_exists dolphin-tool; then MISSING_PACKAGES="$MISSING_PACKAGES dolphin-emu"; fi
    if ! command_exists chdman; then MISSING_PACKAGES="$MISSING_PACKAGES mame-tools"; fi
    if ! command_exists git; then MISSING_PACKAGES="$MISSING_PACKAGES git"; fi
    if ! command_exists make; then MISSING_PACKAGES="$MISSING_PACKAGES base-devel"; fi

    if [ ! -z "$MISSING_PACKAGES" ]; then
        echo -e "Installing missing official packages: ${RED}$MISSING_PACKAGES${NC}"
        sudo pacman -S --noconfirm $MISSING_PACKAGES
    else
        echo -e "${GREEN}All official system packages installed.${NC}"
    fi

    # maxcso is usually in AUR for Arch
    if ! command_exists maxcso; then
        echo -e "${YELLOW}Checking for maxcso...${NC}"
        if command_exists yay; then
            echo "Installing maxcso via yay..."
            yay -S --noconfirm maxcso
        elif command_exists paru; then
            echo "Installing maxcso via paru..."
            paru -S --noconfirm maxcso
        else
            echo -e "${RED}maxcso not found and no AUR helper detected.${NC}"
            echo "Please install 'maxcso' manually (e.g. from AUR)."
        fi
    else
        echo -e "${GREEN}maxcso is installed.${NC}"
    fi
}

install_fedora_deps() {
    MISSING_PACKAGES=""
    if ! command_exists clamscan; then MISSING_PACKAGES="$MISSING_PACKAGES clamav"; fi
    if ! command_exists dolphin-tool; then MISSING_PACKAGES="$MISSING_PACKAGES dolphin-emu"; fi
    if ! command_exists chdman; then MISSING_PACKAGES="$MISSING_PACKAGES mame-tools"; fi
    if ! command_exists maxcso; then MISSING_PACKAGES="$MISSING_PACKAGES maxcso"; fi
    if ! command_exists git; then MISSING_PACKAGES="$MISSING_PACKAGES git"; fi
    if ! command_exists make; then MISSING_PACKAGES="$MISSING_PACKAGES make automake gcc gcc-c++"; fi

    if [ ! -z "$MISSING_PACKAGES" ]; then
        echo -e "Installing missing packages: ${RED}$MISSING_PACKAGES${NC}"
        echo "Sudo access required for installation."
        sudo dnf install -y $MISSING_PACKAGES
    else
        echo -e "${GREEN}All system packages installed.${NC}"
    fi
}

case "$DISTRO" in
    ubuntu|debian|pop|mint|kali)
        install_debian_deps
        ;;
    arch|manjaro|endeavouros)
        install_arch_deps
        ;;
    fedora|rhel|centos)
        install_fedora_deps
        ;;
    *)
        echo -e "${RED}Unsupported or unknown distribution: $DISTRO${NC}"
        echo "Attempting to continue, but you might need to install dependencies manually:"
        echo "  clamav, dolphin-emu, mame-tools, maxcso, git, build-essential/base-devel"
        ;;
esac

# 2. Hactool (Switch Metadata)
echo -e "\n${YELLOW}[2/4] Checking hactool...${NC}"
if ! command_exists hactool; then
    echo "hactool not found. Compiling from source..."
    TEMP_DIR=$(mktemp -d)
    echo "Cloning hactool..."
    git clone https://github.com/SciresM/hactool.git "$TEMP_DIR"
    
    pushd "$TEMP_DIR" > /dev/null
    cp config.mk.template config.mk
    echo "Compiling..."
    make
    
    echo "Installing to /usr/local/bin..."
    sudo cp hactool /usr/local/bin/
    popd > /dev/null
    
    rm -rf "$TEMP_DIR"
    echo -e "${GREEN}hactool installed successfully.${NC}"
else
    echo -e "${GREEN}hactool already installed.${NC}"
fi

# 3. Python Environment
echo -e "\n${YELLOW}[3/4] Setting up Python environment...${NC}"

if [ -z "$VIRTUAL_ENV" ]; then
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment in .venv..."
        python3 -m venv .venv
    else
        echo "Found existing .venv"
    fi
    
    echo "Activating virtual environment..."
    # This activation is only for the script's duration
    source .venv/bin/activate
else
    echo "Already running inside a virtual environment: $VIRTUAL_ENV"
fi

# 4. Python Packages
echo -e "\n${YELLOW}[4/4] Installing Python dependencies...${NC}"
# Ensure we are using the pip from the venv
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Install nsz explicitly as it might not be in requirements.txt
echo "Installing nsz..."
pip install nsz

# Final check for dolphin-tool
if ! command_exists dolphin-tool && ! command_exists dolphin-emu-tool; then
    echo -e "\n${RED}WARNING: dolphin-tool not found!${NC}"
    echo "GameCube/Wii compression/decompression will not work."
    echo "Please ensure 'dolphin-emu' is installed and 'dolphin-tool' is in your PATH."
fi

echo -e "\n${GREEN}=== Bootstrap Complete! ===${NC}"
echo "To start the manager, run:"
echo -e "  ${YELLOW}source .venv/bin/activate${NC}"
echo "  python3 -m emumanager.gui"
