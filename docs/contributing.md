# Contributing

Thanks for considering contributing! This file contains a short guide to get you started.

## Development setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # optional
```

2. Install the package in editable mode:

```bash
python -m pip install -e .
```

3. (Optional) Install GUI extras if you plan to run the GUI:

```bash
python -m pip install pyqt6
# or if the project exposes extras: python -m pip install -e .[gui]
```

## Running tests

Run the test suite with pytest:

```bash
python -m pytest -q
```

The repository includes a headless GUI smoke test (`tests/test_gui_smoke.py`) that requires `xvfb-run` or an X server.

## Linting and formatting

We recommend using `ruff` for linting and `black` for formatting (if desired):

```bash
python -m pip install ruff black
ruff check .
black .
```

Keep changes small and focused. Add tests for new features and ensure the CI passes before opening a PR.

## Submitting changes

- Fork the repository.
- Create a branch with a meaningful name (e.g., `fix/ci-gui-smoke`).
- Commit small changes with clear messages.
- Open a pull request with a description of what you changed and why.

Thank you!

---

# Contribuindo (Português)

Obrigado por querer contribuir! Algumas orientações rápidas:

- Abra uma issue para discutir mudanças grandes antes de implementar.
- Use branches com nomes descritivos (ex.: feature/organize-refactor, fix/typo-readme).
- Sempre rode os testes localmente antes de abrir um pull request:

```bash
. .venv/bin/activate
python -m pytest -q
```

- Escreva testes para novos recursos e mantenha o estilo do projeto.
- Siga as convenções do PEP8; recomendo usar `ruff` ou `black` para formatação.

Ao enviar um PR, inclua uma descrição curta do que foi alterado e o motivo.
