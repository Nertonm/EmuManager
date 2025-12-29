import importlib.util
from pathlib import Path


def load_main_from_path(path: Path):
    spec = importlib.util.spec_from_file_location("architect_module", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module.main


def test_build_creates_structure(tmp_path):
    script_path = Path(__file__).parents[1] / "scripts" / "architect_roms_master.py"
    main = load_main_from_path(script_path)

    target = tmp_path / "Acervo_Test"
    # Run the main function with our temporary folder
    rc = main([str(target)])
    assert rc == 0

    # Basic checks
    assert (target / "bios").is_dir()
    assert (target / "dats").is_dir()
    assert (target / "dats" / "no-intro").is_dir()
    assert (target / "dats" / "redump").is_dir()
    assert (target / "roms").is_dir()
    # Check a known system folder and one of its subfolders
    assert (target / "roms" / "nes" / "# Favoritos").is_dir()
    # Install log
    log = target / "_INSTALL_LOG.txt"
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    assert "Início da criação" in content
