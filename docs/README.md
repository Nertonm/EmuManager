# 🎮 EmuManager Core Engine v3.0

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Architecture: Clean](https://img.shields.io/badge/Architecture-Clean-green.svg)](#-arquitetura)

O **EmuManager** é uma engine industrial para a gestão de bibliotecas de emulação. Projetado para colecionadores e entusiastas que exigem **perfeição bit-a-bit**, organização rigorosa e alta performance.

---

## ⚡ Quick Start (30 segundos)

Transforme a sua pasta de downloads num acervo organizado:

1. **Inicialize**: `python -m emumanager.cli init --base ./MeuAcervo`
2. **Audite**: `python -m emumanager.cli scan --base ./MeuAcervo`
3. **Organize**: `python -m emumanager.cli organize --base ./MeuAcervo`

---

## 🛠 Tecnologias de Elite

O EmuManager v3.0 não é apenas um script; é uma peça de engenharia:
- **Multiprocessing Nativo**: Utilize todos os núcleos do seu processador para hashing e compressão.
- **SQLite WAL Mode**: Base de dados de alta concorrência para acesso instantâneo a milhares de registros.
- **Pathlib Puro**: Compatibilidade total e segura entre Windows, Linux e macOS.
- **Plugins de Sistema**: Lógica isolada para cada consola através de `SystemProviders`.

---

## 📖 Workflows Principais

### 🔍 Auditoria Profunda
O comando `scan` realiza uma autópsia em cada ficheiro. Se um ficheiro DAT oficial (No-Intro/Redump) estiver presente, o EmuManager garante que o seu jogo é um dump 1:1 perfeito.

### 📂 Organização Inteligente
Esqueça nomes como `game_final_v2_fix.iso`. O comando `organize` utiliza metadados internos para renomear ficheiros para o padrão da indústria e criar hierarquias lógicas (Base Games, Updates, DLCs).

### ⏩ Modernização (Transcoding)
O comando `transcode` migra automaticamente formatos ineficientes para os padrões modernos:
- **PS1/PS2**: ISO/BIN ➔ **CHD**
- **GC/Wii**: ISO/GCM ➔ **RVZ**
- **PSP**: ISO ➔ **CSO**

---

## 🏗 Arquitetura

O projeto segue a **Clean Architecture**:
- **Core**: Lógica de negócio agnóstica e Managers de estado.
- **Workers**: Motores de execução paralela desacoplados.
- **Providers**: Definições específicas de hardware e metadados.
- **UI/CLI**: Consumidores da API do Core.

---
*Mantido por Engenheiros para Colecionadores.*
