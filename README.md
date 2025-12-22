# Switch Organizer (forked)

Pequena ferramenta para organizar/compressar/validar coleções Nintendo Switch.

Como usar:

- Instale dependências de teste (opcional):

# Switch Organizer (switch_organizer.py)

Ferramenta CLI para organizar, verificar e gerenciar uma coleção de ROMs Nintendo Switch (XCI/NSP/NSZ/XCZ).

Este repositório contém `switch_organizer.py`, um script que automatiza tarefas comuns sobre coleções: extrair metadados (via `nstool`/`hactool`), renomear/organizar arquivos em pastas por nome/ID/região/idiomas, (des)comprimir com `nsz`, verificar integridade e executar um health-check com varredura por vírus (ClamAV) e quarentena automática.

## Recursos principais

- Extrai metadados (Nome, TitleID, Versão, Idiomas, Tipo) usando `nstool` ou `hactool`.
- Renomeia arquivos e cria pastas com `Nome (Região) [Idiomas] [BaseID]` quando usado com `--organize`.
- Compressão e descompressão via `nsz` (`--compress`, `--decompress`).
- Verificação de integridade automática (`verify`) usando `nsz` / `nstool` / `hactool` conforme disponível.
- Modo `--health-check`: varre a coleção, detecta arquivos corrompidos e (opcionalmente) faz escaneamento por vírus com `clamscan`/`clamdscan`.
- Suporte a quarentena (`--quarantine` / `--quarantine-dir`) para mover arquivos infectados/corrompidos.
- Geração de relatório CSV detalhado para health-check (`--report-csv`).
- Modo `--dry-run` para simular operações sem alterar arquivos.

---

## Pré-requisitos

- Python 3.8+
- Ferramentas nativas (recomendado):
	- `nstool` ou `hactool` — para extrair metadados e verificar arquivos.
	- `nsz` — para compressão/descompressão NSZ/XCZ.
	- `clamscan` / `clamdscan` (opcional) — para escanear arquivos por vírus (ClamAV).

Instale os binários no PATH do seu sistema. Em Linux, alguns estão disponíveis via gerenciadores de pacotes ou AUR.

Se houver `requirements.txt`, instale dependências de desenvolvimento com pip (opcional):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

> Nota: o script depende principalmente do sistema e de binários nativos; não há muitas dependências Python além de testes (`pytest`).

---

## Instalação rápida

