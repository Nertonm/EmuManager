from __future__ import annotations

import argparse
import sys

from emumanager.logging_cfg import Col


COMPRESSION_PROFILE_LEVELS = {
    "fast": 1,
    "balanced": 3,
    "best": 19,
}


def show_banner():
    print(f"{Col.CYAN}")
    print(r"   _____         _ _       _       ")
    print(r"  / ____|       (_) |     | |      ")
    print(r" | (___   __      _ |_ ___| |__    ")
    print(r"  \___ \ \ \ /\ / / | __/ __| '_ \   ORGANIZER v13.3")
    print(r"  ____) | \ V  V /| | || (__| | | |  Nintendo Switch Library Manager")
    print(r" |_____/   \_/\_/ |_|\__\___|_| |_|  ")
    print(f"{Col.RESET}")


def show_manual():
    show_banner()
    print(f"{Col.BOLD}BEM-VINDO AO SWITCH ORGANIZER!{Col.RESET}")
    print("Este script organiza, comprime, verifica e cataloga sua coleção de jogos.\n")

    print(f"{Col.YELLOW}EXEMPLOS DE USO COMUNS:{Col.RESET}")
    print(f"  1. {Col.GREEN}Organizar Tudo (Recomendado):{Col.RESET}")
    print("     python3 script.py --organize --clean-junk")
    print(
        f"     {Col.GREY}* Cria pastas, renomeia corretamente e remove lixo.{Col.RESET}"
        "\n"
    )

    print(f"  2. {Col.GREEN}Economizar Espaço (Compressão):{Col.RESET}")
    print("     python3 script.py --compress --organize --clean-junk")
    print(f"     {Col.GREY}* Converte tudo para .NSZ e organiza.{Col.RESET}\n")

    print(f"  3. {Col.GREEN}Restaurar para Original:{Col.RESET}")
    print("     python3 script.py --decompress")
    print(f"     {Col.GREY}* Converte .NSZ de volta para .NSP.{Col.RESET}\n")

    print(f"  4. {Col.GREEN}Modo Simulação (Teste):{Col.RESET}")
    print("     python3 script.py --organize --dry-run")
    print(f"     {Col.GREY}* Mostra o que seria feito sem alterar nada.{Col.RESET}\n")

    print(f"{Col.YELLOW}ARGUMENTOS DISPONÍVEIS:{Col.RESET}")
    print("  --dir [PASTA]    : Define a pasta dos jogos (Padrão: atual).")
    print("  --keys [ARQUIVO] : Caminho do arquivo prod.keys.")
    print(
        "  --no-verify      : Pula a verificação de integridade "
        "(Mais rápido, menos seguro)."
    )
    print("  --level [1-22]   : Nível de compressão NSZ (Padrão: 1).")
    print(
        f"\n{Col.CYAN}Para ver a lista técnica completa, use: "
        f"python3 script.py --help{Col.RESET}"
    )
    sys.exit(0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gerenciador Avançado de ROMs Nintendo Switch",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Exemplo: python3 script.py --compress --organize --clean-junk",
    )

    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Diretório alvo das ROMs (Default: pasta atual)",
    )
    parser.add_argument(
        "--keys",
        type=str,
        default="./prod.keys",
        help="Caminho do arquivo prod.keys",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="SIMULAÇÃO: Não move nem deleta arquivos",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Pula verificação de hash (SHA256/CRC)",
    )
    parser.add_argument(
        "--organize",
        action="store_true",
        help="Move arquivos para subpastas: 'Nome do Jogo [IDBase]'",
    )
    parser.add_argument(
        "--clean-junk",
        action="store_true",
        help="Remove arquivos inúteis (.txt, .nfo, .url, .lnk)",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Comprime ROMs (XCI/NSP) para formato NSZ",
    )
    parser.add_argument(
        "--decompress",
        action="store_true",
        help="Descomprime (NSZ) de volta para NSP",
    )
    parser.add_argument(
        "--rm-originals",
        action="store_true",
        help=(
            "Ao comprimir, remove os arquivos originais somente se a compressão "
            "for bem-sucedida"
        ),
    )
    parser.add_argument(
        "--recompress",
        action="store_true",
        help=(
            "Recomprime arquivos já em .nsz/.xcz para o nível especificado "
            "(substitui o arquivo comprimido se bem-sucedido)"
        ),
    )
    parser.add_argument(
        "--level",
        type=int,
        default=3,
        help="Nível de compressão Zstd (1-22). Padrão: 3 (balanced)",
    )
    parser.add_argument(
        "--compression-profile",
        choices=["fast", "balanced", "best"],
        default=None,
        help=(
            "Perfil de compressão predefinido: 'fast' (prioriza velocidade), "
            "'balanced' (bom equilíbrio tempo/espaço), 'best' (máxima compressão, "
            "mais lento). Se definido, sobrescreve --level."
        ),
    )
    parser.add_argument(
        "--dup-check",
        choices=["fast", "strict"],
        default="fast",
        help=(
            "Modo de verificação de duplicatas: 'fast' usa size+mtime, "
            "'strict' usa SHA256 (padrão: fast)"
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Ativa logging verboso (DEBUG)")
    parser.add_argument(
        "--log-file",
        type=str,
        default="organizer_v13.log",
        help="Arquivo de log (padrão: organizer_v13.log)",
    )
    parser.add_argument(
        "--log-max-bytes",
        type=int,
        default=5 * 1024 * 1024,
        help="Tamanho máximo do log em bytes antes de rotacionar (padrão: 5MB)",
    )
    parser.add_argument(
        "--log-backups",
        type=int,
        default=3,
        help="Número de arquivos de log de backup a manter (padrão: 3)",
    )
    parser.add_argument(
        "--keep-on-failure",
        action="store_true",
        help=(
            "Preserva arquivos gerados quando ocorrer falha (move para quarentena "
            "ou deixa no lugar)"
        ),
    )
    parser.add_argument(
        "--cmd-timeout",
        type=int,
        default=3600,
        help="Timeout em segundos para comandos externos (padrão: 3600)",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help=(
            "Verifica integridade dos arquivos e escaneia por vírus "
            "(usa clamscan/clamdscan se disponíveis)"
        ),
    )
    parser.add_argument(
        "--quarantine",
        action="store_true",
        help=(
            "(usado com --health-check) move arquivos infectados/corrompidos "
            "para _QUARANTINE"
        ),
    )
    parser.add_argument(
        "--quarantine-dir",
        type=str,
        default=None,
        help=(
            "Diretório onde mover arquivos em quarentena "
            "(default: _QUARANTINE dentro de --dir)"
        ),
    )
    parser.add_argument(
        "--deep-verify",
        action="store_true",
        help="Executa verificação mais profunda quando possível (usa hactool/nsz juntos)",
    )
    parser.add_argument(
        "--report-csv",
        type=str,
        default=None,
        help="(usado com --health-check) caminho para salvar relatório CSV detalhado",
    )

    return parser
