import importlib.util
from pathlib import Path


def load_main_from_path(path: Path):
    spec = importlib.util.spec_from_file_location("emumanager_module", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module.main


def test_emumanager_init_list_add(tmp_path):
    emu_path = Path(__file__).parents[1] / "scripts" / "emumanager.py"
    main = load_main_from_path(emu_path)

    base = tmp_path / "Acervo_Test"
    # init
    rc = main(["init", str(base)])
    assert rc == 0

    # list-systems (should include known systems like nes)
    rc = main(["list-systems", str(base)])
    assert rc == 0

    # add-rom: create a fake rom and add it
    fake = tmp_path / "game.nes"
    fake.write_text("dummy")
    rc = main(["add-rom", str(fake), str(base)])
    assert rc == 0
    assert (base / "roms" / "nes" / "game.nes").exists()
