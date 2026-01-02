"""Compatibility shims for different `textual` versions used by the TUI.

This project targets a fairly wide range of Textual versions. Rather than
scattering `try/except ImportError` checks throughout the UI, the TUI imports
helpers from here.

Currently provided:

- `TextLog`: exposes `.write()` even when Textual's built-in `TextLog` isn't
    available.
- `safe_clear`, `safe_append`, `safe_mount`, `safe_remove`, `safe_focus`:
    defensive wrappers around container APIs.
- `data_table_class()`: returns the `DataTable` class or `None`.
- `create_checkbox()` / `get_checkbox_value()`: Checkbox compatibility.
- `normalize_key()` / `key_matches()`: consistent keyboard shortcut matching
    across Textual versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

try:
    from textual.widgets import ScrollView  # type: ignore
except Exception:  # pragma: no cover - defensive
    try:
        from textual.widgets import scroll_view as ScrollView  # type: ignore
    except Exception:  # pragma: no cover - defensive
        try:
            # Some older/newer textual versions may expose `Static` which is
            # a suitable container for simple fallback behaviour.
            from textual.widgets import Static as ScrollView  # type: ignore
        except Exception:
            # Fallback to a very small stub; real Textual should provide Static
            class ScrollView:  # type: ignore
                def __init__(self, *a, **k):
                    pass


try:
    from textual.widgets import TextLog  # type: ignore
except Exception:

    class TextLog(ScrollView):  # type: ignore
        """Fallback TextLog that exposes .write(msg).

        This is intentionally minimal: it attempts to call `update()` if present
        and otherwise ignores writes.
        """

        def write(self, msg: str) -> None:
            try:
                if hasattr(self, "update"):
                    # preserve existing renderable if possible
                    try:
                        existing = str(getattr(self, "renderable", "") or "")
                    except Exception:
                        existing = ""
                    new = (existing + "\n" + msg).lstrip("\n")
                    try:
                        self.update(new)
                    except Exception:
                        try:
                            self.update(msg)
                        except Exception:
                            pass
                else:
                    # no-op
                    pass
            except Exception:
                pass


def safe_clear(container: Any) -> None:
    """Clear children/items from a ListView-like container defensively."""
    if container is None:
        return
    try:
        # Preferred API
        container.clear()
        return
    except Exception:
        pass
    try:
        # Older API
        if hasattr(container, "remove_children"):
            container.remove_children()
            return
    except Exception:
        pass
    try:
        # Fallback: remove children one-by-one
        children = list(getattr(container, "children", []) or [])
        for c in children:
            try:
                c.remove()
            except Exception:
                try:
                    container.remove(c)
                except Exception:
                    pass
    except Exception:
        pass


def safe_append(container: Any, widget: Any) -> None:
    """Append a child to a container defensively."""
    if container is None or widget is None:
        return
    try:
        container.append(widget)
        return
    except Exception:
        pass
    try:
        container.mount(widget)
        return
    except Exception:
        pass
    try:
        # Some containers support add() or add_child()
        if hasattr(container, "add"):
            container.add(widget)
            return
        if hasattr(container, "add_child"):
            container.add_child(widget)
            return
    except Exception:
        pass


def safe_mount(parent: Any, widget: Any) -> None:
    """Mount a widget into parent, using available APIs."""
    if parent is None or widget is None:
        return
    try:
        parent.mount(widget)
        return
    except Exception:
        pass
    try:
        parent.append(widget)
        return
    except Exception:
        pass
    try:
        parent.add(widget)
    except Exception:
        pass


def safe_remove(widget: Any) -> None:
    if widget is None:
        return
    try:
        widget.remove()
    except Exception:
        try:
            parent = getattr(widget, "parent", None)
            if parent and hasattr(parent, "remove"):
                parent.remove(widget)
        except Exception:
            pass


def safe_focus(widget: Any) -> None:
    try:
        if widget is None:
            return
        if hasattr(widget, "focus"):
            widget.focus()
    except Exception:
        pass


def data_table_class() -> Optional[type]:
    try:
        from textual.widgets import DataTable  # type: ignore

        return DataTable
    except Exception:
        return None


@dataclass(frozen=True)
class NormalizedKey:
    """A tiny normalized representation of a key press.

    Textual key strings vary slightly over versions (e.g. "ctrl+p" vs "ctrl+p",
    upper/lowercase, and sometimes named keys). This keeps comparisons stable.
    """

    key: str


def normalize_key(key: str | None) -> NormalizedKey:
    """Normalize Textual key strings.

    This is intentionally conservative: it only lowercases and trims spaces.
    """

    if not key:
        return NormalizedKey("")
    return NormalizedKey(str(key).strip().lower())


def key_matches(key: str | None, expected: str | Iterable[str]) -> bool:
    """Return True if a pressed key matches one or more expected values."""

    pressed = normalize_key(key).key
    if isinstance(expected, str):
        return pressed == normalize_key(expected).key
    return pressed in {normalize_key(e).key for e in expected}


def create_checkbox(label: str, value: bool = False) -> object:
    """Return a Checkbox-like widget for the current Textual version.

    If Textual provides `Checkbox`, construct and return it. Otherwise
    return a minimal stub object that exposes a `value` attribute and can
    be mounted into the UI (to the extent the fallback allows).
    """
    try:
        from textual.widgets import Checkbox  # type: ignore

        try:
            # Modern Checkbox often accepts `label` and `value` kwargs
            return Checkbox(label, value=value)  # type: ignore
        except TypeError:
            # Fallback: try without value kwarg then set attribute
            cb = Checkbox(label)  # type: ignore
            try:
                setattr(cb, "value", bool(value))
            except Exception:
                pass
            return cb
    except Exception:
        # Minimal stub to allow tests and headless code paths to interact
        class _CheckboxStub:
            def __init__(self, label: str, value: bool = False):
                self.label = label
                self.value = bool(value)

            def __repr__(self) -> str:  # pragma: no cover - tiny shim
                return f"<CheckboxStub {self.label}={self.value}>"

        return _CheckboxStub(label, value)


def get_checkbox_value(widget: object) -> bool:
    """Return the boolean value of a Checkbox-like widget safely."""
    try:
        return bool(getattr(widget, "value", False))
    except Exception:
        return False
