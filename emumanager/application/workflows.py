from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True, slots=True)
class WorkflowSpec:
    id: str
    method_name: str
    supports_dry_run: bool = False
    supports_progress: bool = False
    supports_cancel: bool = False
    refresh_library: bool = False


CORE_WORKFLOWS: dict[str, WorkflowSpec] = {
    "scan": WorkflowSpec(
        id="scan",
        method_name="scan_library",
        supports_progress=True,
        supports_cancel=True,
        refresh_library=True,
    ),
    "organize": WorkflowSpec(
        id="organize",
        method_name="full_organization_flow",
        supports_dry_run=True,
        supports_progress=True,
        refresh_library=True,
    ),
    "maintain": WorkflowSpec(
        id="maintain",
        method_name="maintain_integrity",
        supports_dry_run=True,
        refresh_library=True,
    ),
    "transcode": WorkflowSpec(
        id="transcode",
        method_name="bulk_transcode",
        supports_dry_run=True,
        supports_progress=True,
        refresh_library=True,
    ),
    "update_dats": WorkflowSpec(
        id="update_dats",
        method_name="update_dats",
        supports_progress=True,
    ),
}


def execute_core_workflow(
    orchestrator: Any,
    workflow_id: str,
    *,
    dry_run: bool = False,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    cancel_event: Any = None,
) -> Any:
    """Run a core orchestrator workflow using a shared interface-neutral contract."""
    spec = CORE_WORKFLOWS[workflow_id]
    workflow = getattr(orchestrator, spec.method_name)

    kwargs = {}
    if spec.supports_dry_run:
        kwargs["dry_run"] = dry_run
    if spec.supports_progress and progress_cb is not None:
        kwargs["progress_cb"] = progress_cb
    if spec.supports_cancel and cancel_event is not None:
        kwargs["cancel_event"] = cancel_event
    return workflow(**kwargs)
