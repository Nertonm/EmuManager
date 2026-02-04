# Contributing

We welcome contributions to EmuManager. Please follow these guidelines to ensure code quality and consistency.

## Environment Setup

1.  **Python Version**: Ensure you are using Python 3.10+.
2.  **Dependencies**: Install in editable mode with dev dependencies:
    ```bash
    pip install -e ".[dev,gui]"
    ```

## Development Standards

### Code Style
*   Follow PEP 8 guidelines.
*   Use type hints for all function arguments and return values.
*   Keep functions small and focused on a single responsibility.

### Testing
*   All new features must be accompanied by unit tests.
*   Run the test suite using `pytest` before submitting a Pull Request.
*   Ensure that existing tests do not break.

### Commits
*   Write clear, concise commit messages.
*   Reference issue numbers where applicable.

## Providers
If adding support for a new system:
1.  Create a new package under `emumanager/[system_name]`.
2.  Implement `provider.py` inheriting from `SystemProvider`.
3.  Register the provider in `emumanager/common/registry.py` (or ensure auto-discovery works).
4.  Add unit tests for metadata extraction and file validation.
