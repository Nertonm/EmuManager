from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class CoreEvent:
    """Base para todos os eventos emitidos pelo Core."""
    event_type: str
    payload: dict[str, Any]


class EventBus:
    """Barramento de eventos centralizado para comunicação Core -> UI."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable[[CoreEvent], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[CoreEvent], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def emit(self, event_type: str, **kwargs):
        event = CoreEvent(event_type=event_type, payload=kwargs)
        for callback in self._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception:
                pass

# Singleton Global
bus = EventBus()
