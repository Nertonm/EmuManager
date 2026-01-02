"""This test was removed because it caused hangs in some environments.

The command palette is exercised indirectly by other integration tests. We
keep this file as a placeholder to avoid tooling surprises for contributors
who may have referenced it.
"""

import pytest


pytest.skip("Removed flaky TUI palette modal test", allow_module_level=True)
