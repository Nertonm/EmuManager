# Configuração

O EmuManager salva suas configurações automaticamente usando `QSettings` (Qt).

## Configurações da Interface

As seguintes configurações são persistidas entre sessões:

- **Tamanho e Posição da Janela**: A janela reabrirá no mesmo lugar e tamanho.
- **Layout**: A posição dos painéis (Log, etc.) é salva.
- **Última Biblioteca**: A última pasta de biblioteca aberta será lembrada.
- **Filtros**: O último filtro de texto e filtro de verificação são salvos.

## Configurações de Processamento

Na aba "Settings" (ou checkboxes na interface principal), você pode configurar:

- **Dry Run**: Simula as operações sem fazer alterações reais.
- **Compression Level**: Nível de compressão para ferramentas que suportam (ex: NSZ).
- **Remove Originals**: Se marcado, remove os arquivos originais após compressão/conversão bem-sucedida.
- **Quarantine**: Move arquivos corrompidos ou desconhecidos para uma pasta `_QUARANTINE`.
- **Deep Verify**: Ativa verificação MD5 e SHA256 (mais lento, mas mais seguro).
- **Recursive**: Processa subpastas recursivamente.
- **Process Selected**: Aplica ações apenas aos itens selecionados na lista.
- **Standardize Names**: Renomeia arquivos seguindo um padrão estrito (ex: `Nome do Jogo (Região) (Serial).ext`).

### Opções de Verificação/Processamento Avançadas

- **Decompress CSO**: Quando habilitado, o EmuManager tentará descomprimir arquivos `.cso` (PS2) temporariamente para extrair cabeçalhos/seriais ou calcular hashes. Isso requer o utilitário `maxcso` no PATH. Se desabilitado, arquivos `.cso` serão ignorados para operações que requerem leitura do cabeçalho.
- **Verify CHD (CHD Verify)**: Habilita uma verificação interna de arquivos `.chd` usando `chdman verify -i <file>` antes de tentar extrair ou processar o conteúdo. Por padrão esta opção está ligada. Se `chdman` não estiver disponível, a verificação falhará e o arquivo será marcado como `UNKNOWN` (comportamento conservador). Você pode desabilitar essa checagem definindo `args.verify_chd = False` em fluxos programáticos ou adicionando uma opção no GUI (próximo passo).