1. Clone o repositório ou copie `switch_organizer.py` para sua máquina.
2. De preferência crie um ambiente virtual Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # se existir
```

3. Garanta que `nstool`/`hactool`/`nsz` estejam no PATH e, se utilizar `hactool`, que o arquivo de chaves (`prod.keys`) esteja acessível ou passe `--keys /caminho/prod.keys`.

---

## Uso básico

O script fornece várias opções via CLI. Abaixo exemplos práticos.

- Ajuda e manual:

```bash
./switch_organizer.py --help
```

- Simular organização (sem mover):

```bash
./switch_organizer.py --dir /caminho/para/roms --organize --dry-run --verbose
```

- Organizar de fato (renomeia e cria pastas):

```bash
./switch_organizer.py --dir /caminho/para/roms --organize
```

- Comprimir tudo para NSZ (poupando espaço):

```bash
./switch_organizer.py --dir /caminho/para/roms --compress --organize
```

Remover originais depois de comprimir (somente se compressão for bem-sucedida):

```bash
./switch_organizer.py --dir /caminho/para/roms --compress --rm-originals
```

Recomprimir arquivos já comprimidos para um nível maior (ex.: melhorar compressão):

```bash
# Força recompressão de arquivos .nsz/.xcz para o nível 19 (pode demorar):
./switch_organizer.py --dir /caminho/para/roms --compress --recompress --level 19
```

Perfis de compressão (convenientes):

- `--compression-profile fast`  -> zstd level 1 (prioriza velocidade)
- `--compression-profile balanced` -> zstd level 3 (bom equilíbrio tempo/espaço, recomendado)
- `--compression-profile best` -> zstd level 19 (máxima compressão, mais lento)

Por padrão o script agora usa o perfil "balanced" (equivalente a `--level 3`) se você não passar `--level` nem `--compression-profile`.

Dicas e casos de uso:

- Espaço rápido: `--compress --compression-profile fast` — compila rápido, menor redução.
- Uso geral (recomendado): `--compress --compression-profile balanced --rm-originals` — bom equilíbrio e remove originais quando verificado.
- Arquivos já comprimidos e quer economizar mais espaço: `--compress --recompress --level 19` — recomprime arquivos .nsz/.xcz para o nível 19 e substitui o original se a verificação passar.

Segurança e cautela:

- `--recompress` e `--rm-originals` apenas removem/substituem arquivos quando a nova artefato for verificado com sucesso — isso evita perda de dados quando a recompressão falhar.
- Use `--dry-run` para simular o que seria feito antes de executar alterações em massa.


- Descomprimir NSZ/XCZ de volta para NSP/XCI:

```bash
./switch_organizer.py --dir /caminho/para/roms --decompress --organize
```

---

## Health check (integridade + antivírus)

Verifique rapidamente integridade e vírus sem modificar arquivos:

```bash
./switch_organizer.py --dir /caminho/para/roms --health-check --verbose
```

Com quarentena automática (move infectados/corrompidos para `_QUARANTINE` dentro de `--dir`):

```bash
./switch_organizer.py --dir /caminho/para/roms --health-check --quarantine
```

Quarentena em pasta personalizada e relatório CSV:

```bash
./switch_organizer.py --dir /caminho/para/roms --health-check --quarantine --quarantine-dir /tmp/roms_quarantine --report-csv /tmp/health_report.csv --deep-verify
```

Comportamento e códigos de saída:
- Exit 0: nenhum arquivo corrompido/infectado detectado (AV pode não estar disponível).
- Exit 3: encontrou arquivos corrompidos e/ou infectados.

### O que o health-check faz:
- Roda `verify_integrity` em cada arquivo (usa `nsz`, `nstool` e — se `--deep-verify` — `hactool`).
- Roda `clamscan` ou `clamdscan` se encontrados no PATH.
- Opcionalmente, move arquivos para quarentena.
- Opcionalmente, escreve um CSV com colunas: path, integrity, integrity_output, av_status, av_output, action.

---

## Nome das pastas e convenção

Quando usado com `--organize`, o script cria (por padrão) pastas com o seguinte padrão:

```
Nome do Jogo (Região) [Idiomas] [BASEID]
```

- `Nome do Jogo` é sanitizado (tags de release removidas, caracteres inválidos excluídos, comprimento limitado).
- `Região` é inferida a partir do nome do arquivo ou dos idiomas detectados (`determine_region`).
- `Idiomas` são extraídos da saída de `nstool`/`hactool` ou inferidos do nome do arquivo (`detect_languages_from_filename`).

Exemplo:
```
Mario Kart 8 Deluxe (World) [En,PtBR] [0100A0000000BCDE]
```

Se preferir outro formato, posso adicionar uma flag `--folder-format` com template personalizável.

---

## Logs

O script escreve logs (RotatingFileHandler) no arquivo padrão `organizer_v13.log`, e imprime mensagens no console. Use `--verbose` para ver saída de depuração detalhada.

Opções de logging:
- `--log-file PATH` — caminho do arquivo de log.
- `--log-max-bytes N` — tamanho para rotacionar logs.
- `--log-backups M` — quantos arquivos de backup manter.

---

## Dicas de troubleshooting

- Metadados ausentes:
	- Alguns arquivos comprimidos (`.nsz`/`.xcz`) podem não expor metadados; use `--decompress` ou instale/utilize `nsz` (o script já tem tentativas de fallback para descompressão temporária).

- `hactool` falhando:
	- Garanta que `prod.keys` está correto e que você passou `--keys /caminho/prod.keys` quando necessário.

- Scanner AV não encontrado:
	- Instale `clamav` ou `clamd`, ou passe um scanner customizado (pode ser implementado se você precisar).

- Problemas de permissão ao mover arquivos:
	- Execute com a conta que tem acesso aos arquivos ou corrija permissões do sistema de arquivos.

---

## Testes e desenvolvimento

O repositório inclui testes `pytest` básicos (localizados em `tests/`). Para rodar:

```bash
. .venv/bin/activate
python -m pytest -q
```

Os testes cobrem utilitários e caminhos críticos; adicionei testes antes de mudanças significativas.

---

## Segurança e limitações

- O script não substitui uma verificação humana quando você suspeita que um dump foi adulterado. Ele automatiza verificações baseadas nas ferramentas disponíveis.
- O scanner AV (ClamAV) tem cobertura limitada — use ferramentas específicas ou listas de hashes se precisar de garantia mais forte.

---

## Contribuição

Contribuições são bem-vindas. Para mudanças maiores, sugiro separar funcionalidades em módulos menores (reduzir a complexidade de `main()` e funções longas) e adicionar testes cobrindo os fluxos novos.

---

## Publicando no GitHub

Antes de publicar, garanta que você não tenha arquivos de log grandes no root do repositório e que `requirements.txt` esteja atualizado. Eu adicionei um `.gitignore` e arquivei logs em `logs/old/`.

Passos rápidos para publicar:

1. Inicialize o repositório (se ainda não):

```bash
git init
git add .
git commit -m "Initial project import: switch-organizer"
```

2. Crie o repositório no GitHub e conecte o remoto (substitua URL):

```bash
git branch -M main
git remote add origin git@github.com:<OWNER>/<REPO>.git
git push -u origin main
```

3. Para evitar commitar arquivos de log que já estavam no histórico, des-trackeie-os antes de commitar:

```bash
git rm --cached architect_v13.log || true
git rm --cached organizer_v13.log || true
git commit -m "Remove logs from tracking"
git push
```

4. A CI foi adicionada em `.github/workflows/ci.yml` e executará os testes em pushes/PRs.

5. Depois de subir, verifique a aba Actions no GitHub para confirmar que os testes passam.

Se quiser, eu posso preparar o commit final com essas mudanças e criar um exemplo de release tag.

## Licen